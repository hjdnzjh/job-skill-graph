"""Elasticsearch client for full-text search and aggregation analytics."""

import logging
from typing import Dict, List, Optional

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from config.schema import UnifiedJobSchema

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    """Manages ES index for full-text job search and analytics."""

    INDEX_NAME = "job_positions"

    # --- ES index mapping ---
    INDEX_MAPPING = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "ik_smart_analyzer": {
                        "type": "custom",
                        "tokenizer": "ik_smart",
                    },
                    "ik_max_word_analyzer": {
                        "type": "custom",
                        "tokenizer": "ik_max_word",
                    },
                }
            },
        },
        "mappings": {
            "properties": {
                "record_id": {"type": "keyword"},
                "source_id": {"type": "keyword"},
                "source_type": {"type": "keyword"},
                "source_name": {"type": "keyword"},
                "source_url": {"type": "keyword", "index": False},
                "job_title": {
                    "type": "text",
                    "analyzer": "ik_smart_analyzer",
                    "fields": {"raw": {"type": "keyword"}},
                },
                "job_title_raw": {"type": "text", "analyzer": "ik_max_word_analyzer"},
                "company_name": {
                    "type": "text",
                    "analyzer": "ik_smart_analyzer",
                    "fields": {"raw": {"type": "keyword"}},
                },
                "company_name_raw": {"type": "keyword"},
                "industry": {"type": "keyword"},
                "location": {"type": "keyword"},
                "location_raw": {"type": "keyword"},
                "job_description": {"type": "text", "analyzer": "ik_max_word_analyzer"},
                "salary_min": {"type": "float"},
                "salary_max": {"type": "float"},
                "experience_required": {"type": "keyword"},
                "education_required": {"type": "keyword"},
                "job_type": {"type": "keyword"},
                "skills_required": {"type": "keyword"},
                "skills_preferred": {"type": "keyword"},
                "abilities": {"type": "keyword"},
                "publish_date": {"type": "date", "format": "strict_date_optional_time||epoch_millis"},
                "crawl_timestamp": {"type": "date", "format": "strict_date_optional_time||epoch_millis"},
                "data_format": {"type": "keyword"},
                "quality_score": {"type": "float"},
                "quality_grade": {"type": "keyword"},
                "completeness_score": {"type": "float"},
                "freshness_score": {"type": "float"},
                "consistency_score": {"type": "float"},
                "extra": {"type": "object", "enabled": False},
            }
        },
    }

    def __init__(self, settings):
        self.settings = settings
        self._client: Optional[Elasticsearch] = None

    @property
    def client(self) -> Elasticsearch:
        if self._client is None:
            self._client = Elasticsearch(
                hosts=self.settings.es_hosts,
                request_timeout=30,
                max_retries=3,
                retry_on_timeout=True,
            )
        return self._client

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def create_index(self, force: bool = False):
        """Create the ES index with IK analyzer mapping."""
        idx = self.settings.es_index
        if self.client.indices.exists(index=idx):
            if force:
                self.client.indices.delete(index=idx)
                logger.info(f"ES index '{idx}' deleted")
            else:
                logger.info(f"ES index '{idx}' already exists")
                return

        self.client.indices.create(index=idx, body=self.INDEX_MAPPING)
        logger.info(f"ES index '{idx}' created with IK analyzer")

    def delete_index(self):
        idx = self.settings.es_index
        if self.client.indices.exists(index=idx):
            self.client.indices.delete(index=idx)
            logger.info(f"ES index '{idx}' deleted")

    # ------------------------------------------------------------------
    # Bulk indexing
    # ------------------------------------------------------------------

    def index_batch(self, records: List[UnifiedJobSchema], batch_size: int = 500) -> int:
        """Bulk-index a batch of unified records."""
        idx = self.settings.es_index

        actions = []
        for rec in records:
            actions.append({
                "_index": idx,
                "_id": rec.record_id,
                "_source": self._to_doc(rec),
            })

        success, errors = bulk(
            self.client,
            actions,
            chunk_size=batch_size,
            raise_on_error=False,
            stats_only=True,
        )
        if errors:
            logger.warning(f"ES bulk indexing: {success} ok, {errors} errors")
        else:
            logger.info(f"ES: indexed {success} documents")
        return success

    # ------------------------------------------------------------------
    # Full-text search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        fields: List[str] = None,
        filters: Dict[str, str] = None,
        size: int = 20,
        offset: int = 0,
    ) -> dict:
        """Full-text search across specified fields."""
        idx = self.settings.es_index
        fields = fields or ["job_title^3", "job_description", "skills_required^2", "company_name"]

        body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": fields,
                                "type": "best_fields",
                            }
                        }
                    ]
                }
            },
            "from": offset,
            "size": size,
            "highlight": {
                "fields": {
                    "job_title": {},
                    "job_description": {"fragment_size": 150, "number_of_fragments": 2},
                }
            },
        }

        # Add filter clauses
        if filters:
            filter_clauses = []
            for field, value in filters.items():
                filter_clauses.append({"term": {field: value}})
            body["query"]["bool"]["filter"] = filter_clauses

        resp = self.client.search(index=idx, body=body)
        return {
            "total": resp["hits"]["total"]["value"],
            "hits": [h["_source"] for h in resp["hits"]["hits"]],
            "highlight": {
                h["_source"]["record_id"]: h.get("highlight", {})
                for h in resp["hits"]["hits"]
            },
        }

    # ------------------------------------------------------------------
    # Aggregation analytics
    # ------------------------------------------------------------------

    def skill_trends(self, date_from: str = None, date_to: str = None) -> dict:
        """Aggregate top skills and their frequencies."""
        idx = self.settings.es_index

        body = {
            "size": 0,
            "aggs": {
                "top_skills": {
                    "terms": {
                        "field": "skills_required",
                        "size": 30,
                    }
                },
                "skills_over_time": {
                    "date_histogram": {
                        "field": "publish_date",
                        "calendar_interval": "month",
                    },
                    "aggs": {
                        "top_skills": {
                            "terms": {"field": "skills_required", "size": 10}
                        }
                    },
                },
                "avg_salary_by_skill": {
                    "terms": {"field": "skills_required", "size": 20},
                    "aggs": {
                        "avg_salary_min": {"avg": {"field": "salary_min"}},
                        "avg_salary_max": {"avg": {"field": "salary_max"}},
                    },
                },
            },
        }

        if date_from or date_to:
            range_filter = {}
            if date_from:
                range_filter["gte"] = date_from
            if date_to:
                range_filter["lte"] = date_to
            body["query"] = {"range": {"publish_date": range_filter}}

        resp = self.client.search(index=idx, body=body)
        aggs = resp.get("aggregations", {})

        return {
            "top_skills": [
                {"skill": b["key"], "count": b["doc_count"]}
                for b in aggs.get("top_skills", {}).get("buckets", [])
            ],
            "monthly_skill_trends": [
                {
                    "month": b["key_as_string"],
                    "top_skills": [
                        {"skill": sb["key"], "count": sb["doc_count"]}
                        for sb in b.get("top_skills", {}).get("buckets", [])
                    ],
                }
                for b in aggs.get("skills_over_time", {}).get("buckets", [])
            ],
            "salary_by_skill": [
                {
                    "skill": b["key"],
                    "count": b["doc_count"],
                    "avg_salary_min": round(b.get("avg_salary_min", {}).get("value", 0), 1),
                    "avg_salary_max": round(b.get("avg_salary_max", {}).get("value", 0), 1),
                }
                for b in aggs.get("avg_salary_by_skill", {}).get("buckets", [])
            ],
        }

    def quality_distribution(self) -> dict:
        """Get quality score distribution."""
        idx = self.settings.es_index
        body = {
            "size": 0,
            "aggs": {
                "quality_ranges": {
                    "range": {
                        "field": "quality_score",
                        "ranges": [
                            {"key": "A", "from": 0.8, "to": 1.01},
                            {"key": "B", "from": 0.6, "to": 0.8},
                            {"key": "C", "from": 0.4, "to": 0.6},
                            {"key": "D", "from": 0.0, "to": 0.4},
                        ],
                    }
                },
                "by_source": {
                    "terms": {"field": "source_type", "size": 10},
                    "aggs": {
                        "avg_quality": {"avg": {"field": "quality_score"}}
                    },
                },
            },
        }
        resp = self.client.search(index=idx, body=body)
        return resp.get("aggregations", {})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_doc(rec: UnifiedJobSchema) -> dict:
        """Convert a UnifiedJobSchema to an ES document."""
        return {
            "record_id": rec.record_id,
            "source_id": rec.source_id,
            "source_type": rec.source_type.value,
            "source_name": rec.source_name,
            "source_url": rec.source_url,
            "job_title": rec.job_title,
            "job_title_raw": rec.job_title_raw,
            "company_name": rec.company_name,
            "company_name_raw": rec.company_name_raw,
            "industry": rec.industry,
            "location": rec.location,
            "location_raw": rec.location_raw,
            "job_description": rec.job_description,
            "salary_min": rec.salary_min,
            "salary_max": rec.salary_max,
            "experience_required": rec.experience_required,
            "education_required": rec.education_required,
            "job_type": rec.job_type,
            "skills_required": rec.skills_required,
            "skills_preferred": rec.skills_preferred,
            "abilities": rec.abilities,
            "publish_date": rec.publish_date.isoformat() if rec.publish_date else None,
            "crawl_timestamp": rec.crawl_timestamp.isoformat(),
            "data_format": rec.data_format.value,
            "quality_score": rec.quality_score,
            "quality_grade": rec.quality_grade.value,
            "completeness_score": rec.completeness_score,
            "freshness_score": rec.freshness_score,
            "consistency_score": rec.consistency_score,
            "extra": rec.extra,
        }

    def health_check(self) -> bool:
        try:
            return self.client.ping()
        except Exception:
            return False

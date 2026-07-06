"""Near-duplicate detection using MinHash LSH and fuzzy text matching.

Handles the common case where the same job is posted across multiple platforms
(e.g. a position listed on both 51job and BOSS Zhipin).
"""

import hashlib
import logging
import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Dict, List, Set, Tuple

from config.schema import UnifiedJobSchema

logger = logging.getLogger(__name__)


class Deduplicator:
    """Detect and merge or drop duplicate job records.

    Strategy (layered):
      1. Exact match on (normalized_title + company_name + location) → direct dedup
      2. MinHash-based LSH for near-duplicate detection on job_description
      3. Cross-source merge: keep the record with highest quality_score, merge skills
    """

    def __init__(self, similarity_threshold: float = 0.85, shingle_size: int = 3, num_hashes: int = 128):
        self.threshold = similarity_threshold
        self.shingle_size = shingle_size
        self.num_hashes = num_hashes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def deduplicate(self, records: List[UnifiedJobSchema]) -> List[UnifiedJobSchema]:
        """Remove duplicates and near-duplicates. Returns dedup'd list."""
        if not records:
            return []

        # Step 1: exact key dedup
        key_map: Dict[str, UnifiedJobSchema] = {}
        for rec in records:
            key = self._exact_key(rec)
            if key in key_map:
                key_map[key] = self._merge(key_map[key], rec)
            else:
                key_map[key] = rec

        stage1 = list(key_map.values())
        logger.info(f"Exact dedup: {len(records)} → {len(stage1)}")

        # Step 2: near-duplicate detection via description similarity
        stage2 = self._lsh_dedup(stage1)
        logger.info(f"LSH dedup: {len(stage1)} → {len(stage2)}")

        return stage2

    # ------------------------------------------------------------------
    # Exact matching
    # ------------------------------------------------------------------

    @staticmethod
    def _exact_key(rec: UnifiedJobSchema) -> str:
        """A fingerprint key for exact duplicate detection."""
        parts = [
            rec.job_title.strip().lower(),
            rec.company_name.strip().lower(),
            rec.location.strip().lower(),
        ]
        return hashlib.md5("|".join(parts).encode()).hexdigest()

    @staticmethod
    def _merge(keep: UnifiedJobSchema, drop: UnifiedJobSchema) -> UnifiedJobSchema:
        """Keep the richer record when merging duplicates."""
        # Merge skills
        keep.skills_required = list(set(keep.skills_required + drop.skills_required))
        keep.skills_preferred = list(set(keep.skills_preferred + drop.skills_preferred))
        keep.abilities = list(set(keep.abilities + drop.abilities))

        # Prefer longer description
        if len(drop.job_description) > len(keep.job_description):
            keep.job_description = drop.job_description

        # Take earlier publish_date
        if keep.publish_date and drop.publish_date:
            keep.publish_date = min(keep.publish_date, drop.publish_date)

        # Mark cross-source
        keep.extra["merged_sources"] = keep.extra.get("merged_sources", []) + [drop.source_name]

        # Keep the higher quality score
        if drop.quality_score > keep.quality_score:
            keep.quality_score = drop.quality_score
            keep.quality_grade = drop.quality_grade

        logger.debug(f"Merged {drop.record_id} into {keep.record_id}")
        return keep

    # ------------------------------------------------------------------
    # LSH-based near-duplicate detection (MinHash sketch)
    # ------------------------------------------------------------------

    def _lsh_dedup(self, records: List[UnifiedJobSchema]) -> List[UnifiedJobSchema]:
        """Bucket records via MinHash LSH, then pairwise compare within buckets."""
        if len(records) <= 1:
            return records

        # Build MinHash signatures
        signatures: Dict[int, List[int]] = {}
        text_cache: Dict[int, str] = {}

        for i, rec in enumerate(records):
            text = self._preprocess(rec.job_description)
            text_cache[i] = text
            signatures[i] = self._minhash_signature(text)

        # LSH banding
        bands = self.num_hashes // 4  # 32 bands of 4 rows each
        bucket: Dict[Tuple[int, str], List[int]] = defaultdict(list)

        for idx, sig in signatures.items():
            for b in range(bands):
                band_key = (b, self._hash_band(sig[b * 4 : (b + 1) * 4]))
                bucket[band_key].append(idx)

        # Pairwise compare within each bucket
        to_remove: Set[int] = set()
        merge_map: Dict[int, int] = {}  # idx → keep_idx

        for indices in bucket.values():
            if len(indices) < 2:
                continue
            for i in range(len(indices)):
                for j in range(i + 1, len(indices)):
                    a, b = indices[i], indices[j]
                    if a in to_remove or b in to_remove:
                        continue
                    sim = SequenceMatcher(None, text_cache[a], text_cache[b]).ratio()
                    if sim >= self.threshold:
                        # Merge b into a
                        records[a] = self._merge(records[a], records[b])
                        to_remove.add(b)
                        merge_map[b] = a

        result = [r for i, r in enumerate(records) if i not in to_remove]
        return result

    # ------------------------------------------------------------------
    # MinHash helpers
    # ------------------------------------------------------------------

    def _preprocess(self, text: str) -> str:
        """Normalize text for shingling."""
        text = re.sub(r"\s+", " ", text.lower())
        text = re.sub(r"[^a-zA-Z0-9一-鿿\s]", "", text)
        return text.strip()

    def _shingles(self, text: str) -> List[str]:
        """Character n-gram shingles."""
        return [text[i:i + self.shingle_size] for i in range(max(0, len(text) - self.shingle_size + 1))]

    def _minhash_signature(self, text: str) -> List[int]:
        """Compute MinHash signature for a text."""
        shingles = self._shingles(text)
        if not shingles:
            return [0] * self.num_hashes

        sig = []
        for h in range(self.num_hashes):
            min_val = float("inf")
            for s in shingles:
                val = self._hash(s, seed=h)
                if val < min_val:
                    min_val = val
            sig.append(min_val)
        return sig

    @staticmethod
    def _hash(s: str, seed: int) -> int:
        return int(hashlib.md5(f"{seed}:{s}".encode()).hexdigest()[:8], 16)

    @staticmethod
    def _hash_band(band: List[int]) -> str:
        return hashlib.md5("|".join(map(str, band)).encode()).hexdigest()[:16]

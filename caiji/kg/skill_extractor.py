"""Skill extraction via title inference + keyword matching + industry fallback.

Addresses the 97% empty-skills problem by mapping canonical job titles to
expected skill sets, supplemented by regex keyword scanning of descriptions.
"""

import re
from typing import Dict, List, Set

# Canonical title → expected skills (from etl/normalizer.py TITLE_NORMALIZE patterns)
TITLE_TO_SKILLS: Dict[str, List[str]] = {
    "Java开发工程师": ["Java", "Spring Boot", "MyBatis", "MySQL", "微服务", "Redis",
                       "Docker", "Kafka", "Linux", "Git", "Maven", "分布式"],
    "Python开发工程师": ["Python", "Django", "Flask", "FastAPI", "MySQL",
                        "Redis", "Docker", "Linux", "Git", "MongoDB"],
    "Go开发工程师": ["Go", "gRPC", "Docker", "Kubernetes", "微服务", "Redis",
                    "MySQL", "Linux", "Git", "分布式"],
    "C++开发工程师": ["C++", "Linux", "TCP/IP", "多线程", "STL", "Qt",
                     "Redis", "MySQL", "Git", "CMake"],
    "前端开发工程师": ["JavaScript", "TypeScript", "React", "Vue", "HTML5", "CSS3",
                     "Node.js", "Webpack", "Git", "小程序"],
    "全栈开发工程师": ["JavaScript", "TypeScript", "React", "Vue", "Node.js",
                      "Python", "Java", "MySQL", "Docker", "Git", "Redis"],
    "算法工程师": ["Python", "TensorFlow", "PyTorch", "机器学习", "深度学习",
                  "NLP", "计算机视觉", "数据挖掘", "Scikit-learn", "Transformer"],
    "人工智能工程师": ["Python", "TensorFlow", "PyTorch", "机器学习", "深度学习",
                     "NLP", "计算机视觉", "Transformer"],
    "机器学习工程师": ["Python", "TensorFlow", "PyTorch", "Scikit-learn",
                     "特征工程", "模型部署", "XGBoost"],
    "深度学习工程师": ["Python", "PyTorch", "TensorFlow", "CNN", "RNN",
                     "Transformer", "CUDA", "模型优化"],
    "NLP算法工程师": ["Python", "PyTorch", "NLP", "Transformer", "BERT",
                     "GPT", "文本分类", "命名实体识别", "HuggingFace"],
    "计算机视觉工程师": ["Python", "PyTorch", "计算机视觉", "OpenCV", "CNN",
                       "目标检测", "图像分割", "TensorRT"],
    "大数据开发工程师": ["Spark", "Flink", "Hadoop", "Hive", "Kafka",
                       "Java", "Scala", "SQL", "HBase", "数据仓库"],
    "数据分析师": ["SQL", "Python", "Pandas", "NumPy", "Tableau", "Excel",
                  "数据可视化", "统计分析", "MySQL"],
    "运维工程师": ["Linux", "Docker", "Kubernetes", "CI/CD", "Nginx",
                  "Prometheus", "Grafana", "Shell", "Python", "Ansible"],
    "测试工程师": ["Python", "Selenium", "Appium", "JMeter", "Postman",
                  "自动化测试", "性能测试", "Jenkins", "Linux", "SQL"],
    "产品经理": ["Axure", "Figma", "SQL", "数据分析", "PRD", "用户研究",
                "敏捷开发", "项目管理", "竞品分析"],
    "项目经理": ["项目管理", "敏捷开发", "Scrum", "JIRA", "风险管理",
                "沟通协调", "PMO"],
    "架构师": ["微服务", "分布式", "高并发", "系统设计", "Docker",
              "Kubernetes", "MySQL", "Redis", "Kafka", "Spring Boot", "Java"],
    "Android开发工程师": ["Java", "Kotlin", "Android SDK", "Jetpack",
                         "MVVM", "Git", "SQLite", "Retrofit"],
    "iOS开发工程师": ["Swift", "Objective-C", "UIKit", "SwiftUI",
                     "Xcode", "Git", "Core Data", "Combine"],
    "云计算工程师": ["AWS", "Azure", "Docker", "Kubernetes", "Terraform",
                   "Linux", "Python", "CI/CD", "Prometheus"],
    "安全工程师": ["网络安全", "渗透测试", "WAF", "漏洞扫描", "Python",
                  "Linux", "密码学", "SOC", "ISO27001"],
    "区块链工程师": ["Solidity", "Go", "Rust", "以太坊", "智能合约",
                   "共识算法", "Web3", "DeFi"],
}

# Merged skill keywords from recruitment.py._extract_skills + demo_data.SKILLS_POOL
SKILL_KEYWORDS: List[tuple] = [
    # Programming languages
    (r"\bPython\b", "Python"), (r"\bJava\b", "Java"), (r"\bGo\b", "Go"),
    (r"\bC\+\+\b", "C++"), (r"\bRust\b", "Rust"), (r"\bScala\b", "Scala"),
    (r"\bKotlin\b", "Kotlin"), (r"\bTypeScript\b", "TypeScript"),
    (r"\bJavaScript\b", "JavaScript"), (r"\bPHP\b", "PHP"),
    (r"\bRuby\b", "Ruby"), (r"\bSwift\b", "Swift"),
    # Frontend
    (r"\bReact\b", "React"), (r"\bVue\b", "Vue"), (r"\bAngular\b", "Angular"),
    (r"\bHTML5?\b", "HTML5"), (r"\bCSS3?\b", "CSS3"),
    (r"\bWebpack\b", "Webpack"), (r"\b小程序\b", "小程序"),
    # Backend frameworks
    (r"\bSpring\s*Boot\b", "Spring Boot"), (r"\bSpring\b", "Spring"),
    (r"\bDjango\b", "Django"), (r"\bFlask\b", "Flask"),
    (r"\bFastAPI\b", "FastAPI"), (r"\bMyBatis\b", "MyBatis"),
    (r"\bHibernate\b", "Hibernate"), (r"\bExpress\b", "Express"),
    (r"\bgRPC\b", "gRPC"), (r"\bGraphQL\b", "GraphQL"),
    # Databases
    (r"\bMySQL\b", "MySQL"), (r"\bPostgreSQL\b", "PostgreSQL"),
    (r"\bMongoDB\b", "MongoDB"), (r"\bRedis\b", "Redis"),
    (r"\bElasticsearch\b", "Elasticsearch"), (r"\bHBase\b", "HBase"),
    (r"\bSQLite\b", "SQLite"),
    # AI/ML
    (r"\bTensorFlow\b", "TensorFlow"), (r"\bPyTorch\b", "PyTorch"),
    (r"\bKeras\b", "Keras"), (r"\bScikit-learn\b", "Scikit-learn"),
    (r"\bTransformer\b", "Transformer"), (r"\bBERT\b", "BERT"),
    (r"\bNLP\b", "NLP"), (r"\bOpenCV\b", "OpenCV"),
    (r"\b机器学习\b", "机器学习"), (r"\b深度学习\b", "深度学习"),
    (r"\b计算机视觉\b", "计算机视觉"), (r"\b数据挖掘\b", "数据挖掘"),
    # DevOps / Cloud
    (r"\bDocker\b", "Docker"), (r"\bKubernetes\b|K8s\b", "Kubernetes"),
    (r"\bAWS\b", "AWS"), (r"\bAzure\b", "Azure"), (r"\bGCP\b", "Google Cloud"),
    (r"\bJenkins\b", "Jenkins"), (r"\bCI/CD\b", "CI/CD"),
    (r"\bNginx\b", "Nginx"), (r"\bAnsible\b", "Ansible"),
    (r"\bTerraform\b", "Terraform"), (r"\bPrometheus\b", "Prometheus"),
    # Big data
    (r"\bSpark\b", "Spark"), (r"\bFlink\b", "Flink"),
    (r"\bHadoop\b", "Hadoop"), (r"\bHive\b", "Hive"),
    (r"\bKafka\b", "Kafka"), (r"\bRabbitMQ\b", "RabbitMQ"),
    # General
    (r"\bLinux\b", "Linux"), (r"\bGit\b", "Git"),
    (r"\bDevOps\b", "DevOps"), (r"\bMaven\b", "Maven"),
    (r"\bGradle\b", "Gradle"), (r"\b微服务\b", "微服务"),
    (r"\b分布式\b", "分布式"), (r"\b高并发\b", "高并发"),
    (r"\b系统设计\b", "系统设计"), (r"\b多线程\b", "多线程"),
    # Additional patterns for skills in SKILL_CATEGORIES
    (r"\bSelenium\b", "Selenium"), (r"\bAppium\b", "Appium"),
    (r"\bJMeter\b", "JMeter"), (r"\bPostman\b", "Postman"),
    (r"\b自动化测试\b", "自动化测试"), (r"\b性能测试\b", "性能测试"),
    (r"\bCelery\b", "Celery"), (r"\bRedux\b", "Redux"),
    (r"\b数据仓库\b", "数据仓库"), (r"\b数据分析\b", "数据分析"),
    (r"\b推荐系统\b", "推荐系统"), (r"\b网络安全\b", "网络安全"),
    (r"\b渗透测试\b", "渗透测试"),
    (r"\bAxure\b", "Axure"), (r"\bFigma\b", "Figma"),
    (r"\bUnity\b", "Unity"), (r"\bUnreal\b", "Unreal"),
    (r"\bSolidity\b", "Solidity"), (r"\b项目管理\b", "项目管理"),
    (r"\b敏捷开发\b", "敏捷开发"), (r"\bScrum\b", "Scrum"),
    (r"\bJIRA\b", "JIRA"), (r"\bAB实验\b", "AB实验"),
    (r"\bC\#\b", "C#"), (r"\bDart\b", "Dart"),
    (r"\bFlutter\b", "Flutter"), (r"\bFFmpeg\b", "FFmpeg"),
    (r"\bWebRTC\b", "WebRTC"), (r"\bOpenGL\b", "OpenGL"),
    (r"\bTableau\b", "Tableau"), (r"\bPandas\b", "Pandas"),
    (r"\bNumPy\b", "NumPy"), (r"\bExcel\b", "Excel"),
    (r"\bAndroid\b", "Android"), (r"\biOS\b", "iOS"),
    # Additional common technologies
    (r"\bSpring\s*Cloud\b", "Spring Cloud"),
    (r"\bSpring\s*MVC\b", "Spring MVC"),
    (r"\bNetty\b", "Netty"), (r"\bDubbo\b", "Dubbo"),
    (r"\bZooKeeper\b", "ZooKeeper"), (r"\bNacos\b", "Nacos"),
    (r"\bSentinel\b", "Sentinel"), (r"\bSeata\b", "Seata"),
    (r"\bRocketMQ\b", "RocketMQ"), (r"\bOracle\b", "Oracle"),
    (r"\bWebLogic\b", "WebLogic"), (r"\bJVM\b", "JVM"),
    (r"\bJUC\b", "JUC"), (r"\bXGBoost\b", "XGBoost"),
    (r"\bLightGBM\b", "LightGBM"), (r"\bLangChain\b", "LangChain"),
    (r"\bMLflow\b", "MLflow"), (r"\bKubeflow\b", "Kubeflow"),
    (r"\bCUDA\b", "CUDA"), (r"\bYOLO\b", "YOLO"),
    (r"\bStable\s*Diffusion\b", "Stable Diffusion"),
    (r"\bTensorRT\b", "TensorRT"), (r"\bONNX\b", "ONNX"),
    (r"\bD3\.js\b", "D3.js"), (r"\bThree\.js\b", "Three.js"),
    (r"\bWebGL\b", "WebGL"), (r"\bCanvas\b", "Canvas"),
    (r"\bSVG\b", "SVG"), (r"\bNext\.js\b", "Next.js"),
    (r"\bNode\.js\b", "Node.js"), (r"\bTailwind\s*CSS\b", "Tailwind CSS"),
    (r"\bPrisma\b", "Prisma"), (r"\bRxJS\b", "RxJS"),
    (r"\bAxios\b", "Axios"), (r"\bECharts\b", "ECharts"),
    (r"\bVite\b", "Vite"), (r"\bReact\s*Native\b", "React Native"),
    (r"\bWebSocket\b", "WebSocket"), (r"\bTaro\b", "Taro"),
    (r"\b微信小程序\b", "微信小程序"), (r"\bArkTS\b", "ArkTS"),
    (r"\bHarmonyOS\b", "HarmonyOS"),
    (r"\bScrapy\b", "Scrapy"), (r"\bRequests\b", "Requests"),
    (r"\bXPath\b", "XPath"), (r"\b正则表达式\b", "正则表达式"),
    (r"\bSQLAlchemy\b", "SQLAlchemy"), (r"\bAlembic\b", "Alembic"),
    (r"\bPytest\b", "Pytest"), (r"\bGunicorn\b", "Gunicorn"),
    (r"\bMatplotlib\b", "Matplotlib"), (r"\bSciPy\b", "SciPy"),
    (r"\bC\b(?![+])", "C"), (r"\bShell\b", "Shell"),
    (r"\bARM\b", "ARM"), (r"\b嵌入式\b", "嵌入式"),
    (r"\b物联网\b", "物联网"), (r"\bClickHouse\b", "ClickHouse"),
    (r"\bDoris\b", "Doris"), (r"\bHelm\b", "Helm"),
    (r"\bIstio\b", "Istio"), (r"\bEnvoy\b", "Envoy"),
    (r"\bHarbor\b", "Harbor"), (r"\bConsul\b", "Consul"),
    (r"\bJaeger\b", "Jaeger"), (r"\bELK\b", "ELK"),
    (r"\bSonarQube\b", "SonarQube"), (r"\bGrafana\b", "Grafana"),
    (r"\bRetrofit\b", "Retrofit"), (r"\bRoom\b", "Room"),
    (r"\bJetpack\b", "Jetpack"), (r"\bMVVM\b", "MVVM"),
    (r"\bAlamofire\b", "Alamofire"), (r"\bCocos\b", "Cocos"),
    (r"\bUnreal\s*Engine\b", "Unreal Engine"),
    (r"\bLLM\b", "LLM"), (r"\bRAG\b", "RAG"),
    (r"\b多模态\b", "多模态"), (r"\b向量数据库\b", "向量数据库"),
    (r"\b量化交易\b", "量化交易"), (r"\b语音识别\b", "语音识别"),
    (r"\b语音合成\b", "语音合成"), (r"\b强化学习\b", "强化学习"),
    (r"\b微前端\b", "微前端"), (r"\b前端监控\b", "前端监控"),
    (r"\b消息队列\b", "消息队列"), (r"\b架构设计\b", "架构设计"),
    (r"\b技术管理\b", "技术管理"), (r"\b安全测试\b", "安全测试"),
    (r"\b安全运维\b", "安全运维"), (r"\b云计算\b", "云计算"),
    (r"\b网络工程\b", "网络工程"), (r"\b音视频\b", "音视频"),
    (r"\b技术方案\b", "技术方案"), (r"\b原型设计\b", "原型设计"),
    (r"\b需求分析\b", "需求分析"), (r"\b单元测试\b", "单元测试"),
    (r"\b领域驱动设计\b", "领域驱动设计"),
    (r"\b并发编程\b", "并发编程"), (r"\b特征工程\b", "特征工程"),
    (r"\b搜索引擎\b", "搜索引擎"), (r"\b向量检索\b", "向量检索"),
    (r"\b统计学\b", "统计学"), (r"\b用户体验\b", "用户体验"),
    (r"\bWeb3\b", "Web3"), (r"\b以太坊\b", "以太坊"),
    (r"\b区块链\b", "区块链"), (r"\bLaravel\b", "Laravel"),
    (r"\bSAP\b", "SAP"), (r"\bERP\b", "ERP"),
    (r"\bKaldi\b", "Kaldi"), (r"\bjieba\b", "jieba"),
    (r"\bspaCy\b", "spaCy"), (r"\bYARN\b", "YARN"),
    (r"\bAI\b", "AI"), (r"\bHTML\b", "HTML"),
    (r"\bSketch\b", "Sketch"),
]

# Broad industry → default skills (fallback when <3 skills detected)
INDUSTRY_TO_SKILLS: Dict[str, List[str]] = {
    "互联网/IT": ["Linux", "Git", "MySQL", "HTTP"],
    "人工智能": ["Python", "机器学习", "深度学习"],
    "通信/电子": ["C++", "Linux", "嵌入式", "TCP/IP"],
    "金融": ["Java", "Python", "SQL", "Spring Boot"],
    "教育/培训": ["Python", "Java", "SQL"],
    "医疗健康": ["Python", "Java", "MySQL", "数据分析"],
    "智能制造": ["C++", "Python", "嵌入式", "Linux"],
    "汽车/出行": ["C++", "Python", "Linux", "ROS"],
    "电商/零售": ["Java", "MySQL", "Redis", "Kafka"],
    "游戏/娱乐": ["C++", "Unity", "Unreal", "Python"],
    "半导体/集成电路": ["C++", "Verilog", "FPGA", "Linux"],
    "新能源": ["Python", "C++", "MATLAB", "嵌入式"],
}

SKILL_CATEGORIES: Dict[str, str] = {
    "Python": "编程语言", "Java": "编程语言", "Go": "编程语言",
    "C++": "编程语言", "Rust": "编程语言", "Scala": "编程语言",
    "Kotlin": "编程语言", "TypeScript": "编程语言", "JavaScript": "编程语言",
    "PHP": "编程语言", "Ruby": "编程语言", "Swift": "编程语言",
    "React": "前端框架", "Vue": "前端框架", "Angular": "前端框架",
    "HTML5": "前端技术", "CSS3": "前端技术", "Webpack": "构建工具",
    "小程序": "前端技术",
    "Spring Boot": "后端框架", "Spring": "后端框架", "Django": "后端框架",
    "Flask": "后端框架", "FastAPI": "后端框架", "MyBatis": "后端框架",
    "Hibernate": "后端框架", "Express": "后端框架", "gRPC": "通信协议",
    "GraphQL": "通信协议",
    "MySQL": "数据库", "PostgreSQL": "数据库", "MongoDB": "数据库",
    "Redis": "数据库", "Elasticsearch": "数据库", "HBase": "数据库",
    "SQLite": "数据库",
    "TensorFlow": "AI框架", "PyTorch": "AI框架", "Keras": "AI框架",
    "Scikit-learn": "AI框架", "Transformer": "AI模型",
    "BERT": "AI模型", "HuggingFace": "AI工具",
    "机器学习": "AI领域", "深度学习": "AI领域",
    "NLP": "AI领域", "计算机视觉": "AI领域", "数据挖掘": "AI领域",
    "OpenCV": "视觉库", "CNN": "AI模型", "RNN": "AI模型",
    "GPT": "AI模型",
    "Docker": "DevOps", "Kubernetes": "DevOps",
    "AWS": "云平台", "Azure": "云平台", "Google Cloud": "云平台",
    "Jenkins": "CI/CD", "CI/CD": "CI/CD",
    "Nginx": "Web服务器", "Ansible": "配置管理",
    "Terraform": "IaC", "Prometheus": "监控",
    "Grafana": "监控",
    "Spark": "大数据", "Flink": "大数据", "Hadoop": "大数据",
    "Hive": "大数据", "Kafka": "消息队列", "RabbitMQ": "消息队列",
    "Linux": "操作系统", "Git": "版本控制", "DevOps": "DevOps",
    "Maven": "构建工具", "Gradle": "构建工具",
    "微服务": "架构模式", "分布式": "架构模式",
    "高并发": "架构能力", "系统设计": "架构能力", "多线程": "编程基础",
    "TCP/IP": "网络协议",
    "网络安全": "安全领域", "渗透测试": "安全领域",
    "Solidity": "智能合约", "以太坊": "区块链", "智能合约": "区块链",
    "Web3": "区块链", "共识算法": "区块链",
    "Unity": "游戏引擎", "Unreal": "游戏引擎",
    "Android SDK": "移动开发", "Jetpack": "移动开发",
    "UIKit": "移动开发", "SwiftUI": "移动开发",
    "项目管理": "管理能力", "敏捷开发": "管理方法",
    "SQL": "数据库", "Tableau": "BI工具", "Pandas": "数据分析",
    "NumPy": "数据分析", "Excel": "办公工具",
    "Axure": "产品工具", "Figma": "设计工具",
    "JIRA": "项目管理工具", "Scrum": "管理方法",
    "自动化测试": "测试领域", "性能测试": "测试领域",
    "Selenium": "测试工具", "JMeter": "测试工具", "Postman": "测试工具",
    "Appium": "测试工具",
    "Shell": "脚本语言", "CMake": "构建工具", "STL": "C++库",
    "Objective-C": "编程语言", "Qt": "UI框架", "Xcode": "IDE工具",
    "Combine": "iOS框架", "Core Data": "iOS框架", "MVVM": "架构模式",
    "Retrofit": "网络框架", "CUDA": "AI加速", "TensorRT": "AI推理",
    "模型部署": "AI工具", "模型优化": "AI工具", "图像分割": "AI领域",
    "命名实体识别": "AI领域", "文本分类": "AI领域", "目标检测": "AI领域",
    "数据仓库": "数据领域", "统计分析": "数据分析", "数据可视化": "数据分析",
    "数据分析": "数据分析",
    "用户研究": "产品设计", "PRD": "产品文档", "竞品分析": "产品能力",
    "风险管理": "管理能力", "沟通协调": "管理能力", "PMO": "管理能力",
    "WAF": "安全工具", "漏洞扫描": "安全工具", "SOC": "安全运营",
    "ISO27001": "安全标准", "密码学": "安全领域", "DeFi": "区块链",
    "通信协议": "网络协议", "量化交易": "金融科技",
    "Node.js": "运行时", "NLP": "AI领域",
    "XGBoost": "AI框架", "特征工程": "AI领域",
}


class SkillExtractor:
    """Extract skills from job records using hybrid title/keyword/industry inference."""

    def __init__(self):
        self._compiled_patterns = []
        for p, name in SKILL_KEYWORDS:
            # Fix \b for CJK text compatibility:
            # - re.ASCII: \b only matches ASCII word boundaries, so Chinese
            #   characters count as non-word → boundary between Chinese and English
            # - For Chinese-only patterns, remove \b (CJK chars are all \W with
            #   re.ASCII, so \b can't match between them)
            if any('一' <= c <= '鿿' for c in p):
                p = p.replace('\\b', '')
            self._compiled_patterns.append(
                (re.compile(p, re.IGNORECASE | re.ASCII), name)
            )

    def extract(self, title: str = "", description: str = "",
                industry: str = "", existing_skills: List[str] = None) -> List[str]:
        """Return deduplicated, canonical skill names for a job record.

        Args:
            title: Normalized job title (e.g. 'Java开发工程师')
            description: Job description text
            industry: Normalized industry (e.g. '互联网/IT')
            existing_skills: Any skills already in the record
        """
        skills: Set[str] = set()

        # 1. Start with any existing skills
        if existing_skills:
            skills.update(s.lower().strip() for s in existing_skills if s)

        # 2. Title inference — primary source
        inferred = TITLE_TO_SKILLS.get(title, [])
        skills.update(s.lower() for s in inferred)

        # 3. Keyword matching on description
        if description:
            for pattern, skill_name in self._compiled_patterns:
                if pattern.search(description):
                    skills.add(skill_name.lower())

        # 4. Industry fallback
        if len(skills) < 3 and industry:
            fallback = INDUSTRY_TO_SKILLS.get(industry, [])
            skills.update(s.lower() for s in fallback)

        # 5. Normalize through skill aliases (same as etl/normalizer.py)
        normalized = self._normalize(list(skills))

        # 6. Title case for canonical form
        return sorted(self._canonical_case(s) for s in normalized)

    @staticmethod
    def _normalize(skills: List[str]) -> List[str]:
        """Apply skill alias normalization."""
        from etl.normalizer import Normalizer
        return Normalizer.normalize_skills(skills)

    # Built once: lowercase → canonical casing lookup from all known skills
    _CANONICAL: Dict[str, str] = {}

    @classmethod
    def _build_canonical_map(cls):
        if cls._CANONICAL:
            return
        seen = set()
        for skill_list in TITLE_TO_SKILLS.values():
            for s in skill_list:
                seen.add(s)
        for _, name in SKILL_KEYWORDS:
            seen.add(name)
        # Add all from skill categories
        seen.update(SKILL_CATEGORIES.keys())
        # Build lowercase → canonical
        for s in sorted(seen):
            cls._CANONICAL[s.lower()] = s

    @classmethod
    def _canonical_case(cls, skill: str) -> str:
        """Restore proper casing from known canonical forms."""
        cls._build_canonical_map()
        return cls._CANONICAL.get(skill.lower(), skill)

    @staticmethod
    def get_category(skill: str) -> str:
        """Return category label for a skill."""
        return SKILL_CATEGORIES.get(skill, "其他")

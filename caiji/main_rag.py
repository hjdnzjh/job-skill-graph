"""RAG QA CLI.

Usage:
    python main_rag.py --index              # Build vector index
    python main_rag.py --index --force     # Force rebuild index
    python main_rag.py "Python工程师需要什么技能？"
    python main_rag.py --interactive       # Interactive QA mode
"""

import argparse
import logging
import sys

from config.settings import Settings
from kg.rag_engine import RAGEngine

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="RAG 增强问答系统")
    parser.add_argument("question", type=str, nargs="?", default=None,
                        help="要查询的问题")
    parser.add_argument("--index", action="store_true",
                        help="构建/更新向量索引")
    parser.add_argument("--force", action="store_true",
                        help="强制重建索引")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="交互式问答模式")
    parser.add_argument("--top", type=int, default=5,
                        help="检索文档数 (默认 5)")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    settings = Settings()
    engine = RAGEngine(settings)

    try:
        if args.index:
            count = engine.build_index(force=args.force)
            print(f"\n索引构建完成: {count} 条文档")
        elif args.interactive:
            _interactive(engine, args.top)
        elif args.question:
            _ask(engine, args.question, args.top)
        else:
            parser.print_help()
    finally:
        engine.close()


def _ask(engine, question, top_k):
    """Single question query."""
    print(f"\n问题: {question}")
    print("正在检索并生成回答...\n")
    result = engine.query(question, top_k=top_k)

    print("=" * 60)
    print(result["answer"])
    print("=" * 60)

    if result["warnings"]:
        print(f"\n[幻觉检测] {len(result['warnings'])} 条警告:")
        for w in result["warnings"]:
            print(f"  - {w['message']}")

    print(f"\n检索文档数: {len(result['retrieved_docs'])}")
    print(f"图谱上下文: {len(result['graph_context'])} 条")


def _interactive(engine, top_k):
    """Interactive QA loop."""
    print("\n" + "=" * 60)
    print("  RAG 增强问答交互模式")
    print("  基于知识图谱 + 向量检索 + 大模型生成")
    print("  输入 quit 退出")
    print("=" * 60 + "\n")

    while True:
        try:
            question = input("你的问题: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if question.lower() in ("quit", "exit", "q"):
            print("再见！")
            break
        if not question:
            continue

        result = engine.query(question, top_k=top_k)
        print(f"\n{result['answer']}")
        if result["warnings"]:
            print(f"\n[提醒] {', '.join(w['message'] for w in result['warnings'])}")
        print()


if __name__ == "__main__":
    main()

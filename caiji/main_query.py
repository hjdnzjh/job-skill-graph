"""Standalone Text-to-Cypher natural language query system.

Usage:
    python main_query.py "上海有哪些公司招Python工程师？"
    python main_query.py -i              # interactive REPL mode
    python main_query.py "..." --raw    # raw Cypher + JSON output only
"""

import argparse
import json
import logging
import sys

from config.settings import Settings
from kg.query_engine import TextToCypherEngine

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Text-to-Cypher 自然语言查询系统"
    )
    parser.add_argument(
        "question", nargs="?", type=str, default=None,
        help="自然语言问题（中文）",
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="启动交互式 REPL 模式",
    )
    parser.add_argument(
        "--raw", action="store_true",
        help="只输出原始 Cypher 和 JSON 数据",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    settings = Settings()

    if not settings.llm_api_key:
        print("提示：未设置 LLM_API_KEY 环境变量，DeepSeek 可能需要 API Key")
        print("获取地址：https://platform.deepseek.com/api_keys\n")

    engine = TextToCypherEngine(settings)

    try:
        if args.interactive:
            _run_repl(engine, raw=args.raw)
        elif args.question:
            _run_single(engine, args.question, raw=args.raw)
        else:
            parser.print_help()
            sys.exit(1)
    finally:
        engine.close()


def _run_single(engine, question, raw=False):
    """Execute a single question and print results."""
    print(f"\n问题：{question}")
    result = engine.query(question)

    if result.get("error"):
        print(f"\n[错误] {result['error']}")
        return

    if raw:
        print(f"\n--- Cypher ---\n{result['cypher']}")
        print(f"\n--- 数据 ---")
        print(json.dumps(result["data"], ensure_ascii=False, indent=2, default=str))
    else:
        print(f"\n--- 生成的 Cypher ---\n{result['cypher']}")
        print(f"\n--- 答案 ---\n{result['answer']}")
        print(f"\n（共 {len(result['data'])} 条结果）")


def _run_repl(engine, raw=False):
    """Interactive REPL loop."""
    print("\n" + "=" * 60)
    print("  Text-to-Cypher 交互查询系统")
    print("  输入中文问题，生成 Cypher 并查询知识图谱")
    print("  输入 quit / exit / q 退出，输入 raw 切换原始模式")
    print("=" * 60 + "\n")

    while True:
        try:
            question = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if question.lower() in ("quit", "exit", "q"):
            print("再见！")
            break
        if question.lower() == "raw":
            raw = not raw
            print(f"原始模式：{'开' if raw else '关'}")
            continue
        if not question:
            continue

        _run_single(engine, question, raw=raw)
        print()


if __name__ == "__main__":
    main()

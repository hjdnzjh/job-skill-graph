"""Person-job matching CLI.

Usage:
    python main_match.py --resume my_resume.pdf --target "Java开发工程师"
    python main_match.py --resume my_resume.pdf --recommend
    python main_match.py --interactive
"""

import argparse
import json
import logging
import sys

from config.settings import Settings
from kg.resume_parser import ResumeParser
from kg.job_matcher import JobMatcher

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="人岗匹配与差距分析系统"
    )
    parser.add_argument("--resume", "-r", type=str, default=None,
                        help="简历文件路径 (.pdf / .docx / .txt)")
    parser.add_argument("--target", "-t", type=str, default=None,
                        help="目标岗位名称")
    parser.add_argument("--recommend", action="store_true",
                        help="自动推荐最适合的岗位")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="交互模式：手动输入技能和目标岗位")
    parser.add_argument("--list-titles", action="store_true",
                        help="列出所有可匹配的岗位")
    parser.add_argument("--top", type=int, default=10,
                        help="推荐岗位数量 (默认 10)")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    settings = Settings()
    matcher = JobMatcher(settings)

    try:
        if args.list_titles:
            _list_titles(matcher)
        elif args.interactive:
            _interactive(settings, matcher)
        elif args.resume and args.recommend:
            _resume_recommend(settings, matcher, args.resume, args.top)
        elif args.resume and args.target:
            _resume_match(settings, matcher, args.resume, args.target)
        elif args.resume:
            parser.error("请指定 --target 或 --recommend")
        else:
            parser.print_help()
            print("\n示例:")
            print("  python main_match.py --list-titles")
            print("  python main_match.py --resume resume.pdf --target Java开发工程师")
            print("  python main_match.py --resume resume.pdf --recommend")
            print("  python main_match.py --interactive")

    finally:
        matcher.close()


def _list_titles(matcher):
    """Show available job titles for matching."""
    titles = matcher.list_available_titles()
    print(f"\n可匹配岗位 ({len(titles)}):\n")
    for t in titles:
        print(f"  - {t}")


def _resume_match(settings, matcher, filepath, target):
    """Parse resume and match against a target job."""
    # Parse
    parser = ResumeParser(settings)
    try:
        print(f"\n读取简历: {filepath}")
        text = parser.read_file(filepath)
        print(f"  提取文本: {len(text)} 字符")

        resume = parser.extract(text)
        raw_skills = resume.get("skills", [])
        print(f"  姓名: {resume.get('name', '未识别')}")
        print(f"  技能: {', '.join(raw_skills)}")
        print(f"  经验: {resume.get('years_of_experience', 'N/A')} 年")
        print(f"  学历: {resume.get('education', '未识别')}")

        # Align skills
        skills = parser.align_skills(raw_skills)
        if skills != raw_skills:
            print(f"  对齐后技能: {', '.join(skills)}")
    except Exception as exc:
        print(f"\n[错误] 简历解析失败: {exc}")
        return
    finally:
        parser.close()

    # Resolve title
    resolved = matcher.find_title(target)
    if not resolved:
        print(f"\n[错误] 未找到岗位 '{target}'，使用 --list-titles 查看可匹配岗位")
        return
    print(f"\n目标岗位: {target}")
    if resolved != target:
        print(f"  匹配到: {resolved}")

    # Match
    result = matcher.match(skills, resolved)
    _print_match_result(result)


def _resume_recommend(settings, matcher, filepath, top_n):
    """Parse resume and recommend best jobs."""
    # Parse
    parser = ResumeParser(settings)
    try:
        print(f"\n读取简历: {filepath}")
        text = parser.read_file(filepath)
        resume = parser.extract(text)
        raw_skills = resume.get("skills", [])
        print(f"  技能: {', '.join(raw_skills)}")

        skills = parser.align_skills(raw_skills)
    except Exception as exc:
        print(f"\n[错误] 简历解析失败: {exc}")
        return
    finally:
        parser.close()

    # Recommend
    print(f"\n正在推荐最佳匹配岗位...")
    recommendations = matcher.recommend_jobs(skills, top_n=top_n)

    print(f"\n{'='*60}")
    print(f"  岗位推荐 (Top {len(recommendations)})")
    print(f"{'='*60}")
    for i, rec in enumerate(recommendations, 1):
        bar = "#" * int(rec["match_score"] * 20) + "-" * (20 - int(rec["match_score"] * 20))
        print(f"\n  [{i}] {rec['title']}")
        print(f"      匹配度: {bar} {rec['match_score']:.0%}")
        print(f"      匹配技能: {rec['matched']}/{rec['required']}")


def _interactive(settings, matcher):
    """Interactive matching mode."""
    print("\n" + "=" * 60)
    print("  人岗匹配交互模式")
    print("  输入你的技能和目标岗位，获取匹配分析")
    print("  输入 quit 退出，输入 titles 查看可匹配岗位")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("你的技能（逗号分隔）: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break
        if user_input.lower() == "titles":
            _list_titles(matcher)
            continue
        if not user_input:
            continue

        skills = [s.strip() for s in user_input.split(",") if s.strip()]

        target = input("目标岗位: ").strip()
        if target.lower() in ("quit", "exit", "q"):
            print("再见！")
            break
        if not target:
            print("请输入目标岗位\n")
            continue

        resolved = matcher.find_title(target)
        if not resolved:
            near = matcher.find_title(target)
            print(f"未找到 '{target}'，试试 --list-titles\n")
            continue

        if resolved != target:
            print(f"匹配到岗位: {resolved}")

        result = matcher.match(skills, resolved)
        _print_match_result(result)
        print()


def _print_match_result(result):
    """Print formatted match result."""
    score = result["match_score"]
    bar = "#" * int(score * 20) + "-" * (20 - int(score * 20))

    print(f"\n{'='*60}")
    print(f"  匹配报告: {result['target_title']}")
    print(f"{'='*60}")
    print(f"\n  综合匹配度: {bar} {score:.0%}")
    print(f"  必备技能 ({result['total_required']}): {result['matched_skills']}")
    print(f"    已具备 ({len(result['matched_skills'])}): {', '.join(result['matched_skills'])}")
    print(f"    缺失   ({len(result['missing_skills'])}): {', '.join(result['missing_skills'])}")
    if result["preferred_matched"] or result["preferred_missing"]:
        print(f"  加分技能 ({result['total_preferred']})")
        print(f"    已具备: {', '.join(result['preferred_matched']) if result['preferred_matched'] else '无'}")
        print(f"    缺失:   {', '.join(result['preferred_missing']) if result['preferred_missing'] else '无'}")

    learning = result.get("learning_path", [])
    if learning:
        print(f"\n  --- 学习路径建议 ---")
        for step in learning:
            skill = step.get("skill", "")
            note = step.get("note", "")
            bridges = step.get("bridge_skills", [])
            if bridges:
                print(f"\n  目标: {skill}")
                print(f"  路径: {step.get('from_skill', '')} → {' → '.join(bridges)} → {skill}")
            else:
                print(f"\n  {skill}: {note}")

    print()


if __name__ == "__main__":
    main()

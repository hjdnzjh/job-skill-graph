"""Launch the web visualization dashboard.

Usage:
    python main_web.py                  # default: http://0.0.0.0:8000
    python main_web.py --port 8080      # custom port
    python main_web.py --host 127.0.0.1 # localhost only
    python main_web.py --reload         # auto-reload on code changes (dev)
"""

import argparse
import logging
import sys


def main():
    parser = argparse.ArgumentParser(description="全息可视化 Web Dashboard")
    parser.add_argument("--host", default="0.0.0.0", help="绑定地址 (默认 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="绑定端口 (默认 8000)")
    parser.add_argument("--reload", action="store_true", help="开发模式，代码变更时自动重载")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    import uvicorn

    print(f"\n  全息可视化平台启动中...")
    print(f"  地址: http://{args.host}:{args.port}")
    print(f"  按 Ctrl+C 停止\n")

    uvicorn.run(
        "web.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()

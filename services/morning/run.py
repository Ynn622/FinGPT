"""手動執行盤前報告的命令列入口。"""

import argparse
import asyncio
import json

from services.morning.pipeline import run_morning_pipeline


def main() -> None:
    """解析命令列參數並執行一次盤前報告流程。"""
    parser = argparse.ArgumentParser(description="Run the FinGPT morning pipeline")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--no-push", action="store_true", help="run and write debug JSON only")
    mode.add_argument("--push", action="store_true", help="multicast to subscribed users after a successful run")
    parser.add_argument("--force", action="store_true", help="bypass trading-day and idempotency checks")
    args = parser.parse_args()
    push = bool(args.push)
    # 不推播模式視為完整開發測試，因此週末也允許執行。
    force = args.force or not push
    report = asyncio.run(run_morning_pipeline(push=push, force=force))
    print(json.dumps(report.to_dict() if report else None, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

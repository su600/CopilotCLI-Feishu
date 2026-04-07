# -*- coding: utf-8 -*-
import logging
import sys

from app.bot import FeishuBot


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    try:
        bot = FeishuBot()
        bot.start()
    except RuntimeError as exc:
        print(f"启动失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

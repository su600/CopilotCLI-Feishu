# -*- coding: utf-8 -*-
import logging

from app.bot import FeishuBot


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    bot = FeishuBot()
    bot.start()


if __name__ == "__main__":
    main()

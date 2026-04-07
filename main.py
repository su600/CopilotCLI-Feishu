# -*- coding: utf-8 -*-
import logging

from app.tray import TrayApplication


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    app = TrayApplication()
    app.run()


if __name__ == "__main__":
    main()

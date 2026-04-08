# -*- coding: utf-8 -*-
import ctypes
from ctypes import wintypes
import logging
import sys

from app.config import get_app_log_path
from app.tray import TrayApplication


ERROR_ALREADY_EXISTS = 183
_SINGLE_INSTANCE_MUTEX = None


def configure_logging() -> str:
    log_path = str(get_app_log_path())
    handlers = [logging.FileHandler(log_path, encoding="utf-8")]
    if not getattr(sys, "frozen", False):
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
        force=True,
    )
    return log_path


def show_message_box(title: str, message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        pass


def acquire_single_instance() -> bool:
    global _SINGLE_INSTANCE_MUTEX

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.GetLastError.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    mutex_name = "Local\\CopilotCLI-Feishu-Tray"
    handle = kernel32.CreateMutexW(None, False, mutex_name)
    if not handle:
        raise RuntimeError("无法创建单实例互斥锁。")

    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False

    _SINGLE_INSTANCE_MUTEX = handle
    return True


def main() -> None:
    log_path = configure_logging()
    logger = logging.getLogger("feishu-bot.main")

    try:
        if not acquire_single_instance():
            message = f"程序已经在后台运行。\n如果没看到图标，请先展开系统托盘隐藏图标。\n\n日志文件：{log_path}"
            logger.info("Another tray instance is already running")
            show_message_box("CopilotCLI-Feishu", message)
            return

        logger.info("Starting tray application")
        app = TrayApplication()
        app.run()
    except Exception as exc:
        logger.exception("Tray application exited unexpectedly")
        show_message_box(
            "CopilotCLI-Feishu 启动失败",
            f"{exc}\n\n详细日志：{log_path}",
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

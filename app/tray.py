# -*- coding: utf-8 -*-
import logging
import os
import threading
from pathlib import Path
from typing import Optional

import pystray
from PIL import Image, ImageDraw

from app.bot import FeishuBot
from app.config import get_env_file_path, get_settings
from app.copilot_runtime import CopilotRuntime
from app.executor import LocalExecutor


logger = logging.getLogger("feishu-bot.tray")


class TrayApplication:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._copilot_runtime = CopilotRuntime(self._settings)
        self._lock = threading.Lock()
        self._bot_status = "等待启动"
        self._copilot_status = "等待检查"
        self._icon: Optional[pystray.Icon] = None

    def run(self) -> None:
        logger.info("Initializing tray icon")
        self._icon = pystray.Icon(
            "CopilotCLI-Feishu",
            self._load_icon_image(),
            self._settings.bot_name,
            self._build_menu(),
        )
        self._icon.run(self._on_ready)

    def _on_ready(self, icon: pystray.Icon) -> None:
        logger.info("Tray icon is ready")
        icon.visible = True
        self._refresh_menu()
        self._notify("CopilotCLI-Feishu", "已启动并最小化到系统托盘。")
        threading.Thread(target=self._bootstrap_background_services, daemon=True).start()

    def _bootstrap_background_services(self) -> None:
        self._refresh_copilot_status(notify=False)
        self._start_bot_thread()

    def _start_bot_thread(self) -> None:
        threading.Thread(target=self._run_bot, daemon=True).start()

    def _run_bot(self) -> None:
        self._set_bot_status("启动中")
        executor = LocalExecutor(
            work_dir=self._settings.work_dir,
            artifact_dir=self._settings.artifact_dir,
            copilot_runtime=self._copilot_runtime,
        )
        bot = FeishuBot(settings=self._settings, executor=executor)
        try:
            logger.info("Starting Feishu bot thread")
            self._set_bot_status("运行中")
            bot.start()
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__
            logger.exception("Feishu bot failed to start")
            self._set_bot_status(f"启动失败：{message}")
            self._notify("Feishu 机器人启动失败", message)

    def _refresh_copilot_status_async(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        threading.Thread(target=self._refresh_copilot_status, daemon=True).start()

    def _refresh_copilot_status(self, notify: bool = True) -> None:
        self._set_copilot_status("检查中")
        try:
            status = self._copilot_runtime.ensure_ready()
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__
            logger.warning("Copilot CLI check failed: %s", message)
            self._set_copilot_status(f"不可用：{message}")
            if notify:
                self._notify("Copilot CLI 不可用", message)
            return

        summary = f"已关联：{Path(status.executable or 'copilot').name} / {self._copilot_runtime.current_model()}"
        logger.info("Copilot CLI is ready: %s", summary)
        self._set_copilot_status(summary)
        if notify:
            self._notify("Copilot CLI 已就绪", status.detail)

    def _switch_model(self, model: str) -> None:
        try:
            selected = self._copilot_runtime.persist_model(model)
        except Exception as exc:
            logger.exception("Failed to switch Copilot model")
            self._notify("模型切换失败", str(exc))
            return

        logger.info("Switched Copilot model to %s", selected)
        self._set_copilot_status(f"模型已切换：{selected}")
        self._notify("Copilot 模型已更新", selected)

    def _switch_model_action(self, model: str):
        return lambda icon, item: self._switch_model(model)

    def _build_menu(self) -> pystray.Menu:
        current_model = self._copilot_runtime.current_model()
        model_items = [
            pystray.MenuItem(
                f"{'●' if model == current_model else '○'} {model}",
                self._switch_model_action(model),
            )
            for model in self._copilot_runtime.supported_models
        ]

        return pystray.Menu(
            pystray.MenuItem(f"机器人状态：{self._bot_status}", None, enabled=False),
            pystray.MenuItem(f"Copilot 状态：{self._copilot_status}", None, enabled=False),
            pystray.MenuItem(f"当前模型：{current_model}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("切换 Copilot 模型", pystray.Menu(*model_items)),
            pystray.MenuItem("重新检查 Copilot CLI", self._refresh_copilot_status_async),
            pystray.MenuItem("打开 .env 配置文件", self._open_env_file),
            pystray.MenuItem("打开程序目录", self._open_runtime_dir),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._quit),
        )

    def _refresh_menu(self) -> None:
        if self._icon is None:
            return
        self._icon.menu = self._build_menu()
        self._icon.update_menu()

    def _set_bot_status(self, value: str) -> None:
        with self._lock:
            self._bot_status = value
        self._refresh_menu()

    def _set_copilot_status(self, value: str) -> None:
        with self._lock:
            self._copilot_status = value
        self._refresh_menu()

    @staticmethod
    def _open_env_file(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        env_path = get_env_file_path()
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.touch(exist_ok=True)
        os.startfile(str(env_path))

    def _open_runtime_dir(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        os.startfile(str(Path(self._settings.env_file_path).resolve().parent))

    def _quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        logger.info("Tray application is exiting")
        self._notify("CopilotCLI-Feishu", "程序即将退出。")
        icon.stop()

    def _notify(self, title: str, message: str) -> None:
        if self._icon is None:
            return
        try:
            self._icon.notify(message[:256], title)
        except Exception:
            pass

    def _load_icon_image(self) -> Image.Image:
        custom_icon = self._settings.tray_icon_file
        if custom_icon is not None:
            logger.info("Using tray icon file: %s", custom_icon)
            return Image.open(custom_icon).convert("RGBA")
        logger.info("Using generated fallback tray icon")
        return self._build_placeholder_icon()

    @staticmethod
    def _build_placeholder_icon(size: int = 256) -> Image.Image:
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (18, 18, size - 18, size - 18),
            radius=56,
            fill=(17, 24, 39, 255),
        )
        draw.rounded_rectangle(
            (44, 44, size - 44, size - 44),
            radius=44,
            fill=(44, 199, 183, 255),
        )
        draw.rounded_rectangle(
            (74, 74, size - 74, size - 74),
            radius=32,
            fill=(26, 86, 219, 255),
        )
        draw.text((size * 0.33, size * 0.25), "C", fill=(255, 255, 255, 255))
        return image

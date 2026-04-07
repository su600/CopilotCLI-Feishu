# -*- coding: utf-8 -*-
import shutil
import subprocess
import threading
from dataclasses import dataclass
from typing import Optional

from app.config import (
    DEFAULT_COPILOT_MODEL,
    SUPPORTED_COPILOT_MODELS,
    Settings,
    persist_env_value,
)


@dataclass(frozen=True)
class CopilotStatus:
    ready: bool
    detail: str
    executable: Optional[str] = None


class CopilotRuntime:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._model = settings.copilot_model or DEFAULT_COPILOT_MODEL
        self._configured_executable = settings.copilot_cli_path

    @property
    def supported_models(self) -> tuple[str, ...]:
        return SUPPORTED_COPILOT_MODELS

    def current_model(self) -> str:
        with self._lock:
            return self._model

    def resolve_executable(self) -> str:
        candidates = []
        if self._configured_executable:
            candidates.append(self._configured_executable)
        candidates.extend(["copilot.exe", "copilot"])

        for candidate in candidates:
            resolved = shutil.which(candidate) if candidate in {"copilot.exe", "copilot"} else candidate
            if resolved:
                return resolved
        raise RuntimeError(
            "未找到 copilot CLI。请先安装并确保 `copilot.exe` 在 PATH 中，或在 `.env` 里配置 `COPILOT_CLI_PATH`。"
        )

    def ensure_ready(self, timeout: int = 30) -> CopilotStatus:
        executable = self.resolve_executable()
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or f"exit code {completed.returncode}").strip()
            raise RuntimeError(f"copilot CLI 启动检查失败：{detail}")

        version = (completed.stdout or completed.stderr or "").strip().splitlines()
        detail = version[0] if version else "copilot CLI 已就绪"
        return CopilotStatus(True, detail=detail, executable=executable)

    def persist_model(self, model: str) -> str:
        normalized = model.strip()
        if normalized not in SUPPORTED_COPILOT_MODELS:
            raise ValueError(f"Unsupported Copilot model: {model}")
        with self._lock:
            self._model = normalized
        persist_env_value("COPILOT_MODEL", normalized)
        return normalized

    def build_command(self, prompt: str) -> list[str]:
        executable = self.resolve_executable()
        return [
            executable,
            "-p",
            prompt,
            "--allow-all",
            "--no-ask-user",
            "--model",
            self.current_model(),
            "-s",
            "--log-level",
            "error",
        ]

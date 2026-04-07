# -*- coding: utf-8 -*-
import os
import subprocess
import re
import textwrap
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class ExecutionResponse:
    handled: bool
    reply: str
    attachment_path: Optional[str] = None
    attachment_kind: Optional[str] = None


class LocalExecutor:
    def __init__(self, work_dir: str = "", artifact_dir: str = "") -> None:
        self._cwd = (
            Path(os.path.expandvars(os.path.expanduser(work_dir))).resolve()
            if work_dir
            else Path.home()
        )
        self._artifact_dir = (
            Path(os.path.expandvars(os.path.expanduser(artifact_dir))).resolve()
            if artifact_dir
            else Path.home() / ".feishu-bot" / "artifacts"
        )
        self._recent_artifacts: List[Path] = []

    def help_text(self) -> str:
        return (
            "执行模式：\n"
            "- `/help`、`ping` 走机器人内置回复\n"
            "- 以 `!` 开头时，后面的内容直接作为 PowerShell 命令执行\n"
            "- 其他自然语言消息会先理解意图，再自动执行最合适的单一步骤\n"
            "- 优先触发已安装的 skill，例如 `填写周报` / `打开浏览器`\n"
            "- 默认不要展开成多个无关操作"
        )

    def handle_text(self, text: str) -> ExecutionResponse:
        normalized = text.strip()
        if not normalized:
            return ExecutionResponse(True, "ℹ️ 收到空消息，未执行任何操作。")

        if self._looks_like_screenshot_request(normalized):
            screenshot_path = self._capture_screenshot()
            self._remember_artifact(screenshot_path)
            return ExecutionResponse(
                True,
                f"📸 已截图并准备通过飞书发回：`{screenshot_path.name}`",
                attachment_path=str(screenshot_path),
                attachment_kind="image",
            )

        if self._looks_like_send_request(normalized):
            send_request = self._resolve_send_request(normalized)
            if send_request is None:
                return ExecutionResponse(
                    True,
                    "⚠️ 我没找到可发送的本地文件。你可以直接发完整路径，或者先让我生成/找到文件后再发 `把文件通过飞书发给我`。",
                )
            path, kind = send_request
            icon = "🖼️" if kind == "image" else "📎"
            return ExecutionResponse(
                True,
                f"{icon} 准备通过飞书发送：`{path.name}`",
                attachment_path=str(path),
                attachment_kind=kind,
            )

        if normalized.startswith("!"):
            command = normalized[1:].strip()
            if not command:
                return ExecutionResponse(True, "⚠️ 请在 `!` 后面附上要执行的 PowerShell 命令。")
            result = self._run_powershell(command, timeout=120)
            self._remember_artifacts_from_text(result)
            return ExecutionResponse(True, f"✅ 已执行 PowerShell：\n`{command}`\n\n{result}")

        result = self._run_copilot(self._build_copilot_prompt(normalized), timeout=900)
        self._remember_artifacts_from_text(result)
        return ExecutionResponse(True, result)

    @staticmethod
    def _looks_like_screenshot_request(text: str) -> bool:
        screenshot_terms = (
            "截图",
            "截个图",
            "截屏",
            "屏幕截图",
            "把电脑截个图",
            "把屏幕截个图",
            "截一下图",
        )
        return any(term in text for term in screenshot_terms)

    def _capture_screenshot(self) -> Path:
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = self._artifact_dir / f"desktop-screenshot-{timestamp}.png"
        command = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Drawing; "
            "$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen; "
            "$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height; "
            "$graphics = [System.Drawing.Graphics]::FromImage($bitmap); "
            "$graphics.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bitmap.Size); "
            f"$bitmap.Save('{str(output_path)}', [System.Drawing.Imaging.ImageFormat]::Png); "
            "$graphics.Dispose(); "
            "$bitmap.Dispose()"
        )
        completed = subprocess.run(
            ["pwsh", "-NoProfile", "-Command", command],
            cwd=str(self._cwd),
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0 or not output_path.is_file():
            stderr = (completed.stderr or "").strip()
            stdout = (completed.stdout or "").strip()
            detail = stderr or stdout or f"exit code {completed.returncode}"
            raise RuntimeError(f"截图失败：{detail}")
        return output_path

    @staticmethod
    def _looks_like_send_request(text: str) -> bool:
        send_terms = ("发给我", "发我", "发送给我", "通过飞书发", "发到飞书", "发送文件", "发送图片", "发文件", "发图片")
        return any(term in text for term in send_terms)

    def _resolve_send_request(self, text: str) -> Optional[tuple[Path, str]]:
        if not self._looks_like_send_request(text):
            return None

        explicit_path = self._extract_explicit_path(text)
        prefer_image = any(term in text for term in ("图片", "截图", "照片", "image", "png", "jpg", "jpeg"))
        path = explicit_path or self._find_recent_artifact(prefer_image=prefer_image)
        if path is None:
            return None

        kind = "image" if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"} else "file"
        return path, kind

    def _find_recent_artifact(self, prefer_image: bool) -> Optional[Path]:
        image_suffixes = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
        if prefer_image:
            for path in reversed(self._recent_artifacts):
                if path.suffix.lower() in image_suffixes and path.is_file():
                    return path

        for path in reversed(self._recent_artifacts):
            if path.is_file():
                return path
        return None

    def _remember_artifacts_from_text(self, text: str) -> None:
        for path in self._extract_existing_paths(text):
            self._remember_artifact(path)

    def _remember_artifact(self, path: Path) -> None:
        resolved = path.resolve()
        self._recent_artifacts = [item for item in self._recent_artifacts if item != resolved]
        self._recent_artifacts.append(resolved)
        if len(self._recent_artifacts) > 20:
            self._recent_artifacts = self._recent_artifacts[-20:]

    @staticmethod
    def _extract_existing_paths(text: str) -> List[Path]:
        matches = re.findall(r"[A-Za-z]:\\[^\r\n`\"']+", text)
        results: List[Path] = []
        for match in matches:
            cleaned = match.rstrip("。！，,.;:)]}")
            path = Path(cleaned)
            if path.is_file():
                results.append(path)
        return results

    @staticmethod
    def _extract_explicit_path(text: str) -> Optional[Path]:
        paths = LocalExecutor._extract_existing_paths(text)
        return paths[-1] if paths else None

    @staticmethod
    def _build_copilot_prompt(user_text: str) -> str:
        return (
            "你是一个本机 Feishu 自动执行器。"
            "请先理解用户意图，然后只执行一个最合适的动作。"
            "优先调用已安装的 skill；如果意图是周报，请使用 weekly-report-wps；"
            "如果意图是打开浏览器，只打开一次；如果意图明确是系统命令，再执行对应命令。"
            "如果任务产出本地文件，请在回复中明确写出完整 Windows 路径。"
            "不要重复执行，不要展开成多个无关步骤，不要追问，除非确实无法判断意图。"
            "完成后用简短中文回复执行结果，并适当带一个 emoji。"
            f"\n\n用户消息：{user_text}"
        )

    def _run_copilot(self, prompt: str, timeout: int) -> str:
        completed = subprocess.run(
            [
                "copilot.exe",
                "-p",
                prompt,
                "--allow-all",
                "--no-ask-user",
                "--model",
                "gpt-5.4",
                "-s",
                "--log-level",
                "error",
            ],
            cwd=str(self._cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()

        if completed.returncode == 0 and stdout:
            return self._with_emoji(self._truncate(stdout, limit=4000))

        parts = [f"Copilot 执行失败，退出码: {completed.returncode}"]
        if stdout:
            parts.append("输出:\n" + self._truncate(stdout))
        if stderr:
            parts.append("错误:\n" + self._truncate(stderr))
        if not stdout and not stderr:
            parts.append("无输出。")
        return "\n\n".join(parts)

    def _run_powershell(self, command: str, timeout: int) -> str:
        completed = subprocess.run(
            ["pwsh", "-NoProfile", "-Command", command],
            cwd=str(self._cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()

        parts = [f"退出码: {completed.returncode}"]
        if stdout:
            parts.append("输出:\n" + self._truncate(stdout))
        if stderr:
            parts.append("错误:\n" + self._truncate(stderr))
        if not stdout and not stderr:
            parts.append("无输出。")
        return "\n\n".join(parts)

    @staticmethod
    def _truncate(text: str, limit: int = 2000) -> str:
        if len(text) <= limit:
            return text
        return textwrap.shorten(text, width=limit, placeholder="\n...[输出已截断]")

    @staticmethod
    def _with_emoji(text: str) -> str:
        if text.startswith(("✅", "📝", "⚠️", "ℹ️", "🤖")):
            return text
        return f"✨ {text}"

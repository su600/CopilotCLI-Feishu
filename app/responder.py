# -*- coding: utf-8 -*-
import json
from typing import Any, Dict, Optional

import requests

from app.config import Settings


class Responder:
    def __init__(self, settings: Settings, executor_help_text: str = "") -> None:
        self._settings = settings
        self._executor_help_text = executor_help_text

    def _help_text(self) -> str:
        return (
            f"🤖 {self._settings.bot_name} 已启动。\n\n"
            "可用命令：\n"
            "- /help：查看帮助\n"
            "- ping：检查机器人是否在线\n"
            f"{self._executor_help_text}\n\n"
            "如果已配置 OpenAI 兼容接口，普通文本会转为智能回复。"
        )

    def build_builtin_reply(self, incoming_text: str) -> Optional[str]:
        text = incoming_text.strip()
        lower = text.lower()

        if lower in {"/help", "help", "帮助"}:
            return self._help_text()

        if lower in {"ping", "/ping"}:
            return "✅ pong"

        return None

    def _llm_reply(self, user_text: str) -> str:
        response = requests.post(
            f"{self._settings.openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._settings.openai_api_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "model": self._settings.openai_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant running inside a Feishu private-chat bot. "
                            "Reply briefly and clearly in Chinese unless the user clearly asks for another language."
                        ),
                    },
                    {"role": "user", "content": user_text},
                ],
                "temperature": 0.4,
            },
            timeout=60,
        )
        response.raise_for_status()
        data: Dict[str, Any] = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"LLM response had no choices: {data}")

        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

        raise RuntimeError(f"LLM response did not include text content: {data}")

    def build_reply(self, incoming_text: str) -> str:
        text = incoming_text.strip()
        lower = text.lower()

        builtin_reply = self.build_builtin_reply(text)
        if builtin_reply is not None:
            return builtin_reply

        if self._settings.llm_ready:
            try:
                return self._llm_reply(text)
            except Exception as exc:
                return f"LLM 调用失败：{exc}"

        return (
            f"已收到：{text}\n\n"
            "当前还没有配置智能回复。"
            "如果你想让机器人直接聊天，请在 `.env` 中配置 OPENAI_API_KEY。"
        )

    @staticmethod
    def extract_text_content(content: str) -> str:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return content

        text = data.get("text")
        if isinstance(text, str):
            return text
        return content

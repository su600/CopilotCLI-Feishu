# -*- coding: utf-8 -*-
import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImChatAccessEventBotP2pChatEnteredV1,
    P2ImMessageReceiveV1,
)
from lark_oapi.event.custom import CustomizedEvent

from app.config import get_settings
from app.feishu_api import FeishuAPIClient
from app.executor import LocalExecutor
from app.responder import Responder


logger = logging.getLogger("feishu-bot")


class FeishuBot:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.executor = LocalExecutor()
        self.responder = Responder(self.settings, self.executor.help_text())
        self.feishu_api = FeishuAPIClient(self.settings)
        self._recent_message_ids: "OrderedDict[str, float]" = OrderedDict()
        self._recent_message_ids_lock = threading.Lock()
        self._active_messages: Dict[str, float] = {}
        self._active_messages_lock = threading.Lock()
        self.client = (
            lark.Client.builder()
            .app_id(self.settings.feishu_app_id)
            .app_secret(self.settings.feishu_app_secret)
            .log_level(lark.LogLevel.INFO)
            .build()
        )

    def health(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "mode": "long_connection",
            "feishu_ready": self.settings.feishu_ready,
            "llm_ready": self.settings.llm_ready,
            "missing_feishu_settings": self.settings.missing_feishu_settings,
        }

    def send_text_message(self, receive_open_id: str, text: str) -> None:
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("open_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(receive_open_id)
                .msg_type("text")
                .content(json.dumps({"text": text}, ensure_ascii=False))
                .build()
            )
            .build()
        )
        response = self.client.im.v1.message.create(request)
        if not response.success():
            raise RuntimeError(
                f"Failed to send Feishu message. code={response.code}, msg={response.msg}, log_id={response.get_log_id()}"
            )

    def _process_text_message(self, message_id: str, open_id: str, incoming_text: str) -> None:
        progress_sent = threading.Event()

        def send_progress() -> None:
            try:
                progress_sent.set()
                self.send_text_message(open_id, "⏳ 正在处理，我马上回来。")
            except Exception:
                logger.exception("Failed to send progress message")

        progress_timer = threading.Timer(2.0, send_progress)
        try:
            progress_timer.start()
            builtin_reply = self.responder.build_builtin_reply(incoming_text)
            if builtin_reply is not None:
                progress_timer.cancel()
                self.send_text_message(open_id, builtin_reply)
                return
            execution = self.executor.handle_text(incoming_text)
            if execution.attachment_path and execution.attachment_kind:
                if execution.attachment_kind == "image":
                    image_key = self.feishu_api.upload_image(execution.attachment_path)
                    self.feishu_api.send_image_message(open_id, image_key)
                else:
                    file_key = self.feishu_api.upload_file(execution.attachment_path)
                    self.feishu_api.send_file_message(open_id, file_key)
            progress_timer.cancel()
            self.send_text_message(open_id, execution.reply)
        except Exception as exc:
            progress_timer.cancel()
            logger.exception("Failed to process message")
            self.send_text_message(open_id, f"⚠️ 处理消息时出错：{exc}")
        finally:
            with self._active_messages_lock:
                self._active_messages.pop(message_id, None)

    def _dispatch_text_message(self, message_id: str, open_id: str, incoming_text: str) -> None:
        with self._active_messages_lock:
            now = time.time()
            cutoff = now - 600
            stale_ids = [mid for mid, seen_at in self._active_messages.items() if seen_at < cutoff]
            for stale_id in stale_ids:
                self._active_messages.pop(stale_id, None)
            if message_id in self._active_messages:
                logger.info("Message already being processed: %s", message_id)
                return
            self._active_messages[message_id] = now

        worker = threading.Thread(
            target=self._process_text_message,
            args=(message_id, open_id, incoming_text),
            daemon=True,
        )
        worker.start()

    @staticmethod
    def _is_stale_message(create_time: Optional[str], max_age_seconds: int = 180) -> bool:
        if not create_time:
            return False
        try:
            created_at = int(create_time) / 1000.0
        except (TypeError, ValueError):
            return False
        return (time.time() - created_at) > max_age_seconds

    def _should_process_message(self, message_id: str) -> bool:
        with self._recent_message_ids_lock:
            now = time.time()
            cutoff = now - 120
            while self._recent_message_ids:
                oldest_message_id, oldest_seen_at = next(iter(self._recent_message_ids.items()))
                if oldest_seen_at >= cutoff:
                    break
                self._recent_message_ids.popitem(last=False)

            if message_id in self._recent_message_ids:
                return False

            self._recent_message_ids[message_id] = now
            return True

    def handle_message(self, data: P2ImMessageReceiveV1) -> None:
        event = data.event
        logger.info("Received Feishu message event")
        if event is None or event.message is None or event.sender is None:
            logger.warning("Ignored malformed message event")
            return

        sender = event.sender
        message = event.message
        sender_id = getattr(sender, "sender_id", None)
        open_id = getattr(sender_id, "open_id", None)

        if sender.sender_type != "user":
            logger.info("Ignored non-user sender")
            return

        if message.chat_type != "p2p":
            logger.info("Ignored non-private chat")
            return

        if message.message_type != "text":
            if open_id:
                self.send_text_message(open_id, "当前版本仅支持文本消息。")
            return

        if not open_id:
            logger.warning("Ignored message without sender open_id")
            return

        message_id = getattr(message, "message_id", None)
        if message_id and not self._should_process_message(message_id):
            logger.info("Ignored duplicate message event: %s", message_id)
            return
        create_time = getattr(message, "create_time", None)
        if self._is_stale_message(create_time):
            logger.info("Ignored stale message event: %s", message_id)
            return

        incoming_text = self.responder.extract_text_content(message.content or "")
        self._dispatch_text_message(message_id or f"legacy-{time.time()}", open_id, incoming_text)

    def handle_raw_message_event(self, data: CustomizedEvent) -> None:
        logger.info("Received raw customized event: type=%s, header=%s, event=%s", data.type, data.header, data.event)
        event = data.event or {}
        sender = event.get("sender") or {}
        sender_id = sender.get("sender_id") or {}
        message = event.get("message") or {}
        open_id = sender_id.get("open_id")

        if sender.get("sender_type") != "user":
            logger.info("Ignored non-user sender in raw event")
            return

        if message.get("chat_type") != "p2p":
            logger.info("Ignored non-private raw event")
            return

        if message.get("message_type") != "text":
            if open_id:
                self.send_text_message(open_id, "当前版本仅支持文本消息。")
            return

        if not open_id:
            logger.warning("Ignored raw message without sender open_id")
            return

        message_id = message.get("message_id")
        if message_id and not self._should_process_message(message_id):
            logger.info("Ignored duplicate raw message event: %s", message_id)
            return
        if self._is_stale_message(message.get("create_time")):
            logger.info("Ignored stale raw message event: %s", message_id)
            return

        incoming_text = self.responder.extract_text_content(message.get("content", ""))
        self._dispatch_text_message(message_id or f"legacy-{time.time()}", open_id, incoming_text)

    def handle_message_read_event(self, data: Any) -> None:
        logger.info("Ignored message read event")

    def handle_p2p_chat_entered(self, data: P2ImChatAccessEventBotP2pChatEnteredV1) -> None:
        logger.info("User entered bot p2p chat")

    def start(self) -> None:
        if not self.settings.feishu_ready:
            missing = ", ".join(self.settings.missing_feishu_settings)
            raise RuntimeError(f"Missing Feishu configuration: {missing}")

        event_handler = (
            lark.EventDispatcherHandler.builder("", self.settings.feishu_verify_token, lark.LogLevel.INFO)
            .register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(self.handle_p2p_chat_entered)
            .register_p2_customized_event("im.message.message_read_v1", self.handle_message_read_event)
            .register_p2_customized_event("im.message.receive_v1", self.handle_raw_message_event)
            .build()
        )

        ws_client = lark.ws.Client(
            self.settings.feishu_app_id,
            self.settings.feishu_app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        logger.info("Starting Feishu long connection bot")
        ws_client.start()

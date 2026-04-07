# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from app.config import Settings


class FeishuAPIError(RuntimeError):
    pass


class FeishuAPIClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._tenant_access_token: Optional[str] = None
        self._tenant_token_expire_at: float = 0.0

    def _require_feishu_config(self) -> None:
        if not self._settings.feishu_ready:
            missing = ", ".join(self._settings.missing_feishu_settings)
            raise FeishuAPIError(f"Missing Feishu configuration: {missing}")

    def get_tenant_access_token(self) -> str:
        self._require_feishu_config()

        now = time.time()
        if self._tenant_access_token and now < self._tenant_token_expire_at:
            return self._tenant_access_token

        response = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={
                "app_id": self._settings.feishu_app_id,
                "app_secret": self._settings.feishu_app_secret,
            },
            timeout=15,
        )
        data = self._read_json_response(response)
        self._raise_for_api_error(data, "Failed to get tenant_access_token")

        token = data.get("tenant_access_token")
        expire = int(data.get("expire", 7200))
        if not token:
            raise FeishuAPIError("Feishu auth response did not include tenant_access_token")

        self._tenant_access_token = token
        self._tenant_token_expire_at = now + max(expire - 60, 60)
        return token

    def send_text_message(self, receive_open_id: str, text: str) -> dict:
        token = self.get_tenant_access_token()
        response = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "receive_id": receive_open_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
            },
            timeout=15,
        )
        data = self._read_json_response(response)
        self._raise_for_api_error(data, "Failed to send Feishu message")
        return data

    def send_file_message(self, receive_open_id: str, file_key: str) -> dict:
        token = self.get_tenant_access_token()
        response = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "receive_id": receive_open_id,
                "msg_type": "file",
                "content": json.dumps({"file_key": file_key}, ensure_ascii=False),
            },
            timeout=15,
        )
        data = self._read_json_response(response)
        self._raise_for_api_error(data, "Failed to send Feishu file message")
        return data

    def send_image_message(self, receive_open_id: str, image_key: str) -> dict:
        token = self.get_tenant_access_token()
        response = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "receive_id": receive_open_id,
                "msg_type": "image",
                "content": json.dumps({"image_key": image_key}, ensure_ascii=False),
            },
            timeout=15,
        )
        data = self._read_json_response(response)
        self._raise_for_api_error(data, "Failed to send Feishu image message")
        return data

    def upload_file(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.is_file():
            raise FeishuAPIError(f"Local file not found: {path}")

        token = self.get_tenant_access_token()
        with path.open("rb") as file_handle:
            response = requests.post(
                "https://open.feishu.cn/open-apis/im/v1/files",
                headers={"Authorization": f"Bearer {token}"},
                data={"file_type": "stream", "file_name": path.name},
                files={"file": (path.name, file_handle, "application/octet-stream")},
                timeout=60,
            )
        data = self._read_json_response(response)
        self._raise_for_api_error(data, "Failed to upload Feishu file")

        file_key = ((data.get("data") or {}).get("file_key")) or data.get("file_key")
        if not file_key:
            raise FeishuAPIError(f"Feishu file upload response missing file_key: {data}")
        return file_key

    def upload_image(self, image_path: str) -> str:
        path = Path(image_path)
        if not path.is_file():
            raise FeishuAPIError(f"Local image not found: {path}")

        token = self.get_tenant_access_token()
        mime_type = self._guess_image_mime_type(path)
        with path.open("rb") as file_handle:
            response = requests.post(
                "https://open.feishu.cn/open-apis/im/v1/images",
                headers={"Authorization": f"Bearer {token}"},
                data={"image_type": "message"},
                files={"image": (path.name, file_handle, mime_type)},
                timeout=60,
            )
        data = self._read_json_response(response)
        self._raise_for_api_error(data, "Failed to upload Feishu image")

        image_key = ((data.get("data") or {}).get("image_key")) or data.get("image_key")
        if not image_key:
            raise FeishuAPIError(f"Feishu image upload response missing image_key: {data}")
        return image_key

    @staticmethod
    def _guess_image_mime_type(path: Path) -> str:
        suffix = path.suffix.lower()
        mapping = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
        }
        return mapping.get(suffix, "application/octet-stream")

    @staticmethod
    def _read_json_response(response: requests.Response) -> Dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            raise FeishuAPIError(f"Feishu API returned non-JSON response: {response.text}")
        return data

    @staticmethod
    def _raise_for_api_error(data: Dict[str, Any], prefix: str) -> None:
        if data.get("code") == 0:
            return

        msg = str(data.get("msg", "")).strip()
        permission_violations = ((data.get("error") or {}).get("permission_violations")) or []
        scopes = [item.get("subject") for item in permission_violations if item.get("subject")]
        if scopes:
            raise FeishuAPIError(f"{prefix}: 缺少飞书权限 {', '.join(scopes)}")
        if msg:
            raise FeishuAPIError(f"{prefix}: {msg}")
        raise FeishuAPIError(f"{prefix}: {data}")

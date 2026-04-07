# -*- coding: utf-8 -*-
from dataclasses import dataclass
from functools import lru_cache
import os
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv


def _runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _load_env_files() -> None:
    candidates = [Path.cwd() / ".env", _runtime_dir() / ".env"]
    runtime_parent = _runtime_dir().parent
    if runtime_parent not in {candidate.parent for candidate in candidates}:
        candidates.append(runtime_parent / ".env")

    for env_path in candidates:
        if env_path.is_file():
            load_dotenv(env_path)


_load_env_files()


@dataclass(frozen=True)
class Settings:
    feishu_app_id: str
    feishu_app_secret: str
    feishu_verify_token: str
    openai_base_url: str
    openai_api_key: str
    openai_model: str
    bot_name: str
    work_dir: str
    artifact_dir: str

    @property
    def missing_feishu_settings(self) -> List[str]:
        missing: List[str] = []
        if not self.feishu_app_id:
            missing.append("FEISHU_APP_ID")
        if not self.feishu_app_secret:
            missing.append("FEISHU_APP_SECRET")
        if not self.feishu_verify_token:
            missing.append("FEISHU_VERIFY_TOKEN")
        return missing

    @property
    def feishu_ready(self) -> bool:
        return not self.missing_feishu_settings

    @property
    def llm_ready(self) -> bool:
        return bool(self.openai_api_key and self.openai_model and self.openai_base_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    default_work_dir = str(Path.home())
    default_artifact_dir = str(Path.home() / ".feishu-bot" / "artifacts")
    return Settings(
        feishu_app_id=os.getenv("FEISHU_APP_ID", "").strip(),
        feishu_app_secret=os.getenv("FEISHU_APP_SECRET", "").strip(),
        feishu_verify_token=os.getenv("FEISHU_VERIFY_TOKEN", "").strip(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        bot_name=os.getenv("BOT_NAME", "Feishu Local Bot").strip() or "Feishu Local Bot",
        work_dir=os.getenv("WORK_DIR", "").strip() or default_work_dir,
        artifact_dir=os.getenv("ARTIFACT_DIR", "").strip() or default_artifact_dir,
    )

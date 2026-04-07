# -*- coding: utf-8 -*-
from dataclasses import dataclass
from functools import lru_cache
import os
import sys
from pathlib import Path
from typing import Iterable, List, Optional

from dotenv import load_dotenv, set_key


DEFAULT_COPILOT_MODEL = "gpt-5.4"
SUPPORTED_COPILOT_MODELS = (
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5-mini",
    "gpt-5.3-codex",
    "gpt-5.2-codex",
    "gpt-5.2",
    "gpt-5.1",
    "gpt-4.1",
)


def _runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def iter_env_candidates() -> Iterable[Path]:
    seen: set[Path] = set()
    for candidate in (Path.cwd() / ".env", _runtime_dir() / ".env", _runtime_dir().parent / ".env"):
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        yield resolved


def find_env_file() -> Optional[Path]:
    for env_path in iter_env_candidates():
        if env_path.is_file():
            return env_path
    return None


def get_env_file_path() -> Path:
    existing = find_env_file()
    if existing is not None:
        return existing
    return (_runtime_dir() / ".env").resolve()


def _load_env_files() -> None:
    for env_path in iter_env_candidates():
        if env_path.is_file():
            load_dotenv(env_path)


def clear_settings_cache() -> None:
    get_settings.cache_clear()


def reload_environment() -> None:
    env_path = find_env_file()
    if env_path is not None:
        load_dotenv(env_path, override=True)
    clear_settings_cache()


def persist_env_value(key: str, value: str) -> Path:
    env_path = get_env_file_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    if not env_path.exists():
        env_path.touch()
    set_key(str(env_path), key, value, quote_mode="auto")
    os.environ[key] = value
    reload_environment()
    return env_path


_load_env_files()


@dataclass(frozen=True)
class Settings:
    feishu_app_id: str
    feishu_app_secret: str
    feishu_verify_token: str
    openai_base_url: str
    openai_api_key: str
    openai_model: str
    copilot_model: str
    copilot_cli_path: str
    tray_icon_path: str
    bot_name: str
    work_dir: str
    artifact_dir: str
    env_file_path: str

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

    @property
    def tray_icon_file(self) -> Optional[Path]:
        if not self.tray_icon_path:
            return None
        path = Path(os.path.expandvars(os.path.expanduser(self.tray_icon_path))).resolve()
        return path if path.is_file() else None


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
        copilot_model=os.getenv("COPILOT_MODEL", DEFAULT_COPILOT_MODEL).strip() or DEFAULT_COPILOT_MODEL,
        copilot_cli_path=os.getenv("COPILOT_CLI_PATH", "").strip(),
        tray_icon_path=os.getenv("TRAY_ICON_PATH", "").strip(),
        bot_name=os.getenv("BOT_NAME", "Feishu Local Bot").strip() or "Feishu Local Bot",
        work_dir=os.getenv("WORK_DIR", "").strip() or default_work_dir,
        artifact_dir=os.getenv("ARTIFACT_DIR", "").strip() or default_artifact_dir,
        env_file_path=str(get_env_file_path()),
    )

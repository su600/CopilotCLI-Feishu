import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dotenv import dotenv_values

from app.config import Settings, persist_env_value, resolve_tray_icon_path
from app.copilot_runtime import CopilotRuntime


def make_settings(**overrides) -> Settings:
    defaults = {
        "feishu_app_id": "app-id",
        "feishu_app_secret": "app-secret",
        "feishu_verify_token": "verify-token",
        "openai_base_url": "https://api.openai.com/v1",
        "openai_api_key": "",
        "openai_model": "gpt-4.1-mini",
        "copilot_model": "gpt-5.4",
        "copilot_cli_path": r"C:\Tools\copilot.exe",
        "tray_icon_path": "",
        "bot_name": "Feishu Local Bot",
        "work_dir": r"C:\Users\su600",
        "artifact_dir": r"C:\Users\su600\.feishu-bot\artifacts",
        "env_file_path": str(Path(tempfile.gettempdir()) / ".env"),
    }
    defaults.update(overrides)
    return Settings(**defaults)


class ConfigPersistenceTests(unittest.TestCase):
    def test_persist_env_value_updates_env_file_and_process_env(self) -> None:
        previous = os.environ.get("COPILOT_MODEL")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                env_path = Path(temp_dir) / ".env"
                with patch("app.config.get_env_file_path", return_value=env_path), patch("app.config.reload_environment"):
                    written_path = persist_env_value("COPILOT_MODEL", "gpt-5-mini")

                self.assertEqual(written_path, env_path)
                self.assertEqual(dotenv_values(env_path).get("COPILOT_MODEL"), "gpt-5-mini")
                self.assertEqual(os.environ.get("COPILOT_MODEL"), "gpt-5-mini")
        finally:
            if previous is None:
                os.environ.pop("COPILOT_MODEL", None)
            else:
                os.environ["COPILOT_MODEL"] = previous

    def test_resolve_tray_icon_path_prefers_repo_favicon(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            dist_dir = repo_root / "dist"
            dist_dir.mkdir()
            icon_path = repo_root / "favicon.ico"
            icon_path.write_bytes(b"ico")

            with patch("app.config._runtime_dir", return_value=dist_dir):
                resolved = resolve_tray_icon_path("")

        self.assertEqual(resolved, icon_path.resolve())

    def test_resolve_tray_icon_path_uses_explicit_path_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            icon_path = Path(temp_dir) / "custom.ico"
            icon_path.write_bytes(b"ico")

            resolved = resolve_tray_icon_path(str(icon_path))

        self.assertEqual(resolved, icon_path.resolve())


class CopilotRuntimeTests(unittest.TestCase):
    def test_build_command_uses_persisted_model(self) -> None:
        runtime = CopilotRuntime(make_settings())
        with patch("app.copilot_runtime.persist_env_value"):
            runtime.persist_model("gpt-5-mini")
        with patch.object(runtime, "resolve_executable", return_value=r"C:\Tools\copilot.exe"):
            command = runtime.build_command("hello")

        self.assertEqual(command[0], r"C:\Tools\copilot.exe")
        self.assertEqual(command[1:3], ["-p", "hello"])
        self.assertEqual(command[command.index("--model") + 1], "gpt-5-mini")

    def test_ensure_ready_checks_copilot_version(self) -> None:
        runtime = CopilotRuntime(make_settings(copilot_cli_path=""))
        completed = subprocess.CompletedProcess(
            args=[r"C:\Tools\copilot.exe", "--version"],
            returncode=0,
            stdout="copilot-cli 1.2.3\n",
            stderr="",
        )

        with patch("app.copilot_runtime.shutil.which", return_value=r"C:\Tools\copilot.exe"), patch(
            "app.copilot_runtime.subprocess.run", return_value=completed
        ) as run_mock:
            status = runtime.ensure_ready()

        self.assertTrue(status.ready)
        self.assertEqual(status.executable, r"C:\Tools\copilot.exe")
        self.assertEqual(status.detail, "copilot-cli 1.2.3")
        run_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()

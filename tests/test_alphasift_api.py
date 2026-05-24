# -*- coding: utf-8 -*-
"""Tests for the minimal AlphaSift screening endpoints."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager

DEFAULT_ALPHASIFT_TEST_SPEC = "git+https://github.com/ZhuLinsen/alphasift.git"


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class AlphaSiftOpportunitiesApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "alphasift_api_test.db"
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("ALPHASIFT_ENABLED", None)
        os.environ.pop("ALPHASIFT_INSTALL_SPEC", None)
        self.temp_dir.cleanup()

    def _client(self, *, enabled: bool, install_spec: str = DEFAULT_ALPHASIFT_TEST_SPEC) -> TestClient:
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=false",
                    f"DATABASE_PATH={self.db_path}",
                    f"ALPHASIFT_ENABLED={'true' if enabled else 'false'}",
                    f"ALPHASIFT_INSTALL_SPEC={install_spec}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        Config.reset_instance()
        DatabaseManager.reset_instance()
        os.environ["ALPHASIFT_ENABLED"] = "true" if enabled else "false"
        os.environ["ALPHASIFT_INSTALL_SPEC"] = install_spec
        return TestClient(create_app(static_dir=self.data_dir / "empty-static"))

    def test_status_defaults_to_disabled(self) -> None:
        client = self._client(enabled=False)

        resp = client.get("/api/v1/alphasift/status")

        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["enabled"], False)
        self.assertEqual(payload["install_spec"], DEFAULT_ALPHASIFT_TEST_SPEC)

    def test_screen_rejects_when_disabled(self) -> None:
        client = self._client(enabled=False)

        resp = client.post("/api/v1/alphasift/screen", json={})

        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["error"], "alphasift_disabled")

    def test_screen_reports_alphasift_install_failure(self) -> None:
        client = self._client(enabled=True)
        completed = SimpleNamespace(returncode=1, stdout="", stderr="not found")

        with (
            patch("api.v1.endpoints.alphasift.subprocess.run", return_value=completed),
            patch("api.v1.endpoints.alphasift.importlib.import_module", side_effect=ModuleNotFoundError("No module named 'alphasift'")),
        ):
            resp = client.post("/api/v1/alphasift/screen", json={})

        self.assertEqual(resp.status_code, 424)
        payload = resp.json()
        self.assertEqual(payload["error"], "alphasift_install_failed")
        self.assertIn("AlphaSift", payload["message"])

    def test_screen_rejects_pypi_placeholder_without_running_pip(self) -> None:
        client = self._client(enabled=True, install_spec="alphasift")

        with (
            patch("api.v1.endpoints.alphasift.subprocess.run") as run_mock,
            patch("api.v1.endpoints.alphasift.importlib.import_module", side_effect=ModuleNotFoundError("No module named 'alphasift'")),
        ):
            resp = client.post("/api/v1/alphasift/screen", json={})

        self.assertEqual(resp.status_code, 424)
        self.assertEqual(resp.json()["error"], "alphasift_install_spec_missing")
        run_mock.assert_not_called()

    def test_screen_auto_installs_alphasift_package_when_enabled(self) -> None:
        client = self._client(enabled=True)
        fake_module = SimpleNamespace(
            screen=MagicMock(return_value=[{"code": "600519", "name": "Kweichow Moutai", "score": 88.5}])
        )
        completed = SimpleNamespace(returncode=0, stdout="installed", stderr="")

        with (
            patch("api.v1.endpoints.alphasift.subprocess.run", return_value=completed) as run_mock,
            patch(
                "api.v1.endpoints.alphasift.importlib.import_module",
                side_effect=[
                    ModuleNotFoundError("No module named 'alphasift'"),
                    ModuleNotFoundError("No module named 'alphasift'"),
                    fake_module,
                    fake_module,
                ],
            ),
        ):
            resp = client.post(
                "/api/v1/alphasift/screen",
                json={"market": "cn", "strategy": "dual_low", "max_results": 5},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["candidate_count"], 1)
        run_mock.assert_called_once()

    def test_install_can_run_before_enable(self) -> None:
        client = self._client(enabled=False)
        fake_module = SimpleNamespace(screen=MagicMock())

        with patch("api.v1.endpoints.alphasift.importlib.import_module", return_value=fake_module):
            resp = client.post("/api/v1/alphasift/install")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["already_installed"], True)

    def test_install_invokes_pip_when_enabled_and_missing(self) -> None:
        client = self._client(enabled=True)
        fake_module = SimpleNamespace(screen=MagicMock())
        completed = SimpleNamespace(returncode=0, stdout="installed", stderr="")

        with (
            patch("api.v1.endpoints.alphasift.subprocess.run", return_value=completed) as run_mock,
            patch(
                "api.v1.endpoints.alphasift.importlib.import_module",
                side_effect=[ModuleNotFoundError("No module named 'alphasift'"), fake_module],
            ),
        ):
            resp = client.post("/api/v1/alphasift/install")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["installed"], True)
        self.assertEqual(resp.json()["already_installed"], False)
        run_mock.assert_called_once()
        self.assertIn(DEFAULT_ALPHASIFT_TEST_SPEC, run_mock.call_args.args[0])

    def test_screen_calls_alphasift_package_when_enabled(self) -> None:
        client = self._client(enabled=True)
        fake_module = SimpleNamespace(
            screen=MagicMock(return_value=[{"code": "600519", "name": "Kweichow Moutai", "score": 88.5}])
        )

        with patch("api.v1.endpoints.alphasift.importlib.import_module", return_value=fake_module):
            resp = client.post(
                "/api/v1/alphasift/screen",
                json={"market": "cn", "strategy": "dual_low", "max_results": 5},
            )

        self.assertEqual(resp.status_code, 200)
        fake_module.screen.assert_called_once_with(
            "dual_low",
            market="cn",
            max_output=5,
            use_llm=False,
        )
        payload = resp.json()
        self.assertEqual(payload["candidate_count"], 1)
        self.assertEqual(payload["candidates"][0]["code"], "600519")


if __name__ == "__main__":
    unittest.main()

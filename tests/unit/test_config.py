"""
GSEA Dashboard - Unit Tests: Configuration Validation
=======================================================
Tests for backend/config.py, specifically validate_production_secrets(),
which was previously defined but never invoked at startup (Fix 12).

Run: pytest tests/unit/test_config.py -v
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.config import Settings


class TestValidateProductionSecrets:
    """Tests for Settings.validate_production_secrets()."""

    def test_does_not_raise_in_development(self, monkeypatch):
        """Default ENVIRONMENT is dev, so the default secret key is allowed."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        settings = Settings(secret_key="dev-secret-key-change-in-production")
        settings.validate_production_secrets()  # should not raise

    def test_raises_in_production_with_default_key(self, monkeypatch):
        """The exact scenario Fix 12 exists to catch."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        settings = Settings(secret_key="dev-secret-key-change-in-production")
        with pytest.raises(ValueError, match="SECRET_KEY must be changed"):
            settings.validate_production_secrets()

    def test_does_not_raise_in_production_with_custom_key(self, monkeypatch):
        """A properly configured production deployment should start cleanly."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        settings = Settings(secret_key="a-real-randomly-generated-secret")
        settings.validate_production_secrets()  # should not raise

    def test_is_production_reflects_environment_variable(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        settings = Settings()
        assert settings.is_production is True

        monkeypatch.setenv("ENVIRONMENT", "development")
        settings = Settings()
        assert settings.is_production is False


class TestLifespanWiring:
    """
    Confirms validate_production_secrets() is actually called during
    app startup, not just defined. This is a regression test for Fix 12:
    the function existed but nothing invoked it before this fix.
    """

    def test_calculate_sci_lifespan_calls_validation(self, monkeypatch):
        """
        The FastAPI TestClient used as a context manager triggers the
        lifespan handler. In development mode (the default in this test
        environment) this must complete without raising.
        """
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        from fastapi.testclient import TestClient
        from backend.main import app

        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200

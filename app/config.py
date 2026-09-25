"""Configuration objects selected by ``FLASK_ENV``.

Every setting has a working default so the application starts without a ``.env``
file, except :attr:`Config.SECRET_KEY` in production, which must be supplied.
"""

from __future__ import annotations

import os
from typing import Dict, Type

__all__ = ["Config", "DevelopmentConfig", "TestingConfig", "ProductionConfig", "get_config"]

#: Default connection string used when ``DATABASE_URL`` is not set.
DEFAULT_DATABASE_URL = "mysql+pymysql://root:password@localhost:3306/school_db"


def _as_bool(value: str | None, default: bool = False) -> bool:
    """Interpret an environment string as a boolean."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    """Interpret an environment string as an integer, falling back on default."""
    try:
        return int(value) if value is not None and value.strip() else default
    except ValueError:
        return default


class Config:
    """Settings shared by every environment."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        # MySQL closes idle connections after wait_timeout; recycling below that
        # avoids "MySQL server has gone away" on long-lived workers.
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
    WTF_CSRF_ENABLED = True

    #: Rows per page in the student list and the class result list.
    ITEMS_PER_PAGE = _as_int(os.environ.get("ITEMS_PER_PAGE"), 25)

    #: Percentage thresholds, highest first, used to award a letter grade.
    GRADE_BANDS = (
        (90.0, "A+"),
        (80.0, "A"),
        (70.0, "B"),
        (60.0, "C"),
        (50.0, "D"),
        (40.0, "E"),
    )

    #: Grade awarded below the lowest band.
    FAIL_GRADE = "F"

    SCHOOL_NAME = os.environ.get("SCHOOL_NAME", "Greenfield Public School")


class DevelopmentConfig(Config):
    """Local development: verbose errors, optional SQL echo."""

    DEBUG = True
    SQLALCHEMY_ECHO = _as_bool(os.environ.get("SQLALCHEMY_ECHO"), False)


class TestingConfig(Config):
    """Automated tests: in-memory SQLite and no CSRF tokens."""

    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    SQLALCHEMY_ENGINE_OPTIONS: Dict[str, object] = {}
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "testing-secret"


class ProductionConfig(Config):
    """Production: debugging off and a mandatory secret key."""

    DEBUG = False
    TESTING = False

    def __init__(self) -> None:
        if os.environ.get("SECRET_KEY") is None:
            raise RuntimeError("SECRET_KEY must be set in the environment when FLASK_ENV=production")


#: Environment name to configuration class.
CONFIGURATIONS: Dict[str, Type[Config]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None) -> Type[Config] | Config:
    """Return the configuration for ``name`` or for ``FLASK_ENV``.

    Args:
        name: Explicit environment name; falls back to ``FLASK_ENV`` and then
            to ``development``.

    Returns:
        A configuration class, or an instance when the class validates its
        environment on construction.
    """
    environment = (name or os.environ.get("FLASK_ENV") or "development").strip().lower()
    configuration = CONFIGURATIONS.get(environment, DevelopmentConfig)
    if configuration is ProductionConfig:
        return ProductionConfig()
    return configuration

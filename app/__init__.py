"""Application factory for the school student management system."""

from __future__ import annotations

import logging
import os
from logging.config import dictConfig
from typing import Any, Mapping, Optional

from flask import Flask, render_template
from sqlalchemy.exc import SQLAlchemyError

from .config import get_config
from .extensions import csrf, db, migrate

__all__ = ["create_app"]

__version__ = "1.0.0"

LOGGER = logging.getLogger(__name__)


def _configure_logging(level_name: str) -> None:
    """Configure application-wide logging before the app object is built."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"level": level, "handlers": ["console"]},
        }
    )


def create_app(config_name: Optional[str] = None, overrides: Optional[Mapping[str, Any]] = None) -> Flask:
    """Build and configure a Flask application.

    Args:
        config_name: ``development``, ``testing`` or ``production``.  Falls back
            to ``FLASK_ENV`` and then to ``development``.
        overrides: Extra configuration applied last, which tests use to point
            the application at a temporary database.

    Returns:
        The configured application, with extensions, blueprints, error handlers
        and CLI commands registered.
    """
    _configure_logging(os.environ.get("LOG_LEVEL", "INFO"))

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(get_config(config_name))
    if overrides:
        app.config.update(overrides)

    db.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(app.root_path, "..", "migrations"))
    csrf.init_app(app)

    # Importing the models registers every table on db.metadata.
    from . import models  # noqa: F401  (imported for the side effect)

    _register_blueprints(app)
    _register_error_handlers(app)
    _register_template_helpers(app)
    _register_cli(app)

    app.logger.info(
        "Application ready (env=%s, database=%s)",
        config_name or os.environ.get("FLASK_ENV", "development"),
        _safe_database_label(app.config.get("SQLALCHEMY_DATABASE_URI", "")),
    )
    return app


def _safe_database_label(uri: str) -> str:
    """Return the database URI with any password removed, for logging."""
    if "@" not in uri:
        return uri
    scheme, _, remainder = uri.partition("://")
    credentials, _, host = remainder.partition("@")
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


def _register_blueprints(app: Flask) -> None:
    """Attach every blueprint to the application."""
    from .blueprints import all_blueprints

    for blueprint in all_blueprints():
        app.register_blueprint(blueprint)


def _register_error_handlers(app: Flask) -> None:
    """Render friendly pages for the errors a user can actually hit."""

    @app.errorhandler(404)
    def not_found(error: Exception):  # type: ignore[no-untyped-def]
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error: Exception):  # type: ignore[no-untyped-def]
        app.logger.exception("Unhandled application error: %s", error)
        return render_template("errors/500.html"), 500

    @app.errorhandler(SQLAlchemyError)
    def database_error(error: SQLAlchemyError):  # type: ignore[no-untyped-def]
        db.session.rollback()
        app.logger.exception("Database error, session rolled back: %s", error)
        return render_template("errors/500.html"), 500


def _register_template_helpers(app: Flask) -> None:
    """Expose a few helpers to Jinja templates."""
    from datetime import date

    @app.context_processor
    def inject_globals() -> dict:
        return {
            "school_name": app.config.get("SCHOOL_NAME", "School"),
            "today": date.today(),
            "app_version": __version__,
        }

    @app.template_filter("percent")
    def percent(value: Optional[float], digits: int = 2) -> str:
        """Render a number as a percentage, or ``-`` when it is missing."""
        if value is None:
            return "-"
        return f"{float(value):.{digits}f}%"


def _register_cli(app: Flask) -> None:
    """Register ``flask init-db`` and ``flask db-stats``."""
    import click

    @app.cli.command("init-db")
    @click.option("--drop", is_flag=True, help="Drop every table before creating it again.")
    def init_db(drop: bool) -> None:
        """Create the database tables from the models."""
        if drop:
            click.echo("Dropping all tables...")
            db.drop_all()
        db.create_all()
        click.echo("Tables created.")

    @app.cli.command("db-stats")
    def db_stats() -> None:
        """Print a row count for each table."""
        from .models import AcademicYear, ClassSubject, Exam, Mark, SchoolClass, Student, Subject

        for model in (AcademicYear, SchoolClass, Subject, ClassSubject, Exam, Student, Mark):
            click.echo(f"{model.__tablename__:>16}: {db.session.query(model).count()}")

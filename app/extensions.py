"""Flask extension instances and shared model helpers.

Extensions are created here without an application so that
:func:`app.create_app` can bind them to whichever application instance it
builds.  Keeping them in their own module also stops the models, the blueprints
and the factory from importing each other in a circle.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

__all__ = ["csrf", "db", "migrate", "utcnow", "TimestampMixin"]

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()


def utcnow() -> datetime:
    """Return the current UTC time as a naive ``datetime``.

    MySQL ``DATETIME`` columns do not store a timezone, so the value is made
    naive here rather than letting the driver drop the offset silently.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns to a model."""

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

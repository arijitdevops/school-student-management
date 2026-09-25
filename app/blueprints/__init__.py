"""Blueprint registry.

:func:`all_blueprints` is the single place that lists the blueprints, so
:func:`app.create_app` never has to import them one by one.
"""

from __future__ import annotations

from typing import List

from flask import Blueprint

from .main import bp as main_bp
from .marks import bp as marks_bp
from .reports import bp as reports_bp
from .students import bp as students_bp
from .subjects import bp as subjects_bp

__all__ = ["all_blueprints"]


def all_blueprints() -> List[Blueprint]:
    """Return every blueprint in registration order."""
    return [main_bp, students_bp, subjects_bp, marks_bp, reports_bp]

"""Dashboard and service endpoints."""

from __future__ import annotations

import logging

from flask import Blueprint, render_template
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import AcademicYear, Exam, Mark, SchoolClass, Student, Subject

LOGGER = logging.getLogger(__name__)

bp = Blueprint("main", __name__)


@bp.route("/")
def index() -> str:
    """Render the dashboard with headline counts and per-class strength."""
    academic_year = AcademicYear.current()
    totals = {
        "students": db.session.scalar(
            select(func.count()).select_from(Student).where(Student.is_active.is_(True))
        )
        or 0,
        "inactive_students": db.session.scalar(
            select(func.count()).select_from(Student).where(Student.is_active.is_(False))
        )
        or 0,
        "classes": db.session.scalar(select(func.count()).select_from(SchoolClass)) or 0,
        "subjects": db.session.scalar(select(func.count()).select_from(Subject)) or 0,
        "exams": db.session.scalar(select(func.count()).select_from(Exam)) or 0,
        "marks": db.session.scalar(select(func.count()).select_from(Mark)) or 0,
    }

    strength_rows = db.session.execute(
        select(SchoolClass, func.count(Student.id))
        .outerjoin(Student, (Student.school_class_id == SchoolClass.id) & (Student.is_active.is_(True)))
        .group_by(SchoolClass.id)
        .order_by(SchoolClass.numeral)
    ).all()

    return render_template(
        "index.html",
        academic_year=academic_year,
        totals=totals,
        strength_rows=strength_rows,
    )


@bp.route("/healthz")
def healthz() -> tuple[dict, int]:
    """Report whether the application can reach its database."""
    try:
        db.session.execute(select(1))
    except SQLAlchemyError as error:
        LOGGER.error("Health check failed: %s", error)
        return {"status": "error", "database": "unreachable"}, 503
    return {"status": "ok", "database": "reachable"}, 200

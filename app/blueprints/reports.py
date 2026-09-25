"""Report cards, class result lists and the CSV export."""

from __future__ import annotations

import csv
import io
import logging
from typing import List, Optional, Sequence, Tuple

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import select

from ..extensions import db
from ..models import AcademicYear, ClassSubject, Exam, Mark, SchoolClass, Section, Student
from ..services.results import (
    GradeScale,
    StudentResult,
    build_class_results,
    build_student_result,
    class_summary,
    index_marks,
    result_csv_header,
    result_csv_rows,
)

LOGGER = logging.getLogger(__name__)

bp = Blueprint("reports", __name__, url_prefix="/reports")


def _grade_scale() -> GradeScale:
    """Build the grade scale from the application configuration."""
    bands = tuple((float(minimum), grade) for minimum, grade in current_app.config["GRADE_BANDS"])
    return GradeScale(bands=bands, fail_grade=current_app.config["FAIL_GRADE"])


def _exams() -> List[Exam]:
    """Return the exams of the current academic year in sequence order."""
    year = AcademicYear.current()
    statement = select(Exam).order_by(Exam.sequence)
    if year is not None:
        statement = statement.where(Exam.academic_year_id == year.id)
    return list(db.session.scalars(statement).all())


def _class_subjects(school_class_id: int) -> List[ClassSubject]:
    """Return a class's subjects, ordered by subject name."""
    return list(
        db.session.scalars(
            select(ClassSubject)
            .where(ClassSubject.school_class_id == school_class_id)
            .join(ClassSubject.subject)
            .order_by(ClassSubject.subject_id)
        ).all()
    )


def _class_students(school_class_id: int, section_id: Optional[int]) -> List[Student]:
    """Return the active students of a class, optionally one section only."""
    statement = (
        select(Student)
        .join(Student.section)
        .where(Student.school_class_id == school_class_id, Student.is_active.is_(True))
        .order_by(Section.name, Student.roll_number)
    )
    if section_id:
        statement = statement.where(Student.section_id == section_id)
    return list(db.session.scalars(statement).all())


def _class_marks(student_ids: Sequence[int]) -> List[Mark]:
    """Return every mark belonging to the given students."""
    if not student_ids:
        return []
    return list(db.session.scalars(select(Mark).where(Mark.student_id.in_(list(student_ids)))).all())


def _ranked_class(
    school_class_id: int, section_id: Optional[int]
) -> Tuple[List[StudentResult], List[ClassSubject], List[Exam]]:
    """Build the ranked result list for a class or section."""
    class_subjects = _class_subjects(school_class_id)
    exams = _exams()
    students = _class_students(school_class_id, section_id)
    marks = _class_marks([student.id for student in students])
    results = build_class_results(students, class_subjects, exams, marks, _grade_scale())
    return results, class_subjects, exams


@bp.route("/")
def index() -> str:
    """Landing page listing the classes a report can be produced for."""
    classes = db.session.scalars(select(SchoolClass).order_by(SchoolClass.numeral)).all()
    return render_template("reports/index.html", classes=classes, exams=_exams())


@bp.route("/student/<int:student_id>")
def report_card(student_id: int) -> str:
    """Show one student's report card, including their rank in the class."""
    student = db.get_or_404(Student, student_id)
    class_subjects = _class_subjects(student.school_class_id)
    exams = _exams()
    marks_index = index_marks(db.session.scalars(select(Mark).where(Mark.student_id == student.id)).all())
    result = build_student_result(student, class_subjects, exams, marks_index, _grade_scale())

    class_results, _, _ = _ranked_class(student.school_class_id, None)
    ranked = next((item for item in class_results if item.student_id == student.id), None)
    if ranked is not None:
        result.rank = ranked.rank

    return render_template(
        "reports/report_card.html",
        student=student,
        result=result,
        exams=exams,
        academic_year=AcademicYear.current(),
        class_size=len(class_results),
        printable=False,
    )


@bp.route("/student/<int:student_id>/print")
def report_card_print(student_id: int) -> str:
    """Render the same report card using the print-optimised template."""
    student = db.get_or_404(Student, student_id)
    class_subjects = _class_subjects(student.school_class_id)
    exams = _exams()
    marks_index = index_marks(db.session.scalars(select(Mark).where(Mark.student_id == student.id)).all())
    result = build_student_result(student, class_subjects, exams, marks_index, _grade_scale())
    class_results, _, _ = _ranked_class(student.school_class_id, None)
    ranked = next((item for item in class_results if item.student_id == student.id), None)
    if ranked is not None:
        result.rank = ranked.rank
    return render_template(
        "reports/report_card_print.html",
        student=student,
        result=result,
        exams=exams,
        academic_year=AcademicYear.current(),
        class_size=len(class_results),
    )


@bp.route("/class/<int:class_id>")
def class_result(class_id: int) -> str:
    """Show every student in a class ranked by aggregate percentage."""
    school_class = db.get_or_404(SchoolClass, class_id)
    section_id = request.args.get("section_id", type=int)
    results, class_subjects, exams = _ranked_class(class_id, section_id)
    return render_template(
        "reports/class_result.html",
        school_class=school_class,
        section_id=section_id,
        results=results,
        class_subjects=class_subjects,
        exams=exams,
        summary=class_summary(results),
        academic_year=AcademicYear.current(),
    )


@bp.route("/class/<int:class_id>/export.csv")
def class_result_csv(class_id: int) -> Response:
    """Download the class result list as CSV."""
    school_class = db.get_or_404(SchoolClass, class_id)
    section_id = request.args.get("section_id", type=int)
    results, class_subjects, _ = _ranked_class(class_id, section_id)

    if not results:
        flash("There are no students to export for that class.", "info")
        return redirect(url_for("reports.class_result", class_id=class_id))

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(result_csv_header(class_subjects))
    writer.writerows(result_csv_rows(results, class_subjects))

    section = db.session.get(Section, section_id) if section_id else None
    suffix = f"-{section.name}" if section is not None else ""
    filename = f"result-class-{school_class.numeral}{suffix}.csv"
    LOGGER.info("Exported %d result rows for %s", len(results), filename)

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

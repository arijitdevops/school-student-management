"""Student records: listing, search, creation, editing, soft and permanent deletion."""

from __future__ import annotations

import logging

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import delete as sql_delete
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.wrappers import Response

from ..extensions import db
from ..forms import StudentFilterForm, StudentForm
from ..models import AcademicYear, Exam, Mark, SchoolClass, Section, Student

LOGGER = logging.getLogger(__name__)

bp = Blueprint("students", __name__, url_prefix="/students")


def _apply_form(form: StudentForm, student: Student) -> None:
    """Copy the validated form values onto a student instance."""
    student.admission_number = form.admission_number.data.strip()
    student.full_name = form.full_name.data.strip()
    student.school_class_id = form.school_class_id.data
    student.section_id = form.section_id.data
    student.roll_number = form.roll_number.data
    student.date_of_birth = form.date_of_birth.data
    student.gender = form.gender.data
    student.blood_group = form.blood_group.data or None
    student.guardian_name = form.guardian_name.data.strip()
    student.guardian_relation = form.guardian_relation.data
    student.guardian_phone = form.guardian_phone.data.strip()
    student.email = (form.email.data or "").strip() or None
    student.address = (form.address.data or "").strip() or None
    student.admission_date = form.admission_date.data
    student.is_active = bool(form.is_active.data)


@bp.route("/")
def list_students() -> str:
    """List students with a text search, class and section filters and paging."""
    form = StudentFilterForm(formdata=request.args)
    statement = (
        select(Student)
        .join(Student.school_class)
        .join(Student.section)
        .order_by(SchoolClass.numeral, Section.name, Student.roll_number)
    )

    search = (form.q.data or "").strip()
    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            or_(
                Student.full_name.ilike(pattern),
                Student.admission_number.ilike(pattern),
                Student.guardian_name.ilike(pattern),
            )
        )

    if form.school_class_id.data:
        statement = statement.where(Student.school_class_id == form.school_class_id.data)
    if form.section_id.data:
        statement = statement.where(Student.section_id == form.section_id.data)

    status = form.status.data or "active"
    if status == "active":
        statement = statement.where(Student.is_active.is_(True))
    elif status == "inactive":
        statement = statement.where(Student.is_active.is_(False))

    page = request.args.get("page", default=1, type=int)
    pagination = db.paginate(
        statement,
        page=max(page, 1),
        per_page=current_app.config["ITEMS_PER_PAGE"],
        error_out=False,
    )
    return render_template("students/list.html", form=form, pagination=pagination, search=search)


@bp.route("/<int:student_id>")
def detail(student_id: int) -> str:
    """Show one student together with their recorded marks per exam."""
    student = db.get_or_404(Student, student_id)
    exams = db.session.scalars(select(Exam).order_by(Exam.sequence)).all()
    marks = db.session.scalars(select(Mark).where(Mark.student_id == student.id)).all()
    marks_by_exam: dict[int, list[Mark]] = {exam.id: [] for exam in exams}
    for mark in marks:
        marks_by_exam.setdefault(mark.exam_id, []).append(mark)
    return render_template(
        "students/detail.html",
        student=student,
        exams=exams,
        marks_by_exam=marks_by_exam,
        academic_year=AcademicYear.current(),
    )


@bp.route("/new", methods=["GET", "POST"])
def create() -> str | Response:
    """Add a student."""
    form = StudentForm()
    if form.validate_on_submit():
        student = Student()
        _apply_form(form, student)
        db.session.add(student)
        try:
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            LOGGER.warning("Rejected duplicate student: %s", error.orig)
            flash("That admission number or roll number is already taken.", "danger")
        except SQLAlchemyError as error:
            db.session.rollback()
            LOGGER.exception("Could not save the student: %s", error)
            flash("The student could not be saved. Please try again.", "danger")
        else:
            flash(f"{student.full_name} was added.", "success")
            return redirect(url_for("students.detail", student_id=student.id))
    return render_template("students/form.html", form=form, student=None)


@bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
def edit(student_id: int) -> str | Response:
    """Edit an existing student."""
    student = db.get_or_404(Student, student_id)
    form = StudentForm(obj=student, student_id=student.id)
    if form.validate_on_submit():
        _apply_form(form, student)
        try:
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            LOGGER.warning("Rejected duplicate student on edit: %s", error.orig)
            flash("That admission number or roll number is already taken.", "danger")
        except SQLAlchemyError as error:
            db.session.rollback()
            LOGGER.exception("Could not update the student: %s", error)
            flash("The changes could not be saved. Please try again.", "danger")
        else:
            flash(f"{student.full_name} was updated.", "success")
            return redirect(url_for("students.detail", student_id=student.id))
    return render_template("students/form.html", form=form, student=student)


@bp.route("/<int:student_id>/deactivate", methods=["POST"])
def deactivate(student_id: int) -> Response:
    """Soft-delete a student, keeping their marks and report cards."""
    student = db.get_or_404(Student, student_id)
    student.deactivate()
    try:
        db.session.commit()
    except SQLAlchemyError as error:
        db.session.rollback()
        LOGGER.exception("Could not deactivate student %s: %s", student_id, error)
        flash("The student could not be removed from the roll.", "danger")
    else:
        flash(f"{student.full_name} was marked as left. The record is kept.", "warning")
    return redirect(request.referrer or url_for("students.list_students"))


@bp.route("/<int:student_id>/restore", methods=["POST"])
def restore(student_id: int) -> Response:
    """Undo a soft delete."""
    student = db.get_or_404(Student, student_id)
    student.restore()
    try:
        db.session.commit()
    except SQLAlchemyError as error:
        db.session.rollback()
        LOGGER.exception("Could not restore student %s: %s", student_id, error)
        flash("The student could not be restored.", "danger")
    else:
        flash(f"{student.full_name} was restored to the roll.", "success")
    return redirect(request.referrer or url_for("students.detail", student_id=student_id))


@bp.route("/<int:student_id>/delete", methods=["POST"])
def delete(student_id: int) -> Response:
    """Permanently delete a student and every mark recorded for them."""
    student = db.get_or_404(Student, student_id)
    name = student.full_name
    try:
        removed_marks = db.session.execute(sql_delete(Mark).where(Mark.student_id == student.id)).rowcount
        db.session.delete(student)
        db.session.commit()
    except SQLAlchemyError as error:
        db.session.rollback()
        LOGGER.exception("Could not delete student %s: %s", student_id, error)
        flash("The student could not be deleted.", "danger")
        return redirect(url_for("students.detail", student_id=student_id))
    flash(f"{name} and {removed_marks} mark(s) were permanently deleted.", "success")
    return redirect(url_for("students.list_students"))

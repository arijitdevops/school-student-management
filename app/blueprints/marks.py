"""Mark entry: a bulk grid per class-subject-exam and a per-student editor."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.wrappers import Response

from ..extensions import db
from ..forms import BulkMarkForm, MarkEntryFilterForm, parse_mark_inputs
from ..models import ClassSubject, Exam, Mark, Section, Student

LOGGER = logging.getLogger(__name__)

bp = Blueprint("marks", __name__, url_prefix="/marks")


def _students_for(school_class_id: int, section_id: Optional[int]) -> List[Student]:
    """Return the active students of a class, optionally narrowed to one section."""
    statement = (
        select(Student)
        .join(Student.section)
        .where(Student.school_class_id == school_class_id, Student.is_active.is_(True))
        .order_by(Section.name, Student.roll_number)
    )
    if section_id:
        statement = statement.where(Student.section_id == section_id)
    return list(db.session.scalars(statement).all())


def _existing_marks(student_ids: Sequence[int], class_subject_id: int, exam_id: int) -> Dict[int, Mark]:
    """Return the marks already recorded for a grid, keyed by student id."""
    if not student_ids:
        return {}
    rows = db.session.scalars(
        select(Mark).where(
            Mark.class_subject_id == class_subject_id,
            Mark.exam_id == exam_id,
            Mark.student_id.in_(list(student_ids)),
        )
    ).all()
    return {mark.student_id: mark for mark in rows}


@bp.route("/")
def index() -> str | Response:
    """Choose the class, section, subject and exam to work on."""
    form = MarkEntryFilterForm(formdata=request.args)
    if form.school_class_id.data:
        form.set_subject_choices(form.school_class_id.data)
    if request.args.get("submit") and form.validate():
        return redirect(
            url_for(
                "marks.entry",
                class_subject_id=form.class_subject_id.data,
                exam_id=form.exam_id.data,
                section_id=form.section_id.data or None,
            )
        )
    return render_template("marks/select.html", form=form)


@bp.route("/entry", methods=["GET", "POST"])
def entry() -> str | Response:
    """Show and save the bulk entry grid for one class-subject and exam."""
    class_subject_id = request.args.get("class_subject_id", type=int)
    exam_id = request.args.get("exam_id", type=int)
    section_id = request.args.get("section_id", type=int)

    if not class_subject_id or not exam_id:
        flash("Choose a class, subject and exam first.", "info")
        return redirect(url_for("marks.index"))

    class_subject = db.get_or_404(ClassSubject, class_subject_id)
    exam = db.get_or_404(Exam, exam_id)
    students = _students_for(class_subject.school_class_id, section_id)
    existing = _existing_marks([student.id for student in students], class_subject_id, exam_id)
    form = BulkMarkForm()

    if form.validate_on_submit():
        keys = [student.id for student in students]
        labels = {student.id: f"Roll {student.roll_number} ({student.full_name})" for student in students}
        ceilings = {student.id: class_subject.max_marks for student in students}
        parsed, errors = parse_mark_inputs(request.form, keys, ceilings, labels)

        for problem in errors:
            flash(problem, "danger")

        saved = cleared = 0
        for cell in parsed:
            mark = existing.get(cell.key)
            if cell.cleared:
                if mark is not None:
                    db.session.delete(mark)
                    cleared += 1
                continue
            if mark is None:
                mark = Mark(student_id=cell.key, class_subject_id=class_subject_id, exam_id=exam_id)
                db.session.add(mark)
            mark.set_score(cell.value, class_subject.max_marks)
            saved += 1

        try:
            db.session.commit()
        except SQLAlchemyError as error:
            db.session.rollback()
            LOGGER.exception("Could not save the mark grid: %s", error)
            flash("The marks could not be saved. Nothing was changed.", "danger")
        else:
            message = f"Saved {saved} mark(s)."
            if cleared:
                message += f" Cleared {cleared}."
            flash(message, "success" if not errors else "warning")
            return redirect(
                url_for(
                    "marks.entry",
                    class_subject_id=class_subject_id,
                    exam_id=exam_id,
                    section_id=section_id or None,
                )
            )
        existing = _existing_marks([student.id for student in students], class_subject_id, exam_id)

    sections = db.session.scalars(
        select(Section).where(Section.school_class_id == class_subject.school_class_id).order_by(Section.name)
    ).all()
    return render_template(
        "marks/entry.html",
        form=form,
        class_subject=class_subject,
        exam=exam,
        students=students,
        existing=existing,
        sections=sections,
        section_id=section_id,
    )


@bp.route("/student/<int:student_id>", methods=["GET", "POST"])
def student_marks(student_id: int) -> str | Response:
    """Edit every subject mark for one student in one exam."""
    student = db.get_or_404(Student, student_id)
    exams = list(db.session.scalars(select(Exam).order_by(Exam.sequence)).all())
    if not exams:
        flash("No exams have been created yet.", "info")
        return redirect(url_for("students.detail", student_id=student.id))

    exam_id = request.args.get("exam_id", type=int) or exams[0].id
    exam = db.get_or_404(Exam, exam_id)
    class_subjects = list(
        db.session.scalars(
            select(ClassSubject)
            .where(ClassSubject.school_class_id == student.school_class_id)
            .join(ClassSubject.subject)
            .order_by(ClassSubject.subject_id)
        ).all()
    )
    existing = {
        mark.class_subject_id: mark
        for mark in db.session.scalars(
            select(Mark).where(Mark.student_id == student.id, Mark.exam_id == exam.id)
        ).all()
    }
    form = BulkMarkForm()

    if form.validate_on_submit():
        keys = [class_subject.id for class_subject in class_subjects]
        labels = {class_subject.id: class_subject.subject.name for class_subject in class_subjects}
        ceilings = {class_subject.id: class_subject.max_marks for class_subject in class_subjects}
        parsed, errors = parse_mark_inputs(request.form, keys, ceilings, labels)
        for problem in errors:
            flash(problem, "danger")

        ceiling_by_key = ceilings
        for cell in parsed:
            mark = existing.get(cell.key)
            if cell.cleared:
                if mark is not None:
                    db.session.delete(mark)
                continue
            if mark is None:
                mark = Mark(student_id=student.id, class_subject_id=cell.key, exam_id=exam.id)
                db.session.add(mark)
            mark.set_score(cell.value, ceiling_by_key[cell.key])

        try:
            db.session.commit()
        except SQLAlchemyError as error:
            db.session.rollback()
            LOGGER.exception("Could not save marks for student %s: %s", student_id, error)
            flash("The marks could not be saved. Nothing was changed.", "danger")
        else:
            flash(f"Marks for {exam.name} saved.", "success" if not errors else "warning")
            return redirect(url_for("marks.student_marks", student_id=student.id, exam_id=exam.id))

    return render_template(
        "marks/student.html",
        form=form,
        student=student,
        exam=exam,
        exams=exams,
        class_subjects=class_subjects,
        existing=existing,
    )

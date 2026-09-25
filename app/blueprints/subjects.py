"""Subjects and the class-subject assignments that carry the mark scheme."""

from __future__ import annotations

import logging

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.wrappers import Response

from ..extensions import db
from ..forms import ClassSubjectForm, SubjectForm
from ..models import ClassSubject, Mark, SchoolClass, Subject

LOGGER = logging.getLogger(__name__)

bp = Blueprint("subjects", __name__, url_prefix="/subjects")


@bp.route("/")
def list_subjects() -> str:
    """List every subject with the classes it is assigned to."""
    subjects = db.session.scalars(select(Subject).order_by(Subject.name)).all()
    assignments = db.session.scalars(
        select(ClassSubject).join(ClassSubject.school_class).order_by(SchoolClass.numeral)
    ).all()
    by_subject: dict[int, list[ClassSubject]] = {}
    for assignment in assignments:
        by_subject.setdefault(assignment.subject_id, []).append(assignment)
    return render_template("subjects/list.html", subjects=subjects, by_subject=by_subject)


@bp.route("/new", methods=["GET", "POST"])
def create() -> str | Response:
    """Add a subject."""
    form = SubjectForm()
    if form.validate_on_submit():
        subject = Subject(
            code=form.code.data,
            name=form.name.data.strip(),
            description=(form.description.data or "").strip() or None,
            is_active=bool(form.is_active.data),
        )
        db.session.add(subject)
        try:
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            LOGGER.warning("Rejected duplicate subject: %s", error.orig)
            flash("That subject code or name already exists.", "danger")
        except SQLAlchemyError as error:
            db.session.rollback()
            LOGGER.exception("Could not save the subject: %s", error)
            flash("The subject could not be saved.", "danger")
        else:
            flash(f"{subject.name} was added.", "success")
            return redirect(url_for("subjects.list_subjects"))
    return render_template("subjects/form.html", form=form, subject=None)


@bp.route("/<int:subject_id>/edit", methods=["GET", "POST"])
def edit(subject_id: int) -> str | Response:
    """Edit a subject."""
    subject = db.get_or_404(Subject, subject_id)
    form = SubjectForm(obj=subject, subject_id=subject.id)
    if form.validate_on_submit():
        subject.code = form.code.data
        subject.name = form.name.data.strip()
        subject.description = (form.description.data or "").strip() or None
        subject.is_active = bool(form.is_active.data)
        try:
            db.session.commit()
        except SQLAlchemyError as error:
            db.session.rollback()
            LOGGER.exception("Could not update the subject: %s", error)
            flash("The changes could not be saved.", "danger")
        else:
            flash(f"{subject.name} was updated.", "success")
            return redirect(url_for("subjects.list_subjects"))
    return render_template("subjects/form.html", form=form, subject=subject)


@bp.route("/<int:subject_id>/delete", methods=["POST"])
def delete(subject_id: int) -> Response:
    """Delete a subject together with its class assignments and their marks.

    The confirmation dialogue on the subjects page warns that marks go too.
    """
    subject = db.get_or_404(Subject, subject_id)
    name = subject.name
    assignment_ids = [assignment.id for assignment in subject.class_subjects]
    try:
        removed_marks = 0
        if assignment_ids:
            removed_marks = db.session.execute(
                sql_delete(Mark).where(Mark.class_subject_id.in_(assignment_ids))
            ).rowcount
        db.session.delete(subject)
        db.session.commit()
    except SQLAlchemyError as error:
        db.session.rollback()
        LOGGER.exception("Could not delete subject %s: %s", subject_id, error)
        flash("The subject could not be removed.", "danger")
    else:
        flash(
            f"{name} was removed, with {len(assignment_ids)} class assignment(s) "
            f"and {removed_marks} mark(s).",
            "success",
        )
    return redirect(url_for("subjects.list_subjects"))


@bp.route("/assign", methods=["GET", "POST"])
def assign() -> str | Response:
    """Assign a subject to a class and set its mark scheme."""
    form = ClassSubjectForm()
    if form.validate_on_submit():
        assignment = ClassSubject(
            school_class_id=form.school_class_id.data,
            subject_id=form.subject_id.data,
            max_marks=form.max_marks.data,
            pass_marks=form.pass_marks.data,
        )
        db.session.add(assignment)
        try:
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            LOGGER.warning("Rejected duplicate assignment: %s", error.orig)
            flash("That subject is already assigned to the class.", "danger")
        except SQLAlchemyError as error:
            db.session.rollback()
            LOGGER.exception("Could not assign the subject: %s", error)
            flash("The assignment could not be saved.", "danger")
        else:
            flash("Subject assigned to the class.", "success")
            return redirect(url_for("subjects.assign"))

    assignments = db.session.scalars(
        select(ClassSubject).join(ClassSubject.school_class).order_by(SchoolClass.numeral)
    ).all()
    by_class: dict[int, list[ClassSubject]] = {}
    for assignment in assignments:
        by_class.setdefault(assignment.school_class_id, []).append(assignment)
    classes = db.session.scalars(select(SchoolClass).order_by(SchoolClass.numeral)).all()
    return render_template("subjects/assign.html", form=form, classes=classes, by_class=by_class)


@bp.route("/assignments/<int:assignment_id>/remove", methods=["POST"])
def remove_assignment(assignment_id: int) -> Response:
    """Unassign a subject from a class, deleting the marks recorded against it."""
    assignment = db.get_or_404(ClassSubject, assignment_id)
    label = f"{assignment.subject.name} in {assignment.school_class.name}"
    try:
        removed_marks = db.session.execute(
            sql_delete(Mark).where(Mark.class_subject_id == assignment.id)
        ).rowcount
        db.session.delete(assignment)
        db.session.commit()
    except SQLAlchemyError as error:
        db.session.rollback()
        LOGGER.exception("Could not remove assignment %s: %s", assignment_id, error)
        flash("The assignment could not be removed.", "danger")
    else:
        flash(f"Removed {label} and {removed_marks} mark(s).", "success")
    return redirect(request.referrer or url_for("subjects.assign"))

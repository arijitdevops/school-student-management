"""Forms and parsing helpers for mark entry."""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField
from wtforms.validators import DataRequired
from wtforms.validators import Optional as OptionalValidator

from ..models import ClassSubject, Exam, SchoolClass, Section, Subject

__all__ = ["MarkEntryFilterForm", "BulkMarkForm", "ParsedMark", "parse_mark_inputs"]


class MarkEntryFilterForm(FlaskForm):
    """Chooses which grid of marks to edit.

    Submitted with ``GET`` so the resulting page can be bookmarked, which is why
    CSRF protection is turned off for this form only.
    """

    class Meta:
        csrf = False

    school_class_id = SelectField("Class", coerce=int, validators=[DataRequired()])
    section_id = SelectField("Section", coerce=int, validators=[OptionalValidator()])
    class_subject_id = SelectField("Subject", coerce=int, validators=[DataRequired()])
    exam_id = SelectField("Exam", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Open grid")

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.school_class_id.choices = [
            (school_class.id, school_class.name)
            for school_class in SchoolClass.query.order_by(SchoolClass.numeral).all()
        ]
        self.section_id.choices = [(0, "All sections")] + [
            (section.id, section.label)
            for section in Section.query.join(SchoolClass).order_by(SchoolClass.numeral, Section.name).all()
        ]
        self.exam_id.choices = [(exam.id, exam.name) for exam in Exam.query.order_by(Exam.sequence).all()]
        self.set_subject_choices(self.school_class_id.data)

    def set_subject_choices(self, school_class_id: Optional[int]) -> None:
        """Limit the subject list to the subjects the chosen class studies."""
        query = ClassSubject.query.join(Subject).order_by(Subject.name)
        if school_class_id:
            query = query.filter(ClassSubject.school_class_id == school_class_id)
        self.class_subject_id.choices = [
            (class_subject.id, class_subject.subject.name) for class_subject in query.all()
        ]


class BulkMarkForm(FlaskForm):
    """Carries nothing but the CSRF token for the bulk entry grid.

    The grid itself has one input per student, named ``mark-<student id>``, with
    an optional ``absent-<student id>`` checkbox.  Those fields are read with
    :func:`parse_mark_inputs` rather than being declared here, because the row
    count changes with every class.
    """

    submit = SubmitField("Save marks")


class ParsedMark:
    """One parsed grid cell.

    Attributes:
        key: The identifier the input was named after (a student id in the bulk
            grid, a class-subject id on the per-student page).
        value: The score, or ``None`` when the student was absent.
        is_absent: Whether the absent box was ticked.
        cleared: Whether the cell was left empty, meaning "no mark recorded".
    """

    __slots__ = ("key", "value", "is_absent", "cleared")

    def __init__(self, key: int, value: Optional[float], is_absent: bool, cleared: bool) -> None:
        self.key = key
        self.value = value
        self.is_absent = is_absent
        self.cleared = cleared

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ParsedMark(key={self.key}, value={self.value}, is_absent={self.is_absent})"


def parse_mark_inputs(
    form_data: Mapping[str, str],
    keys: Iterable[int],
    max_marks: Mapping[int, int],
    labels: Optional[Mapping[int, str]] = None,
) -> Tuple[List[ParsedMark], List[str]]:
    """Read and validate the mark inputs of a submitted grid.

    Args:
        form_data: ``request.form``.
        keys: The identifiers whose inputs to look for.
        max_marks: Maximum marks per key, used to bound each value.
        labels: Optional display names per key, used in the error messages.

    Returns:
        A tuple of the parsed cells and a list of human readable errors.  Cells
        that failed validation are left out of the parsed list, so a caller can
        still save the valid rows if it chooses to.
    """
    parsed: List[ParsedMark] = []
    errors: List[str] = []
    label_lookup: Dict[int, str] = dict(labels or {})

    for key in keys:
        raw = (form_data.get(f"mark-{key}") or "").strip()
        is_absent = form_data.get(f"absent-{key}") in {"on", "1", "true", "yes"}
        label = label_lookup.get(key, str(key))

        if is_absent:
            parsed.append(ParsedMark(key=key, value=None, is_absent=True, cleared=False))
            continue

        if raw == "":
            parsed.append(ParsedMark(key=key, value=None, is_absent=False, cleared=True))
            continue

        try:
            value = float(raw)
        except ValueError:
            errors.append(f"{label}: '{raw}' is not a number.")
            continue

        ceiling = float(max_marks.get(key, 100))
        if value < 0 or value > ceiling:
            errors.append(f"{label}: marks must be between 0 and {ceiling:g}.")
            continue

        parsed.append(ParsedMark(key=key, value=value, is_absent=False, cleared=False))

    return parsed, errors

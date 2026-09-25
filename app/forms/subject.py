"""Forms for subjects and for assigning subjects to classes."""

from __future__ import annotations

from typing import Optional

from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Regexp, ValidationError
from wtforms.validators import Optional as OptionalValidator

from ..models import ClassSubject, SchoolClass, Subject

__all__ = ["SubjectForm", "ClassSubjectForm"]


class SubjectForm(FlaskForm):
    """Create or edit a subject.

    Args:
        subject_id: Primary key being edited, so uniqueness checks skip it.
    """

    code = StringField(
        "Code",
        # Codes are stored upper case, so normalise before the validators run.
        filters=[lambda value: value.strip().upper() if isinstance(value, str) else value],
        validators=[
            DataRequired(message="A subject code is required."),
            Length(min=2, max=10),
            Regexp(r"^[A-Z0-9]+$", message="Use letters and digits only."),
        ],
    )
    name = StringField(
        "Name", validators=[DataRequired(message="A subject name is required."), Length(min=2, max=60)]
    )
    description = TextAreaField("Description", validators=[OptionalValidator(), Length(max=255)])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save subject")

    def __init__(self, *args: object, subject_id: Optional[int] = None, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.subject_id = subject_id

    def validate_code(self, field: StringField) -> None:
        """Reject a code another subject already uses."""
        query = Subject.query.filter(Subject.code == field.data)
        if self.subject_id is not None:
            query = query.filter(Subject.id != self.subject_id)
        if query.first() is not None:
            raise ValidationError("Another subject already uses this code.")

    def validate_name(self, field: StringField) -> None:
        """Reject a name another subject already uses."""
        query = Subject.query.filter(Subject.name == field.data)
        if self.subject_id is not None:
            query = query.filter(Subject.id != self.subject_id)
        if query.first() is not None:
            raise ValidationError("Another subject already uses this name.")


class ClassSubjectForm(FlaskForm):
    """Assign a subject to a class with its mark scheme."""

    school_class_id = SelectField("Class", coerce=int, validators=[DataRequired()])
    subject_id = SelectField("Subject", coerce=int, validators=[DataRequired()])
    max_marks = IntegerField(
        "Maximum marks",
        default=100,
        validators=[DataRequired(), NumberRange(min=1, max=500, message="Maximum marks run from 1 to 500.")],
    )
    pass_marks = IntegerField(
        "Pass marks",
        default=33,
        validators=[
            DataRequired(),
            NumberRange(min=0, max=500, message="Pass marks run from 0 to 500."),
        ],
    )
    submit = SubmitField("Assign subject")

    def __init__(self, *args: object, assignment_id: Optional[int] = None, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.assignment_id = assignment_id
        self.school_class_id.choices = [
            (school_class.id, school_class.name)
            for school_class in SchoolClass.query.order_by(SchoolClass.numeral).all()
        ]
        self.subject_id.choices = [
            (subject.id, f"{subject.code} - {subject.name}")
            for subject in Subject.query.filter_by(is_active=True).order_by(Subject.name).all()
        ]

    def validate_pass_marks(self, field: IntegerField) -> None:
        """Reject a pass mark above the paper's maximum."""
        if field.data is not None and self.max_marks.data is not None and field.data > self.max_marks.data:
            raise ValidationError("Pass marks cannot exceed the maximum marks.")

    def validate_subject_id(self, field: SelectField) -> None:
        """Reject a duplicate class-subject pairing."""
        query = ClassSubject.query.filter(
            ClassSubject.school_class_id == self.school_class_id.data,
            ClassSubject.subject_id == field.data,
        )
        if self.assignment_id is not None:
            query = query.filter(ClassSubject.id != self.assignment_id)
        if query.first() is not None:
            raise ValidationError("That subject is already assigned to this class.")

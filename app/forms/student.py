"""Forms for creating and editing students."""

from __future__ import annotations

from datetime import date
from typing import Optional

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Regexp, ValidationError
from wtforms.validators import Optional as OptionalValidator

from ..extensions import db
from ..models import (
    BLOOD_GROUP_CHOICES,
    GENDER_CHOICES,
    GUARDIAN_RELATION_CHOICES,
    SchoolClass,
    Section,
    Student,
)

__all__ = ["StudentForm", "StudentFilterForm"]


class StudentForm(FlaskForm):
    """Create or edit a student.

    Args:
        student_id: Primary key of the student being edited, so that the
            uniqueness checks ignore the row itself.
    """

    admission_number = StringField(
        "Admission number",
        validators=[
            DataRequired(message="An admission number is required."),
            Length(max=20),
            Regexp(r"^[A-Za-z0-9/-]+$", message="Use letters, digits, '-' or '/' only."),
        ],
    )
    full_name = StringField(
        "Full name",
        validators=[DataRequired(message="The student's name is required."), Length(min=2, max=120)],
    )
    school_class_id = SelectField("Class", coerce=int, validators=[DataRequired()])
    section_id = SelectField("Section", coerce=int, validators=[DataRequired()])
    roll_number = IntegerField(
        "Roll number",
        validators=[
            DataRequired(message="A roll number is required."),
            NumberRange(min=1, max=200, message="Roll numbers run from 1 to 200."),
        ],
    )
    date_of_birth = DateField("Date of birth", validators=[DataRequired()])
    gender = SelectField("Gender", choices=list(GENDER_CHOICES), validators=[DataRequired()])
    blood_group = SelectField(
        "Blood group",
        choices=[("", "Not recorded")] + [(group, group) for group in BLOOD_GROUP_CHOICES],
        validators=[OptionalValidator()],
    )
    guardian_name = StringField(
        "Parent / guardian name",
        validators=[DataRequired(message="A parent or guardian name is required."), Length(max=120)],
    )
    guardian_relation = SelectField(
        "Relation to student",
        choices=[(relation, relation) for relation in GUARDIAN_RELATION_CHOICES],
        default="Father",
        validators=[DataRequired()],
    )
    guardian_phone = StringField(
        "Guardian phone",
        validators=[
            DataRequired(message="A guardian phone number is required."),
            Regexp(r"^[0-9+][0-9 +()-]{6,19}$", message="Enter a phone number of 7 to 20 characters."),
        ],
    )
    email = StringField(
        "Email",
        validators=[OptionalValidator(), Email(message="Enter a valid email address."), Length(max=120)],
    )
    address = TextAreaField("Address", validators=[OptionalValidator(), Length(max=255)])
    admission_date = DateField("Admission date", validators=[DataRequired()], default=date.today)
    is_active = BooleanField("Currently enrolled", default=True)
    submit = SubmitField("Save student")

    def __init__(self, *args: object, student_id: Optional[int] = None, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.student_id = student_id
        self.school_class_id.choices = [
            (school_class.id, school_class.name)
            for school_class in SchoolClass.query.order_by(SchoolClass.numeral).all()
        ]
        self.section_id.choices = [
            (section.id, section.label)
            for section in Section.query.join(SchoolClass).order_by(SchoolClass.numeral, Section.name).all()
        ]

    def validate_admission_number(self, field: StringField) -> None:
        """Reject an admission number that another student already holds."""
        query = Student.query.filter(Student.admission_number == field.data)
        if self.student_id is not None:
            query = query.filter(Student.id != self.student_id)
        if query.first() is not None:
            raise ValidationError("Another student already uses this admission number.")

    def validate_section_id(self, field: SelectField) -> None:
        """Reject a section that does not belong to the chosen class."""
        section = db.session.get(Section, field.data)
        if section is None:
            raise ValidationError("Choose a section.")
        if section.school_class_id != self.school_class_id.data:
            raise ValidationError("That section belongs to a different class.")

    def validate_roll_number(self, field: IntegerField) -> None:
        """Reject a roll number already used in the same class and section."""
        query = Student.query.filter(
            Student.school_class_id == self.school_class_id.data,
            Student.section_id == self.section_id.data,
            Student.roll_number == field.data,
        )
        if self.student_id is not None:
            query = query.filter(Student.id != self.student_id)
        if query.first() is not None:
            raise ValidationError("That roll number is already used in this class and section.")

    def validate_date_of_birth(self, field: DateField) -> None:
        """Reject a date of birth in the future or implausibly old."""
        if field.data is None:
            return
        today = date.today()
        if field.data >= today:
            raise ValidationError("The date of birth must be in the past.")
        if today.year - field.data.year > 30:
            raise ValidationError("That date of birth looks wrong for a school student.")

    def validate_admission_date(self, field: DateField) -> None:
        """Reject an admission date in the future or before the date of birth."""
        if field.data is None:
            return
        if field.data > date.today():
            raise ValidationError("The admission date cannot be in the future.")
        if self.date_of_birth.data and field.data < self.date_of_birth.data:
            raise ValidationError("The admission date cannot precede the date of birth.")


class StudentFilterForm(FlaskForm):
    """Search and filter controls above the student list.

    Submitted with ``GET``, so CSRF protection is disabled for this form only.
    """

    class Meta:
        csrf = False

    q = StringField("Search", validators=[OptionalValidator(), Length(max=120)])
    school_class_id = SelectField("Class", coerce=int, validators=[OptionalValidator()])
    section_id = SelectField("Section", coerce=int, validators=[OptionalValidator()])
    status = SelectField(
        "Status",
        choices=[("active", "Enrolled"), ("inactive", "Left"), ("all", "All")],
        default="active",
    )
    submit = SubmitField("Apply")

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.school_class_id.choices = [(0, "All classes")] + [
            (school_class.id, school_class.name)
            for school_class in SchoolClass.query.order_by(SchoolClass.numeral).all()
        ]
        self.section_id.choices = [(0, "All sections")] + [
            (section.id, section.label)
            for section in Section.query.join(SchoolClass).order_by(SchoolClass.numeral, Section.name).all()
        ]

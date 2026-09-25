"""The student record."""

from __future__ import annotations

from datetime import date
from typing import Optional

from ..extensions import TimestampMixin, db

__all__ = ["BLOOD_GROUP_CHOICES", "GENDER_CHOICES", "GUARDIAN_RELATION_CHOICES", "Student"]

#: Stored value to label, used by the forms and the templates.
GENDER_CHOICES = (("F", "Female"), ("M", "Male"), ("O", "Other"))

#: Blood groups offered by the form; the column itself is free text up to 3 characters.
BLOOD_GROUP_CHOICES = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")

#: How the guardian is related to the student.
GUARDIAN_RELATION_CHOICES = ("Father", "Mother", "Guardian")

_GENDER_LABELS = dict(GENDER_CHOICES)


class Student(TimestampMixin, db.Model):
    """One enrolled student.

    Both ``school_class_id`` and ``section_id`` are stored.  The section already
    implies the class, but keeping the class on the row makes the common
    "everyone in Class 7" query a single index lookup and lets the database
    enforce that a roll number is unique within a class and section.  The
    invariant that the section belongs to the class is enforced by
    :class:`app.forms.student.StudentForm` and by the seeder.

    Removal is normally soft: :attr:`is_active` is cleared so that historical
    marks and report cards stay intact.  A permanent delete, which also removes
    the student's marks, is available for records entered by mistake.
    """

    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    admission_number = db.Column(db.String(20), nullable=False, unique=True, index=True)
    full_name = db.Column(db.String(120), nullable=False, index=True)
    roll_number = db.Column(db.Integer, nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(1), nullable=False, default="O")
    blood_group = db.Column(db.String(3), nullable=True)
    guardian_name = db.Column(db.String(120), nullable=False)
    guardian_relation = db.Column(db.String(20), nullable=False, default="Guardian")
    guardian_phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    admission_date = db.Column(db.Date, nullable=False, default=date.today)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    school_class_id = db.Column(
        db.Integer, db.ForeignKey("school_classes.id", ondelete="RESTRICT"), nullable=False
    )
    section_id = db.Column(db.Integer, db.ForeignKey("sections.id", ondelete="RESTRICT"), nullable=False)

    school_class = db.relationship("SchoolClass", back_populates="students")
    section = db.relationship("Section", back_populates="students")
    marks = db.relationship("Mark", back_populates="student", cascade="all, delete-orphan", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint(
            "school_class_id", "section_id", "roll_number", name="uq_student_roll_in_section"
        ),
        db.Index("ix_student_class_section", "school_class_id", "section_id"),
    )

    @property
    def gender_label(self) -> str:
        """The readable gender, for example ``Female``."""
        return _GENDER_LABELS.get(self.gender, "Other")

    @property
    def class_label(self) -> str:
        """Class and section together, for example ``Class 8 - A``."""
        class_name = self.school_class.name if self.school_class else "Unassigned"
        section_name = self.section.name if self.section else "?"
        return f"{class_name} - {section_name}"

    def age_on(self, reference: Optional[date] = None) -> int:
        """Return the student's age in whole years on ``reference`` (today by default)."""
        moment = reference or date.today()
        years = moment.year - self.date_of_birth.year
        if (moment.month, moment.day) < (self.date_of_birth.month, self.date_of_birth.day):
            years -= 1
        return max(years, 0)

    def deactivate(self) -> None:
        """Soft-delete the student."""
        self.is_active = False

    def restore(self) -> None:
        """Undo a soft delete."""
        self.is_active = True

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Student {self.admission_number} {self.full_name}>"

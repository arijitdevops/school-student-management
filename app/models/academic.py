"""Academic calendar and class structure: years, classes and sections."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from ..extensions import TimestampMixin, db

__all__ = ["AcademicYear", "SchoolClass", "Section"]


class AcademicYear(TimestampMixin, db.Model):
    """A school year such as ``2025-2026``.

    Exactly one year is expected to carry ``is_current``; :meth:`current`
    returns it and falls back to the most recently started year.
    """

    __tablename__ = "academic_years"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False, unique=True, index=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_current = db.Column(db.Boolean, nullable=False, default=False)

    exams = db.relationship(
        "Exam", back_populates="academic_year", cascade="all, delete-orphan", lazy="selectin"
    )

    @classmethod
    def current(cls) -> Optional[AcademicYear]:
        """Return the active academic year, or ``None`` when none exists."""
        year = cls.query.filter_by(is_current=True).first()
        if year is not None:
            return year
        return cls.query.order_by(cls.start_date.desc()).first()

    def contains(self, moment: date) -> bool:
        """Return whether ``moment`` falls inside this academic year."""
        return self.start_date <= moment <= self.end_date

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AcademicYear {self.name}>"


class SchoolClass(TimestampMixin, db.Model):
    """One of classes 1 to 10.

    ``numeral`` is the sortable integer; ``name`` is the label shown in the UI.
    """

    __tablename__ = "school_classes"

    id = db.Column(db.Integer, primary_key=True)
    numeral = db.Column(db.Integer, nullable=False, unique=True, index=True)
    name = db.Column(db.String(40), nullable=False, unique=True)

    sections = db.relationship(
        "Section",
        back_populates="school_class",
        cascade="all, delete-orphan",
        order_by="Section.name",
        lazy="selectin",
    )
    class_subjects = db.relationship(
        "ClassSubject",
        back_populates="school_class",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    students = db.relationship("Student", back_populates="school_class", lazy="dynamic")

    __table_args__ = (db.CheckConstraint("numeral BETWEEN 1 AND 10", name="ck_school_class_numeral_range"),)

    @property
    def section_names(self) -> List[str]:
        """Section labels in alphabetical order, for example ``["A", "B"]``."""
        return [section.name for section in self.sections]

    @property
    def active_student_count(self) -> int:
        """Number of students in this class who have not been soft-deleted."""
        return self.students.filter_by(is_active=True).count()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<SchoolClass {self.name}>"


class Section(TimestampMixin, db.Model):
    """A division of a class, such as ``1-A``."""

    __tablename__ = "sections"

    id = db.Column(db.Integer, primary_key=True)
    school_class_id = db.Column(
        db.Integer, db.ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(2), nullable=False)
    room = db.Column(db.String(20), nullable=True)
    capacity = db.Column(db.Integer, nullable=False, default=50)

    school_class = db.relationship("SchoolClass", back_populates="sections")
    students = db.relationship("Student", back_populates="section", lazy="dynamic")

    __table_args__ = (db.UniqueConstraint("school_class_id", "name", name="uq_section_class_name"),)

    @property
    def label(self) -> str:
        """Human readable identifier such as ``Class 5 - B``."""
        return f"{self.school_class.name} - {self.name}"

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Section {self.school_class_id}-{self.name}>"

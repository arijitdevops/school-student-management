"""Subjects and the per-class mark scheme that governs them."""

from __future__ import annotations

from ..extensions import TimestampMixin, db

__all__ = ["Subject", "ClassSubject"]


class Subject(TimestampMixin, db.Model):
    """A teachable subject, independent of any class.

    Which classes actually study a subject, and the marks it carries there, is
    recorded by :class:`ClassSubject` rather than here, because the same subject
    can be worth different marks in different classes.
    """

    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False, unique=True, index=True)
    name = db.Column(db.String(60), nullable=False, unique=True)
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    class_subjects = db.relationship(
        "ClassSubject",
        back_populates="subject",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def class_count(self) -> int:
        """How many classes currently study this subject."""
        return len(self.class_subjects)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Subject {self.code}>"


class ClassSubject(TimestampMixin, db.Model):
    """The link between a class and a subject, carrying the mark scheme.

    A row states that, say, Class 7 studies Science out of 100 marks with 33 to
    pass.  Marks are recorded against this row rather than against the subject
    so that a paper's maximum is never ambiguous.
    """

    __tablename__ = "class_subjects"

    id = db.Column(db.Integer, primary_key=True)
    school_class_id = db.Column(
        db.Integer, db.ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False
    )
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    max_marks = db.Column(db.Integer, nullable=False, default=100)
    pass_marks = db.Column(db.Integer, nullable=False, default=33)

    school_class = db.relationship("SchoolClass", back_populates="class_subjects")
    subject = db.relationship("Subject", back_populates="class_subjects")
    marks = db.relationship(
        "Mark", back_populates="class_subject", cascade="all, delete-orphan", lazy="dynamic"
    )

    __table_args__ = (
        db.UniqueConstraint("school_class_id", "subject_id", name="uq_class_subject"),
        db.CheckConstraint("max_marks > 0", name="ck_class_subject_max_marks_positive"),
        db.CheckConstraint("pass_marks >= 0 AND pass_marks <= max_marks", name="ck_class_subject_pass_marks"),
    )

    @property
    def subject_name(self) -> str:
        """Name of the linked subject."""
        return self.subject.name

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ClassSubject class={self.school_class_id} subject={self.subject_id}>"

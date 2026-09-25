"""Marks awarded to a student for one subject in one exam."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from ..extensions import TimestampMixin, db

__all__ = ["Mark"]


class Mark(TimestampMixin, db.Model):
    """A single score.

    The unique constraint over student, class-subject and exam is what makes
    bulk entry safe to repeat: saving the grid twice updates rows instead of
    duplicating them.
    """

    __tablename__ = "marks"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    class_subject_id = db.Column(
        db.Integer, db.ForeignKey("class_subjects.id", ondelete="CASCADE"), nullable=False
    )
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    marks_obtained = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    is_absent = db.Column(db.Boolean, nullable=False, default=False)
    remarks = db.Column(db.String(255), nullable=True)

    student = db.relationship("Student", back_populates="marks")
    class_subject = db.relationship("ClassSubject", back_populates="marks")
    exam = db.relationship("Exam", back_populates="marks")

    __table_args__ = (
        db.UniqueConstraint("student_id", "class_subject_id", "exam_id", name="uq_mark_student_subject_exam"),
        db.CheckConstraint("marks_obtained >= 0", name="ck_mark_non_negative"),
        db.Index("ix_mark_exam_class_subject", "exam_id", "class_subject_id"),
    )

    @property
    def score(self) -> float:
        """Marks as a float; an absent student scores zero."""
        if self.is_absent:
            return 0.0
        return float(self.marks_obtained or 0)

    @property
    def display_score(self) -> str:
        """``AB`` for an absent student, otherwise the score without trailing zeros."""
        if self.is_absent:
            return "AB"
        value = self.score
        return str(int(value)) if float(value).is_integer() else f"{value:.2f}"

    @classmethod
    def for_student_exam(cls, student_id: int, exam_id: int) -> list[Mark]:
        """Return every mark a student scored in one exam."""
        return cls.query.filter_by(student_id=student_id, exam_id=exam_id).all()

    def set_score(self, value: Optional[float], max_marks: int) -> None:
        """Set the score, clamping to ``0..max_marks``.

        Args:
            value: The new score, or ``None`` to mark the student absent.
            max_marks: The paper's maximum, taken from the class-subject row.
        """
        if value is None:
            self.is_absent = True
            self.marks_obtained = Decimal("0.00")
            return
        self.is_absent = False
        clamped = max(0.0, min(float(value), float(max_marks)))
        self.marks_obtained = Decimal(f"{clamped:.2f}")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Mark student={self.student_id} exam={self.exam_id}>"

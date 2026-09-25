"""Examinations held during an academic year."""

from __future__ import annotations

from decimal import Decimal

from ..extensions import TimestampMixin, db

__all__ = ["Exam"]


class Exam(TimestampMixin, db.Model):
    """One assessment in the year, such as ``Half Yearly``.

    ``weightage`` is the share this exam contributes to the final aggregate.
    The weightages of a year's exams are expected to add up to 100, but nothing
    enforces that: :mod:`app.services.results` normalises by whatever total it
    finds so a partially entered year still produces sensible percentages.
    """

    __tablename__ = "exams"

    id = db.Column(db.Integer, primary_key=True)
    academic_year_id = db.Column(
        db.Integer, db.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False
    )
    code = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(60), nullable=False)
    sequence = db.Column(db.Integer, nullable=False, default=1)
    weightage = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal("25.00"))
    held_on = db.Column(db.Date, nullable=True)

    academic_year = db.relationship("AcademicYear", back_populates="exams")
    marks = db.relationship("Mark", back_populates="exam", cascade="all, delete-orphan", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("academic_year_id", "code", name="uq_exam_year_code"),
        db.CheckConstraint("weightage >= 0", name="ck_exam_weightage_non_negative"),
    )

    @property
    def weight(self) -> float:
        """The weightage as a plain float, for arithmetic in the services layer."""
        return float(self.weightage or 0)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Exam {self.code}>"

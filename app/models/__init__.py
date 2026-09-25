"""SQLAlchemy models.

Importing this package imports every model module, which is what registers the
tables with :data:`app.extensions.db.metadata`.  Alembic autogeneration and
``db.create_all()`` both depend on that having happened.
"""

from __future__ import annotations

from .academic import AcademicYear, SchoolClass, Section
from .exam import Exam
from .mark import Mark
from .student import BLOOD_GROUP_CHOICES, GENDER_CHOICES, GUARDIAN_RELATION_CHOICES, Student
from .subject import ClassSubject, Subject

__all__ = [
    "AcademicYear",
    "BLOOD_GROUP_CHOICES",
    "ClassSubject",
    "Exam",
    "GENDER_CHOICES",
    "GUARDIAN_RELATION_CHOICES",
    "Mark",
    "SchoolClass",
    "Section",
    "Student",
    "Subject",
]

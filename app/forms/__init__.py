"""Flask-WTF forms used by the blueprints."""

from __future__ import annotations

from .mark import BulkMarkForm, MarkEntryFilterForm, ParsedMark, parse_mark_inputs
from .student import StudentFilterForm, StudentForm
from .subject import ClassSubjectForm, SubjectForm

__all__ = [
    "BulkMarkForm",
    "ClassSubjectForm",
    "MarkEntryFilterForm",
    "ParsedMark",
    "StudentFilterForm",
    "StudentForm",
    "SubjectForm",
    "parse_mark_inputs",
]

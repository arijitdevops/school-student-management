"""Business logic that the views, the CLI and the seeder all share.

:mod:`app.services.results` aggregates, grades and ranks marks;
:mod:`app.services.seed_helpers` produces the fictional demo dataset.  Neither
module imports Flask, so both can be exercised without an application context.
"""

from __future__ import annotations

from .results import (
    DEFAULT_GRADE_SCALE,
    ClassSummary,
    GradeScale,
    StudentResult,
    SubjectResult,
    assign_ranks,
    build_class_results,
    build_student_result,
    class_summary,
    index_marks,
    result_csv_header,
    result_csv_rows,
)

__all__ = [
    "DEFAULT_GRADE_SCALE",
    "ClassSummary",
    "GradeScale",
    "StudentResult",
    "SubjectResult",
    "assign_ranks",
    "build_class_results",
    "build_student_result",
    "class_summary",
    "index_marks",
    "result_csv_header",
    "result_csv_rows",
]

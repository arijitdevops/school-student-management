"""Result aggregation, grading and ranking.

Everything in this module is a pure function over rows that the caller has
already fetched.  Nothing here opens a session, issues a query or touches
``current_app``, which is what makes the logic testable without a database and
reusable from the report views, the CSV export and the seeder alike.

The inputs are duck-typed rather than annotated with the ORM classes so that
tests can pass lightweight stand-ins:

* a *student* needs ``id``, ``full_name``, ``admission_number`` and ``roll_number``
* a *class subject* needs ``id``, ``max_marks``, ``pass_marks`` and ``subject``
  (which in turn needs ``name`` and ``code``)
* an *exam* needs ``id``, ``name``, ``code``, ``sequence`` and ``weight``
* a *mark* needs ``student_id``, ``class_subject_id``, ``exam_id``, ``score``
  and ``is_absent``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "DEFAULT_GRADE_SCALE",
    "ClassSummary",
    "ExamScore",
    "ExamTotal",
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

#: Key used to look a mark up quickly: (student id, class subject id, exam id).
MarkKey = Tuple[int, int, int]


@dataclass(frozen=True)
class GradeScale:
    """Percentage bands that turn a percentage into a letter grade.

    Args:
        bands: ``(minimum_percentage, grade)`` pairs, highest band first.
        fail_grade: Grade awarded below the lowest band.
    """

    bands: Tuple[Tuple[float, str], ...]
    fail_grade: str = "F"

    def grade_for(self, percentage: Optional[float]) -> str:
        """Return the letter grade for ``percentage``."""
        if percentage is None:
            return "-"
        for minimum, grade in self.bands:
            if percentage >= minimum:
                return grade
        return self.fail_grade


#: The scale used when a caller does not supply one.  Mirrors ``Config.GRADE_BANDS``.
DEFAULT_GRADE_SCALE = GradeScale(
    bands=(
        (90.0, "A+"),
        (80.0, "A"),
        (70.0, "B"),
        (60.0, "C"),
        (50.0, "D"),
        (40.0, "E"),
    ),
    fail_grade="F",
)


@dataclass(frozen=True)
class ExamScore:
    """What a student scored for one subject in one exam."""

    exam_id: int
    exam_name: str
    max_marks: float
    obtained: Optional[float] = None
    is_absent: bool = False

    @property
    def recorded(self) -> bool:
        """Whether a mark exists for this subject and exam."""
        return self.obtained is not None

    @property
    def display(self) -> str:
        """``AB`` when absent, ``-`` when nothing was recorded, else the score."""
        if not self.recorded:
            return "-"
        if self.is_absent:
            return "AB"
        value = float(self.obtained or 0.0)
        return str(int(value)) if value.is_integer() else f"{value:.2f}"


@dataclass
class SubjectResult:
    """A student's standing in one subject, across every exam."""

    class_subject_id: int
    subject_name: str
    subject_code: str
    max_marks: float
    pass_marks: float
    exam_scores: List[ExamScore] = field(default_factory=list)
    obtained: float = 0.0
    total_max: float = 0.0
    percentage: Optional[float] = None
    grade: str = "-"
    passed: bool = False

    @property
    def has_marks(self) -> bool:
        """Whether at least one exam mark was recorded for this subject."""
        return self.total_max > 0.0


@dataclass(frozen=True)
class ExamTotal:
    """A student's total across every subject for one exam."""

    exam_id: int
    exam_name: str
    obtained: float
    total_max: float
    weight: float

    @property
    def percentage(self) -> Optional[float]:
        """Percentage for this exam, or ``None`` when nothing was recorded."""
        if self.total_max <= 0.0:
            return None
        return self.obtained / self.total_max * 100.0


@dataclass
class StudentResult:
    """A student's complete result for the year."""

    student_id: int
    student_name: str
    admission_number: str
    roll_number: int
    subjects: List[SubjectResult] = field(default_factory=list)
    exam_totals: List[ExamTotal] = field(default_factory=list)
    obtained: float = 0.0
    total_max: float = 0.0
    percentage: Optional[float] = None
    weighted_percentage: Optional[float] = None
    grade: str = "-"
    passed: bool = False
    rank: Optional[int] = None

    @property
    def has_marks(self) -> bool:
        """Whether any mark at all was recorded for this student."""
        return self.total_max > 0.0

    @property
    def ranking_percentage(self) -> float:
        """The percentage ranking is based on; zero when nothing was recorded."""
        value = self.weighted_percentage if self.weighted_percentage is not None else self.percentage
        return float(value) if value is not None else 0.0

    @property
    def failed_subjects(self) -> List[str]:
        """Names of the subjects the student did not pass."""
        return [subject.subject_name for subject in self.subjects if subject.has_marks and not subject.passed]


@dataclass(frozen=True)
class ClassSummary:
    """Headline numbers for a whole class."""

    student_count: int
    evaluated_count: int
    passed_count: int
    failed_count: int
    average_percentage: Optional[float]
    highest_percentage: Optional[float]
    lowest_percentage: Optional[float]

    @property
    def pass_rate(self) -> Optional[float]:
        """Percentage of evaluated students who passed."""
        if self.evaluated_count == 0:
            return None
        return self.passed_count / self.evaluated_count * 100.0


def index_marks(marks: Iterable[object]) -> Dict[MarkKey, object]:
    """Index marks by ``(student_id, class_subject_id, exam_id)``.

    A later row with the same key wins, which mirrors the unique constraint on
    the table.
    """
    indexed: Dict[MarkKey, object] = {}
    for mark in marks:
        key = (
            int(mark.student_id),
            int(mark.class_subject_id),
            int(mark.exam_id),
        )
        indexed[key] = mark
    return indexed


def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
    """Round a percentage, passing ``None`` through untouched."""
    return None if value is None else round(float(value), digits)


def build_student_result(
    student: object,
    class_subjects: Sequence[object],
    exams: Sequence[object],
    marks_index: Dict[MarkKey, object],
    scale: GradeScale = DEFAULT_GRADE_SCALE,
) -> StudentResult:
    """Aggregate one student's marks into a :class:`StudentResult`.

    Args:
        student: The student row.
        class_subjects: The subjects that student's class studies.
        exams: The exams of the academic year, in the order to display them.
        marks_index: Output of :func:`index_marks`.
        scale: Grade bands to apply.

    Returns:
        The student's subject rows, per-exam totals, overall percentage,
        weighted percentage, grade and pass/fail flag.  ``rank`` is left unset;
        :func:`assign_ranks` fills it in.
    """
    student_id = int(student.id)
    result = StudentResult(
        student_id=student_id,
        student_name=str(student.full_name),
        admission_number=str(student.admission_number),
        roll_number=int(getattr(student, "roll_number", 0) or 0),
    )

    exam_obtained: Dict[int, float] = {int(exam.id): 0.0 for exam in exams}
    exam_max: Dict[int, float] = {int(exam.id): 0.0 for exam in exams}

    for class_subject in class_subjects:
        class_subject_id = int(class_subject.id)
        subject = class_subject.subject
        max_marks = float(class_subject.max_marks)
        pass_marks = float(class_subject.pass_marks)
        subject_result = SubjectResult(
            class_subject_id=class_subject_id,
            subject_name=str(subject.name),
            subject_code=str(subject.code),
            max_marks=max_marks,
            pass_marks=pass_marks,
        )

        for exam in exams:
            exam_id = int(exam.id)
            mark = marks_index.get((student_id, class_subject_id, exam_id))
            if mark is None:
                subject_result.exam_scores.append(
                    ExamScore(exam_id=exam_id, exam_name=str(exam.name), max_marks=max_marks)
                )
                continue

            score = float(mark.score)
            is_absent = bool(getattr(mark, "is_absent", False))
            subject_result.exam_scores.append(
                ExamScore(
                    exam_id=exam_id,
                    exam_name=str(exam.name),
                    max_marks=max_marks,
                    obtained=score,
                    is_absent=is_absent,
                )
            )
            subject_result.obtained += score
            subject_result.total_max += max_marks
            exam_obtained[exam_id] = exam_obtained.get(exam_id, 0.0) + score
            exam_max[exam_id] = exam_max.get(exam_id, 0.0) + max_marks

        if subject_result.has_marks:
            subject_result.percentage = subject_result.obtained / subject_result.total_max * 100.0
            subject_result.grade = scale.grade_for(subject_result.percentage)
            recorded_exams = sum(1 for score in subject_result.exam_scores if score.recorded)
            subject_result.passed = subject_result.obtained >= pass_marks * recorded_exams
        result.subjects.append(subject_result)
        result.obtained += subject_result.obtained
        result.total_max += subject_result.total_max

    result.exam_totals = [
        ExamTotal(
            exam_id=int(exam.id),
            exam_name=str(exam.name),
            obtained=exam_obtained.get(int(exam.id), 0.0),
            total_max=exam_max.get(int(exam.id), 0.0),
            weight=float(getattr(exam, "weight", 0.0) or 0.0),
        )
        for exam in exams
    ]

    if result.has_marks:
        result.percentage = _round(result.obtained / result.total_max * 100.0)
        result.weighted_percentage = _round(_weighted_percentage(result.exam_totals))
        result.grade = scale.grade_for(result.weighted_percentage)
        evaluated = [subject for subject in result.subjects if subject.has_marks]
        result.passed = bool(evaluated) and all(subject.passed for subject in evaluated)

    for subject_result in result.subjects:
        subject_result.percentage = _round(subject_result.percentage)

    return result


def _weighted_percentage(exam_totals: Sequence[ExamTotal]) -> Optional[float]:
    """Combine per-exam percentages using each exam's weightage.

    Exams with no marks, or with a weightage of zero, are ignored.  When no exam
    carries a weightage the plain total is used instead, so a year configured
    without weightages still ranks correctly.
    """
    usable = [total for total in exam_totals if total.total_max > 0.0]
    if not usable:
        return None
    weighted = [total for total in usable if total.weight > 0.0]
    if not weighted:
        obtained = sum(total.obtained for total in usable)
        maximum = sum(total.total_max for total in usable)
        return obtained / maximum * 100.0 if maximum > 0 else None
    weight_sum = sum(total.weight for total in weighted)
    return sum((total.percentage or 0.0) * total.weight for total in weighted) / weight_sum


def assign_ranks(results: Sequence[StudentResult], digits: int = 2) -> List[StudentResult]:
    """Sort results best-first and apply competition ranking.

    Ties share a rank and the next rank skips accordingly, so three students on
    the same percentage occupy ranks 1, 1, 1 and the next student is 4th.
    Students with no marks at all are placed last and left unranked.

    Args:
        results: The results to rank.  They are not modified in place until
            their rank is set; the returned list is a new ordering.
        digits: Decimal places used when deciding whether two percentages tie.

    Returns:
        The same objects, ordered by rank, with :attr:`StudentResult.rank` set.
    """
    ranked = sorted(
        results,
        key=lambda item: (
            not item.has_marks,
            -round(item.ranking_percentage, digits),
            -item.obtained,
            item.student_name.lower(),
        ),
    )

    previous_key: Optional[float] = None
    current_rank = 0
    for position, result in enumerate(ranked, start=1):
        if not result.has_marks:
            result.rank = None
            continue
        key = round(result.ranking_percentage, digits)
        if previous_key is None or key != previous_key:
            current_rank = position
            previous_key = key
        result.rank = current_rank
    return ranked


def build_class_results(
    students: Sequence[object],
    class_subjects: Sequence[object],
    exams: Sequence[object],
    marks: Iterable[object],
    scale: GradeScale = DEFAULT_GRADE_SCALE,
) -> List[StudentResult]:
    """Build and rank the results for a whole class.

    Args:
        students: Every student to include.
        class_subjects: The subjects their class studies.
        exams: The exams of the academic year.
        marks: All marks for those students; indexed internally.
        scale: Grade bands to apply.

    Returns:
        Ranked results, best first.
    """
    marks_index = index_marks(marks)
    results = [
        build_student_result(student, class_subjects, exams, marks_index, scale) for student in students
    ]
    return assign_ranks(results)


def class_summary(results: Sequence[StudentResult]) -> ClassSummary:
    """Summarise a ranked class result list."""
    evaluated = [result for result in results if result.has_marks]
    percentages = [result.ranking_percentage for result in evaluated]
    passed = sum(1 for result in evaluated if result.passed)
    return ClassSummary(
        student_count=len(results),
        evaluated_count=len(evaluated),
        passed_count=passed,
        failed_count=len(evaluated) - passed,
        average_percentage=_round(sum(percentages) / len(percentages)) if percentages else None,
        highest_percentage=_round(max(percentages)) if percentages else None,
        lowest_percentage=_round(min(percentages)) if percentages else None,
    )


def result_csv_header(class_subjects: Sequence[object]) -> List[str]:
    """Column names for :func:`result_csv_rows`."""
    header = ["Rank", "Roll No", "Admission No", "Student Name"]
    header.extend(str(subject.subject.name) for subject in class_subjects)
    header.extend(["Total Obtained", "Total Maximum", "Percentage", "Weighted %", "Grade", "Result"])
    return header


def result_csv_rows(results: Sequence[StudentResult], class_subjects: Sequence[object]) -> List[List[str]]:
    """Flatten ranked results into rows ready for :mod:`csv`.

    Subject columns follow the order of ``class_subjects`` so that the rows line
    up with :func:`result_csv_header`.
    """
    order = [int(subject.id) for subject in class_subjects]
    rows: List[List[str]] = []
    for result in results:
        by_id = {subject.class_subject_id: subject for subject in result.subjects}
        row = [
            str(result.rank) if result.rank is not None else "-",
            str(result.roll_number),
            result.admission_number,
            result.student_name,
        ]
        for class_subject_id in order:
            subject = by_id.get(class_subject_id)
            if subject is None or not subject.has_marks:
                row.append("-")
            else:
                row.append(f"{subject.obtained:g}/{subject.total_max:g}")
        row.extend(
            [
                f"{result.obtained:g}",
                f"{result.total_max:g}",
                f"{result.percentage:.2f}" if result.percentage is not None else "-",
                f"{result.weighted_percentage:.2f}" if result.weighted_percentage is not None else "-",
                result.grade,
                "PASS" if result.passed else ("FAIL" if result.has_marks else "NO MARKS"),
            ]
        )
        rows.append(row)
    return rows

"""Tests for the pure result-aggregation layer.

These tests use lightweight stand-ins rather than ORM objects: the functions in
:mod:`app.services.results` are duck-typed on purpose, and keeping the tests
free of a database is what makes them fast and unambiguous.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.results import (
    DEFAULT_GRADE_SCALE,
    GradeScale,
    assign_ranks,
    build_class_results,
    build_student_result,
    class_summary,
    index_marks,
    result_csv_header,
    result_csv_rows,
)


def make_class_subject(identifier: int, name: str, code: str, max_marks: int = 100, pass_marks: int = 33):
    """Build a stand-in for a ClassSubject row."""
    return SimpleNamespace(
        id=identifier,
        max_marks=max_marks,
        pass_marks=pass_marks,
        subject=SimpleNamespace(name=name, code=code),
    )


def make_exam(identifier: int, name: str, weight: float, sequence: int = 1):
    """Build a stand-in for an Exam row."""
    return SimpleNamespace(id=identifier, name=name, code=name[:3].upper(), sequence=sequence, weight=weight)


def make_student(identifier: int, name: str, roll: int):
    """Build a stand-in for a Student row."""
    return SimpleNamespace(
        id=identifier, full_name=name, admission_number=f"ADM{identifier:04d}", roll_number=roll
    )


def make_mark(student_id: int, class_subject_id: int, exam_id: int, score: float, absent: bool = False):
    """Build a stand-in for a Mark row."""
    return SimpleNamespace(
        student_id=student_id,
        class_subject_id=class_subject_id,
        exam_id=exam_id,
        score=0.0 if absent else score,
        is_absent=absent,
    )


@pytest.fixture()
def subjects():
    return [make_class_subject(1, "English", "ENG"), make_class_subject(2, "Mathematics", "MAT")]


@pytest.fixture()
def exams():
    return [make_exam(10, "Unit Test 1", 40.0, 1), make_exam(11, "Annual", 60.0, 2)]


class TestGradeScale:
    @pytest.mark.parametrize(
        ("percentage", "grade"),
        [
            (100.0, "A+"),
            (90.0, "A+"),
            (89.9, "A"),
            (80.0, "A"),
            (70.0, "B"),
            (60.0, "C"),
            (50.0, "D"),
            (40.0, "E"),
            (39.9, "F"),
            (0.0, "F"),
        ],
    )
    def test_bands(self, percentage: float, grade: str) -> None:
        assert DEFAULT_GRADE_SCALE.grade_for(percentage) == grade

    def test_missing_percentage(self) -> None:
        assert DEFAULT_GRADE_SCALE.grade_for(None) == "-"

    def test_custom_scale(self) -> None:
        scale = GradeScale(bands=((50.0, "Pass"),), fail_grade="Retake")
        assert scale.grade_for(60.0) == "Pass"
        assert scale.grade_for(49.9) == "Retake"


class TestIndexMarks:
    def test_last_row_wins(self) -> None:
        first = make_mark(1, 1, 10, 40)
        second = make_mark(1, 1, 10, 55)
        assert index_marks([first, second])[(1, 1, 10)] is second

    def test_key_shape(self) -> None:
        assert list(index_marks([make_mark(3, 2, 11, 10)])) == [(3, 2, 11)]


class TestBuildStudentResult:
    def test_totals_and_percentage(self, subjects, exams) -> None:
        student = make_student(1, "Asha", 1)
        marks = [make_mark(1, subject.id, exam.id, 80) for subject in subjects for exam in exams]
        result = build_student_result(student, subjects, exams, index_marks(marks))
        assert result.obtained == 320.0
        assert result.total_max == 400.0
        assert result.percentage == 80.0
        assert result.grade == "A"
        assert result.passed is True

    def test_weighted_percentage_uses_exam_weights(self, subjects, exams) -> None:
        student = make_student(1, "Asha", 1)
        marks = [make_mark(1, subject.id, 10, 50) for subject in subjects]
        marks += [make_mark(1, subject.id, 11, 100) for subject in subjects]
        result = build_student_result(student, subjects, exams, index_marks(marks))
        # 50% weighted 40 plus 100% weighted 60 gives 80.
        assert result.weighted_percentage == 80.0
        assert result.percentage == 75.0

    def test_falls_back_to_plain_total_without_weights(self, subjects) -> None:
        exams = [make_exam(10, "Only", 0.0)]
        student = make_student(1, "Asha", 1)
        marks = [make_mark(1, subject.id, 10, 60) for subject in subjects]
        result = build_student_result(student, subjects, exams, index_marks(marks))
        assert result.weighted_percentage == 60.0

    def test_absence_scores_zero_but_still_counts_the_paper(self, subjects, exams) -> None:
        student = make_student(1, "Asha", 1)
        marks = [make_mark(1, subjects[0].id, exams[0].id, 0, absent=True)]
        result = build_student_result(student, subjects, exams, index_marks(marks))
        english = result.subjects[0]
        assert english.obtained == 0.0
        assert english.total_max == 100.0
        assert english.exam_scores[0].display == "AB"
        assert english.exam_scores[1].display == "-"

    def test_missing_marks_are_not_counted(self, subjects, exams) -> None:
        student = make_student(1, "Asha", 1)
        marks = [make_mark(1, subjects[0].id, exams[0].id, 90)]
        result = build_student_result(student, subjects, exams, index_marks(marks))
        assert result.total_max == 100.0
        assert result.subjects[1].has_marks is False

    def test_student_without_marks(self, subjects, exams) -> None:
        result = build_student_result(make_student(9, "Nobody", 9), subjects, exams, {})
        assert result.has_marks is False
        assert result.percentage is None
        assert result.grade == "-"
        assert result.passed is False

    def test_subject_pass_threshold_scales_with_exam_count(self, subjects, exams) -> None:
        student = make_student(1, "Asha", 1)
        # 33 in each of two exams is exactly the pass mark each time.
        marks = [make_mark(1, subjects[0].id, exam.id, 33) for exam in exams]
        marks += [make_mark(1, subjects[1].id, exam.id, 32) for exam in exams]
        result = build_student_result(student, subjects, exams, index_marks(marks))
        assert result.subjects[0].passed is True
        assert result.subjects[1].passed is False
        assert result.passed is False
        assert result.failed_subjects == ["Mathematics"]


class TestRanking:
    def test_orders_by_weighted_percentage(self, subjects, exams) -> None:
        students = [make_student(index, f"Student {index}", index) for index in (1, 2, 3)]
        marks = []
        for student, score in zip(students, (55, 95, 75)):
            marks += [
                make_mark(student.id, subject.id, exam.id, score) for subject in subjects for exam in exams
            ]
        results = build_class_results(students, subjects, exams, marks)
        assert [result.student_id for result in results] == [2, 3, 1]
        assert [result.rank for result in results] == [1, 2, 3]

    def test_ties_share_a_rank_and_the_next_rank_skips(self, subjects, exams) -> None:
        students = [make_student(index, f"Student {index}", index) for index in (1, 2, 3, 4)]
        marks = []
        for student, score in zip(students, (80, 80, 80, 40)):
            marks += [
                make_mark(student.id, subject.id, exam.id, score) for subject in subjects for exam in exams
            ]
        results = build_class_results(students, subjects, exams, marks)
        assert [result.rank for result in results] == [1, 1, 1, 4]

    def test_students_without_marks_sort_last_and_stay_unranked(self, subjects, exams) -> None:
        with_marks = make_student(1, "Has marks", 1)
        without = make_student(2, "No marks", 2)
        marks = [make_mark(1, subject.id, exam.id, 50) for subject in subjects for exam in exams]
        results = build_class_results([without, with_marks], subjects, exams, marks)
        assert [result.student_id for result in results] == [1, 2]
        assert results[0].rank == 1
        assert results[1].rank is None

    def test_ties_are_broken_by_name_for_a_stable_order(self, subjects, exams) -> None:
        zara = make_student(1, "Zara", 1)
        aarav = make_student(2, "Aarav", 2)
        marks = [
            make_mark(student.id, subject.id, exam.id, 60)
            for student in (zara, aarav)
            for subject in subjects
            for exam in exams
        ]
        results = build_class_results([zara, aarav], subjects, exams, marks)
        assert [result.student_name for result in results] == ["Aarav", "Zara"]

    def test_assign_ranks_is_safe_on_an_empty_list(self) -> None:
        assert assign_ranks([]) == []


class TestClassSummary:
    def test_counts_and_extremes(self, subjects, exams) -> None:
        students = [make_student(index, f"Student {index}", index) for index in (1, 2, 3)]
        marks = []
        for student, score in zip(students, (90, 60, 20)):
            marks += [
                make_mark(student.id, subject.id, exam.id, score) for subject in subjects for exam in exams
            ]
        summary = class_summary(build_class_results(students, subjects, exams, marks))
        assert summary.student_count == 3
        assert summary.evaluated_count == 3
        assert summary.passed_count == 2
        assert summary.failed_count == 1
        assert summary.highest_percentage == 90.0
        assert summary.lowest_percentage == 20.0
        assert summary.average_percentage == pytest.approx(56.67, abs=0.01)
        assert summary.pass_rate == pytest.approx(66.67, abs=0.01)

    def test_summary_without_any_marks(self, subjects, exams) -> None:
        summary = class_summary(build_class_results([make_student(1, "Nobody", 1)], subjects, exams, []))
        assert summary.evaluated_count == 0
        assert summary.average_percentage is None
        assert summary.pass_rate is None


class TestCsvExport:
    def test_header_lists_every_subject(self, subjects) -> None:
        header = result_csv_header(subjects)
        assert header[:4] == ["Rank", "Roll No", "Admission No", "Student Name"]
        assert "English" in header and "Mathematics" in header
        assert header[-1] == "Result"

    def test_rows_line_up_with_the_header(self, subjects, exams) -> None:
        students = [make_student(1, "Asha", 1), make_student(2, "Nobody", 2)]
        marks = [make_mark(1, subject.id, exam.id, 75) for subject in subjects for exam in exams]
        results = build_class_results(students, subjects, exams, marks)
        rows = result_csv_rows(results, subjects)
        assert len(rows) == 2
        assert len(rows[0]) == len(result_csv_header(subjects))
        assert rows[0][0] == "1"
        assert rows[0][4] == "150/200"
        assert rows[0][-1] == "PASS"
        assert rows[1][-1] == "NO MARKS"

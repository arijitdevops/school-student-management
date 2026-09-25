"""Tests for the demo data generators and the committed MySQL dump."""

from __future__ import annotations

import random
import sys
from datetime import date
from pathlib import Path

import pytest
from faker import Faker

from app.services.seed_helpers import (
    CLASS_NUMERALS,
    EXAM_CATALOGUE,
    student_payload,
    students_per_class,
    subjects_for_class,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import export_seed_sql  # noqa: E402


@pytest.mark.parametrize("numeral", CLASS_NUMERALS)
def test_student_payload_has_every_field(numeral: int) -> None:
    rng = random.Random(numeral)
    faker = Faker("en_IN")
    Faker.seed(numeral)
    payload = student_payload(faker, rng, numeral, 1, 1, date(2025, 4, 1))
    for field in (
        "admission_number",
        "full_name",
        "roll_number",
        "date_of_birth",
        "gender",
        "blood_group",
        "guardian_name",
        "guardian_relation",
        "guardian_phone",
        "email",
        "address",
        "admission_date",
    ):
        assert payload[field], field
    assert payload["admission_date"] <= date(2025, 7, 31)
    assert payload["date_of_birth"].year == 2025 - (numeral + 5)


def test_class_strength_is_between_40_and_50() -> None:
    rng = random.Random(1)
    sizes = {students_per_class(rng) for _ in range(500)}
    assert min(sizes) >= 40 and max(sizes) <= 50


def test_sql_literal_escaping() -> None:
    assert export_seed_sql.sql_literal(None) == "NULL"
    assert export_seed_sql.sql_literal(True) == "1"
    assert export_seed_sql.sql_literal("D'Souza") == "'D''Souza'"
    assert export_seed_sql.sql_literal("a\\b") == "'a\\\\b'"
    assert export_seed_sql.sql_literal(date(2025, 4, 1)) == "'2025-04-01'"


def test_committed_dump_matches_the_seed_rules() -> None:
    """The dump in database/seed_data.sql covers classes 1-10 with 40-50 students each."""
    text = (ROOT / "database" / "seed_data.sql").read_text(encoding="utf-8")
    header = next(line for line in text.splitlines() if "students=" in line)
    counts = dict(item.split("=") for item in header.strip("- ").split(", "))
    students = int(counts["students"])
    assert int(counts["school_classes"]) == 10
    assert 400 <= students <= 500

    student_block = text.split("INSERT INTO `students`")[1].split(";\n")[0]
    rows = [line for line in student_block.splitlines() if line.startswith("(")]
    assert len(rows) == students
    per_class: dict = {}
    for row in rows:
        # school_class_id is the third column from the end, before section_id and timestamps.
        class_id = int(row.rstrip(",").rstrip(")").split(", ")[-4])
        per_class[class_id] = per_class.get(class_id, 0) + 1
    assert sorted(per_class) == list(range(1, 11))
    assert all(40 <= size <= 50 for size in per_class.values())

    subjects_per_student = {n: len(subjects_for_class(n)) for n in CLASS_NUMERALS}
    expected_marks = sum(per_class[n] * subjects_per_student[n] * len(EXAM_CATALOGUE) for n in CLASS_NUMERALS)
    assert int(counts["marks"]) == expected_marks

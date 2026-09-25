"""Catalogues and generators used to build the fictional demo dataset.

The functions here are deterministic given the random generator handed to them,
which is what lets ``scripts/seed_data.py`` reproduce the same school on every
run.  Nothing in this module touches the database; the script owns the session.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = [
    "CLASS_NUMERALS",
    "EXAM_CATALOGUE",
    "SECTION_NAMES",
    "SUBJECT_CATALOGUE",
    "ExamSpec",
    "SubjectSpec",
    "ability_factor",
    "class_name",
    "generate_score",
    "mark_scheme_for",
    "student_payload",
    "students_per_class",
    "subjects_for_class",
]

#: Classes the school runs.
CLASS_NUMERALS: Tuple[int, ...] = tuple(range(1, 11))

#: Sections every class is divided into.
SECTION_NAMES: Tuple[str, ...] = ("A", "B")


@dataclass(frozen=True)
class SubjectSpec:
    """A subject in the catalogue and the classes that study it.

    Attributes:
        code: Short unique code, used as the subject's business key.
        name: Display name.
        description: One line shown on the subjects page.
        first_class: Lowest class numeral that studies it.
        last_class: Highest class numeral that studies it.
        difficulty: Score modifier applied when generating marks.  Negative
            values make the subject harder, so the demo data has believable
            subject-to-subject variation.
    """

    code: str
    name: str
    description: str
    first_class: int
    last_class: int
    difficulty: float = 0.0

    def applies_to(self, numeral: int) -> bool:
        """Whether class ``numeral`` studies this subject."""
        return self.first_class <= numeral <= self.last_class


#: Every subject the school teaches.
SUBJECT_CATALOGUE: Tuple[SubjectSpec, ...] = (
    SubjectSpec("ENG", "English", "Language, reading comprehension and composition.", 1, 10, 0.02),
    SubjectSpec("MAT", "Mathematics", "Arithmetic, algebra, geometry and statistics.", 1, 10, -0.06),
    SubjectSpec("HIN", "Hindi", "Hindi language, grammar and literature.", 1, 10, 0.01),
    SubjectSpec(
        "EVS",
        "Environmental Studies",
        "Nature, community and basic science for the primary years.",
        1,
        5,
        0.04,
    ),
    SubjectSpec(
        "SCI", "Science", "Physics, chemistry and biology for the middle and senior years.", 6, 10, -0.03
    ),
    SubjectSpec("SST", "Social Studies", "History, civics, geography and economics.", 6, 10, -0.01),
    SubjectSpec(
        "CSC",
        "Computer Science",
        "Computer fundamentals, spreadsheets and introductory programming.",
        6,
        10,
        0.03,
    ),
)


@dataclass(frozen=True)
class ExamSpec:
    """An exam in the academic calendar.

    Attributes:
        code: Short unique code within the academic year.
        name: Display name.
        sequence: Order within the year.
        weightage: Share of the final aggregate, in percent.
        month_offset: Months after the start of the academic year when it is held.
        difficulty: Score modifier; later exams are set slightly harder.
    """

    code: str
    name: str
    sequence: int
    weightage: float
    month_offset: int
    difficulty: float = 0.0


#: The four assessments held each year.  The weightages add up to 100.
EXAM_CATALOGUE: Tuple[ExamSpec, ...] = (
    ExamSpec("UT1", "Unit Test 1", 1, 10.0, 2, 0.03),
    ExamSpec("HY", "Half Yearly", 2, 30.0, 5, -0.01),
    ExamSpec("UT2", "Unit Test 2", 3, 10.0, 8, 0.02),
    ExamSpec("ANN", "Annual", 4, 50.0, 10, -0.03),
)


def class_name(numeral: int) -> str:
    """Return the display name for a class numeral, for example ``Class 7``."""
    return f"Class {numeral}"


def subjects_for_class(numeral: int) -> List[SubjectSpec]:
    """Return the subjects studied by class ``numeral``."""
    return [spec for spec in SUBJECT_CATALOGUE if spec.applies_to(numeral)]


def mark_scheme_for(numeral: int) -> Tuple[int, int]:
    """Return ``(max_marks, pass_marks)`` for a class.

    Primary classes (1 to 5) are assessed out of 50 with 17 to pass; classes 6
    to 10 are assessed out of 100 with 33 to pass.
    """
    if numeral <= 5:
        return 50, 17
    return 100, 33


def students_per_class(rng: random.Random) -> int:
    """Return a class strength between 40 and 50 inclusive."""
    return rng.randint(40, 50)


def ability_factor(rng: random.Random) -> float:
    """Return a per-student ability between 0.25 and 0.99.

    Marks are generated from this factor plus noise, so a strong student stays
    strong across subjects and exams and class rankings become meaningful
    instead of random.
    """
    return min(0.99, max(0.25, rng.gauss(0.68, 0.15)))


def generate_score(
    rng: random.Random,
    ability: float,
    max_marks: int,
    subject_difficulty: float = 0.0,
    exam_difficulty: float = 0.0,
    absence_probability: float = 0.015,
) -> Optional[float]:
    """Generate one plausible score.

    Args:
        rng: Seeded random generator.
        ability: The student's ability factor from :func:`ability_factor`.
        max_marks: The paper's maximum.
        subject_difficulty: Modifier from :class:`SubjectSpec`.
        exam_difficulty: Modifier from :class:`ExamSpec`.
        absence_probability: Chance the student was absent.

    Returns:
        A score clamped to ``0..max_marks``, or ``None`` when the student was
        absent.
    """
    if rng.random() < absence_probability:
        return None
    fraction = ability + subject_difficulty + exam_difficulty + rng.gauss(0.0, 0.08)
    fraction = min(1.0, max(0.0, fraction))
    return float(min(max_marks, max(0, round(fraction * max_marks))))


def _random_date(rng: random.Random, earliest: date, latest: date) -> date:
    """Return a date uniformly chosen between two bounds, inclusive."""
    span = (latest - earliest).days
    if span <= 0:
        return earliest
    return earliest + timedelta(days=rng.randint(0, span))


def student_payload(
    faker: object,
    rng: random.Random,
    numeral: int,
    roll_number: int,
    admission_sequence: int,
    year_start: date,
) -> Dict[str, object]:
    """Build the field values for one fictional student.

    Args:
        faker: A seeded ``Faker`` instance.
        rng: Seeded random generator, used for everything Faker does not cover.
        numeral: The class the student joins.
        roll_number: Roll number, unique within the class and section.
        admission_sequence: Running number used to build the admission number.
        year_start: First day of the academic year.

    Returns:
        A dictionary matching the columns of :class:`app.models.student.Student`.
    """
    gender = rng.choice(["F", "M", "O"] if rng.random() < 0.02 else ["F", "M"])
    if gender == "F":
        full_name = faker.name_female()  # type: ignore[attr-defined]
    else:
        full_name = faker.name_male()  # type: ignore[attr-defined]

    # The parent shares the child's surname; fathers are listed a little more
    # often than mothers, and a few students have another guardian.
    surname = full_name.split()[-1]
    relation = rng.choices(["Father", "Mother", "Guardian"], weights=[60, 35, 5])[0]
    if relation == "Mother":
        guardian_first = faker.first_name_female()  # type: ignore[attr-defined]
    else:
        guardian_first = faker.first_name_male()  # type: ignore[attr-defined]
    guardian_name = f"{guardian_first} {surname}"
    blood_group = rng.choices(
        ["O+", "B+", "A+", "AB+", "O-", "B-", "A-", "AB-"], weights=[37, 32, 22, 7, 1, 1, 0.5, 0.5]
    )[0]

    # A child in class N is typically N + 5 years old at the start of the year.
    expected_age = numeral + 5
    birth_year = year_start.year - expected_age
    date_of_birth = _random_date(rng, date(birth_year, 1, 1), date(birth_year, 12, 31))

    # Students join in class 1 unless they transferred in later.
    joined_in_class = 1 if numeral == 1 or rng.random() < 0.8 else rng.randint(2, numeral)
    admission_year = year_start.year - (numeral - joined_in_class)
    admission_date = _random_date(rng, date(admission_year, 4, 1), date(admission_year, 7, 31))

    slug = full_name.lower().replace(" ", ".").replace("'", "")
    return {
        "admission_number": f"ADM{year_start.year}{admission_sequence:04d}",
        "full_name": full_name,
        "roll_number": roll_number,
        "date_of_birth": date_of_birth,
        "gender": gender,
        "blood_group": blood_group,
        "guardian_name": guardian_name,
        "guardian_relation": relation,
        "guardian_phone": f"9{rng.randint(100000000, 999999999)}",
        "email": f"{slug}.{admission_sequence}@example.edu",
        "address": faker.address().replace("\n", ", "),  # type: ignore[attr-defined]
        "admission_date": admission_date,
        # A small share of the roll has left the school and is kept as an
        # inactive record so the soft-delete and restore flows have real data.
        "is_active": rng.random() > 0.03,
    }


def exam_dates(year_start: date, specs: Sequence[ExamSpec] = EXAM_CATALOGUE) -> Dict[str, date]:
    """Return the date each exam is held, keyed by exam code."""
    dates: Dict[str, date] = {}
    for spec in specs:
        month_index = year_start.month - 1 + spec.month_offset
        year = year_start.year + month_index // 12
        month = month_index % 12 + 1
        dates[spec.code] = date(year, month, 15)
    return dates

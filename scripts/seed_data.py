#!/usr/bin/env python3
"""Populate the database with a reproducible, fictional school.

Every value is generated from a fixed seed, so two runs produce the same school:
the same names, the same marks and therefore the same rankings.  The script is
idempotent - running it twice does not duplicate anything - and ``--reset``
drops the schema first for a clean start.

Usage::

    python scripts/seed_data.py
    python scripts/seed_data.py --reset
    python scripts/seed_data.py --seed 99 --year 2026-2027

The same data is committed as a MySQL dump in ``database/seed_data.sql``
(regenerate it with ``python scripts/export_seed_sql.py``).
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import (  # noqa: E402
    AcademicYear,
    ClassSubject,
    Exam,
    Mark,
    SchoolClass,
    Section,
    Student,
    Subject,
)
from app.services.seed_helpers import (  # noqa: E402
    CLASS_NUMERALS,
    EXAM_CATALOGUE,
    SECTION_NAMES,
    SUBJECT_CATALOGUE,
    ability_factor,
    class_name,
    exam_dates,
    generate_score,
    mark_scheme_for,
    student_payload,
    students_per_class,
    subjects_for_class,
)

LOGGER = logging.getLogger("seed")

#: How many Mark objects to accumulate before flushing them to the session.
MARK_FLUSH_SIZE = 2000

#: Default random seed and academic year.  Both are fixed so that the seeded
#: database matches the committed dump in database/seed_data.sql.
DEFAULT_SEED = 20250401
DEFAULT_YEAR = "2025-2026"


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED, help=f"Random seed (default: {DEFAULT_SEED})."
    )
    parser.add_argument(
        "--year", default=DEFAULT_YEAR, help=f"Academic year label (default: {DEFAULT_YEAR})."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate every table before seeding. This destroys all data.",
    )
    parser.add_argument("--config", default=None, help="Configuration name to load.")
    parser.add_argument("--quiet", action="store_true", help="Only report the final counts.")
    return parser.parse_args(argv)


def ensure_academic_year(label: str) -> AcademicYear:
    """Fetch or create the academic year and mark it as the current one."""
    year = db.session.scalar(select(AcademicYear).where(AcademicYear.name == label))
    start_year = int(label.split("-")[0])
    if year is None:
        year = AcademicYear(
            name=label,
            start_date=date(start_year, 4, 1),
            end_date=date(start_year + 1, 3, 31),
            is_current=True,
        )
        db.session.add(year)
        db.session.flush()
        LOGGER.info("Created academic year %s", label)

    for other in db.session.scalars(select(AcademicYear).where(AcademicYear.id != year.id)).all():
        other.is_current = False
    year.is_current = True
    return year


def ensure_classes_and_sections() -> Dict[int, SchoolClass]:
    """Fetch or create classes 1 to 10, each with sections A and B."""
    classes: Dict[int, SchoolClass] = {}
    for numeral in CLASS_NUMERALS:
        school_class = db.session.scalar(select(SchoolClass).where(SchoolClass.numeral == numeral))
        if school_class is None:
            school_class = SchoolClass(numeral=numeral, name=class_name(numeral))
            db.session.add(school_class)
            db.session.flush()
        existing = {section.name for section in school_class.sections}
        for index, section_name in enumerate(SECTION_NAMES):
            if section_name in existing:
                continue
            # Append through the relationship (not just session.add) so that
            # school_class.sections is up to date for seed_students().
            school_class.sections.append(
                Section(name=section_name, room=f"{numeral}{index + 1:02d}", capacity=50)
            )
        classes[numeral] = school_class
    db.session.flush()
    return classes


def ensure_subjects() -> Dict[str, Subject]:
    """Fetch or create every subject in the catalogue, keyed by code."""
    subjects: Dict[str, Subject] = {}
    for spec in SUBJECT_CATALOGUE:
        subject = db.session.scalar(select(Subject).where(Subject.code == spec.code))
        if subject is None:
            subject = Subject(code=spec.code, name=spec.name, description=spec.description, is_active=True)
            db.session.add(subject)
        subjects[spec.code] = subject
    db.session.flush()
    return subjects


def ensure_class_subjects(
    classes: Dict[int, SchoolClass], subjects: Dict[str, Subject]
) -> Dict[Tuple[int, str], ClassSubject]:
    """Map every class to the subjects it studies, with the right mark scheme."""
    mapping: Dict[Tuple[int, str], ClassSubject] = {}
    for numeral, school_class in classes.items():
        max_marks, pass_marks = mark_scheme_for(numeral)
        for spec in subjects_for_class(numeral):
            subject = subjects[spec.code]
            class_subject = db.session.scalar(
                select(ClassSubject).where(
                    ClassSubject.school_class_id == school_class.id,
                    ClassSubject.subject_id == subject.id,
                )
            )
            if class_subject is None:
                class_subject = ClassSubject(
                    school_class_id=school_class.id,
                    subject_id=subject.id,
                    max_marks=max_marks,
                    pass_marks=pass_marks,
                )
                db.session.add(class_subject)
                db.session.flush()
            mapping[(numeral, spec.code)] = class_subject
    return mapping


def ensure_exams(year: AcademicYear) -> List[Exam]:
    """Fetch or create the four exams of the academic year."""
    dates = exam_dates(year.start_date)
    exams: List[Exam] = []
    for spec in EXAM_CATALOGUE:
        exam = db.session.scalar(select(Exam).where(Exam.academic_year_id == year.id, Exam.code == spec.code))
        if exam is None:
            exam = Exam(
                academic_year_id=year.id,
                code=spec.code,
                name=spec.name,
                sequence=spec.sequence,
                weightage=spec.weightage,
                held_on=dates[spec.code],
            )
            db.session.add(exam)
            db.session.flush()
        exams.append(exam)
    return exams


def seed_students(
    faker: object,
    rng: random.Random,
    classes: Dict[int, SchoolClass],
    year: AcademicYear,
) -> Tuple[List[Student], int]:
    """Create 40 to 50 students in each class that does not have any yet.

    Returns:
        Every student now on the roll, and how many were created by this run.
    """
    created = 0
    admission_sequence = (db.session.scalar(select(db.func.count()).select_from(Student)) or 0) + 1

    for numeral in sorted(classes):
        school_class = classes[numeral]
        existing = (
            db.session.scalar(
                select(db.func.count()).select_from(Student).where(Student.school_class_id == school_class.id)
            )
            or 0
        )
        if existing:
            LOGGER.debug("%s already has %d students; skipping", school_class.name, existing)
            continue

        strength = students_per_class(rng)
        sections = sorted(school_class.sections, key=lambda section: section.name)
        for index in range(strength):
            section = sections[index % len(sections)]
            roll_number = index // len(sections) + 1
            payload = student_payload(
                faker=faker,
                rng=rng,
                numeral=numeral,
                roll_number=roll_number,
                admission_sequence=admission_sequence,
                year_start=year.start_date,
            )
            db.session.add(
                Student(
                    school_class_id=school_class.id,
                    section_id=section.id,
                    **payload,
                )
            )
            admission_sequence += 1
            created += 1
        LOGGER.info("%s: created %d students", school_class.name, strength)
        db.session.flush()

    students = list(db.session.scalars(select(Student)).all())
    return students, created


def seed_marks(
    rng: random.Random,
    students: List[Student],
    class_subjects: Dict[Tuple[int, str], ClassSubject],
    exams: List[Exam],
) -> int:
    """Generate marks for every student, subject and exam that lacks one.

    Each student is given an ability factor once, so a strong student scores
    consistently well across subjects and exams and the class ranking means
    something.
    """
    exam_specs = {spec.code: spec for spec in EXAM_CATALOGUE}
    subject_specs = {spec.code: spec for spec in SUBJECT_CATALOGUE}

    existing_keys = {
        tuple(row) for row in db.session.execute(select(Mark.student_id, Mark.class_subject_id, Mark.exam_id))
    }
    numeral_by_class_id = {
        school_class.id: school_class.numeral
        for school_class in db.session.scalars(select(SchoolClass)).all()
    }

    pending: List[Mark] = []
    created = 0

    for student in students:
        ability = ability_factor(rng)
        numeral = numeral_by_class_id[student.school_class_id]
        for spec in subjects_for_class(numeral):
            class_subject = class_subjects.get((numeral, spec.code))
            if class_subject is None:
                continue
            subject_difficulty = subject_specs[spec.code].difficulty
            for exam in exams:
                key = (student.id, class_subject.id, exam.id)
                if key in existing_keys:
                    continue
                exam_spec = exam_specs.get(exam.code)
                score = generate_score(
                    rng=rng,
                    ability=ability,
                    max_marks=class_subject.max_marks,
                    subject_difficulty=subject_difficulty,
                    exam_difficulty=exam_spec.difficulty if exam_spec else 0.0,
                )
                mark = Mark(
                    student_id=student.id,
                    class_subject_id=class_subject.id,
                    exam_id=exam.id,
                )
                mark.set_score(score, class_subject.max_marks)
                pending.append(mark)
                created += 1

        if len(pending) >= MARK_FLUSH_SIZE:
            db.session.add_all(pending)
            db.session.flush()
            pending = []

    if pending:
        db.session.add_all(pending)
        db.session.flush()
    return created


def report_counts() -> None:
    """Log one row per table with its current size."""
    for model in (AcademicYear, SchoolClass, Section, Subject, ClassSubject, Exam, Student, Mark):
        count = db.session.scalar(select(db.func.count()).select_from(model)) or 0
        LOGGER.info("%-16s %6d", model.__tablename__, count)


class SeedResult(NamedTuple):
    """What a seeding run created."""

    year_label: str
    new_students: int
    new_marks: int


def seed_database(seed: int = DEFAULT_SEED, year_label: str = DEFAULT_YEAR) -> SeedResult:
    """Create the demo school inside the current application context.

    The caller owns the transaction: nothing is committed here.

    Raises:
        ImportError: Faker is not installed.
    """
    from faker import Faker

    rng = random.Random(seed)
    faker = Faker("en_IN")
    Faker.seed(seed)

    year = ensure_academic_year(year_label)
    classes = ensure_classes_and_sections()
    subjects = ensure_subjects()
    class_subjects = ensure_class_subjects(classes, subjects)
    exams = ensure_exams(year)
    students, new_students = seed_students(faker, rng, classes, year)
    new_marks = seed_marks(rng, students, class_subjects, exams)
    return SeedResult(year_label, new_students, new_marks)


def main(argv: List[str] | None = None) -> int:
    """Seed the database and report what is in it afterwards."""
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)-8s %(message)s",
    )

    try:
        import faker  # noqa: F401
    except ImportError:
        LOGGER.error("Faker is not installed. Run: pip install -r requirements.txt")
        return 1

    app = create_app(args.config)
    with app.app_context():
        try:
            if args.reset:
                LOGGER.warning("Dropping every table before seeding")
                db.drop_all()
            db.create_all()
            result = seed_database(args.seed, args.year)
            db.session.commit()
        except SQLAlchemyError as error:
            db.session.rollback()
            LOGGER.error("Seeding failed and was rolled back: %s", error)
            LOGGER.error("Check DATABASE_URL and that the database exists.")
            return 1

        logging.getLogger("seed").setLevel(logging.INFO)
        LOGGER.info("-" * 32)
        LOGGER.info("Academic year:   %s", result.year_label)
        LOGGER.info("New students:    %d", result.new_students)
        LOGGER.info("New marks:       %d", result.new_marks)
        LOGGER.info("-" * 32)
        report_counts()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Shared pytest fixtures.

The suite runs against an in-memory SQLite database created through the
``testing`` configuration, so no MySQL server is needed.  Only the plain SQL the
application actually issues is exercised; MySQL-specific behaviour (such as the
``CHECK`` constraints) is not.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.extensions import db
from app.models import (
    AcademicYear,
    ClassSubject,
    Exam,
    Mark,
    SchoolClass,
    Section,
    Student,
    Subject,
)


@pytest.fixture()
def app() -> Iterator[Flask]:
    """An application bound to a fresh in-memory database, pre-seeded."""
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        seed_fixture_data()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    """A test client for the seeded application."""
    return app.test_client()


@pytest.fixture()
def seeded(app: Flask) -> Dict[str, object]:
    """Handy references to the seeded rows, looked up by their business keys."""
    return {
        "year": db.session.query(AcademicYear).one(),
        "school_class": db.session.query(SchoolClass).filter_by(numeral=6).one(),
        "section_a": db.session.query(Section).filter_by(name="A").one(),
        "section_b": db.session.query(Section).filter_by(name="B").one(),
        "students": db.session.query(Student).order_by(Student.roll_number).all(),
        "exams": db.session.query(Exam).order_by(Exam.sequence).all(),
        "class_subjects": db.session.query(ClassSubject).order_by(ClassSubject.id).all(),
    }


def seed_fixture_data() -> None:
    """Create one class, two sections, three subjects, two exams and four students."""
    year = AcademicYear(
        name="2025-2026",
        start_date=date(2025, 4, 1),
        end_date=date(2026, 3, 31),
        is_current=True,
    )
    school_class = SchoolClass(numeral=6, name="Class 6")
    db.session.add_all([year, school_class])
    db.session.flush()

    section_a = Section(school_class_id=school_class.id, name="A", room="601", capacity=40)
    section_b = Section(school_class_id=school_class.id, name="B", room="602", capacity=40)
    db.session.add_all([section_a, section_b])

    subjects = [
        Subject(code="ENG", name="English", description="Language."),
        Subject(code="MAT", name="Mathematics", description="Numbers."),
        Subject(code="SCI", name="Science", description="Experiments."),
    ]
    db.session.add_all(subjects)
    db.session.flush()

    class_subjects = [
        ClassSubject(
            school_class_id=school_class.id,
            subject_id=subject.id,
            max_marks=100,
            pass_marks=33,
        )
        for subject in subjects
    ]
    exams = [
        Exam(
            academic_year_id=year.id,
            code="UT1",
            name="Unit Test 1",
            sequence=1,
            weightage=40,
            held_on=date(2025, 7, 15),
        ),
        Exam(
            academic_year_id=year.id,
            code="ANN",
            name="Annual",
            sequence=2,
            weightage=60,
            held_on=date(2026, 2, 15),
        ),
    ]
    db.session.add_all(class_subjects + exams)
    db.session.flush()

    # Four students with deliberately chosen marks: two tie at the top, one
    # fails a subject, and one has no marks at all.
    profiles = [
        ("Aarav Sharma", "ADM0001", 1, section_a, [90, 90, 90]),
        ("Bhavna Iyer", "ADM0002", 2, section_a, [90, 90, 90]),
        ("Chirag Nair", "ADM0003", 3, section_b, [70, 20, 60]),
        ("Divya Rao", "ADM0004", 4, section_b, None),
    ]
    for name, admission_number, roll, section, scores in profiles:
        student = Student(
            admission_number=admission_number,
            full_name=name,
            roll_number=roll,
            date_of_birth=date(2013, 6, 12),
            gender="F" if roll % 2 == 0 else "M",
            guardian_name="Guardian of " + name.split()[0],
            guardian_phone=f"9800000{roll:03d}",
            email=f"{admission_number.lower()}@example.edu",
            address="12 Example Street",
            admission_date=date(2019, 4, 10),
            is_active=True,
            school_class_id=school_class.id,
            section_id=section.id,
        )
        db.session.add(student)
        db.session.flush()
        if scores is None:
            continue
        for class_subject, score in zip(class_subjects, scores):
            for exam in exams:
                mark = Mark(
                    student_id=student.id,
                    class_subject_id=class_subject.id,
                    exam_id=exam.id,
                )
                mark.set_score(score, class_subject.max_marks)
                db.session.add(mark)

    db.session.commit()

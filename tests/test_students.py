"""Route-level tests for the student pages and the reports they link to.

They run against the seeded in-memory SQLite database from ``conftest.py`` with
CSRF protection disabled by the testing configuration.
"""

from __future__ import annotations

from typing import Dict

from flask import Flask
from flask.testing import FlaskClient

from app.extensions import db
from app.models import SchoolClass, Section, Student


def student_payload(section_id: int, school_class_id: int, **overrides: object) -> Dict[str, object]:
    """Return a complete, valid payload for the student form."""
    payload: Dict[str, object] = {
        "admission_number": "ADM9001",
        "full_name": "Ishaan Verma",
        "school_class_id": school_class_id,
        "section_id": section_id,
        "roll_number": 41,
        "date_of_birth": "2013-05-04",
        "gender": "M",
        "blood_group": "B+",
        "guardian_name": "Rekha Verma",
        "guardian_relation": "Mother",
        "guardian_phone": "9876543210",
        "email": "ishaan.verma@example.edu",
        "address": "44 Example Road",
        "admission_date": "2019-04-10",
        "is_active": "y",
        "submit": "Save student",
    }
    payload.update(overrides)
    return payload


class TestStudentList:
    def test_lists_the_seeded_students(self, client: FlaskClient) -> None:
        response = client.get("/students/")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Aarav Sharma" in body
        assert "ADM0001" in body

    def test_search_narrows_the_list(self, client: FlaskClient) -> None:
        body = client.get("/students/?q=Chirag").get_data(as_text=True)
        assert "Chirag Nair" in body
        assert "Aarav Sharma" not in body

    def test_search_matches_the_guardian(self, client: FlaskClient) -> None:
        body = client.get("/students/?q=Guardian of Divya").get_data(as_text=True)
        assert "Divya Rao" in body

    def test_filter_by_section(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        section_b = seeded["section_b"]
        body = client.get(f"/students/?section_id={section_b.id}").get_data(as_text=True)
        assert "Chirag Nair" in body
        assert "Aarav Sharma" not in body

    def test_status_filter_hides_former_students(self, app: Flask, client: FlaskClient) -> None:
        student = db.session.query(Student).filter_by(admission_number="ADM0003").one()
        student.deactivate()
        db.session.commit()

        assert "Chirag Nair" not in client.get("/students/").get_data(as_text=True)
        assert "Chirag Nair" in client.get("/students/?status=inactive").get_data(as_text=True)
        assert "Chirag Nair" in client.get("/students/?status=all").get_data(as_text=True)

    def test_pagination_controls_appear_when_needed(self, app: Flask, client: FlaskClient) -> None:
        app.config["ITEMS_PER_PAGE"] = 2
        body = client.get("/students/").get_data(as_text=True)
        assert "page=2" in body


class TestStudentDetail:
    def test_shows_the_record_and_marks(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        student = seeded["students"][0]
        body = client.get(f"/students/{student.id}").get_data(as_text=True)
        assert student.full_name in body
        assert "Unit Test 1" in body

    def test_missing_student_is_a_404(self, client: FlaskClient) -> None:
        response = client.get("/students/99999")
        assert response.status_code == 404
        assert "does not exist" in response.get_data(as_text=True)


class TestCreateStudent:
    def test_creates_a_student(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        section = seeded["section_a"]
        response = client.post(
            "/students/new",
            data=student_payload(section.id, section.school_class_id),
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "was added" in response.get_data(as_text=True)
        student = db.session.query(Student).filter_by(admission_number="ADM9001").one()
        assert student.blood_group == "B+"
        assert student.guardian_relation == "Mother"

    def test_rejects_a_duplicate_admission_number(
        self, client: FlaskClient, seeded: Dict[str, object]
    ) -> None:
        section = seeded["section_a"]
        response = client.post(
            "/students/new",
            data=student_payload(section.id, section.school_class_id, admission_number="ADM0001"),
        )
        assert response.status_code == 200
        assert "already uses this admission number" in response.get_data(as_text=True)
        assert db.session.query(Student).count() == 4

    def test_rejects_a_duplicate_roll_number_in_the_same_section(
        self, client: FlaskClient, seeded: Dict[str, object]
    ) -> None:
        section = seeded["section_a"]
        response = client.post(
            "/students/new",
            data=student_payload(section.id, section.school_class_id, roll_number=1),
        )
        assert "already used in this class and section" in response.get_data(as_text=True)

    def test_rejects_a_section_from_another_class(
        self, app: Flask, client: FlaskClient, seeded: Dict[str, object]
    ) -> None:
        other_class = SchoolClass(numeral=7, name="Class 7")
        db.session.add(other_class)
        db.session.flush()
        db.session.add(Section(school_class_id=other_class.id, name="A", capacity=40))
        db.session.commit()

        section = seeded["section_a"]
        response = client.post(
            "/students/new",
            data=student_payload(section.id, other_class.id),
        )
        assert "belongs to a different class" in response.get_data(as_text=True)

    def test_rejects_a_future_date_of_birth(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        section = seeded["section_a"]
        response = client.post(
            "/students/new",
            data=student_payload(section.id, section.school_class_id, date_of_birth="2099-01-01"),
        )
        assert "must be in the past" in response.get_data(as_text=True)

    def test_rejects_a_bad_phone_number(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        section = seeded["section_a"]
        response = client.post(
            "/students/new",
            data=student_payload(section.id, section.school_class_id, guardian_phone="abc"),
        )
        assert "phone number" in response.get_data(as_text=True)


class TestEditStudent:
    def test_updates_the_record(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        student = seeded["students"][0]
        response = client.post(
            f"/students/{student.id}/edit",
            data=student_payload(
                student.section_id,
                student.school_class_id,
                admission_number=student.admission_number,
                full_name="Aarav S. Sharma",
                roll_number=student.roll_number,
            ),
            follow_redirects=True,
        )
        assert "was updated" in response.get_data(as_text=True)
        assert db.session.get(Student, student.id).full_name == "Aarav S. Sharma"

    def test_keeping_its_own_admission_number_is_allowed(
        self, client: FlaskClient, seeded: Dict[str, object]
    ) -> None:
        student = seeded["students"][1]
        response = client.post(
            f"/students/{student.id}/edit",
            data=student_payload(
                student.section_id,
                student.school_class_id,
                admission_number=student.admission_number,
                full_name=student.full_name,
                roll_number=student.roll_number,
            ),
            follow_redirects=True,
        )
        assert "already uses this admission number" not in response.get_data(as_text=True)


class TestSoftDelete:
    def test_deactivate_then_restore(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        student = seeded["students"][2]

        response = client.post(f"/students/{student.id}/deactivate", follow_redirects=True)
        assert response.status_code == 200
        assert db.session.get(Student, student.id).is_active is False

        response = client.post(f"/students/{student.id}/restore", follow_redirects=True)
        assert response.status_code == 200
        assert db.session.get(Student, student.id).is_active is True

    def test_marks_survive_a_soft_delete(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        student = seeded["students"][0]
        before = student.marks.count()
        client.post(f"/students/{student.id}/deactivate", follow_redirects=True)
        assert db.session.get(Student, student.id).marks.count() == before

    def test_get_is_not_allowed(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        student = seeded["students"][0]
        assert client.get(f"/students/{student.id}/deactivate").status_code == 405


class TestSupportingRoutes:
    def test_dashboard(self, client: FlaskClient) -> None:
        body = client.get("/").get_data(as_text=True)
        assert "Dashboard" in body
        assert "Class 6" in body

    def test_health_check(self, client: FlaskClient) -> None:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.get_json() == {"status": "ok", "database": "reachable"}

    def test_report_card_shows_the_rank(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        student = seeded["students"][0]
        body = client.get(f"/reports/student/{student.id}").get_data(as_text=True)
        assert "Report card" in body
        assert "Mathematics" in body

    def test_printable_report_card(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        student = seeded["students"][0]
        body = client.get(f"/reports/student/{student.id}/print").get_data(as_text=True)
        assert "Progress report" in body
        assert "Principal" in body

    def test_class_result_list(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        school_class = seeded["school_class"]
        body = client.get(f"/reports/class/{school_class.id}").get_data(as_text=True)
        assert "result list" in body
        assert "Aarav Sharma" in body

    def test_class_result_csv_export(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        school_class = seeded["school_class"]
        response = client.get(f"/reports/class/{school_class.id}/export.csv")
        assert response.status_code == 200
        assert response.mimetype == "text/csv"
        assert "attachment" in response.headers["Content-Disposition"]
        rows = response.get_data(as_text=True).strip().splitlines()
        assert rows[0].startswith("Rank,Roll No,Admission No,Student Name")
        assert len(rows) == 5  # one header plus four students


class TestMarkEntry:
    def test_grid_lists_the_class(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        class_subject = seeded["class_subjects"][0]
        exam = seeded["exams"][0]
        body = client.get(f"/marks/entry?class_subject_id={class_subject.id}&exam_id={exam.id}").get_data(
            as_text=True
        )
        assert "Aarav Sharma" in body
        assert "Divya Rao" in body

    def test_saving_updates_existing_marks(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        class_subject = seeded["class_subjects"][0]
        exam = seeded["exams"][0]
        student = seeded["students"][0]
        response = client.post(
            f"/marks/entry?class_subject_id={class_subject.id}&exam_id={exam.id}",
            data={f"mark-{student.id}": "77", "submit": "Save marks"},
            follow_redirects=True,
        )
        assert "Saved" in response.get_data(as_text=True)
        refreshed = db.session.get(Student, student.id)
        saved = [
            item
            for item in refreshed.marks
            if item.class_subject_id == class_subject.id and item.exam_id == exam.id
        ]
        assert saved and float(saved[0].marks_obtained) == 77.0

    def test_out_of_range_marks_are_rejected(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        class_subject = seeded["class_subjects"][0]
        exam = seeded["exams"][0]
        student = seeded["students"][0]
        response = client.post(
            f"/marks/entry?class_subject_id={class_subject.id}&exam_id={exam.id}",
            data={f"mark-{student.id}": "150", "submit": "Save marks"},
            follow_redirects=True,
        )
        assert "must be between 0 and 100" in response.get_data(as_text=True)

    def test_non_numeric_marks_are_rejected(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        class_subject = seeded["class_subjects"][0]
        exam = seeded["exams"][0]
        student = seeded["students"][0]
        response = client.post(
            f"/marks/entry?class_subject_id={class_subject.id}&exam_id={exam.id}",
            data={f"mark-{student.id}": "eighty", "submit": "Save marks"},
            follow_redirects=True,
        )
        assert "is not a number" in response.get_data(as_text=True)

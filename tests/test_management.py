"""Route tests for permanent deletion, the subject catalogue and per-student marks."""

from __future__ import annotations

from typing import Dict

from flask.testing import FlaskClient

from app.extensions import db
from app.models import ClassSubject, Mark, Student, Subject


class TestPermanentDelete:
    def test_deletes_the_student_and_their_marks(
        self, client: FlaskClient, seeded: Dict[str, object]
    ) -> None:
        student = seeded["students"][0]
        student_id = student.id
        assert db.session.query(Mark).filter_by(student_id=student_id).count() == 6

        response = client.post(f"/students/{student_id}/delete", follow_redirects=True)

        assert response.status_code == 200
        assert "permanently deleted" in response.get_data(as_text=True)
        db.session.expire_all()
        assert db.session.get(Student, student_id) is None
        assert db.session.query(Mark).filter_by(student_id=student_id).count() == 0

    def test_get_is_not_allowed(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        student = seeded["students"][0]
        assert client.get(f"/students/{student.id}/delete").status_code == 405

    def test_unknown_student_is_a_404(self, client: FlaskClient) -> None:
        assert client.post("/students/9999/delete").status_code == 404


class TestSubjects:
    def test_add_and_edit_a_subject(self, client: FlaskClient) -> None:
        response = client.post(
            "/subjects/new",
            data={"code": "SAN", "name": "Sanskrit", "description": "Classical language.", "is_active": "y"},
        )
        assert response.status_code == 302
        subject = db.session.query(Subject).filter_by(code="SAN").one()

        response = client.post(
            f"/subjects/{subject.id}/edit",
            data={"code": "SKT", "name": "Sanskrit Language", "description": "", "is_active": "y"},
        )
        assert response.status_code == 302
        db.session.expire_all()
        subject = db.session.get(Subject, subject.id)
        assert (subject.code, subject.name, subject.description) == ("SKT", "Sanskrit Language", None)

    def test_duplicate_code_is_rejected(self, client: FlaskClient) -> None:
        response = client.post("/subjects/new", data={"code": "ENG", "name": "Another English"})
        assert response.status_code == 200
        assert db.session.query(Subject).filter_by(name="Another English").count() == 0

    def test_assign_a_subject_to_a_class(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        client.post("/subjects/new", data={"code": "ART", "name": "Art", "is_active": "y"})
        art = db.session.query(Subject).filter_by(code="ART").one()
        response = client.post(
            "/subjects/assign",
            data={
                "school_class_id": seeded["school_class"].id,
                "subject_id": art.id,
                "max_marks": 50,
                "pass_marks": 17,
            },
        )
        assert response.status_code == 302
        assignment = db.session.query(ClassSubject).filter_by(subject_id=art.id).one()
        assert (assignment.max_marks, assignment.pass_marks) == (50, 17)

    def test_delete_removes_assignments_and_marks(self, client: FlaskClient) -> None:
        english = db.session.query(Subject).filter_by(code="ENG").one()
        assignment_ids = [assignment.id for assignment in english.class_subjects]
        assert db.session.query(Mark).filter(Mark.class_subject_id.in_(assignment_ids)).count() == 6

        response = client.post(f"/subjects/{english.id}/delete", follow_redirects=True)

        assert response.status_code == 200
        assert "English was removed" in response.get_data(as_text=True)
        db.session.expire_all()
        assert db.session.query(Subject).filter_by(code="ENG").count() == 0
        assert db.session.query(ClassSubject).filter(ClassSubject.id.in_(assignment_ids)).count() == 0
        assert db.session.query(Mark).filter(Mark.class_subject_id.in_(assignment_ids)).count() == 0
        # The other subjects' marks are untouched.
        assert db.session.query(Mark).count() == 12

    def test_remove_assignment_deletes_its_marks(
        self, client: FlaskClient, seeded: Dict[str, object]
    ) -> None:
        assignment = seeded["class_subjects"][1]
        assignment_id = assignment.id

        response = client.post(f"/subjects/assignments/{assignment_id}/remove")

        assert response.status_code == 302
        db.session.expire_all()
        assert db.session.get(ClassSubject, assignment_id) is None
        assert db.session.query(Mark).filter_by(class_subject_id=assignment_id).count() == 0

    def test_report_card_still_renders_after_a_subject_is_deleted(
        self, client: FlaskClient, seeded: Dict[str, object]
    ) -> None:
        science = db.session.query(Subject).filter_by(code="SCI").one()
        client.post(f"/subjects/{science.id}/delete", follow_redirects=True)  # consumes the flash
        student = seeded["students"][0]
        response = client.get(f"/reports/student/{student.id}")
        assert response.status_code == 200
        assert "Science" not in response.get_data(as_text=True)


class TestStudentMarks:
    def test_add_and_edit_marks_for_one_student(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        student = seeded["students"][3]  # has no marks yet
        exam = seeded["exams"][0]
        class_subjects = seeded["class_subjects"]
        url = f"/marks/student/{student.id}?exam_id={exam.id}"

        assert client.get(url).status_code == 200
        form = {f"mark-{cs.id}": "64" for cs in class_subjects}
        form[f"absent-{class_subjects[2].id}"] = "on"
        assert client.post(url, data=form).status_code == 302

        marks = db.session.query(Mark).filter_by(student_id=student.id, exam_id=exam.id).all()
        assert len(marks) == 3
        assert sorted(mark.display_score for mark in marks) == ["64", "64", "AB"]

        form = {f"mark-{cs.id}": "72.5" for cs in class_subjects}
        assert client.post(url, data=form).status_code == 302
        db.session.expire_all()
        marks = db.session.query(Mark).filter_by(student_id=student.id, exam_id=exam.id).all()
        assert {mark.score for mark in marks} == {72.5}

    def test_new_marks_change_the_rank(self, client: FlaskClient, seeded: Dict[str, object]) -> None:
        student = seeded["students"][3]
        for exam in seeded["exams"]:
            form = {f"mark-{cs.id}": "100" for cs in seeded["class_subjects"]}
            client.post(f"/marks/student/{student.id}?exam_id={exam.id}", data=form)
        text = client.get(f"/reports/class/{seeded['school_class'].id}/export.csv").get_data(as_text=True)
        first_row = text.splitlines()[1].split(",")
        assert first_row[0] == "1"
        assert first_row[3] == student.full_name

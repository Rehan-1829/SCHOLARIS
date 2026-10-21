import pytest

from app.models import Assessment, Course, FeeInvoice, Student


def login(client, email, password="password123"):
    return client.post(
        "/login", data={"email": email, "password": password}, follow_redirects=False
    )


def test_every_admin_page_renders(client):
    login(client, "registrar@example.edu")
    student = Student.query.first()
    course = Course.query.filter_by(code="BCA501").one()
    quiz = Assessment.query.filter_by(course_id=course.id).first()
    invoice = FeeInvoice.query.first()

    pages = [
        "/",
        "/students/",
        "/students/new",
        f"/students/{student.id}",
        f"/students/{student.id}/edit",
        "/courses/",
        "/courses/new",
        f"/courses/{course.id}",
        f"/courses/{course.id}/edit",
        f"/courses/{course.id}/attendance",
        f"/courses/{course.id}/grades",
        f"/courses/{course.id}/marks/{quiz.id}",
        "/fees/",
        "/fees/",
        "/fees/new",
        f"/fees/{invoice.id}",
        f"/transcript/{student.id}",
        "/reports/attendance",
        "/account",
    ]

    for path in pages:
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"


def test_every_teacher_page_renders(client):
    login(client, "lakshmi@example.edu")
    course = Course.query.filter_by(code="BCA501").one()
    quiz = Assessment.query.filter_by(course_id=course.id).first()

    pages = [
        "/",
        "/students/",
        "/courses/",
        f"/courses/{course.id}",
        f"/courses/{course.id}/attendance",
        f"/courses/{course.id}/grades",
        f"/courses/{course.id}/marks/{quiz.id}",
        "/account",
    ]

    for path in pages:
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"


def test_every_student_page_renders(client):
    login(client, "aarav@example.edu")
    student = Student.query.filter_by(roll_no="BCA2024001").one()
    course = Course.query.filter_by(code="BCA501").one()
    invoice = FeeInvoice.query.first()

    pages = [
        "/",
        "/courses/",
        f"/courses/{course.id}",
        "/fees/",
        f"/fees/{invoice.id}",
        f"/transcript/{student.id}",
        "/account",
    ]

    for path in pages:
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"


def test_unknown_records_return_the_404_page(client):
    login(client, "registrar@example.edu")
    for path in ("/students/9999", "/courses/9999", "/fees/9999", "/transcript/9999"):
        response = client.get(path)
        assert response.status_code == 404
        assert b"Nothing filed here" in response.data


@pytest.mark.parametrize("path", ["/login", "/static/css/app.css", "/static/js/app.js"])
def test_public_assets(client, path):
    assert client.get(path).status_code == 200

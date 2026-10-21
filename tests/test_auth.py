from app.extensions import db
from app.models import FeeInvoice, Student, User


def login(client, email, password="password123"):
    return client.post(
        "/login", data={"email": email, "password": password}, follow_redirects=False
    )


def test_anonymous_is_redirected_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_wrong_password_is_rejected(client):
    response = login(client, "registrar@example.edu", "not-the-password")
    assert response.status_code == 401
    assert b"do not match" in response.data


def test_admin_can_sign_in_and_reaches_registrar_desk(client):
    response = login(client, "registrar@example.edu")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

    page = client.get("/")
    assert page.status_code == 200
    assert b"Registrar's desk" in page.data


def test_deactivated_account_is_blocked(client):
    user = User.query.filter_by(email="aarav@example.edu").one()
    user.is_active = False
    db.session.commit()

    response = login(client, "aarav@example.edu")
    assert response.status_code == 403
    assert b"deactivated" in response.data


def test_teacher_lands_on_my_classes(client):
    login(client, "lakshmi@example.edu")
    page = client.get("/")
    assert page.status_code == 200
    assert b"My classes" in page.data


def test_teacher_cannot_open_fee_ledger(client):
    login(client, "lakshmi@example.edu")
    assert client.get("/fees/").status_code == 403


def test_teacher_cannot_take_another_teachers_register(client):
    login(client, "lakshmi@example.edu")
    assert client.get("/courses/1/attendance").status_code == 200
    # Course 2 belongs to a different faculty member.
    assert client.get("/courses/2/attendance").status_code == 403


def test_student_cannot_open_staff_or_other_students_records(client):
    login(client, "aarav@example.edu")

    assert client.get("/students/").status_code == 403
    assert client.get("/students/2").status_code == 403
    assert client.get("/students/1").status_code == 200
    assert client.get("/transcript/2").status_code == 403
    assert client.get("/transcript/1").status_code == 200


def test_student_cannot_open_another_students_invoice(client):
    login(client, "aarav@example.edu")
    other = FeeInvoice.query.filter_by(student_id=2).first()
    if other is None:
        other_student = Student.query.filter_by(roll_no="BCA2024002").one()
        other = FeeInvoice(
            student_id=other_student.id,
            term="2026-27",
            title="Library fee",
            amount=500,
            due_date=__import__("datetime").date(2026, 9, 1),
        )
        db.session.add(other)
        db.session.commit()

    assert client.get(f"/fees/{other.id}").status_code == 403


def test_password_change_requires_the_current_password(client):
    login(client, "aarav@example.edu")

    rejected = client.post(
        "/account",
        data={
            "current_password": "wrong-password",
            "new_password": "new-password-123",
            "confirm_password": "new-password-123",
        },
        follow_redirects=True,
    )
    assert b"Current password is incorrect" in rejected.data

    accepted = client.post(
        "/account",
        data={
            "current_password": "password123",
            "new_password": "new-password-123",
            "confirm_password": "new-password-123",
        },
        follow_redirects=True,
    )
    assert b"Password updated" in accepted.data

    client.post("/logout")
    assert login(client, "aarav@example.edu", "password123").status_code == 401
    assert login(client, "aarav@example.edu", "new-password-123").status_code == 302


def test_logout_requires_post(client):
    login(client, "aarav@example.edu")
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 302
    assert client.get("/").status_code == 302

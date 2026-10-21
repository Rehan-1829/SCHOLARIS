from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models import (
    AttendanceRecord,
    AttendanceSession,
    Course,
    Enrollment,
    FeeInvoice,
    Payment,
    Score,
    Student,
    User,
)


def login(client, email, password="password123"):
    return client.post(
        "/login", data={"email": email, "password": password}, follow_redirects=False
    )


def test_admin_can_admit_a_student_with_an_account(client):
    login(client, "registrar@example.edu")
    response = client.post(
        "/students/new",
        data={
            "full_name": "Meera Pillai",
            "email": "meera@example.edu",
            "roll_no": "BCA2024009",
            "program": "BCA",
            "batch_year": "2024",
            "current_semester": "5",
            "section": "B",
            "status": "active",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    student = Student.query.filter_by(roll_no="BCA2024009").one()
    assert student.name == "Meera Pillai"
    assert student.user.role == "student"
    assert student.user.check_password("welcome123")


def test_duplicate_email_is_rejected_without_creating_a_record(client):
    login(client, "registrar@example.edu")
    before = Student.query.count()

    response = client.post(
        "/students/new",
        data={
            "full_name": "Copy Cat",
            "email": "aarav@example.edu",
            "roll_no": "BCA2024999",
            "program": "BCA",
            "batch_year": "2024",
            "current_semester": "5",
            "status": "active",
        },
    )

    assert response.status_code == 200
    assert Student.query.count() == before
    assert Student.query.filter_by(roll_no="BCA2024999").first() is None


def test_teacher_saves_and_then_updates_a_register(client):
    login(client, "lakshmi@example.edu")
    student = Student.query.filter_by(roll_no="BCA2024001").one()
    today = date.today().isoformat()

    first = client.post(
        f"/courses/1/attendance",
        data={
            "session_date": today,
            "topic": "Sprint review",
            f"status_{student.id}": "present",
        },
        follow_redirects=False,
    )
    assert first.status_code == 302

    session = AttendanceSession.query.filter_by(course_id=1, session_date=date.today()).one()
    assert session.records[0].status == "present"

    client.post(
        f"/courses/1/attendance",
        data={
            "session_date": today,
            "topic": "Sprint review",
            f"status_{student.id}": "absent",
        },
    )
    db.session.refresh(session)
    assert AttendanceSession.query.filter_by(course_id=1, session_date=date.today()).count() == 1
    record = AttendanceRecord.query.filter_by(
        session_id=session.id, student_id=student.id
    ).one()
    assert record.status == "absent"


def test_future_register_date_is_refused(client):
    login(client, "lakshmi@example.edu")
    student = Student.query.filter_by(roll_no="BCA2024001").one()

    response = client.post(
        "/courses/1/attendance",
        data={
            "session_date": "2099-01-01",
            f"status_{student.id}": "present",
        },
        follow_redirects=True,
    )

    assert b"future date" in response.data
    assert AttendanceSession.query.filter_by(course_id=1, session_date=date(2099, 1, 1)).count() == 0


def test_marks_outside_the_range_are_not_saved(client):
    login(client, "lakshmi@example.edu")
    student = Student.query.filter_by(roll_no="BCA2024001").one()
    quiz = Course.query.filter_by(code="BCA501").one().assessments[0]

    response = client.post(
        f"/courses/1/marks/{quiz.id}",
        data={f"marks_{student.id}": "999"},
        follow_redirects=True,
    )

    assert b"outside" in response.data
    score = Score.query.filter_by(assessment_id=quiz.id, student_id=student.id).one()
    assert score.marks == 18


def test_teacher_can_record_marks(client):
    login(client, "lakshmi@example.edu")
    student = Student.query.filter_by(roll_no="BCA2024001").one()
    quiz = Course.query.filter_by(code="BCA501").one().assessments[0]

    client.post(f"/courses/1/marks/{quiz.id}", data={f"marks_{student.id}": "16"})

    score = Score.query.filter_by(assessment_id=quiz.id, student_id=student.id).one()
    assert score.marks == 16


def test_admin_can_enrol_a_student(client):
    login(client, "registrar@example.edu")
    course = Course.query.filter_by(code="BCA502").one()
    student = Student.query.filter_by(roll_no="BCA2024002").one()

    response = client.post(
        f"/courses/{course.id}/enroll",
        data={"student_id": student.id},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert Enrollment.query.filter_by(
        student_id=student.id, course_id=course.id, status="enrolled"
    ).first() is not None


def test_recording_a_payment_creates_a_receipt(client):
    login(client, "registrar@example.edu")
    invoice = FeeInvoice.query.first()

    response = client.post(
        f"/fees/{invoice.id}/payments",
        data={"amount": "12500", "method": "upi", "paid_on": date.today().isoformat()},
        follow_redirects=False,
    )

    assert response.status_code == 302
    payment = Payment.query.filter_by(invoice_id=invoice.id).one()
    assert payment.amount == Decimal("12500.00")
    assert payment.receipt_no.startswith("RCPT-")

    receipt = client.get(f"/fees/receipts/{payment.id}")
    assert receipt.status_code == 200
    assert payment.receipt_no.encode() in receipt.data
    assert b"Fee receipt" in receipt.data


def test_overpayment_is_refused(client):
    login(client, "registrar@example.edu")
    invoice = FeeInvoice.query.first()
    before = Payment.query.count()

    response = client.post(
        f"/fees/{invoice.id}/payments",
        data={"amount": "999999", "method": "cash", "paid_on": date.today().isoformat()},
        follow_redirects=True,
    )

    assert b"cannot exceed" in response.data
    assert Payment.query.count() == before


def test_admin_can_print_a_transcript(client):
    login(client, "registrar@example.edu")
    response = client.get("/transcript/1")

    assert response.status_code == 200
    assert b"Consolidated transcript" in response.data
    assert b"SGPA" in response.data


def test_attendance_shortage_report_is_admin_only(client):
    login(client, "registrar@example.edu")
    page = client.get("/reports/attendance")
    assert page.status_code == 200
    assert b"Attendance shortage" in page.data

    client.post("/logout")
    login(client, "lakshmi@example.edu")
    assert client.get("/reports/attendance").status_code == 403

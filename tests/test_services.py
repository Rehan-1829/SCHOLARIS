from datetime import date, timedelta
from decimal import Decimal

from app.extensions import db
from app.models import Course, FeeInvoice, Payment, Student
from app.services import (
    attendance_summary,
    course_result,
    cumulative_result,
    fee_summary,
    grade_for,
    semester_result,
)


def test_grade_bands(app):
    assert grade_for(95) == ("O", 10.0)
    assert grade_for(90) == ("O", 10.0)
    assert grade_for(89.9) == ("A+", 9.0)
    assert grade_for(80) == ("A+", 9.0)
    assert grade_for(70) == ("A", 8.0)
    assert grade_for(40) == ("C", 5.0)
    assert grade_for(39.9) == ("F", 0.0)
    assert grade_for(None) == ("—", 0.0)


def test_weighted_course_result(app):
    student = Student.query.filter_by(roll_no="BCA2024001").one()
    course = Course.query.filter_by(code="BCA501").one()

    result = course_result(student.id, course)

    # Quiz 18/20 = 90% at weight 20; final 70/100 = 70% at weight 80.
    assert result.percentage == 74.0
    assert result.letter == "A"
    assert result.points == 8.0
    assert result.graded_weight == 100
    assert result.complete is True


def test_incomplete_course_result_ignores_missing_weight(app):
    student = Student.query.filter_by(roll_no="BCA2024002").one()
    course = Course.query.filter_by(code="BCA501").one()

    result = course_result(student.id, course)

    # Only the quiz has a mark, so the result is based on 20 of 100 weight.
    assert result.percentage == 50.0
    assert result.graded_weight == 20
    assert result.complete is False


def test_attendance_percentage_and_shortage(app):
    student = Student.query.filter_by(roll_no="BCA2024001").one()
    course = Course.query.filter_by(code="BCA501").one()

    summary = attendance_summary(student.id, course.id)

    assert summary.total_sessions == 2
    assert summary.present == 1
    assert summary.absent == 1
    assert summary.percentage == 50.0
    assert summary.is_short is True
    assert summary.classes_needed == 2


def test_excused_absences_are_excluded_from_denominator(app):
    student = Student.query.filter_by(roll_no="BCA2024002").one()
    course = Course.query.filter_by(code="BCA501").one()

    summary = attendance_summary(student.id, course.id)

    assert summary.total_sessions == 3
    assert summary.excused == 1
    assert summary.counted == 2
    assert summary.percentage == 100.0


def test_sgpa_and_cgpa(app):
    student = Student.query.filter_by(roll_no="BCA2024001").one()

    semester = semester_result(student.id, 5)
    assert semester.sgpa == 8.0
    assert semester.credits == 4

    # BCA502 has no assessments, so it must not drag the average down.
    cgpa, credits = cumulative_result(student.id)
    assert cgpa == 8.0
    assert credits == 4


def test_fee_balance_and_status_transitions(app):
    student = Student.query.filter_by(roll_no="BCA2024001").one()
    invoice = student.invoices[0]

    assert invoice.balance == Decimal("40000.00")
    assert invoice.status == "overdue"

    invoice.due_date = date.today() + timedelta(days=10)
    assert invoice.status == "due"

    invoice.payments.append(
        Payment(amount=Decimal("10000.00"), method="upi", receipt_no="RCPT-TEST-1")
    )
    db.session.flush()
    assert invoice.status == "partial"
    assert invoice.balance == Decimal("30000.00")

    invoice.payments.append(
        Payment(amount=Decimal("30000.00"), method="cash", receipt_no="RCPT-TEST-2")
    )
    db.session.flush()
    assert invoice.status == "paid"
    assert invoice.balance == 0

    summary = fee_summary(student)
    assert summary.invoiced == 40000
    assert summary.paid == 40000
    assert summary.balance == 0

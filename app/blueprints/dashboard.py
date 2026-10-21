"""Role-aware landing page."""

from datetime import date

from flask import Blueprint, render_template
from flask_login import current_user, login_required
from sqlalchemy import case, func

from ..extensions import db
from ..models import (
    ROLE_ADMIN,
    ROLE_STUDENT,
    ROLE_TEACHER,
    AttendanceRecord,
    AttendanceSession,
    Course,
    Enrollment,
    FeeInvoice,
    Payment,
    Student,
)
from ..services import (
    attendance_summary,
    course_result,
    cumulative_result,
    fee_summary,
    semester_result,
)

bp = Blueprint("dashboard", __name__)


@bp.get("/")
@login_required
def index():
    if current_user.role == ROLE_ADMIN:
        return _admin_dashboard()
    if current_user.role == ROLE_TEACHER:
        return _teacher_dashboard()
    if current_user.role == ROLE_STUDENT:
        return _student_dashboard()
    return render_template("dashboard/unknown.html")


def _admin_dashboard():
    active_students = Student.query.filter_by(status="active").count()
    total_students = Student.query.count()
    active_courses = Course.query.filter_by(is_active=True).count()
    open_enrollments = Enrollment.query.filter_by(status="enrolled").count()

    invoiced = db.session.query(func.coalesce(func.sum(FeeInvoice.amount), 0)).scalar() or 0
    collected = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).scalar() or 0

    today = date.today()
    overdue = [
        invoice
        for invoice in FeeInvoice.query.filter(FeeInvoice.due_date < today).all()
        if invoice.balance > 0
    ]

    # Attendance health per course: one aggregate query instead of N+1.
    health_rows = (
        db.session.query(
            Course.id,
            Course.code,
            Course.title,
            func.count(AttendanceRecord.id).label("marked"),
            func.count(func.distinct(AttendanceSession.id)).label("sessions"),
            func.coalesce(
                func.sum(
                    case(
                        (AttendanceRecord.status.in_(("present", "late")), 1),
                        else_=0,
                    )
                ),
                0,
            ).label("attended"),
        )
        .join(AttendanceSession, AttendanceSession.course_id == Course.id)
        .join(AttendanceRecord, AttendanceRecord.session_id == AttendanceSession.id)
        .group_by(Course.id)
        .order_by(Course.code)
        .all()
    )
    health = [
        {
            "code": row.code,
            "title": row.title,
            "percentage": round(row.attended / row.marked * 100, 1) if row.marked else None,
            "sessions": row.sessions,
        }
        for row in health_rows
    ]
    health.sort(key=lambda item: (item["percentage"] is None, item["percentage"] or 0))

    recent_payments = (
        Payment.query.order_by(Payment.paid_on.desc(), Payment.id.desc()).limit(6).all()
    )

    return render_template(
        "dashboard/admin.html",
        active_students=active_students,
        total_students=total_students,
        active_courses=active_courses,
        open_enrollments=open_enrollments,
        invoiced=float(invoiced),
        collected=float(collected),
        outstanding=max(float(invoiced) - float(collected), 0),
        overdue=overdue,
        health=health[:6],
        recent_payments=recent_payments,
    )


def _teacher_dashboard():
    teacher = current_user.teacher
    courses = teacher.courses if teacher else []
    cards = []
    for course in courses:
        summary = attendance_summary_over_course(course.id)
        cards.append(
            {
                "course": course,
                "roster": course.registered_count,
                "sessions": len(course.sessions),
                "assessments": len(course.assessments),
                "attendance": summary,
            }
        )
    return render_template("dashboard/teacher.html", cards=cards, teacher=teacher)


def attendance_summary_over_course(course_id: int):
    rows = (
        db.session.query(
            AttendanceRecord.status,
            func.count(AttendanceRecord.id),
        )
        .join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)
        .filter(AttendanceSession.course_id == course_id)
        .group_by(AttendanceRecord.status)
        .all()
    )
    counts = dict(rows)
    total = sum(counts.values())
    attended = counts.get("present", 0) + counts.get("late", 0)
    counted = total - counts.get("excused", 0)
    return {
        "total": total,
        "percentage": round(attended / counted * 100, 1) if counted else None,
    }


def _student_dashboard():
    student = current_user.student
    if student is None:
        return render_template("dashboard/unknown.html")

    courses = []
    for enrollment in student.active_enrollments():
        courses.append(
            {
                "enrollment": enrollment,
                "course": enrollment.course,
                "attendance": attendance_summary(student.id, enrollment.course_id),
                "result": course_result(student.id, enrollment.course),
            }
        )

    current_semester = semester_result(student.id, student.current_semester)
    cgpa, credits = cumulative_result(student.id)
    fees = fee_summary(student)

    return render_template(
        "dashboard/student.html",
        student=student,
        courses=courses,
        semester=current_semester,
        cgpa=cgpa,
        credits=credits,
        fees=fees,
        overall_attendance=attendance_summary(student.id),
    )

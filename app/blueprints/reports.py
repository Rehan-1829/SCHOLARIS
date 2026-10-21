"""Printable academic documents and the attendance shortage report."""

from flask import Blueprint, abort, current_app, render_template
from flask_login import current_user

from ..extensions import db
from ..models import ROLE_ADMIN, ROLE_STUDENT, ROLE_TEACHER, Student
from ..security import role_required
from ..services import attendance_summary, cumulative_result, semester_result

bp = Blueprint("reports", __name__)


@bp.get("/transcript/<int:student_id>")
@role_required(ROLE_ADMIN, ROLE_TEACHER, ROLE_STUDENT)
def transcript(student_id: int):
    student = db.session.get(Student, student_id)
    if student is None:
        abort(404)
    if current_user.role == ROLE_STUDENT and (
        current_user.student is None or current_user.student.id != student.id
    ):
        abort(403)

    semesters = sorted({e.semester for e in student.enrollments if e.status != "dropped"})
    results = [semester_result(student.id, semester) for semester in semesters]
    cgpa, credits = cumulative_result(student.id)

    return render_template(
        "reports/transcript.html",
        student=student,
        results=results,
        cgpa=cgpa,
        credits=credits,
    )


@bp.get("/reports/attendance")
@role_required(ROLE_ADMIN)
def attendance_shortage():
    threshold = current_app.config["ATTENDANCE_THRESHOLD"]
    students = Student.query.filter_by(status="active").join(Student.user).order_by(Student.roll_no).all()
    flagged = []
    for student in students:
        rows = []
        for enrollment in student.active_enrollments():
            summary = attendance_summary(student.id, enrollment.course_id)
            if summary.percentage is not None and summary.percentage < threshold:
                rows.append({"course": enrollment.course, "summary": summary})
        if rows:
            flagged.append({"student": student, "rows": rows})

    return render_template(
        "reports/shortage.html", flagged=flagged, threshold=threshold
    )

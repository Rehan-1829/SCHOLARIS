"""Courses: catalogue, enrolment, class registers and marks entry."""

from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..helpers import clean, parse_date, parse_float, parse_int
from ..models import (
    ATTENDANCE_ABSENT,
    ATTENDANCE_CHOICES,
    ATTENDANCE_PRESENT,
    ROLE_ADMIN,
    ROLE_STUDENT,
    ROLE_TEACHER,
    Assessment,
    AttendanceRecord,
    AttendanceSession,
    Course,
    Enrollment,
    Score,
    Student,
    Teacher,
)
from ..security import admin_required, can_manage_course, require_course_access, role_required
from ..services import attendance_summary, course_result

bp = Blueprint("courses", __name__, url_prefix="/courses")

ASSESSMENT_KINDS = ("assignment", "quiz", "midterm", "practical", "project", "final")


def _visible_courses():
    query = Course.query
    if current_user.role == ROLE_TEACHER and current_user.teacher:
        query = query.filter(Course.teacher_id == current_user.teacher.id)
    elif current_user.role == ROLE_STUDENT and current_user.student:
        course_ids = [e.course_id for e in current_user.student.enrollments if e.status != "dropped"]
        query = query.filter(Course.id.in_(course_ids or [0]))
    return query.order_by(Course.semester, Course.code)


@bp.get("/")
@role_required(ROLE_ADMIN, ROLE_TEACHER, ROLE_STUDENT)
def index():
    courses = _visible_courses().all()
    return render_template("courses/index.html", courses=courses)


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def new():
    teachers = Teacher.query.join(Teacher.user).order_by(Teacher.employee_no).all()
    departments = [
        row[0]
        for row in db.session.query(Teacher.department).distinct().order_by(Teacher.department).all()
    ] or ["Computer Science"]

    if request.method == "POST":
        values = {
            "code": clean(request.form.get("code")).upper(),
            "title": clean(request.form.get("title")),
            "credits": clean(request.form.get("credits")),
            "semester": clean(request.form.get("semester")),
            "department": clean(request.form.get("department")),
            "teacher_id": clean(request.form.get("teacher_id")),
            "capacity": clean(request.form.get("capacity")),
            "description": clean(request.form.get("description")),
        }
        errors = []
        if not values["code"]:
            errors.append("Course code is required.")
        if not values["title"]:
            errors.append("Course title is required.")
        if parse_int(values["credits"]) is None or not 1 <= parse_int(values["credits"]) <= 8:
            errors.append("Credits must be between 1 and 8.")
        if parse_int(values["semester"]) is None or not 1 <= parse_int(values["semester"]) <= 10:
            errors.append("Semester must be between 1 and 10.")
        if not values["department"]:
            errors.append("Department is required.")
        if Course.query.filter_by(code=values["code"]).first():
            errors.append("That course code is already used.")
        if parse_int(values["capacity"], 0) < 1:
            errors.append("Capacity must be at least 1.")

        if not errors:
            course = Course(
                code=values["code"],
                title=values["title"],
                credits=parse_int(values["credits"]),
                semester=parse_int(values["semester"]),
                department=values["department"],
                teacher_id=parse_int(values["teacher_id"]),
                capacity=parse_int(values["capacity"], 60),
                description=values["description"] or None,
            )
            db.session.add(course)
            db.session.commit()
            flash(f"{course.code} added to the catalogue.", "success")
            return redirect(url_for("courses.detail", course_id=course.id))

        for error in errors:
            flash(error, "error")
        return render_template(
            "courses/form.html", mode="new", teachers=teachers, departments=departments, values=values
        )

    return render_template(
        "courses/form.html", mode="new", teachers=teachers, departments=departments, values={}
    )


@bp.get("/<int:course_id>")
@role_required(ROLE_ADMIN, ROLE_TEACHER, ROLE_STUDENT)
def detail(course_id: int):
    course = db.session.get(Course, course_id)
    if course is None:
        abort(404)

    roster = []
    my_result = None
    for enrollment in course.registered_enrollments():
        if current_user.role == ROLE_STUDENT:
            continue
        roster.append(
            {
                "enrollment": enrollment,
                "student": enrollment.student,
                "attendance": attendance_summary(enrollment.student_id, course.id),
                "result": course_result(enrollment.student_id, course),
            }
        )

    if current_user.role == ROLE_STUDENT and current_user.student:
        if course.id not in {e.course_id for e in current_user.student.enrollments}:
            abort(403)
        my_result = {
            "attendance": attendance_summary(current_user.student.id, course.id),
            "result": course_result(current_user.student.id, course),
        }

    candidates = []
    if current_user.role == ROLE_ADMIN:
        enrolled_ids = {e.student_id for e in course.enrollments if e.status != "dropped"}
        candidates = (
            Student.query.filter(Student.status == "active", Student.id.notin_(enrolled_ids or [0]))
            .join(Student.user)
            .order_by(Student.roll_no)
            .all()
        )

    return render_template(
        "courses/detail.html",
        course=course,
        roster=roster,
        my_result=my_result,
        candidates=candidates,
        can_manage=can_manage_course(course),
    )


@bp.route("/<int:course_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(course_id: int):
    course = db.session.get(Course, course_id)
    if course is None:
        abort(404)
    teachers = Teacher.query.join(Teacher.user).order_by(Teacher.employee_no).all()
    departments = [
        row[0]
        for row in db.session.query(Teacher.department).distinct().order_by(Teacher.department).all()
    ] or [course.department]

    if request.method == "POST":
        values = {
            "code": clean(request.form.get("code")).upper(),
            "title": clean(request.form.get("title")),
            "credits": clean(request.form.get("credits")),
            "semester": clean(request.form.get("semester")),
            "department": clean(request.form.get("department")),
            "teacher_id": clean(request.form.get("teacher_id")),
            "capacity": clean(request.form.get("capacity")),
            "description": clean(request.form.get("description")),
        }
        errors = []
        if not values["code"] or not values["title"]:
            errors.append("Course code and title are required.")
        if Course.query.filter(Course.code == values["code"], Course.id != course.id).first():
            errors.append("That course code belongs to another course.")
        credits = parse_int(values["credits"])
        semester = parse_int(values["semester"])
        if credits is None or not 1 <= credits <= 8:
            errors.append("Credits must be between 1 and 8.")
        if semester is None or not 1 <= semester <= 10:
            errors.append("Semester must be between 1 and 10.")
        capacity = parse_int(values["capacity"], 0)
        if capacity < len(course.active_enrollments()):
            errors.append("Capacity cannot be below the number of enrolled students.")

        if not errors:
            course.code = values["code"]
            course.title = values["title"]
            course.credits = credits
            course.semester = semester
            course.department = values["department"] or course.department
            course.teacher_id = parse_int(values["teacher_id"])
            course.capacity = capacity
            course.description = values["description"] or None
            db.session.commit()
            flash("Course updated.", "success")
            return redirect(url_for("courses.detail", course_id=course.id))

        for error in errors:
            flash(error, "error")
        return render_template(
            "courses/form.html", mode="edit", course=course, teachers=teachers,
            departments=departments, values=values,
        )

    values = {
        "code": course.code,
        "title": course.title,
        "credits": course.credits,
        "semester": course.semester,
        "department": course.department,
        "teacher_id": course.teacher_id or "",
        "capacity": course.capacity,
        "description": course.description or "",
    }
    return render_template(
        "courses/form.html", mode="edit", course=course, teachers=teachers,
        departments=departments, values=values,
    )


@bp.post("/<int:course_id>/enroll")
@admin_required
def enroll(course_id: int):
    course = db.session.get(Course, course_id)
    if course is None:
        abort(404)
    student = db.session.get(Student, parse_int(request.form.get("student_id"), 0))
    if student is None:
        flash("Choose a student to enrol.", "error")
        return redirect(url_for("courses.detail", course_id=course.id))

    existing = Enrollment.query.filter_by(
        student_id=student.id, course_id=course.id, semester=course.semester
    ).first()
    if existing and existing.status != "dropped":
        flash(f"{student.name} is already enrolled in this course.", "error")
    elif len(course.active_enrollments()) >= course.capacity:
        flash("The course is at capacity.", "error")
    else:
        if existing:
            existing.status = "enrolled"
        else:
            db.session.add(
                Enrollment(
                    student_id=student.id,
                    course_id=course.id,
                    semester=course.semester,
                    status="enrolled",
                )
            )
        db.session.commit()
        flash(f"{student.name} enrolled in {course.code}.", "success")
    return redirect(url_for("courses.detail", course_id=course.id))


@bp.post("/enrollments/<int:enrollment_id>/drop")
@role_required(ROLE_ADMIN, ROLE_TEACHER)
def drop(enrollment_id: int):
    enrollment = db.session.get(Enrollment, enrollment_id)
    if enrollment is None:
        abort(404)
    require_course_access(enrollment.course)
    enrollment.status = "dropped"
    db.session.commit()
    flash(f"{enrollment.student.name} removed from {enrollment.course.code}.", "info")
    return redirect(url_for("courses.detail", course_id=enrollment.course_id))


@bp.route("/<int:course_id>/attendance", methods=["GET", "POST"])
@role_required(ROLE_ADMIN, ROLE_TEACHER)
def attendance(course_id: int):
    course = db.session.get(Course, course_id)
    if course is None:
        abort(404)
    require_course_access(course)
    roster = [e.student for e in course.registered_enrollments()]

    if request.method == "POST":
        session_date = parse_date(request.form.get("session_date"))
        if session_date is None:
            flash("Pick a valid date for the register.", "error")
            return redirect(url_for("courses.attendance", course_id=course.id))
        if session_date > date.today():
            flash("You cannot mark attendance for a future date.", "error")
            return redirect(url_for("courses.attendance", course_id=course.id))

        session = AttendanceSession.query.filter_by(
            course_id=course.id, session_date=session_date
        ).first()
        if session is None:
            session = AttendanceSession(
                course_id=course.id,
                session_date=session_date,
                topic=clean(request.form.get("topic")) or None,
                created_by_id=current_user.id,
            )
            db.session.add(session)
            db.session.flush()
        elif clean(request.form.get("topic")):
            session.topic = clean(request.form.get("topic"))

        existing = {record.student_id: record for record in session.records}
        saved = 0
        for student in roster:
            status = request.form.get(f"status_{student.id}")
            if status not in ATTENDANCE_CHOICES:
                continue
            record = existing.get(student.id)
            if record is None:
                record = AttendanceRecord(session_id=session.id, student_id=student.id)
                db.session.add(record)
            record.status = status
            saved += 1
        db.session.commit()
        flash(f"Register saved for {session_date:%d %b %Y} — {saved} students.", "success")
        return redirect(url_for("courses.attendance", course_id=course.id, date=session_date.isoformat()))

    selected_date = parse_date(request.args.get("date"), date.today())
    session = AttendanceSession.query.filter_by(
        course_id=course.id, session_date=selected_date
    ).first()
    existing = {record.student_id: record.status for record in session.records} if session else {}
    recent = course.sessions[:10]

    return render_template(
        "courses/attendance.html",
        course=course,
        roster=[
            {
                "student": student,
                "status": existing.get(student.id, ATTENDANCE_PRESENT),
                "summary": attendance_summary(student.id, course.id),
            }
            for student in roster
        ],
        selected_date=selected_date,
        session=session,
        recent=recent,
        choices=ATTENDANCE_CHOICES,
    )


@bp.post("/<int:course_id>/assessments")
@role_required(ROLE_ADMIN, ROLE_TEACHER)
def add_assessment(course_id: int):
    course = db.session.get(Course, course_id)
    if course is None:
        abort(404)
    require_course_access(course)

    name = clean(request.form.get("name"))
    kind = clean(request.form.get("kind"))
    max_score = parse_float(request.form.get("max_score"))
    weight = parse_float(request.form.get("weight"))
    scheduled = parse_date(request.form.get("scheduled_on"))

    errors = []
    if not name:
        errors.append("Assessment name is required.")
    if kind not in ASSESSMENT_KINDS:
        errors.append("Pick a valid assessment type.")
    if max_score is None or max_score <= 0:
        errors.append("Maximum score must be greater than zero.")
    if weight is None or not 0 < weight <= 100:
        errors.append("Weight must be between 0 and 100.")
    if not errors and sum(a.weight for a in course.assessments) + weight > 100:
        errors.append("Weights would exceed 100% for this course.")

    if errors:
        for error in errors:
            flash(error, "error")
    else:
        db.session.add(
            Assessment(
                course_id=course.id,
                name=name,
                kind=kind,
                max_score=max_score,
                weight=weight,
                scheduled_on=scheduled,
            )
        )
        db.session.commit()
        flash(f"{name} added — worth {weight:g}% of the final grade.", "success")
    return redirect(url_for("courses.detail", course_id=course.id))


@bp.route("/<int:course_id>/marks/<int:assessment_id>", methods=["GET", "POST"])
@role_required(ROLE_ADMIN, ROLE_TEACHER)
def marks(course_id: int, assessment_id: int):
    course = db.session.get(Course, course_id)
    assessment = db.session.get(Assessment, assessment_id)
    if course is None or assessment is None or assessment.course_id != course.id:
        abort(404)
    require_course_access(course)

    roster = [e.student for e in course.registered_enrollments()]

    if request.method == "POST":
        existing = {score.student_id: score for score in assessment.scores}
        saved = 0
        errors = 0
        for student in roster:
            raw = clean(request.form.get(f"marks_{student.id}"))
            score = existing.get(student.id)
            if raw == "":
                if score is not None:
                    score.marks = None
                continue
            value = parse_float(raw)
            if value is None or value < 0 or value > assessment.max_score:
                errors += 1
                continue
            if score is None:
                score = Score(assessment_id=assessment.id, student_id=student.id)
                db.session.add(score)
            score.marks = value
            saved += 1
        db.session.commit()
        if errors:
            flash(f"Saved {saved} scores. {errors} entries were outside 0–{assessment.max_score:g}.", "error")
        else:
            flash(f"Saved {saved} scores for {assessment.name}.", "success")
        return redirect(url_for("courses.marks", course_id=course.id, assessment_id=assessment.id))

    rows = [
        {
            "student": student,
            "score": assessment.score_for(student.id),
            "percentage": (
                assessment.score_for(student.id).percentage
                if assessment.score_for(student.id)
                else None
            ),
        }
        for student in roster
    ]
    return render_template(
        "courses/marks.html", course=course, assessment=assessment, rows=rows
    )


@bp.get("/<int:course_id>/grades")
@role_required(ROLE_ADMIN, ROLE_TEACHER)
def grades(course_id: int):
    course = db.session.get(Course, course_id)
    if course is None:
        abort(404)
    require_course_access(course)
    rows = [
        {
            "student": enrollment.student,
            "result": course_result(enrollment.student_id, course),
            "attendance": attendance_summary(enrollment.student_id, course.id),
        }
        for enrollment in course.registered_enrollments()
    ]
    rows.sort(key=lambda row: (row["result"].percentage is None, -(row["result"].percentage or 0)))

    graded = [row["result"].percentage for row in rows if row["result"].percentage is not None]
    average = round(sum(graded) / len(graded), 1) if graded else None
    return render_template(
        "courses/grades.html",
        course=course,
        rows=rows,
        average=average,
        graded_count=len(graded),
        passing_count=sum(1 for row in rows if row["result"].percentage is not None and row["result"].letter != "F"),
        complete_count=sum(1 for row in rows if row["result"].complete),
    )

"""Student records: search, admission, edits and the student profile."""

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from ..extensions import db
from ..helpers import clean, parse_date, parse_int
from ..models import ROLE_ADMIN, ROLE_STUDENT, ROLE_TEACHER, Enrollment, Student, User
from ..security import admin_required, role_required
from ..services import attendance_summary, course_result, cumulative_result, fee_summary, semester_result

bp = Blueprint("students", __name__, url_prefix="/students")

PER_PAGE = 12


def _can_view(student: Student) -> bool:
    if not current_user.is_authenticated:
        return False
    if current_user.role == ROLE_ADMIN:
        return True
    if current_user.role == ROLE_STUDENT:
        return current_user.student is not None and current_user.student.id == student.id
    if current_user.role == ROLE_TEACHER and current_user.teacher:
        taught = {course.id for course in current_user.teacher.courses}
        return any(enrollment.course_id in taught for enrollment in student.enrollments)
    return False


@bp.get("/")
@role_required(ROLE_ADMIN, ROLE_TEACHER)
def index():
    q = clean(request.args.get("q"))
    program = clean(request.args.get("program"))
    status = clean(request.args.get("status"))
    page = max(parse_int(request.args.get("page"), 1), 1)

    query = Student.query.join(User)
    if q:
        needle = f"%{q}%"
        query = query.filter(
            or_(
                User.full_name.ilike(needle),
                User.email.ilike(needle),
                Student.roll_no.ilike(needle),
            )
        )
    if program:
        query = query.filter(Student.program == program)
    if status:
        query = query.filter(Student.status == status)
    if current_user.role == ROLE_TEACHER and current_user.teacher:
        taught = [course.id for course in current_user.teacher.courses] or [0]
        query = query.filter(
            Student.id.in_(
                db.session.query(Enrollment.student_id).filter(
                    Enrollment.course_id.in_(taught)
                )
            )
        )

    pagination = query.order_by(Student.roll_no).paginate(
        page=page, per_page=PER_PAGE, error_out=False
    )
    programs = [
        row[0]
        for row in db.session.query(Student.program).distinct().order_by(Student.program).all()
    ]

    return render_template(
        "students/index.html",
        pagination=pagination,
        students=pagination.items,
        programs=programs,
        q=q,
        program=program,
        status=status,
    )


def _form_context(**overrides):
    context = {
        "programs": [
            "B.Sc. Computer Science",
            "B.Sc. Mathematics",
            "B.Com. Honours",
            "B.A. English",
            "BCA",
            "M.Sc. Computer Science",
        ],
        "statuses": ["active", "graduated", "withdrawn"],
        "values": {},
    }
    context.update(overrides)
    return context


def _read_student_form() -> tuple[dict, list[str]]:
    form = request.form
    values = {
        "full_name": clean(form.get("full_name")),
        "email": clean(form.get("email")).lower(),
        "roll_no": clean(form.get("roll_no")).upper(),
        "program": clean(form.get("program")),
        "batch_year": clean(form.get("batch_year")),
        "current_semester": clean(form.get("current_semester")),
        "section": clean(form.get("section")).upper() or "A",
        "date_of_birth": clean(form.get("date_of_birth")),
        "phone": clean(form.get("phone")),
        "guardian_name": clean(form.get("guardian_name")),
        "guardian_phone": clean(form.get("guardian_phone")),
        "address": clean(form.get("address")),
        "status": clean(form.get("status")) or "active",
        "password": form.get("password") or "",
    }

    errors: list[str] = []
    if not values["full_name"]:
        errors.append("Full name is required.")
    if "@" not in values["email"]:
        errors.append("A valid email address is required.")
    if not values["roll_no"]:
        errors.append("Roll number is required.")
    if not values["program"]:
        errors.append("Program is required.")
    if parse_int(values["batch_year"]) is None:
        errors.append("Batch year must be a number.")
    semester = parse_int(values["current_semester"])
    if semester is None or not 1 <= semester <= 10:
        errors.append("Semester must be between 1 and 10.")
    if values["date_of_birth"] and parse_date(values["date_of_birth"]) is None:
        errors.append("Date of birth must be a valid date.")
    if values["status"] not in ("active", "graduated", "withdrawn"):
        errors.append("Unknown student status.")
    return values, errors


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def new():
    if request.method == "POST":
        values, errors = _read_student_form()

        if User.query.filter(db.func.lower(User.email) == values["email"]).first():
            errors.append("An account with that email already exists.")
        if Student.query.filter_by(roll_no=values["roll_no"]).first():
            errors.append("That roll number is already on file.")
        if values["password"] and len(values["password"]) < 8:
            errors.append("Initial password must be at least 8 characters.")

        if not errors:
            password = values["password"] or "welcome123"
            user = User(
                email=values["email"],
                full_name=values["full_name"],
                role=ROLE_STUDENT,
            )
            user.set_password(password)
            student = Student(
                user=user,
                roll_no=values["roll_no"],
                program=values["program"],
                batch_year=parse_int(values["batch_year"]),
                current_semester=parse_int(values["current_semester"]),
                section=values["section"],
                date_of_birth=parse_date(values["date_of_birth"]),
                phone=values["phone"] or None,
                guardian_name=values["guardian_name"] or None,
                guardian_phone=values["guardian_phone"] or None,
                address=values["address"] or None,
                status=values["status"],
            )
            db.session.add(user)
            db.session.add(student)
            db.session.commit()
            flash(
                f"Admitted {student.name} ({student.roll_no}). Sign-in password: {password}",
                "success",
            )
            return redirect(url_for("students.detail", student_id=student.id))

        for error in errors:
            flash(error, "error")
        return render_template("students/form.html", mode="new", **_form_context(values=values))

    return render_template("students/form.html", mode="new", **_form_context())


@bp.get("/<int:student_id>")
@login_required
def detail(student_id: int):
    student = db.session.get(Student, student_id)
    if student is None:
        abort(404)
    if not _can_view(student):
        abort(403)

    overall = attendance_summary(student.id)
    course_rows = []
    for enrollment in student.active_enrollments():
        course_rows.append(
            {
                "enrollment": enrollment,
                "course": enrollment.course,
                "attendance": attendance_summary(student.id, enrollment.course_id),
                "result": course_result(student.id, enrollment.course),
            }
        )
    semester = semester_result(student.id, student.current_semester)
    cgpa, credits = cumulative_result(student.id)

    return render_template(
        "students/detail.html",
        student=student,
        overall=overall,
        course_rows=course_rows,
        semester=semester,
        cgpa=cgpa,
        credits=credits,
        fees=fee_summary(student) if current_user.role in (ROLE_ADMIN, ROLE_STUDENT) else None,
    )


@bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(student_id: int):
    student = db.session.get(Student, student_id)
    if student is None:
        abort(404)

    if request.method == "POST":
        values, errors = _read_student_form()

        clash = User.query.filter(
            db.func.lower(User.email) == values["email"], User.id != student.user_id
        ).first()
        if clash:
            errors.append("Another account already uses that email.")
        roll_clash = Student.query.filter(
            Student.roll_no == values["roll_no"], Student.id != student.id
        ).first()
        if roll_clash:
            errors.append("Another student already has that roll number.")

        if not errors:
            student.user.full_name = values["full_name"]
            student.user.email = values["email"]
            student.roll_no = values["roll_no"]
            student.program = values["program"]
            student.batch_year = parse_int(values["batch_year"])
            student.current_semester = parse_int(values["current_semester"])
            student.section = values["section"]
            student.date_of_birth = parse_date(values["date_of_birth"])
            student.phone = values["phone"] or None
            student.guardian_name = values["guardian_name"] or None
            student.guardian_phone = values["guardian_phone"] or None
            student.address = values["address"] or None
            student.status = values["status"]
            db.session.commit()
            flash("Student record updated.", "success")
            return redirect(url_for("students.detail", student_id=student.id))

        for error in errors:
            flash(error, "error")
        return render_template(
            "students/form.html", mode="edit", student=student, **_form_context(values=values)
        )

    values = {
        "full_name": student.user.full_name,
        "email": student.user.email,
        "roll_no": student.roll_no,
        "program": student.program,
        "batch_year": student.batch_year,
        "current_semester": student.current_semester,
        "section": student.section,
        "date_of_birth": student.date_of_birth.isoformat() if student.date_of_birth else "",
        "phone": student.phone or "",
        "guardian_name": student.guardian_name or "",
        "guardian_phone": student.guardian_phone or "",
        "address": student.address or "",
        "status": student.status,
        "password": "",
    }
    return render_template(
        "students/form.html", mode="edit", student=student, **_form_context(values=values)
    )

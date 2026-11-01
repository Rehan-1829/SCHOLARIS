"""`flask seed` builds a believable demo college so the app is never empty."""

import random
from datetime import date, timedelta

import click
from flask import current_app
from flask.cli import with_appcontext

from .extensions import db
from .models import (
    ATTENDANCE_ABSENT,
    ATTENDANCE_EXCUSED,
    ATTENDANCE_LATE,
    ATTENDANCE_PRESENT,
    ROLE_ADMIN,
    ROLE_STUDENT,
    ROLE_TEACHER,
    Assessment,
    AttendanceRecord,
    AttendanceSession,
    Course,
    Enrollment,
    FeeInvoice,
    Payment,
    Score,
    Student,
    Teacher,
    User,
)

STUDENT_NAMES = [
    "Aarav Mehta",
    "Ishita Nair",
    "Rohan Kulkarni",
    "Sneha Iyer",
    "Kabir Shah",
    "Ananya Deshpande",
    "Vihaan Rao",
    "Meera Pillai",
    "Arjun Sethi",
    "Diya Menon",
    "Nikhil Joshi",
    "Tara Bhatt",
    "Rehan Ali",
]

FACULTY = [
    ("Dr. Lakshmi Venkatesan", "Computer Science", "Professor"),
    ("Prof. Sanjay Bhattacharya", "Computer Science", "Associate Professor"),
    ("Dr. Rekha Menon", "Mathematics", "Professor"),
    ("Prof. Imran Qureshi", "Computer Science", "Assistant Professor"),
    ("Dr. Nandita Sanyal", "Humanities", "Associate Professor"),
]

COURSES = [
    # code, title, credits, semester, department, faculty index, description
    ("BCA501", "Software Engineering", 4, 5, "Computer Science", 0,
     "Requirements, design, testing and delivery of software as a team."),
    ("BCA502", "Python Programming", 4, 5, "Computer Science", 3,
     "Problem solving with Python, data structures and small applications."),
    ("BCA503", "Computer Networks", 3, 5, "Computer Science", 1,
     "Layered network models, routing, and the protocols behind the web."),
    ("BCA504", "Database Systems", 4, 5, "Computer Science", 1,
     "Relational modelling, SQL, normalisation and transactions."),
    ("BCA401", "Data Structures", 4, 4, "Computer Science", 0,
     "Arrays, lists, trees, graphs and complexity analysis."),
    ("BCA402", "Operating Systems", 3, 4, "Computer Science", 3,
     "Processes, memory, scheduling and file systems."),
    ("BCA403", "Discrete Mathematics", 3, 4, "Mathematics", 2,
     "Logic, sets, combinatorics and graph theory for computing."),
]

TOPICS = {
    "BCA501": ["SRS workshop", "Use case modelling", "Design patterns", "Unit testing", "Sprint review"],
    "BCA502": ["Lists and dicts", "Functions and scope", "Files and CSV", "Flask basics", "Testing with pytest"],
    "BCA503": ["OSI layers", "TCP handshake", "Subnetting drill", "DNS resolution", "HTTP in practice"],
    "BCA504": ["Normal forms", "Joins", "Indexes", "Transactions", "Query tuning"],
}

ASSESSMENTS = [
    ("Quiz 1", "quiz", 20, 10),
    ("Midterm", "midterm", 50, 30),
    ("Assignment", "assignment", 25, 20),
    ("Final exam", "final", 100, 40),
]


def _class_days(count: int, weekdays=(0, 2, 4)) -> list[date]:
    """Most recent `count` weekdays on or before today."""
    days: list[date] = []
    cursor = date.today()
    while len(days) < count:
        if cursor.weekday() in weekdays:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return sorted(days)


def _receipt(seq: int) -> str:
    return f"RCPT-{date.today().year}-{seq:05d}"


def seed_demo_data(force: bool = False) -> bool:
    """Build the demo college. Returns False when data already exists.

    Kept separate from the CLI command so the double-click launcher can call it
    directly without going through Click.
    """
    if User.query.first() and not force:
        return False

    if force:
        db.drop_all()
        db.create_all()

    rng = random.Random(11)
    term = current_app.config["CURRENT_TERM"]

    # ---- people ----------------------------------------------------------
    registrar = User(
        email="registrar@scholaris.edu",
        full_name="Priya Raghavan",
        role=ROLE_ADMIN,
    )
    registrar.set_password("registrar123")
    db.session.add(registrar)

    teachers = []
    for index, (name, department, designation) in enumerate(FACULTY, start=1):
        email = name.lower().replace("dr. ", "").replace("prof. ", "").replace(" ", ".")
        user = User(email=f"{email}@scholaris.edu", full_name=name, role=ROLE_TEACHER)
        user.set_password("faculty123")
        teacher = Teacher(
            user=user,
            employee_no=f"FAC{index:03d}",
            department=department,
            designation=designation,
            joined_on=date(2018 + index % 5, 7, 1),
        )
        db.session.add_all([user, teacher])
        teachers.append(teacher)
    db.session.flush()

    courses = []
    for code, title, credits, semester, department, faculty_index, description in COURSES:
        course = Course(
            code=code,
            title=title,
            credits=credits,
            semester=semester,
            department=department,
            teacher_id=teachers[faculty_index].id,
            capacity=50,
            description=description,
        )
        db.session.add(course)
        courses.append(course)
    db.session.flush()

    semester_four = [course for course in courses if course.semester == 4]
    semester_five = [course for course in courses if course.semester == 5]

    students = []
    for index, name in enumerate(STUDENT_NAMES, start=1):
        slug = name.lower().replace(" ", ".")
        user = User(
            email=f"{slug}@student.scholaris.edu",
            full_name=name,
            role=ROLE_STUDENT,
        )
        user.set_password("student123")
        student = Student(
            user=user,
            roll_no=f"BCA2024{index:03d}",
            program="BCA",
            batch_year=2024,
            current_semester=5,
            section="A" if index <= 6 else "B",
            date_of_birth=date(2005, 1 + index % 12, 1 + index % 27),
            phone=f"98{40000000 + index * 137:08d}",
            guardian_name=name.split()[-1] + " household",
            guardian_phone=f"97{30000000 + index * 311:08d}",
            address=f"{12 + index} Lake View Road, Bengaluru",
            admitted_on=date(2024, 7, 15 + index),
            status="active",
        )
        db.session.add_all([user, student])
        students.append(student)
    db.session.flush()

    # ---- past semester: complete records so transcripts have history ----
    final_assessments = []
    for course in semester_four:
        for name, kind, max_score, weight in ASSESSMENTS:
            assessment = Assessment(
                course_id=course.id,
                name=name,
                kind=kind,
                max_score=max_score,
                weight=weight,
                scheduled_on=date.today() - timedelta(days=200),
            )
            db.session.add(assessment)
            final_assessments.append(assessment)
    db.session.flush()

    for student in students:
        for course in semester_four:
            db.session.add(
                Enrollment(
                    student_id=student.id,
                    course_id=course.id,
                    semester=4,
                    status="completed",
                    enrolled_on=date(2025, 7, 20),
                )
            )
    db.session.flush()

    for assessment in final_assessments:
        for student in students:
            if rng.random() < 0.06:
                continue
            db.session.add(
                Score(
                    assessment_id=assessment.id,
                    student_id=student.id,
                    marks=round(assessment.max_score * rng.uniform(0.55, 0.97)),
                )
            )

    # ---- current semester: enrolments, registers, marks -----------------
    for student in students:
        for course in semester_five:
            db.session.add(
                Enrollment(
                    student_id=student.id,
                    course_id=course.id,
                    semester=5,
                    status="enrolled",
                    enrolled_on=date(2026, 7, 21),
                )
            )
    db.session.flush()

    for course in semester_five:
        # A register for each class held this half of the term.
        for session_date in _class_days(12, weekdays=(0, 2, 4)):
            topic_pool = TOPICS.get(course.code, ["Class discussion"])
            session = AttendanceSession(
                course_id=course.id,
                session_date=session_date,
                topic=topic_pool[session_date.toordinal() % len(topic_pool)],
                created_by_id=teachers[0].user_id,
            )
            db.session.add(session)
            db.session.flush()
            for student in students:
                # Roll 2 and 9 deliberately run a shortage in one class each.
                weak_class = (student.roll_no.endswith("002") and course.code == "BCA503") or (
                    student.roll_no.endswith("009") and course.code == "BCA502"
                )
                roll = rng.random()
                if weak_class:
                    status = ATTENDANCE_ABSENT if roll < 0.45 else ATTENDANCE_PRESENT
                elif roll < 0.82:
                    status = ATTENDANCE_PRESENT
                elif roll < 0.88:
                    status = ATTENDANCE_LATE
                elif roll < 0.97:
                    status = ATTENDANCE_ABSENT
                else:
                    status = ATTENDANCE_EXCUSED
                db.session.add(
                    AttendanceRecord(session_id=session.id, student_id=student.id, status=status)
                )

        for name, kind, max_score, weight in ASSESSMENTS:
            # The final exam has not happened yet in the running term.
            scheduled = date.today() + timedelta(days=21) if kind == "final" else date.today() - timedelta(days=30)
            assessment = Assessment(
                course_id=course.id,
                name=name,
                kind=kind,
                max_score=max_score,
                weight=weight,
                scheduled_on=scheduled,
            )
            db.session.add(assessment)
            db.session.flush()
            if kind == "final":
                continue
            for student in students:
                if rng.random() < 0.1:
                    continue
                db.session.add(
                    Score(
                        assessment_id=assessment.id,
                        student_id=student.id,
                        marks=round(max_score * rng.uniform(0.48, 0.98)),
                    )
                )

    # ---- fees ------------------------------------------------------------
    receipt_seq = 1
    for index, student in enumerate(students):
        tuition = FeeInvoice(
            student_id=student.id,
            term=term,
            title="Tuition fee",
            amount=42000,
            due_date=date.today() - timedelta(days=25),
            issued_on=date.today() - timedelta(days=55),
        )
        lab = FeeInvoice(
            student_id=student.id,
            term=term,
            title="Laboratory and library fee",
            amount=6500,
            due_date=date.today() + timedelta(days=12),
            issued_on=date.today() - timedelta(days=55),
        )
        db.session.add_all([tuition, lab])
        db.session.flush()

        # A spread of fully paid, partly paid and unpaid students.
        if index % 5 == 0:
            continue
        amount = 42000 if index % 3 != 0 else 20000
        db.session.add(
            Payment(
                invoice_id=tuition.id,
                amount=amount,
                method="upi" if index % 2 else "netbanking",
                reference=f"UPI{900000 + index}",
                paid_on=date.today() - timedelta(days=18 - index % 10),
                receipt_no=_receipt(receipt_seq),
                recorded_by_id=registrar.id,
            )
        )
        receipt_seq += 1
        if index % 3 == 0:
            db.session.add(
                Payment(
                    invoice_id=lab.id,
                    amount=6500,
                    method="card",
                    reference=f"CARD{700000 + index}",
                    paid_on=date.today() - timedelta(days=9),
                    receipt_no=_receipt(receipt_seq),
                    recorded_by_id=registrar.id,
                )
            )
            receipt_seq += 1

    db.session.commit()

    click.echo("Demo college created.")
    click.echo("  Registrar  registrar@scholaris.edu / registrar123")
    click.echo("  Faculty    lakshmi.venkatesan@scholaris.edu / faculty123")
    click.echo(f"  Students   {len(students)} accounts, e.g. aarav.mehta@student.scholaris.edu / student123")
    click.echo(f"  Term       {term}")
    return True


@click.command("seed")
@click.option("--force", is_flag=True, help="Drop every table first, then rebuild the demo data.")
@click.option(
    "--if-empty",
    is_flag=True,
    help="Seed only when there are no accounts; safe to run on every boot.",
)
@with_appcontext
def seed_command(force: bool, if_empty: bool):
    """Create demo students, classes, marks and fees."""
    if if_empty and User.query.first():
        click.echo("Data already present, leaving it untouched.")
        return
    if not seed_demo_data(force=force):
        click.echo("Data already exists. Use --force to rebuild the demo college.")


def register_cli(app):
    app.cli.add_command(seed_command)

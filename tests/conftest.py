from datetime import date

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import (
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
    Score,
    Student,
    Teacher,
    User,
)


def _user(name, email, role, password="password123"):
    user = User(email=email, full_name=name, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


def _seed(app):
    admin = _user("Priya Raghavan", "registrar@example.edu", ROLE_ADMIN)

    teacher_user = _user("Dr. Lakshmi Venkatesan", "lakshmi@example.edu", ROLE_TEACHER)
    teacher = Teacher(
        user=teacher_user,
        employee_no="FAC001",
        department="Computer Science",
        designation="Professor",
    )
    db.session.add(teacher)
    other_teacher_user = _user("Prof. Imran Qureshi", "imran@example.edu", ROLE_TEACHER)
    other_teacher = Teacher(
        user=other_teacher_user,
        employee_no="FAC002",
        department="Computer Science",
    )
    db.session.add(other_teacher)
    db.session.flush()

    course = Course(
        code="BCA501",
        title="Software Engineering",
        credits=4,
        semester=5,
        department="Computer Science",
        teacher_id=teacher.id,
        capacity=40,
    )
    other_course = Course(
        code="BCA502",
        title="Python Programming",
        credits=4,
        semester=5,
        department="Computer Science",
        teacher_id=other_teacher.id,
        capacity=40,
    )
    db.session.add_all([course, other_course])
    db.session.flush()

    student = Student(
        user=_user("Aarav Mehta", "aarav@example.edu", ROLE_STUDENT),
        roll_no="BCA2024001",
        program="BCA",
        batch_year=2024,
        current_semester=5,
        section="A",
    )
    db.session.add(student)
    other_student = Student(
        user=_user("Ishita Nair", "ishita@example.edu", ROLE_STUDENT),
        roll_no="BCA2024002",
        program="BCA",
        batch_year=2024,
        current_semester=5,
        section="A",
    )
    db.session.add(other_student)
    db.session.flush()

    for enrolled in (student, other_student):
        db.session.add(
            Enrollment(student_id=enrolled.id, course_id=course.id, semester=5, status="enrolled")
        )
    db.session.add(
        Enrollment(student_id=student.id, course_id=other_course.id, semester=5, status="enrolled")
    )

    # Aarav: present then absent. Ishita: late, late, excused.
    for index, status in enumerate((ATTENDANCE_PRESENT, ATTENDANCE_ABSENT)):
        session = AttendanceSession(
            course_id=course.id,
            session_date=date(2026, 9, 1 + index),
            topic="Lecture",
            created_by_id=teacher_user.id,
        )
        db.session.add(session)
        db.session.flush()
        db.session.add(
            AttendanceRecord(session_id=session.id, student_id=student.id, status=status)
        )
        db.session.add(
            AttendanceRecord(
                session_id=session.id, student_id=other_student.id, status=ATTENDANCE_LATE
            )
        )

    excused_session = AttendanceSession(
        course_id=course.id, session_date=date(2026, 9, 10), created_by_id=teacher_user.id
    )
    db.session.add(excused_session)
    db.session.flush()
    db.session.add(
        AttendanceRecord(
            session_id=excused_session.id, student_id=other_student.id, status=ATTENDANCE_EXCUSED
        )
    )

    quiz = Assessment(course_id=course.id, name="Quiz 1", kind="quiz", max_score=20, weight=20)
    exam = Assessment(course_id=course.id, name="Final", kind="final", max_score=100, weight=80)
    db.session.add_all([quiz, exam])
    db.session.flush()
    db.session.add(Score(assessment_id=quiz.id, student_id=student.id, marks=18))
    db.session.add(Score(assessment_id=quiz.id, student_id=other_student.id, marks=10))
    db.session.add(Score(assessment_id=exam.id, student_id=student.id, marks=70))

    db.session.add(
        FeeInvoice(
            student_id=student.id,
            term=app.config["CURRENT_TERM"],
            title="Tuition fee",
            amount=40000,
            due_date=date(2026, 9, 1),
        )
    )
    db.session.commit()


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    context = application.app_context()
    context.push()
    db.drop_all()
    db.create_all()
    _seed(application)
    yield application
    db.session.remove()
    db.drop_all()
    context.pop()


@pytest.fixture()
def client(app):
    return app.test_client()

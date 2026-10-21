"""Database models for the Scholaris student management system.

The schema is grouped the way a registrar actually keeps records:

* people      - sign-in accounts, students, teaching staff
* curriculum  - courses and the students enrolled on them
* attendance  - one register per class meeting, one row per student
* assessment  - assessments per course, one score per student per assessment
* finance     - invoices raised per student, payments recorded against them
"""

from datetime import date, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

ROLE_ADMIN = "admin"
ROLE_TEACHER = "teacher"
ROLE_STUDENT = "student"

ATTENDANCE_PRESENT = "present"
ATTENDANCE_ABSENT = "absent"
ATTENDANCE_LATE = "late"
ATTENDANCE_EXCUSED = "excused"
ATTENDANCE_CHOICES = (
    ATTENDANCE_PRESENT,
    ATTENDANCE_ABSENT,
    ATTENDANCE_LATE,
    ATTENDANCE_EXCUSED,
)

STUDENT_STATUSES = ("active", "graduated", "withdrawn")
ENROLLMENT_STATUSES = ("enrolled", "completed", "dropped")


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    student = db.relationship(
        "Student", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    teacher = db.relationship(
        "Teacher", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def initials(self) -> str:
        titles = {"dr.", "dr", "prof.", "prof", "mr.", "mr", "ms.", "ms", "mrs.", "mrs"}
        parts = [part for part in self.full_name.split() if part and part.lower() not in titles]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    @property
    def role_label(self) -> str:
        return {
            ROLE_ADMIN: "Registrar",
            ROLE_TEACHER: "Faculty",
            ROLE_STUDENT: "Student",
        }.get(self.role, self.role.title())

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.email} ({self.role})>"


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    roll_no = db.Column(db.String(24), unique=True, nullable=False, index=True)
    program = db.Column(db.String(80), nullable=False)
    batch_year = db.Column(db.Integer, nullable=False)
    current_semester = db.Column(db.Integer, nullable=False, default=1)
    section = db.Column(db.String(8), nullable=False, default="A")
    date_of_birth = db.Column(db.Date)
    phone = db.Column(db.String(20))
    guardian_name = db.Column(db.String(120))
    guardian_phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
    admitted_on = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(20), nullable=False, default="active")

    user = db.relationship("User", back_populates="student")
    enrollments = db.relationship(
        "Enrollment",
        back_populates="student",
        cascade="all, delete-orphan",
        order_by="Enrollment.id",
    )
    invoices = db.relationship(
        "FeeInvoice",
        back_populates="student",
        cascade="all, delete-orphan",
        order_by="FeeInvoice.due_date",
    )

    @property
    def name(self) -> str:
        return self.user.full_name if self.user else "Unnamed student"

    @property
    def email(self) -> str:
        return self.user.email if self.user else ""

    def active_enrollments(self):
        return [e for e in self.enrollments if e.status == "enrolled"]

    def outstanding_balance(self):
        return sum((invoice.balance for invoice in self.invoices), start=0)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Student {self.roll_no} {self.name}>"


class Teacher(db.Model):
    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    employee_no = db.Column(db.String(24), unique=True, nullable=False, index=True)
    department = db.Column(db.String(80), nullable=False)
    designation = db.Column(db.String(80), nullable=False, default="Assistant Professor")
    joined_on = db.Column(db.Date, default=date.today)

    user = db.relationship("User", back_populates="teacher")
    courses = db.relationship("Course", back_populates="teacher", order_by="Course.code")

    @property
    def name(self) -> str:
        return self.user.full_name if self.user else "Unassigned"

    @property
    def email(self) -> str:
        return self.user.email if self.user else ""


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    credits = db.Column(db.Integer, nullable=False, default=3)
    semester = db.Column(db.Integer, nullable=False, default=1)
    department = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"))
    capacity = db.Column(db.Integer, nullable=False, default=60)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    teacher = db.relationship("Teacher", back_populates="courses")
    enrollments = db.relationship(
        "Enrollment", back_populates="course", cascade="all, delete-orphan"
    )
    sessions = db.relationship(
        "AttendanceSession",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="AttendanceSession.session_date.desc()",
    )
    assessments = db.relationship(
        "Assessment",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Assessment.scheduled_on",
    )

    def active_enrollments(self):
        return [e for e in self.enrollments if e.status == "enrolled"]

    def registered_enrollments(self):
        """Everyone who took the course, including completed enrolments."""
        return [e for e in self.enrollments if e.status != "dropped"]

    @property
    def registered_count(self) -> int:
        return len(self.registered_enrollments())

    @property
    def seats_left(self) -> int:
        return max(self.capacity - self.registered_count, 0)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Course {self.code}>"


class Enrollment(db.Model):
    __tablename__ = "enrollments"
    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", "semester", name="uq_enrollment"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    semester = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="enrolled")
    enrolled_on = db.Column(db.Date, nullable=False, default=date.today)

    student = db.relationship("Student", back_populates="enrollments")
    course = db.relationship("Course", back_populates="enrollments")


class AttendanceSession(db.Model):
    __tablename__ = "attendance_sessions"
    __table_args__ = (
        db.UniqueConstraint("course_id", "session_date", name="uq_session_per_day"),
    )

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    session_date = db.Column(db.Date, nullable=False, default=date.today)
    topic = db.Column(db.String(160))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    course = db.relationship("Course", back_populates="sessions")
    records = db.relationship(
        "AttendanceRecord", back_populates="session", cascade="all, delete-orphan"
    )

    @property
    def present_count(self) -> int:
        return sum(
            1
            for record in self.records
            if record.status in (ATTENDANCE_PRESENT, ATTENDANCE_LATE)
        )

    @property
    def summary(self) -> str:
        return f"{self.present_count}/{len(self.records)} present"


class AttendanceRecord(db.Model):
    __tablename__ = "attendance_records"
    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id", name="uq_attendance_record"),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("attendance_sessions.id"), nullable=False, index=True
    )
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    status = db.Column(db.String(12), nullable=False, default=ATTENDANCE_PRESENT)
    note = db.Column(db.String(160))

    session = db.relationship("AttendanceSession", back_populates="records")
    student = db.relationship("Student")


class Assessment(db.Model):
    __tablename__ = "assessments"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    kind = db.Column(db.String(24), nullable=False, default="assignment")
    max_score = db.Column(db.Float, nullable=False, default=100)
    weight = db.Column(db.Float, nullable=False, default=10)
    scheduled_on = db.Column(db.Date)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    course = db.relationship("Course", back_populates="assessments")
    scores = db.relationship("Score", back_populates="assessment", cascade="all, delete-orphan")

    def score_for(self, student_id: int):
        for score in self.scores:
            if score.student_id == student_id:
                return score
        return None


class Score(db.Model):
    __tablename__ = "scores"
    __table_args__ = (
        db.UniqueConstraint("assessment_id", "student_id", name="uq_score"),
    )

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(
        db.Integer, db.ForeignKey("assessments.id"), nullable=False, index=True
    )
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    marks = db.Column(db.Float)
    remarks = db.Column(db.String(160))

    assessment = db.relationship("Assessment", back_populates="scores")
    student = db.relationship("Student")

    @property
    def percentage(self):
        if self.marks is None or not self.assessment or not self.assessment.max_score:
            return None
        return (self.marks / self.assessment.max_score) * 100


class FeeInvoice(db.Model):
    __tablename__ = "fee_invoices"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    term = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    due_date = db.Column(db.Date, nullable=False, default=date.today)
    issued_on = db.Column(db.Date, nullable=False, default=date.today)

    student = db.relationship("Student", back_populates="invoices")
    payments = db.relationship(
        "Payment", back_populates="invoice", cascade="all, delete-orphan", order_by="Payment.paid_on"
    )

    @property
    def paid_total(self):
        return sum((payment.amount for payment in self.payments), start=0)

    @property
    def balance(self):
        return self.amount - self.paid_total

    @property
    def status(self) -> str:
        if self.balance <= 0:
            return "paid"
        if self.due_date and self.due_date < date.today():
            return "overdue"
        if self.paid_total > 0:
            return "partial"
        return "due"


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("fee_invoices.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    method = db.Column(db.String(24), nullable=False, default="upi")
    reference = db.Column(db.String(80))
    paid_on = db.Column(db.Date, nullable=False, default=date.today)
    receipt_no = db.Column(db.String(24), unique=True, nullable=False)
    recorded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    invoice = db.relationship("FeeInvoice", back_populates="payments")
    recorded_by = db.relationship("User")

"""Academic and financial calculations.

These are pure functions over the ORM objects, so the grading and attendance
rules can be unit tested directly and every screen shares one source of truth.
"""

from dataclasses import dataclass, field

from .models import (
    ATTENDANCE_ABSENT,
    ATTENDANCE_EXCUSED,
    ATTENDANCE_LATE,
    ATTENDANCE_PRESENT,
    AttendanceRecord,
    Enrollment,
)

# Ten-point scale: (minimum percentage, letter, grade points).
GRADE_BANDS = (
    (90.0, "O", 10.0),
    (80.0, "A+", 9.0),
    (70.0, "A", 8.0),
    (60.0, "B+", 7.0),
    (50.0, "B", 6.0),
    (40.0, "C", 5.0),
    (0.0, "F", 0.0),
)
PASS_MARK = 40.0


def grade_for(percentage: float | None) -> tuple[str, float]:
    """Map a weighted percentage onto (letter grade, grade points)."""
    if percentage is None:
        return ("—", 0.0)
    for minimum, letter, points in GRADE_BANDS:
        if percentage >= minimum:
            return (letter, points)
    return ("F", 0.0)


@dataclass
class AttendanceSummary:
    total_sessions: int = 0
    present: int = 0
    late: int = 0
    absent: int = 0
    excused: int = 0

    @property
    def attended(self) -> int:
        return self.present + self.late

    @property
    def counted(self) -> int:
        # Authorised absences are left out of the denominator rather than
        # penalising the student for them.
        return max(self.total_sessions - self.excused, 0)

    @property
    def percentage(self) -> float | None:
        if not self.counted:
            return None
        return round(self.attended / self.counted * 100, 1)

    @property
    def is_short(self) -> bool:
        pct = self.percentage
        return pct is not None and pct < 75.0

    @property
    def classes_needed(self) -> int:
        """How many consecutive classes at 100% are needed to reach 75%."""
        if self.percentage is None or self.percentage >= 75.0:
            return 0
        needed = 0
        attended, counted = self.attended, self.counted
        while counted and (attended / counted) * 100 < 75.0:
            attended += 1
            counted += 1
            needed += 1
        return needed


@dataclass
class CourseResult:
    percentage: float | None = None
    letter: str = "—"
    points: float = 0.0
    graded_weight: float = 0.0
    total_weight: float = 0.0
    complete: bool = False
    rows: list[dict] = field(default_factory=list)


@dataclass
class SemesterResult:
    semester: int | None = None
    credits: float = 0.0
    points: float = 0.0
    sgpa: float | None = None
    rows: list[dict] = field(default_factory=list)


@dataclass
class FeeSummary:
    invoiced: float = 0.0
    paid: float = 0.0
    balance: float = 0.0
    overdue: float = 0.0


def attendance_summary(student_id: int, course_id: int | None = None) -> AttendanceSummary:
    """Aggregate attendance for one student, optionally for a single course."""
    from .extensions import db
    from .models import AttendanceSession

    query = (
        db.session.query(AttendanceRecord.status, db.func.count(AttendanceRecord.id))
        .join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)
        .filter(AttendanceRecord.student_id == student_id)
    )
    if course_id is not None:
        query = query.filter(AttendanceSession.course_id == course_id)

    summary = AttendanceSummary()
    counts = {status: 0 for status in (ATTENDANCE_PRESENT, ATTENDANCE_LATE, ATTENDANCE_ABSENT, ATTENDANCE_EXCUSED)}
    for status, count in query.group_by(AttendanceRecord.status).all():
        counts[status] = count
    summary.present = counts[ATTENDANCE_PRESENT]
    summary.late = counts[ATTENDANCE_LATE]
    summary.absent = counts[ATTENDANCE_ABSENT]
    summary.excused = counts[ATTENDANCE_EXCUSED]
    summary.total_sessions = sum(counts.values())
    return summary


def course_result(student_id: int, course) -> CourseResult:
    """Weighted result for a student in a course.

    Weights are normalised, so a course whose assessments happen to add up to
    80% still produces a comparable percentage. Assessments without an entered
    score are left out of the weighting and mark the result as incomplete.
    """
    result = CourseResult()
    graded_marks = 0.0
    for assessment in course.assessments:
        result.total_weight += assessment.weight
        score = assessment.score_for(student_id)
        percentage = None
        if score is not None and score.marks is not None and assessment.max_score:
            percentage = score.marks / assessment.max_score * 100
        result.rows.append(
            {
                "assessment": assessment,
                "score": score,
                "percentage": percentage,
            }
        )
        if percentage is not None:
            graded_marks += percentage * assessment.weight
            result.graded_weight += assessment.weight

    if result.graded_weight:
        result.percentage = round(graded_marks / result.graded_weight, 1)
        result.letter, result.points = grade_for(result.percentage)
    result.complete = bool(result.total_weight) and result.graded_weight >= result.total_weight - 0.01
    return result


def semester_result(student_id: int, semester: int) -> SemesterResult:
    """SGPA for one semester across every enrolled course that has marks."""
    from .extensions import db

    enrollments = (
        Enrollment.query.filter_by(student_id=student_id, semester=semester)
        .filter(Enrollment.status != "dropped")
        .all()
    )
    result = SemesterResult(semester=semester)
    for enrollment in enrollments:
        course_result_for_student = course_result(student_id, enrollment.course)
        result.rows.append(
            {
                "course": enrollment.course,
                "credits": enrollment.course.credits,
                "result": course_result_for_student,
            }
        )
        if course_result_for_student.percentage is None:
            continue
        credits = enrollment.course.credits
        result.credits += credits
        result.points += credits * course_result_for_student.points

    if result.credits:
        result.sgpa = round(result.points / result.credits, 2)
    return result


def cumulative_result(student_id: int) -> tuple[float | None, float]:
    """CGPA and credits earned across all semesters with recorded results."""
    from .extensions import db
    from .models import Student

    student = db.session.get(Student, student_id)
    if student is None:
        return None, 0.0
    semesters = sorted({e.semester for e in student.enrollments if e.status != "dropped"})
    total_credits = 0.0
    total_points = 0.0
    for semester in semesters:
        result = semester_result(student_id, semester)
        if result.credits:
            total_credits += result.credits
            total_points += result.points
    if not total_credits:
        return None, 0.0
    return round(total_points / total_credits, 2), total_credits


def fee_summary(student) -> FeeSummary:
    summary = FeeSummary()
    for invoice in student.invoices:
        summary.invoiced += float(invoice.amount)
        summary.paid += float(invoice.paid_total)
        balance = float(invoice.balance)
        summary.balance += max(balance, 0)
        if invoice.status == "overdue":
            summary.overdue += max(balance, 0)
    return summary

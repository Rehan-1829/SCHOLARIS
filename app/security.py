"""Role helpers shared by the blueprints."""

from functools import wraps

from flask import abort
from flask_login import current_user

from .extensions import login_manager
from .models import ROLE_ADMIN, ROLE_STUDENT, ROLE_TEACHER


def role_required(*roles):
    """Restrict a view to the given roles; everything else gets a 403 page."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


admin_required = role_required(ROLE_ADMIN)
staff_required = role_required(ROLE_ADMIN, ROLE_TEACHER)


def can_manage_course(course) -> bool:
    """Admins manage every course; a teacher only the courses assigned to them."""
    if not current_user.is_authenticated:
        return False
    if current_user.role == ROLE_ADMIN:
        return True
    if current_user.role == ROLE_TEACHER and current_user.teacher is not None:
        return course.teacher_id == current_user.teacher.id
    return False


def require_course_access(course) -> None:
    if not can_manage_course(course):
        abort(403)


def current_student():
    """The Student row for the signed-in student, or None."""
    if current_user.is_authenticated and current_user.role == ROLE_STUDENT:
        return current_user.student
    return None

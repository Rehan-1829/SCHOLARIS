"""Fee ledger: invoices, payments and printable receipts."""

from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..helpers import clean, default_term, parse_date, parse_decimal, parse_int
from ..models import ROLE_ADMIN, ROLE_STUDENT, FeeInvoice, Payment, Student
from ..security import admin_required, role_required
from ..services import fee_summary

bp = Blueprint("finance", __name__, url_prefix="/fees")

PAYMENT_METHODS = ("upi", "card", "netbanking", "cash", "cheque", "scholarship")


def _next_receipt_no() -> str:
    year = date.today().year
    counter = Payment.query.count() + 1
    while True:
        candidate = f"RCPT-{year}-{counter:05d}"
        if not Payment.query.filter_by(receipt_no=candidate).first():
            return candidate
        counter += 1


def _can_view(invoice: FeeInvoice) -> bool:
    if current_user.role == ROLE_ADMIN:
        return True
    return (
        current_user.role == ROLE_STUDENT
        and current_user.student is not None
        and current_user.student.id == invoice.student_id
    )


@bp.get("/")
@role_required(ROLE_ADMIN, ROLE_STUDENT)
def index():
    if current_user.role == ROLE_STUDENT:
        student = current_user.student
        if student is None:
            abort(403)
        invoices = sorted(student.invoices, key=lambda invoice: invoice.due_date, reverse=True)
        return render_template(
            "finance/index.html", student=student, invoices=invoices, summary=fee_summary(student)
        )

    status = clean(request.args.get("status"))
    q = clean(request.args.get("q")).lower()
    invoices = FeeInvoice.query.join(Student).all()
    if q:
        invoices = [
            invoice
            for invoice in invoices
            if q in invoice.student.name.lower() or q in invoice.student.roll_no.lower()
        ]
    if status:
        invoices = [invoice for invoice in invoices if invoice.status == status]
    invoices.sort(key=lambda invoice: (invoice.status == "paid", invoice.due_date))

    total_invoiced = sum(float(invoice.amount) for invoice in invoices)
    total_paid = sum(float(invoice.paid_total) for invoice in invoices)
    return render_template(
        "finance/index.html",
        invoices=invoices,
        status=status,
        q=q,
        total_invoiced=total_invoiced,
        total_paid=total_paid,
        total_balance=max(total_invoiced - total_paid, 0),
        overdue=sum(
            1 for invoice in invoices if invoice.status == "overdue"
        ),
    )


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def new():
    students = Student.query.filter_by(status="active").join(Student.user).order_by(Student.roll_no).all()
    if request.method == "POST":
        student = db.session.get(Student, parse_int(request.form.get("student_id"), 0))
        title = clean(request.form.get("title"))
        amount = parse_decimal(request.form.get("amount"))
        due_date = parse_date(request.form.get("due_date"))
        term = clean(request.form.get("term")) or default_term()

        errors = []
        if student is None:
            errors.append("Choose a student.")
        if not title:
            errors.append("Add a short description for the invoice.")
        if amount is None or amount <= 0:
            errors.append("Amount must be greater than zero.")
        if due_date is None:
            errors.append("Pick a due date.")

        if not errors:
            invoice = FeeInvoice(
                student_id=student.id,
                term=term,
                title=title,
                amount=amount,
                due_date=due_date,
            )
            db.session.add(invoice)
            db.session.commit()
            flash(f"Invoice raised for {student.name}.", "success")
            return redirect(url_for("finance.detail", invoice_id=invoice.id))

        for error in errors:
            flash(error, "error")

    return render_template(
        "finance/new.html",
        students=students,
        term=default_term(),
        today=date.today(),
    )


@bp.get("/<int:invoice_id>")
@role_required(ROLE_ADMIN, ROLE_STUDENT)
def detail(invoice_id: int):
    invoice = db.session.get(FeeInvoice, invoice_id)
    if invoice is None:
        abort(404)
    if not _can_view(invoice):
        abort(403)
    return render_template(
        "finance/detail.html",
        invoice=invoice,
        methods=PAYMENT_METHODS,
        today=date.today(),
    )


@bp.post("/<int:invoice_id>/payments")
@admin_required
def record_payment(invoice_id: int):
    invoice = db.session.get(FeeInvoice, invoice_id)
    if invoice is None:
        abort(404)

    amount = parse_decimal(request.form.get("amount"))
    method = clean(request.form.get("method"))
    reference = clean(request.form.get("reference"))
    paid_on = parse_date(request.form.get("paid_on"), date.today())

    errors = []
    if amount is None or amount <= 0:
        errors.append("Payment amount must be greater than zero.")
    elif invoice.balance <= 0:
        errors.append("This invoice is already settled.")
    elif amount > invoice.balance:
        errors.append(f"Payment cannot exceed the outstanding balance of ₹{invoice.balance:,.2f}.")
    if method not in PAYMENT_METHODS:
        errors.append("Choose a valid payment method.")
    if paid_on > date.today():
        errors.append("Payment date cannot be in the future.")

    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("finance.detail", invoice_id=invoice.id))

    payment = Payment(
        invoice_id=invoice.id,
        amount=amount,
        method=method,
        reference=reference or None,
        paid_on=paid_on,
        receipt_no=_next_receipt_no(),
        recorded_by_id=current_user.id,
    )
    db.session.add(payment)
    db.session.commit()
    flash(f"Payment recorded — receipt {payment.receipt_no}.", "success")
    return redirect(url_for("finance.receipt", payment_id=payment.id))


@bp.get("/receipts/<int:payment_id>")
@role_required(ROLE_ADMIN, ROLE_STUDENT)
def receipt(payment_id: int):
    payment = db.session.get(Payment, payment_id)
    if payment is None:
        abort(404)
    if not _can_view(payment.invoice):
        abort(403)
    return render_template("finance/receipt.html", payment=payment, invoice=payment.invoice)

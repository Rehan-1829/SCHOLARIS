# How Scholaris works — a walkthrough for the viva

This is the file to read the night before the demo. It explains what happens to a click,
in the order it happens, and gives you a 3-minute presentation script plus the questions a
panel usually asks.

---

## 1. The one-paragraph version

Scholaris is a Flask web application. The browser asks for a URL, Flask matches it to a
Python function (a *view*), that function reads or writes rows through SQLAlchemy, and Jinja
renders an HTML page from the result. Three kinds of user — registrar, faculty, student —
share the same tables but see different pages and different rows, and that restriction is
enforced on the server, not by hiding links. Grades, attendance percentages and fee
balances are not stored anywhere; they are calculated from the underlying records every
time a page needs them. That is why changing one mark immediately changes the grade sheet,
the dashboard and the transcript.

---

## 2. What runs when you double-click the batch file

1. `START_SCHOLARIS.bat` looks for `portable/python/python.exe` next to it. If that exists
   it uses it; if not, it falls back to a system Python.
2. It runs `launch.py`.
3. `launch.py` asks Flask to create the app (`create_app()`), which opens the SQLite file
   `instance/scholaris.db` and creates any missing tables.
4. If the `user` table is empty, it calls the seed function from `app/cli.py`, which builds
   the demo college — students, courses, registers, marks, invoices.
5. It finds a free port (5000, then 5001, …), starts the server, and opens the browser once
   the server answers.

The black console window is the web server. Closing it stops the site.

---

## 3. The request lifecycle, in code

```
GET /courses/3/attendance?date=2026-10-21
        │
        ▼
app/__init__.py          app factory registered courses.bp with prefix /courses
        │
        ▼
courses.py:285           @bp.route("/<int:course_id>/attendance", methods=["GET","POST"])
        │                login_required → role check → require_course_access(course)
        ▼
models.py                AttendanceSession.query.filter_by(course_id=…, session_date=…)
        │                AttendanceRecord rows for that session
        ▼
templates/courses/attendance.html   roster + radio buttons, one row per student
        │
        ▼   (POST: the form is submitted with a CSRF token)
courses.py:285           validates, upserts the session, replaces the records
        │
        ▼
services.py:112          attendance_summary() — present + late over (total − excused)
        │
        ▼
templates/…              the new percentage appears on the same page
```

The same three-layer split repeats everywhere: **blueprint (route) → model/service →
template**. Routes are short because they only handle HTTP; the arithmetic is in
`services.py`; the tables are in `models.py`.

---

## 4. The database in eight sentences

- `User` holds the login: email, password hash, role (`admin`, `teacher`, `student`).
- `Student` and `Teacher` extend a user with the details of that role, so authentication is
  written once.
- `Course` belongs to a `Teacher`, carries credits, semester and a seat capacity.
- `Enrollment` joins a student to a course for a semester, with status
  `enrolled` / `completed` / `dropped`; a unique constraint stops double enrolment.
- `AttendanceSession` is one class held on one date; a unique constraint on
  (course, date) enforces one register per course per day.
- `AttendanceRecord` is one student's mark in one session: present, late, absent, excused.
- `Assessment` is a quiz/test/exam with a maximum score and a weight; `Score` is one
  student's marks in it, unique per student per assessment.
- `FeeInvoice` is an amount owed with a due date; `Payment` is money received against it,
  with a sequential receipt number.

Open `instance/scholaris.db` in DB Browser for SQLite during the viva if the panel wants to
see the tables — that is the strongest possible answer to "where is the data".

---

## 5. The three rules, and where they live

| Rule | Function | What it does |
| --- | --- | --- |
| Grade from percentage | `services.grade_for` | 90+ = O … below 40 = F, plus grade points |
| Course result | `services.course_result` | weighted mean of assessments, weights normalised, incomplete assessments skipped |
| SGPA / CGPA | `services.semester_result`, `cumulative_result` | credit-weighted across courses, then across semesters |
| Attendance | `services.attendance_summary` | `(present + late) / (total − excused)` |
| Fee balance | `services.fee_summary` | `amount − payments`, status paid → overdue → partial → due |

Because these are ordinary functions taking rows as arguments, they are unit-tested without
a server: `tests/test_services.py` calls them directly with made-up numbers.

---

## 6. How permissions actually work

`app/security.py` has three tools:

- `role_required("admin")` — decorator on a route; wrong role gets a 403 page.
- `require_course_access(course)` — a teacher may only touch a course they teach; a student
  may only read a course they are enrolled in.
- `current_student()` — resolves the logged-in user to their student row.

So when a student edits the URL to `/students/7` for somebody else's record, the route
checks ownership and returns 403. The test `test_auth.py` asserts exactly this, which is
worth saying out loud in the viva: *"hiding the link is cosmetic; the check is server-side
and it is tested."*

---

## 7. Three-minute demo script

A browser holds one signed-in session, so three tabs in the same window cannot be three
roles at once. Sign in and out as you move down the script, or keep a second role open in
an incognito window if you want two on screen together.

**Registrar (tab 1, 60 seconds)**

1. "This is the registrar's desk" — point at enrolment count, fees collected, overdue
   invoices, attendance health.
2. Students → search `Rehan` → open the profile → show roll number, semester, guardian,
   attendance and dues. Click **Print transcript** and show the print preview, then close it.
3. Courses → open `BCA502` → show the roster and that seats are counted against capacity.

**Faculty (tab 2, 60 seconds)**

1. Sign in as `lakshmi.venkatesan@scholaris.edu` → the desk lists only the two courses she
teaches, `BCA401` and `BCA501`, out of seven in the catalogue.
2. Courses → `BCA503` → **Take register** → tick a couple of students and save → "the
   percentage recalculated immediately because attendance is derived, not stored".
3. Grades → point at the weighted column and the letter grade.

**Student (tab 3, 60 seconds)**

1. Sign in as `aarav.mehta@student.scholaris.edu` → the desk shows this term's attendance,
grades and fee dues. (For a shortage banner, sign in as `ishita.nair@student.scholaris.edu`
instead — she is deliberately below 75% in Networks.)
2. Courses → show per-subject attendance and marks breakdown.
3. My fees → show dues and a receipt. Transcript → SGPA and CGPA.
4. Finish on the registrar tab: "and this student could not open another student's
   transcript — the server returns 403", then paste the URL to prove it.

---

## 8. Questions you will probably be asked

**"Where is the data stored?"**
In a SQLite file, `instance/scholaris.db`, through SQLAlchemy. It is a real relational
database with foreign keys and unique constraints; SQLite just means no server to install.
`DATABASE_URL` switches it to Postgres without code changes.

**"Why Flask and not Django?"**
The project is small and the interesting part is the rules, not the admin scaffolding.
Flask makes every layer visible in about fifteen files, which is easier to explain than
Django's conventions.

**"What happens if two teachers save the same register?"**
The unique constraint on (course, date) means the second save updates the existing session
rather than creating a duplicate; the route already looks the session up before inserting.

**"Why isn't the percentage stored in the student table?"**
Because it would go stale. It is derived from attendance records, so it cannot disagree
with them. The trade-off is a query per page, which is fine at this size and could be
cached later.

**"How are passwords protected?"**
Werkzeug's `generate_password_hash` (PBKDF2/scrypt), never stored in plain text. Sessions
are signed cookies with HttpOnly and SameSite=Lax; every POST carries a CSRF token.

**"What stops a student from reading someone else's marks?"**
`require_course_access` / ownership checks in the route, returning 403. Tested in
`tests/test_auth.py`.

**"How do you know it works?"**
36 automated tests: pure calculation tests, request-level workflow tests, and a smoke test
that renders every page for all three roles. Run `pytest -q`.

**"What are the weaknesses?"**
Attendance is per day rather than per period; login throttling is in memory so it resets on
restart; no migrations, email or file uploads; SQLite is not for concurrent production
traffic. All of these are listed in the README rather than hidden.

---

## 9. If something goes wrong on the day

| Symptom | Fix |
| --- | --- |
| Black window flashes and closes | Run `START_SCHOLARIS.bat` from a terminal to read the message |
| Page says "This site can't be reached" | The console was closed; double-click the batch file again |
| Port already in use | The launcher picks the next free port automatically — check the URL it prints |
| Demo data looks wrong after experimenting | `RESET_DEMO_DATA.bat` rebuilds it in about three seconds |
| Windows blocks the .bat | Right-click → Properties → Unblock, or copy the folder again |
| Teacher's PC has no Python at all | Use the copy that contains the `portable/` folder |

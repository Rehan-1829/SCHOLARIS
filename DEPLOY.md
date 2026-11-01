# Deploying Scholaris

Scholaris is a normal WSGI Flask application, so it runs anywhere Python runs. What
decides the host is the database.

| Where the data lives | Used by |
| --- | --- |
| `instance/scholaris.db`, a SQLite file next to the code | your laptop, PythonAnywhere |
| A Postgres server (Neon, free) | Render, Vercel, any serverless host |
| Cloudflare D1 | only after a rewrite — Flask does not run on Workers |

Two options below are genuinely free and work with this repository as it stands.

---

## Option A — PythonAnywhere (recommended)

Free "Beginner" account, no credit card. The app runs on a real WSGI server and the SQLite
file sits on persistent disk, so **nothing in the repository changes**. The URL is
`https://USERNAME.pythonanywhere.com`.

Catch: free web apps are switched off after about a month without a login. Open the Web tab
and press the renewal button the week before your viva.

1. Create an account at [pythonanywhere.com](https://www.pythonanywhere.com/).
2. Open **Consoles → Bash** and clone the repository:

   ```bash
   git clone https://github.com/lizz1177/SCHOLARIS.git scholaris
   cd scholaris
   ```

3. Create the virtualenv and install the dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Web → Add a new web app → Manual configuration → Python 3.11** (or newer).
5. On the Web tab:
   - **Source code**: `/home/USERNAME/scholaris`
   - **Working directory**: `/home/USERNAME/scholaris`
   - **Virtualenv**: `/home/USERNAME/scholaris/.venv`
6. Click the **WSGI configuration file** link, delete everything in it, paste the contents of
   [`deploy/pythonanywhere_wsgi.py`](deploy/pythonanywhere_wsgi.py) and replace `USERNAME`.
7. Back in the Bash console, create the demo college:

   ```bash
   cd ~/scholaris
   source .venv/bin/activate
   flask --app run.py seed
   ```

8. Press **Reload** on the Web tab and open the URL. Sign in with an account from
   [LOGINS.txt](LOGINS.txt).

The database is the file `/home/USERNAME/scholaris/instance/scholaris.db`. It survives
reloads and sleeps; download it from the **Files** tab for a backup. To rebuild the demo
data, run `flask --app run.py seed --force`.

### Environment variables

Create `~/scholaris/.env`:

```ini
SECRET_KEY=paste-a-long-random-string
CURRENT_TERM=2026-27 · Odd semester
```

`run.py` loads this file on import, including under WSGI, so the same file works locally.
Generate the key with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

PythonAnywhere restricts outbound internet on free accounts, which is fine here: the fonts
are self-hosted and the app makes no external requests.

---

## Option B — Render + Neon

Gives a permanent `*.onrender.com` URL that redeploys from GitHub. Render's free filesystem
is ephemeral, so SQLite would be wiped on every restart — and Render's own free Postgres
expires 30 days after creation. Use Neon's free Postgres instead; it does not expire.

1. Create a project at [neon.com](https://neon.com/) and copy the connection string. It
   starts with `postgresql://` and ends with `?sslmode=require`.
2. At [render.com](https://render.com/): **New → Web Service**, connect
   `lizz1177/SCHOLARIS`.
   - **Language**: Python 3
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**:
     `flask --app run.py seed --if-empty && waitress-serve --port=$PORT run:app`
3. Add environment variables:
   - `DATABASE_URL` — the Neon connection string
   - `SECRET_KEY` — the generated key
4. Create the service. On first boot it creates the tables, seeds the demo college once and
   starts the WSGI server.
5. Open `https://NAME.onrender.com`. The first request after 15 idle minutes takes about a
   minute while the free instance wakes.

`--if-empty` makes the seed line safe on every restart: an existing college is left alone.
Do not create Render's free Postgres — it expires after 30 days.

---

## Vercel (free Hobby)

Flask runs as a serverless function, but the filesystem is read-only apart from `/tmp`, so
SQLite cannot be used and Postgres is mandatory. It also needs an `api/index.py` exporting
`app`, a rewrite in `vercel.json`, and a `DATABASE_URL` pointing at Neon. Hobby accounts are
for non-commercial use, and functions are archived when idle. Nothing is configured for it
in this repository; Option A or B is less work.

## Cloudflare Workers (free)

Cannot run this app. Python Workers are Pyodide isolates, and Flask, SQLAlchemy and a SQLite
file are not supported; Cloudflare's D1 database replaces SQLite. A Cloudflare deployment
would be a port to FastAPI/Workers + D1, not a deployment of this code.

---

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| 500 error on the first page | Usually a missing or malformed `DATABASE_URL` or `SECRET_KEY`; check the host's logs |
| `relation "user" does not exist` | The seed step did not run; run `flask --app run.py seed` |
| Styling missing, plain HTML | Static files are served by Flask; make sure the app loaded at all (a 404 on `/static/css/app.css` means the WSGI path is wrong) |
| Login works, then signs out on refresh | `SECRET_KEY` is not set, so it changes between workers/restarts |
| First request very slow | Render free instance waking up; expected |
| PythonAnywhere says "Something went wrong" | Web tab → **Error log**; usually the WSGI path or virtualenv is wrong |

"""Start Scholaris on this computer and open it in a browser.

Double-click ``START_SCHOLARIS.bat`` on Windows, or run ``python launch.py``.
The launcher is deliberately boring: it finds a free port, creates the demo
database the first time, serves the app on 127.0.0.1 and opens the browser.

    python launch.py            start the app
    python launch.py --check    show what is installed and whether the data is ready
    python launch.py --reset    rebuild the demo college, then start
    python launch.py --port 5010
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORTS = range(5000, 5021)

os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BANNER = "Scholaris - Student Records Office"


def describe_python() -> str:
    return f"Python {sys.version.split()[0]} at {sys.executable}"


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((HOST, port))
        except OSError:
            return False
    return True


def running_instance() -> int | None:
    """Return the port of a Scholaris that is already running, if any."""
    for port in PORTS:
        try:
            with urllib.request.urlopen(f"http://{HOST}:{port}/login", timeout=0.3) as response:
                body = response.read(8192).decode("utf-8", "ignore")
        except (urllib.error.URLError, OSError, ValueError):
            continue
        if "Scholaris" in body:
            return port
    return None


def prepare_database(reset: bool = False):
    """Create the app, seeding the demo college when the database is empty."""
    from app import create_app
    from app.cli import seed_demo_data
    from app.models import Course, Student, User

    app = create_app()
    with app.app_context():
        counts = {
            "users": User.query.count(),
            "students": Student.query.count(),
            "courses": Course.query.count(),
        }
        if reset:
            print("Rebuilding the demo college...")
            seed_demo_data(force=True)
            counts = {
                "users": User.query.count(),
                "students": Student.query.count(),
                "courses": Course.query.count(),
            }
        elif counts["users"] == 0:
            print("First run: creating the demo college (this takes a few seconds)...")
            seed_demo_data(force=False)
            counts = {
                "users": User.query.count(),
                "students": Student.query.count(),
                "courses": Course.query.count(),
            }
    return app, counts


def show_login_hint() -> None:
    print()
    print("  Sign in with:")
    print("    Registrar   registrar@scholaris.edu                 registrar123")
    print("    Faculty     lakshmi.venkatesan@scholaris.edu       faculty123")
    print("    Student     aarav.mehta@student.scholaris.edu      student123")
    print("  All accounts are listed in LOGINS.txt.")


def serve(app, port: int, open_browser: bool) -> int:
    import logging

    from werkzeug.serving import make_server

    # Keep the console readable: our own banner instead of every request line.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    url = f"http://{HOST}:{port}"
    try:
        server = make_server(HOST, port, app, threaded=True)
    except OSError as error:
        print(f"\n  Could not start on port {port}: {error}")
        print("  Try: python launch.py --port 5015")
        return 1

    print()
    print("  " + "=" * 58)
    print(f"  {BANNER}")
    print(f"  Open this address:  {url}")
    print("  " + "=" * 58)
    show_login_hint()
    print()
    print("  Leave this window open while you demo the site.")
    print("  Close the window (or press Ctrl+C) to stop the server.")
    print()

    if open_browser:
        threading.Timer(0.8, webbrowser.open_new_tab, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopping...")
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    try:  # make the banner appear immediately, even when output is redirected
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="Start the Scholaris web app.")
    parser.add_argument("--port", type=int, default=None, help="port to use (default: first free from 5000)")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument("--check", action="store_true", help="check the setup and exit")
    parser.add_argument("--reset", action="store_true", help="rebuild the demo data first")
    args = parser.parse_args(argv)

    print(BANNER + " launcher")
    print("  " + describe_python())
    print("  Folder: " + str(ROOT))

    try:
        import flask  # noqa: F401
        import flask_login  # noqa: F401
        import flask_sqlalchemy  # noqa: F401
        import flask_wtf  # noqa: F401
    except ImportError:
        print()
        print("  The Python packages this app needs are not installed.")
        print("  Use the copy of this folder that includes the 'portable'")
        print("  directory, or run:  pip install -r requirements.txt")
        return 1

    if args.check:
        try:
            app, counts = prepare_database(reset=args.reset)
        except Exception:
            print("\n  The database could not be prepared:")
            traceback.print_exc()
            return 1
        print("  Database: " + str(Path(app.instance_path) / "scholaris.db"))
        print(f"  Data: {counts['users']} accounts, {counts['students']} students, {counts['courses']} courses")
        print("  App imports correctly. Run START_SCHOLARIS.bat to use it.")
        return 0

    if not args.reset:
        existing = running_instance()
        if existing is not None:
            url = f"http://{HOST}:{existing}"
            print(f"\n  Scholaris is already running at {url}")
            if not (args.no_browser or os.environ.get("SCHOLARIS_NO_BROWSER")):
                webbrowser.open_new_tab(url)
            time.sleep(1.5)
            return 0

    try:
        app, _counts = prepare_database(reset=args.reset)
    except ImportError:
        print()
        print("  The Python packages this app needs are not installed.")
        print("  In START_SCHOLARIS.bat, delete the .venv folder and run it again,")
        print("  or use the copy that includes the 'portable' directory.")
        return 1
    except Exception:
        print("\n  Scholaris could not open its database.")
        print("  The file instance/scholaris.db may be damaged.")
        print("  Run RESET_DEMO_DATA.bat (or: python launch.py --reset) to rebuild it.")
        print()
        traceback.print_exc()
        return 1

    if args.port is not None:
        port = args.port
        if not port_is_free(port):
            print(f"\n  Port {port} is already in use. Omit --port to pick a free one.")
            return 1
    else:
        port = next((candidate for candidate in PORTS if port_is_free(candidate)), None)
        if port is None:
            print("\n  No free port between 5000 and 5020. Close other apps and try again.")
            return 1

    open_browser = not (args.no_browser or os.environ.get("SCHOLARIS_NO_BROWSER"))
    return serve(app, port, open_browser)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        print("\n  Scholaris stopped unexpectedly. The error is below.")
        traceback.print_exc()
        input("\n  Press Enter to close this window...")
        raise SystemExit(1)

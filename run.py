from pathlib import Path

from dotenv import load_dotenv

# Config reads the environment when the app package is imported, so .env has to
# be loaded first. This also makes a host's WSGI entry point behave like `flask run`.
load_dotenv(Path(__file__).resolve().parent / ".env")

from app import create_app  # noqa: E402  (import must follow load_dotenv)

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

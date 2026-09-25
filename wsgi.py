"""WSGI entry point.

Development::

    flask --app wsgi run --debug

Production, for example with Gunicorn or Waitress::

    gunicorn "wsgi:app" --bind 0.0.0.0:8000
    waitress-serve --port=8000 wsgi:app
"""

from __future__ import annotations

from app import create_app

app = create_app()


if __name__ == "__main__":
    # Convenience only; use a real WSGI server in production.
    app.run(host="127.0.0.1", port=5000, debug=app.config.get("DEBUG", False))

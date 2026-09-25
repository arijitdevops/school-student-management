#!/usr/bin/env python3
"""Create (or recreate) the database tables from the SQLAlchemy models.

This is the quick path for a development database.  For anything you intend to
keep, use Flask-Migrate instead so that schema changes are versioned::

    flask db upgrade

Usage::

    python scripts/init_db.py
    python scripts/init_db.py --drop
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running the script directly from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

LOGGER = logging.getLogger("init_db")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop every table before creating it again. This destroys all data.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Configuration name to load (development, testing, production).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Create the schema and report the tables that exist afterwards."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    args = parse_args(argv)

    app = create_app(args.config)
    with app.app_context():
        try:
            if args.drop:
                LOGGER.warning(
                    "Dropping every table in %s", app.config["SQLALCHEMY_DATABASE_URI"].rsplit("/", 1)[-1]
                )
                db.drop_all()
            db.create_all()
            tables = sorted(inspect(db.engine).get_table_names())
        except SQLAlchemyError as error:
            LOGGER.error("Could not create the schema: %s", error)
            LOGGER.error("Check DATABASE_URL and that the database itself exists.")
            return 1

    LOGGER.info("Schema ready. %d table(s): %s", len(tables), ", ".join(tables))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

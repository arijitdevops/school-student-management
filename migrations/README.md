# Migrations

Flask-Migrate (Alembic) keeps the versioned schema history here. The initial
revision, `versions/0001_initial_schema.py`, creates every table in
`app/models/` and was generated against MySQL 8.

## Apply the schema

From the repository root, with the virtual environment active and
`DATABASE_URL` pointing at an existing, empty database:

```bash
flask --app wsgi db upgrade
```

## Day-to-day

After changing a model:

```bash
flask --app wsgi db migrate -m "add house column to students"
flask --app wsgi db upgrade
flask --app wsgi db downgrade   # step back one revision
flask --app wsgi db current     # show the applied revision
flask --app wsgi db history     # list every revision
```

## Notes

- Always read the generated revision before applying it. Alembic's
  autogeneration does not reliably detect renamed columns, changed server
  defaults or `CHECK` constraints, and it can write a drop-then-create pair
  that loses data.
- Commit the files under `versions/`. They are the schema's history, and the
  team needs the same sequence of revisions.
- The application sets the migration directory explicitly in `create_app`,
  so `flask db` works from the repository root without extra environment
  variables.
- `database/schema.sql` is a hand-maintained snapshot of the same schema for
  environments that create tables by hand, and it is what the Docker Compose
  MySQL container loads on first start. It is not used by Alembic; if you
  change the models, update both.

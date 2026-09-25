# School Student Management System

A Flask web application for running the student records of a school with classes 1 to 10: enrolment, the subject catalogue, mark entry for four exams a year, and the report cards and ranked result lists that come out of them. Data lives in MySQL 8 through SQLAlchemy, the schema is versioned with Alembic, and the aggregation and ranking logic sits in a pure-Python service layer that is unit tested without a database. A seed script builds a complete fictional school - ten classes, two sections each, 40 to 50 students per class and a mark for every student, subject and exam - from a fixed random seed, and the same data is committed as a ready-to-import MySQL dump in [`database/seed_data.sql`](database/seed_data.sql) (442 students, 8,824 marks), so you can explore the application without running any Python against the database.

![Python](https://img.shields.io/badge/python-3.9%2B-3776AB)
![Flask](https://img.shields.io/badge/Flask-3.x-000000)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.x-D71F00)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

**Students**
- Paginated list with a text search across name, admission number and guardian, plus class, section and status filters.
- A full student record: admission number, roll number, class and section, name, date of birth, gender, blood group, parent or guardian name and relation, contact phone, email, address, admission date and enrolment status.
- Add and edit through a Flask-WTF form that checks the admission number is unique, the roll number is free within the class and section, the section actually belongs to the chosen class, and the dates make sense.
- Two ways to remove a student: **Remove from roll** clears `is_active` so marks and past report cards survive (and can be restored), while **Delete permanently** removes the student and every mark recorded for them.
- Detail page showing the record and every mark on file.

**Subjects**
- A subject catalogue with unique codes, and a separate class-subject assignment carrying the mark scheme, because the same subject is worth 50 marks in class 3 and 100 in class 9.
- English, Mathematics and Hindi in every class; Environmental Studies in classes 1 to 5; Science, Social Studies and Computer Science in classes 6 to 10.
- Add, edit and delete subjects. Deleting a subject also removes its class assignments and every mark recorded for it, after a confirmation that says so; unassigning a subject from one class removes that class's marks for it.

**Marks**
- Bulk entry grid for one class, subject and exam, with an optional section filter. Saving the same grid twice updates rows rather than duplicating them.
- Per-student editor covering every subject for a chosen exam, reached from the student's page with **Edit marks**.
- Server-side validation of every cell: numeric, and within `0` to the paper's maximum. An absent student is recorded as absent rather than as a zero.
- Enter moves down the column, as in a spreadsheet.

**Reports**
- Individual report card: marks per subject per exam, subject totals and percentages, letter grade, subject pass/fail, weighted aggregate and class rank.
- A printable report card with an `@media print` stylesheet, an A4 page box and a signature block.
- Class result list ranked by weighted aggregate, with competition ranking so ties share a rank, plus class average, highest, lowest and pass count.
- CSV export of any class or section result list.

**Engineering**
- Application factory, five blueprints, Flask-Migrate, CSRF protection on every mutating form.
- Ranking and aggregation are pure functions in `app/services/results.py` with no Flask or session imports, unit tested directly.
- Errors handled at the database, form and template layers, with a rollback and a 500 page rather than a traceback.
- Tests run on in-memory SQLite through a configuration override, so no MySQL server is needed to run them.

## Tech stack

| Layer | Choice |
| --- | --- |
| Language | Python 3.9+ |
| Web framework | Flask 3 (application factory, blueprints) |
| ORM | SQLAlchemy 2 via Flask-SQLAlchemy 3.1 |
| Migrations | Flask-Migrate / Alembic |
| Forms | Flask-WTF and WTForms, with CSRF protection |
| Database | MySQL 8 through PyMySQL; SQLite for the test suite |
| Templates | Jinja2 with Bootstrap 5.3 |
| Seed data | Faker with a fixed seed, exported to a MySQL dump |
| Local MySQL | Docker Compose (`mysql:8.0`) |
| Tests | pytest |
| Linting | ruff |

## Project structure

```
school-student-management/
├── app/
│   ├── __init__.py              # create_app: extensions, blueprints, errors, CLI
│   ├── config.py                # Development / Testing / Production settings
│   ├── extensions.py            # db, migrate, csrf, TimestampMixin, utcnow
│   ├── models/
│   │   ├── __init__.py
│   │   ├── academic.py          # AcademicYear, SchoolClass, Section
│   │   ├── student.py           # Student (soft delete, roll uniqueness)
│   │   ├── subject.py           # Subject, ClassSubject (mark scheme)
│   │   ├── exam.py              # Exam (weightage)
│   │   └── mark.py              # Mark (student x class-subject x exam)
│   ├── blueprints/
│   │   ├── __init__.py          # all_blueprints()
│   │   ├── main.py              # dashboard, health check
│   │   ├── students.py          # list, search, create, edit, soft delete
│   │   ├── subjects.py          # catalogue and class assignments
│   │   ├── marks.py             # bulk grid and per-student entry
│   │   └── reports.py           # report cards, class results, CSV export
│   ├── forms/
│   │   ├── __init__.py
│   │   ├── student.py           # StudentForm, StudentFilterForm
│   │   ├── subject.py           # SubjectForm, ClassSubjectForm
│   │   └── mark.py              # filter form and grid parsing helpers
│   ├── services/
│   │   ├── __init__.py
│   │   ├── results.py           # grading, aggregation, competition ranking, CSV rows
│   │   └── seed_helpers.py      # subject and exam catalogues, mark generators
│   ├── templates/
│   │   ├── base.html
│   │   ├── _macros.html         # form fields, pagination, POST buttons
│   │   ├── index.html
│   │   ├── students/            # list.html, form.html, detail.html
│   │   ├── subjects/            # list.html, form.html, assign.html
│   │   ├── marks/               # select.html, entry.html, student.html
│   │   ├── reports/             # index.html, class_result.html, report_card.html,
│   │   │                        # report_card_print.html, _report_card_body.html
│   │   └── errors/              # 404.html, 500.html
│   └── static/
│       ├── css/app.css          # layout tweaks and the @media print rules
│       └── js/app.js            # absent toggles, grid navigation, confirmations
├── database/
│   ├── schema.sql               # plain MySQL 8 DDL (creates school_db)
│   └── seed_data.sql            # the fictional school as MySQL INSERTs (~820 KB)
├── migrations/
│   ├── README.md                # how to create and apply Alembic revisions
│   ├── alembic.ini, env.py, script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
├── scripts/
│   ├── init_db.py               # create the tables straight from the models
│   ├── seed_data.py             # reproducible demo school, with --reset
│   └── export_seed_sql.py       # regenerate database/seed_data.sql
├── tests/
│   ├── conftest.py              # in-memory SQLite app and seeded fixtures
│   ├── test_management.py       # permanent delete, subjects, per-student marks
│   ├── test_results.py          # pure tests for grading and ranking
│   ├── test_seed.py             # seed generators and the committed dump
│   └── test_students.py         # route tests for students, reports and marks
├── docs/
│   └── images/                  # screenshots referenced by this README
├── docker-compose.yml           # MySQL 8 with the schema and demo data preloaded
├── wsgi.py
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## Prerequisites

- Python 3.9 or newer.
- MySQL 8.0: either Docker (the included `docker-compose.yml` starts one) or your own server with an account that can create tables.
- `pip` and the ability to create a virtual environment.

MySQL is not needed to run the test suite; it uses SQLite in memory.

## Installation

Windows (PowerShell or Command Prompt):

```bat
git clone https://github.com/commonlabs/school-student-management.git
cd school-student-management
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

Linux and macOS:

```bash
git clone https://github.com/commonlabs/school-student-management.git
cd school-student-management
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Copy the environment template:

```bat
copy .env.example .env
```

```bash
cp .env.example .env
```

Then set up the database in one of two ways.

### Option A: Docker (schema and demo data loaded automatically)

```bash
docker compose up -d
```

On its first start the `mysql:8.0` container creates `school_db`, runs `database/schema.sql` and imports `database/seed_data.sql`. The root password is `password`, which matches the `DATABASE_URL` in `.env.example`, so nothing else needs configuring. `docker compose down -v` throws the data away; the next `up` reloads it.

### Option B: your own MySQL 8 server

Create the database and a user (or use `root`), and put the credentials in `DATABASE_URL` in `.env`:

```sql
CREATE DATABASE school_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'school'@'localhost' IDENTIFIED BY 'change-me';
GRANT ALL PRIVILEGES ON school_db.* TO 'school'@'localhost';
FLUSH PRIVILEGES;
```

**Create the schema**, using any one of:

```bash
flask --app wsgi db upgrade          # Alembic, recommended for anything long-lived
python scripts/init_db.py            # create the tables straight from the models
mysql -u root -p < database/schema.sql   # hand-written DDL (creates school_db itself)
```

**Load the demo school**, using either:

```bash
# 1. Import the committed dump (no Python needed; replaces any rows in these tables)
mysql -u root -p school_db < database/seed_data.sql

# 2. Or generate the same data with the seed script
python scripts/seed_data.py
```

Both give the same school: the dump was produced by `scripts/export_seed_sql.py`, which runs the seed script's code with the default seed and year. The seed script prints a row count per table when it finishes. It is idempotent, so running it again changes nothing; `python scripts/seed_data.py --reset` drops every table first and rebuilds from scratch.

## Configuration

All settings come from the environment. `flask run` loads `.env` through python-dotenv; a production WSGI server does not, so export the variables there.

| Variable | Description | Default |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy connection string. URL-encode special characters in the password. | `mysql+pymysql://root:password@localhost:3306/school_db` |
| `SECRET_KEY` | Signs the session cookie and CSRF tokens. **Required when `FLASK_ENV=production`**; the factory raises at start-up if it is missing. | `dev-secret-change-me` |
| `FLASK_ENV` | Which configuration class to load: `development`, `testing` or `production`. | `development` |
| `SCHOOL_NAME` | Name shown in the navigation bar and on printed report cards. | `Greenfield Public School` |
| `ITEMS_PER_PAGE` | Rows per page in the student list. | `25` |
| `LOG_LEVEL` | Root logging level. | `INFO` |
| `SQLALCHEMY_ECHO` | Set to `1` to log every SQL statement in development. | `0` |
| `TEST_DATABASE_URL` | Connection string used by the test suite. | `sqlite+pysqlite:///:memory:` |

Generate a secret key with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Usage

Start the development server:

```bash
flask --app wsgi run --debug
```

Then open <http://127.0.0.1:5000/>.

In production, run it behind a real WSGI server:

```bash
waitress-serve --port=8000 wsgi:app          # Windows
gunicorn "wsgi:app" --bind 0.0.0.0:8000      # Linux
```

### Command line

The application registers two Flask CLI commands alongside the `flask db` group:

```bash
flask --app wsgi init-db          # create the tables (add --drop to recreate)
flask --app wsgi db-stats         # print a row count per table
```

And three scripts:

```bash
python scripts/init_db.py [--drop] [--config development]
python scripts/seed_data.py [--reset] [--seed 20250401] [--year 2025-2026] [--quiet]
python scripts/export_seed_sql.py [--output database/seed_data.sql] [--seed 20250401] [--year 2025-2026]
```

### A typical pass through the application

1. **Subjects → Assign to classes** to confirm each class studies the right subjects and that the maximum and pass marks are correct.
2. **Marks → pick class, subject and exam → Open grid**, type the marks down the column, press Save.
3. **Reports → a class → Result list** for the ranked list, or **Export CSV** to hand it to the office.
4. **Reports → a student → Printable version** for the report card to print or save as PDF.

## Application routes

| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | Dashboard: headline counts and class strength |
| GET | `/healthz` | JSON health check, including database reachability |
| GET | `/students/` | Student list with `q`, `school_class_id`, `section_id`, `status` and `page` query parameters |
| GET, POST | `/students/new` | Add a student |
| GET | `/students/<id>` | Student record with every mark on file |
| GET, POST | `/students/<id>/edit` | Edit a student |
| POST | `/students/<id>/deactivate` | Soft delete: mark the student as having left |
| POST | `/students/<id>/restore` | Undo a soft delete |
| POST | `/students/<id>/delete` | Permanently delete the student and their marks |
| GET | `/subjects/` | Subject catalogue with the classes each subject is assigned to |
| GET, POST | `/subjects/new` | Add a subject |
| GET, POST | `/subjects/<id>/edit` | Edit a subject |
| POST | `/subjects/<id>/delete` | Delete a subject with its class assignments and marks |
| GET, POST | `/subjects/assign` | Assign a subject to a class with its mark scheme |
| POST | `/subjects/assignments/<id>/remove` | Unassign a subject from a class, deleting that class's marks for it |
| GET | `/marks/` | Choose class, section, subject and exam |
| GET, POST | `/marks/entry` | Bulk entry grid; takes `class_subject_id`, `exam_id` and optional `section_id` |
| GET, POST | `/marks/student/<id>` | Edit every subject mark for one student in one exam (`exam_id`) |
| GET | `/reports/` | Report landing page, one card per class |
| GET | `/reports/student/<id>` | Report card with class rank |
| GET | `/reports/student/<id>/print` | Printable report card |
| GET | `/reports/class/<class_id>` | Ranked class result list; optional `section_id` |
| GET | `/reports/class/<class_id>/export.csv` | CSV of the same list |

### Example: health check

```bash
curl -s http://127.0.0.1:5000/healthz
```

```json
{ "status": "ok", "database": "reachable" }
```

It answers `503` with `{"status": "error", "database": "unreachable"}` when the database cannot be reached, which makes it usable as a container or load-balancer probe.

### Example: CSV export

```bash
curl -s "http://127.0.0.1:5000/reports/class/6/export.csv?section_id=11"
```

```csv
Rank,Roll No,Admission No,Student Name,English,Hindi,Mathematics,Science,Social Studies,Computer Science,Total Obtained,Total Maximum,Percentage,Weighted %,Grade,Result
1,1,ADM20250224,Anay Nadig,392/400,377/400,388/400,397/400,367/400,386/400,2307,2400,96.12,96.42,A+,PASS
2,18,ADM20250258,Divya Gaba,384/400,354/400,386/400,387/400,392/400,374/400,2277,2400,94.88,93.68,A+,PASS
```

That is real output for Class 6, section A of the demo data (section id 11). Each subject cell is the total across all four exams against the total maximum for those exams. Students who have left the school are not listed.

## Data model

```
AcademicYear 1---* Exam
SchoolClass  1---* Section       1---* Student
SchoolClass  1---* ClassSubject  *---1 Subject
Student      1---* Mark          *---1 ClassSubject
Exam         1---* Mark
```

Points worth knowing:

- **Marks hang off `ClassSubject`, not `Subject`.** A mark therefore always knows the maximum it was scored out of, and the same subject can be worth different marks in different classes.
- **`Mark` is unique on `(student_id, class_subject_id, exam_id)`.** That constraint is what makes saving the bulk grid idempotent.
- **`Student` stores both `school_class_id` and `section_id`.** The section implies the class, but keeping the class on the row makes class filters a single index lookup and lets the database enforce that roll numbers are unique within a class and section. The forms and the seeder keep the two consistent.
- **Student removal is soft by default** (`is_active`), with an explicit permanent delete. Deleting a subject or a class assignment deletes the dependent marks in the same transaction.

### Grading and ranking

`app/services/results.py` holds the rules, as pure functions over rows the caller has already fetched:

| Concept | Rule |
| --- | --- |
| Subject total | Sum of the marks recorded across exams; an absence counts as zero but the paper still counts towards the maximum. |
| Subject pass | `total >= pass_marks x number of exams with a mark recorded`. |
| Overall percentage | Total obtained over total maximum, across every subject and exam with a mark. |
| Weighted aggregate | Each exam's percentage multiplied by its weightage, divided by the total weightage. Exams with no marks are ignored; if no exam carries a weightage, the plain total is used. |
| Letter grade | `A+` 90, `A` 80, `B` 70, `C` 60, `D` 50, `E` 40, otherwise `F`. Configurable through `Config.GRADE_BANDS`. |
| Overall pass | Every subject with marks must be passed. |
| Rank | Competition ranking on the weighted aggregate: ties share a rank and the next rank skips, so three students tied at the top take ranks 1, 1, 1 and the fourth is 4th. Students with no marks are placed last and left unranked. |

## Seed data

`scripts/seed_data.py` builds the demo school from a fixed seed (`--seed`, default `20250401`) for a fixed academic year (`--year`, default `2025-2026`). `database/seed_data.sql` holds exactly the same rows as MySQL `INSERT` statements.

- One academic year, marked as current.
- Classes 1 to 10, each with sections A and B.
- Seven subjects and the class-subject assignments described above, with classes 1 to 5 assessed out of 50 (17 to pass) and classes 6 to 10 out of 100 (33 to pass).
- Four exams: Unit Test 1 (10%), Half Yearly (30%), Unit Test 2 (10%) and Annual (50%).
- 40 to 50 students per class, split across the two sections, roughly 3% of whom are already marked as having left so the soft-delete and restore flows have real data.
- For every student: admission number, roll number, full name, date of birth (age-appropriate for the class), gender, blood group, parent or guardian name and relation, a phone number, an email address, a postal address and an admission date.
- A mark for every student, subject and exam, with an occasional absence.

With the default seed the dump contains:

| Class | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Students | 45 | 45 | 43 | 40 | 50 | 47 | 44 | 42 | 46 | 40 | 442 |

and 8,824 marks (every student x subject x exam).

Marks are not uniform noise. Each student is given an ability factor drawn once from a normal distribution, and every score is that factor plus a per-subject difficulty, a per-exam difficulty and a small amount of noise, clamped to the paper's range, with a small chance of an absence. Strong students are therefore consistently strong and class rankings carry meaning.

All names, addresses and phone numbers are generated by Faker (`en_IN` locale) and are fictional. The names Faker produces for a given seed can change between Faker releases, so `seed_data.py` run with a different Faker version gives the same structure and counts but different names from the committed dump; the dump's header records the version used. To regenerate the dump after changing the models or the generators:

```bash
python scripts/export_seed_sql.py
```

## Screenshots

Screenshots belong in `docs/images/` and are referenced from this section, for example:

```markdown
![Dashboard](docs/images/dashboard.png)
![Student list with filters](docs/images/students-list.png)
![Bulk mark entry grid](docs/images/marks-entry.png)
![Printable report card](docs/images/report-card-print.png)
```

The directory currently holds only a `.gitkeep` placeholder; capture your own after seeding the demo data.

## Testing

```bash
pip install -e ".[dev]"
pytest
```

The suite creates the schema in an in-memory SQLite database through the `testing` configuration, seeds one class with four students and two exams, and tears everything down after each test. No MySQL server is involved and nothing in your development database is touched.

```bash
pytest --cov=app --cov-report=term-missing
pytest tests/test_results.py -v
```

- `tests/test_results.py` exercises the grading bands, weighted aggregates, subject pass thresholds, absence handling, competition ranking including ties, the class summary and the CSV rows, using lightweight stand-ins rather than ORM objects.
- `tests/test_students.py` covers the student routes end to end - listing, search, filters, pagination, creation, every validation failure, editing, soft delete and restore - plus the report card, the class result list, the CSV export and the mark entry grid.
- `tests/test_management.py` covers permanent deletion, adding, editing, assigning and deleting subjects (including the marks that go with them), and the per-student mark editor.
- `tests/test_seed.py` checks the fake-data generators and that the committed `database/seed_data.sql` has classes 1 to 10 with 40 to 50 students each and a mark for every student, subject and exam.

Lint and formatting:

```bash
ruff check .
ruff format --check .
```

## Roadmap and limitations

Known limitations:

- **There is no authentication or authorisation.** Anyone who can reach the application can edit any record. Put it behind an authenticated reverse proxy, or add Flask-Login, before exposing it beyond a trusted network.
- The automated tests run on SQLite, so MySQL-specific behaviour is not exercised by `pytest`: SQLite does not enforce foreign keys unless they are switched on per connection. The schema, the Alembic revision, the dump import and the application were checked by hand against MySQL 8.0.
- Marks are stored as `DECIMAL(5,2)`, capping a single paper at 999.99.
- Attendance, fees, timetables, teachers and co-scholastic grades are not modelled.
- Report cards cover the current academic year only; there is no year-on-year progression or promotion workflow.
- A student's class is a plain foreign key, so moving a student to the next class rewrites the same row rather than creating an enrolment record per year.
- The CSV export builds the whole file in memory, which is fine for a class of fifty and would not be for a whole school.
- Printing depends on the browser's print dialogue; page breaks inside very long report cards are not tuned.

Possible future work:

- Authentication with per-role permissions for office staff, class teachers and the principal.
- An `Enrolment` model so class history is kept per academic year, with a promotion workflow.
- Attendance and fee modules.
- PDF report cards generated server side rather than through the browser.
- A REST API for the student and mark resources.
- Bulk import of students from CSV, with a dry-run preview.

## License

Released under the MIT License. See [LICENSE](LICENSE) for the full text.

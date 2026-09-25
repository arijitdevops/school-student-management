-- ---------------------------------------------------------------------------
-- school_db - plain MySQL 8 DDL
--
-- This file mirrors the SQLAlchemy models in app/models/ and the Alembic
-- revision in migrations/versions/. It is for
-- environments where you would rather create the schema by hand than run
-- `flask db upgrade` or `python scripts/init_db.py`; the application itself
-- does not read it. Keep it in step with the models when they change.
--
-- Usage:
--   mysql -u root -p < database/schema.sql
-- ---------------------------------------------------------------------------

CREATE DATABASE IF NOT EXISTS school_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE school_db;

-- Dropped in dependency order so the script can be re-run.
DROP TABLE IF EXISTS marks;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS exams;
DROP TABLE IF EXISTS class_subjects;
DROP TABLE IF EXISTS subjects;
DROP TABLE IF EXISTS sections;
DROP TABLE IF EXISTS school_classes;
DROP TABLE IF EXISTS academic_years;

CREATE TABLE academic_years (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(20)  NOT NULL,
    start_date  DATE         NOT NULL,
    end_date    DATE         NOT NULL,
    is_current  TINYINT(1)   NOT NULL DEFAULT 0,
    created_at  DATETIME     NOT NULL,
    updated_at  DATETIME     NOT NULL,
    UNIQUE KEY uq_academic_year_name (name),
    KEY ix_academic_year_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE school_classes (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    numeral     INT          NOT NULL,
    name        VARCHAR(40)  NOT NULL,
    created_at  DATETIME     NOT NULL,
    updated_at  DATETIME     NOT NULL,
    UNIQUE KEY uq_school_class_numeral (numeral),
    UNIQUE KEY uq_school_class_name (name),
    CONSTRAINT ck_school_class_numeral_range CHECK (numeral BETWEEN 1 AND 10)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE sections (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    school_class_id  INT          NOT NULL,
    name             VARCHAR(2)   NOT NULL,
    room             VARCHAR(20)  NULL,
    capacity         INT          NOT NULL DEFAULT 50,
    created_at       DATETIME     NOT NULL,
    updated_at       DATETIME     NOT NULL,
    UNIQUE KEY uq_section_class_name (school_class_id, name),
    CONSTRAINT fk_section_class FOREIGN KEY (school_class_id)
        REFERENCES school_classes (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE subjects (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    code         VARCHAR(10)  NOT NULL,
    name         VARCHAR(60)  NOT NULL,
    description  VARCHAR(255) NULL,
    is_active    TINYINT(1)   NOT NULL DEFAULT 1,
    created_at   DATETIME     NOT NULL,
    updated_at   DATETIME     NOT NULL,
    UNIQUE KEY uq_subject_code (code),
    UNIQUE KEY uq_subject_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Which subjects a class studies, and what they are worth there.
CREATE TABLE class_subjects (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    school_class_id  INT       NOT NULL,
    subject_id       INT       NOT NULL,
    max_marks        INT       NOT NULL DEFAULT 100,
    pass_marks       INT       NOT NULL DEFAULT 33,
    created_at       DATETIME  NOT NULL,
    updated_at       DATETIME  NOT NULL,
    UNIQUE KEY uq_class_subject (school_class_id, subject_id),
    CONSTRAINT fk_class_subject_class FOREIGN KEY (school_class_id)
        REFERENCES school_classes (id) ON DELETE CASCADE,
    CONSTRAINT fk_class_subject_subject FOREIGN KEY (subject_id)
        REFERENCES subjects (id) ON DELETE CASCADE,
    CONSTRAINT ck_class_subject_max_marks_positive CHECK (max_marks > 0),
    CONSTRAINT ck_class_subject_pass_marks CHECK (pass_marks >= 0 AND pass_marks <= max_marks)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE exams (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    academic_year_id  INT           NOT NULL,
    code              VARCHAR(20)   NOT NULL,
    name              VARCHAR(60)   NOT NULL,
    sequence          INT           NOT NULL DEFAULT 1,
    weightage         DECIMAL(5, 2) NOT NULL DEFAULT 25.00,
    held_on           DATE          NULL,
    created_at        DATETIME      NOT NULL,
    updated_at        DATETIME      NOT NULL,
    UNIQUE KEY uq_exam_year_code (academic_year_id, code),
    KEY ix_exam_code (code),
    CONSTRAINT fk_exam_year FOREIGN KEY (academic_year_id)
        REFERENCES academic_years (id) ON DELETE CASCADE,
    CONSTRAINT ck_exam_weightage_non_negative CHECK (weightage >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE students (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    admission_number  VARCHAR(20)  NOT NULL,
    full_name         VARCHAR(120) NOT NULL,
    roll_number       INT          NOT NULL,
    date_of_birth     DATE         NOT NULL,
    gender            VARCHAR(1)   NOT NULL DEFAULT 'O',
    blood_group       VARCHAR(3)   NULL,
    guardian_name     VARCHAR(120) NOT NULL,
    guardian_relation VARCHAR(20)  NOT NULL DEFAULT 'Guardian',
    guardian_phone    VARCHAR(20)  NOT NULL,
    email             VARCHAR(120) NULL,
    address           VARCHAR(255) NULL,
    admission_date    DATE         NOT NULL,
    is_active         TINYINT(1)   NOT NULL DEFAULT 1,
    school_class_id   INT          NOT NULL,
    section_id        INT          NOT NULL,
    created_at        DATETIME     NOT NULL,
    updated_at        DATETIME     NOT NULL,
    UNIQUE KEY uq_student_admission_number (admission_number),
    UNIQUE KEY uq_student_roll_in_section (school_class_id, section_id, roll_number),
    KEY ix_student_full_name (full_name),
    KEY ix_student_is_active (is_active),
    KEY ix_student_class_section (school_class_id, section_id),
    CONSTRAINT fk_student_class FOREIGN KEY (school_class_id)
        REFERENCES school_classes (id) ON DELETE RESTRICT,
    CONSTRAINT fk_student_section FOREIGN KEY (section_id)
        REFERENCES sections (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- One row per student, subject and exam. The unique key is what makes the bulk
-- entry grid safe to save repeatedly.
CREATE TABLE marks (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    student_id        INT           NOT NULL,
    class_subject_id  INT           NOT NULL,
    exam_id           INT           NOT NULL,
    marks_obtained    DECIMAL(5, 2) NOT NULL DEFAULT 0.00,
    is_absent         TINYINT(1)    NOT NULL DEFAULT 0,
    remarks           VARCHAR(255)  NULL,
    created_at        DATETIME      NOT NULL,
    updated_at        DATETIME      NOT NULL,
    UNIQUE KEY uq_mark_student_subject_exam (student_id, class_subject_id, exam_id),
    KEY ix_mark_exam_class_subject (exam_id, class_subject_id),
    CONSTRAINT fk_mark_student FOREIGN KEY (student_id)
        REFERENCES students (id) ON DELETE CASCADE,
    CONSTRAINT fk_mark_class_subject FOREIGN KEY (class_subject_id)
        REFERENCES class_subjects (id) ON DELETE CASCADE,
    CONSTRAINT fk_mark_exam FOREIGN KEY (exam_id)
        REFERENCES exams (id) ON DELETE CASCADE,
    CONSTRAINT ck_mark_non_negative CHECK (marks_obtained >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

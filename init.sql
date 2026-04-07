-- =====================================
-- INITIALIZATION SCRIPT FOR SEA_database
-- =====================================

-- =====================================
-- TABLE: person
-- =====================================

CREATE TABLE IF NOT EXISTS person (
    id_person SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    status BOOLEAN NOT NULL DEFAULT TRUE,
    id_group INT NULL
);


-- =====================================
-- TABLE: user_account (1:1 with person)
-- =====================================

CREATE TABLE IF NOT EXISTS user_account (
    id_user SERIAL PRIMARY KEY,
    id_person INT NOT NULL UNIQUE,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    status BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_user_person
        FOREIGN KEY (id_person)
        REFERENCES person(id_person)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);


-- =====================================
-- TABLE: generation (academic cohort)
-- =====================================

CREATE TABLE IF NOT EXISTS generation (
    id_generation SERIAL PRIMARY KEY,
    year INT NOT NULL UNIQUE,
    total_levels INT NOT NULL DEFAULT 11 CHECK (total_levels >= 1),
    status BOOLEAN NOT NULL DEFAULT TRUE
);


-- =====================================
-- TABLE: period (academic term)
-- Three periods per year:
--   Enero-Abril | Mayo-Agosto | Septiembre-Diciembre
-- =====================================

CREATE TABLE IF NOT EXISTS period (
    id_period SERIAL PRIMARY KEY,
    year INT NOT NULL,
    period_name VARCHAR(50) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_period_year_name UNIQUE (year, period_name),
    CONSTRAINT chk_period_dates CHECK (end_date > start_date),
    CONSTRAINT chk_period_name CHECK (
        period_name IN ('Enero-Abril', 'Mayo-Agosto', 'Septiembre-Diciembre')
    )
);


-- =====================================
-- TABLE: group (academic group)
-- =====================================

CREATE TABLE IF NOT EXISTS "group" (
    id_group SERIAL PRIMARY KEY,
    id_generation INT NOT NULL,
    id_period INT NULL,
    group_letter VARCHAR(5) NOT NULL,
    academic_level INT NOT NULL CHECK (academic_level >= 1),
    status BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_group_generation_letter UNIQUE (id_generation, group_letter),
    CONSTRAINT fk_group_generation
        FOREIGN KEY (id_generation)
        REFERENCES generation(id_generation)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT fk_group_period
        FOREIGN KEY (id_period)
        REFERENCES period(id_period)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);


-- =====================================
-- TABLE: subject
-- =====================================

CREATE TABLE IF NOT EXISTS subject (
    id_subject SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    level_number INT NOT NULL CHECK (level_number >= 1),
    status BOOLEAN NOT NULL DEFAULT TRUE
);


-- =====================================
-- TABLE: unit
-- =====================================

CREATE TABLE IF NOT EXISTS unit (
    id_unit SERIAL PRIMARY KEY,
    id_subject INT NOT NULL,
    unit_name VARCHAR(150) NOT NULL,
    unit_number INT NOT NULL,
    CONSTRAINT fk_unit_subject
        FOREIGN KEY (id_subject)
        REFERENCES subject(id_subject)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);


-- =====================================
-- TABLE: question
-- =====================================

CREATE TABLE IF NOT EXISTS question (
    id_question SERIAL PRIMARY KEY,
    id_subject INT NOT NULL,
    statement TEXT NOT NULL,
    bloom_level VARCHAR(50) NOT NULL,
    status BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_question_subject
        FOREIGN KEY (id_subject)
        REFERENCES subject(id_subject)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);


-- =====================================
-- TABLE: answer
-- =====================================

CREATE TABLE IF NOT EXISTS answer (
    id_answer SERIAL PRIMARY KEY,
    id_question INT NOT NULL,
    answer_text TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    CONSTRAINT fk_answer_question
        FOREIGN KEY (id_question)
        REFERENCES question(id_question)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);


-- =====================================
-- TABLE: exam
-- =====================================

CREATE TABLE IF NOT EXISTS exam (
    id_exam SERIAL PRIMARY KEY,
    id_subject INT NOT NULL,
    id_teacher INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    secure_mode BOOLEAN NOT NULL DEFAULT FALSE,
    creation_date DATE NOT NULL,
    status BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_exam_subject
        FOREIGN KEY (id_subject)
        REFERENCES subject(id_subject)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT fk_exam_teacher
        FOREIGN KEY (id_teacher)
        REFERENCES person(id_person)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);


-- =====================================
-- TABLE: exam_question (junction table)
-- =====================================

CREATE TABLE IF NOT EXISTS exam_question (
    id_exam_question SERIAL PRIMARY KEY,
    id_exam INT NOT NULL,
    id_question INT NOT NULL,
    CONSTRAINT fk_exam_question_exam
        FOREIGN KEY (id_exam)
        REFERENCES exam(id_exam)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_exam_question_question
        FOREIGN KEY (id_question)
        REFERENCES question(id_question)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    UNIQUE (id_exam, id_question)
);


-- =====================================
-- TABLE: exam_person (student assignment)
-- =====================================

CREATE TABLE IF NOT EXISTS exam_person (
    id_exam_person SERIAL PRIMARY KEY,
    id_exam INT NOT NULL,
    id_person INT NOT NULL,
    assignment_date DATE NOT NULL,
    start_datetime TIMESTAMP NULL,
    end_datetime TIMESTAMP NULL,
    grade DECIMAL(5,2) NULL,
    status VARCHAR(50) NOT NULL,
    CONSTRAINT fk_exam_person_exam
        FOREIGN KEY (id_exam)
        REFERENCES exam(id_exam)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_exam_person_person
        FOREIGN KEY (id_person)
        REFERENCES person(id_person)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    UNIQUE (id_exam, id_person)
);


-- =====================================
-- FOREIGN KEY: person -> group
-- =====================================

ALTER TABLE person
ADD CONSTRAINT fk_person_group
    FOREIGN KEY (id_group)
    REFERENCES "group"(id_group)
    ON DELETE SET NULL
    ON UPDATE CASCADE;


-- =====================================
-- INITIAL DATA: Admin User
-- =====================================

-- Insert admin person
INSERT INTO person (first_name, last_name, email, status)
VALUES ('Admin', 'LegacyDevs', 'admin@legacydevs.com', TRUE)
ON CONFLICT (email) DO NOTHING;

-- Insert admin user account
-- Password for '1234' will be updated by create_admin.py script
INSERT INTO user_account (id_person, username, password_hash, role, status)
SELECT 
    id_person,
    'admin',
    'temp_password',
    'admin',
    TRUE
FROM person
WHERE email = 'admin@legacydevs.com'
ON CONFLICT (username) DO NOTHING;

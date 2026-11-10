"""Создание учебной базы university.db на чистом sqlite3.

Используется заданиями средней сложности №4 и №8 и повышенным №8.
"""

import os
import sqlite3

from university_data import COURSES, GRADES, GROUPS, STUDENTS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "university.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id          INTEGER PRIMARY KEY,
    code        TEXT    NOT NULL UNIQUE,
    speciality  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    id          INTEGER PRIMARY KEY,
    full_name   TEXT    NOT NULL,
    email       TEXT    UNIQUE,
    group_id    INTEGER REFERENCES groups(id),
    scholarship REAL    NOT NULL DEFAULT 0 CHECK (scholarship >= 0)
);

CREATE TABLE IF NOT EXISTS courses (
    id          INTEGER PRIMARY KEY,
    title       TEXT    NOT NULL UNIQUE,
    credits     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS grades (
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id   INTEGER NOT NULL REFERENCES courses(id),
    grade       INTEGER NOT NULL CHECK (grade BETWEEN 2 AND 5),
    PRIMARY KEY (student_id, course_id)
);
"""


def connect(path=DB_PATH):
    """Открывает соединение с настройками, нужными во всех заданиях."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # В SQLite проверка внешних ключей по умолчанию ВЫКЛЮЧЕНА
    # и включается отдельно для каждого соединения.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def seed(conn):
    """Заполняет пустую базу учебными данными."""
    conn.executemany("INSERT INTO groups (code, speciality) VALUES (?, ?)",
                     GROUPS)
    conn.executemany(
        "INSERT INTO students (full_name, email, scholarship, group_id) "
        "VALUES (?, ?, ?, (SELECT id FROM groups WHERE code = ?))",
        [(name, email, money, group) for name, group, email, money in STUDENTS])
    conn.executemany("INSERT INTO courses (title, credits) VALUES (?, ?)",
                     COURSES)
    conn.executemany(
        "INSERT INTO grades (student_id, course_id, grade) VALUES ("
        "(SELECT id FROM students WHERE full_name = ?), "
        "(SELECT id FROM courses WHERE title = ?), ?)",
        GRADES)
    conn.commit()


def create_database(path=DB_PATH, reset=False):
    """Создаёт таблицы и заполняет их, если база пустая.

    reset=True удаляет старый файл — каждое задание начинает с одинаковых данных.
    """
    if reset and path != ":memory:" and os.path.exists(path):
        os.remove(path)

    conn = connect(path)
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0] == 0:
        seed(conn)
    return conn


def print_table(rows, headers):
    """Печатает строки выборки ровной таблицей."""
    rows = [tuple("—" if value is None else value for value in row)
            for row in rows]
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows
              else len(str(h)) for i, h in enumerate(headers)]
    line = "  ".join(f"{h:<{w}}" for h, w in zip(headers, widths))
    print("  " + line)
    print("  " + "-" * len(line))
    for row in rows:
        print("  " + "  ".join(f"{str(v):<{w}}" for v, w in zip(row, widths)))
    if not rows:
        print("  (нет строк)")


if __name__ == "__main__":
    connection = create_database(reset=True)
    for table in ("groups", "students", "courses", "grades"):
        # Имя таблицы нельзя передать параметром «?» — только вставить в текст.
        # Здесь это безопасно: имена берутся из нашего списка, а не от пользователя.
        count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table:<10} {count} строк")
    connection.close()
    print(f"База создана: {DB_PATH}")

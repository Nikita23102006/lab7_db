"""Задание средней сложности №4: обновить запись.

Запуск:  python3 task04_update.py
"""

import sqlite3

from db_setup import create_database, print_table

# Какие колонки разрешено менять через update_student.
# Имя колонки нельзя передать параметром «?», его приходится вставлять
# в текст запроса — поэтому допускаются только имена из этого списка.
UPDATABLE = ("full_name", "email", "scholarship", "group_id")


def show_student(conn, student_id):
    row = conn.execute(
        "SELECT s.id, s.full_name, s.email, g.code, s.scholarship "
        "FROM students s LEFT JOIN groups g ON g.id = s.group_id "
        "WHERE s.id = ?", (student_id,)).fetchone()
    print_table([tuple(row)] if row else [],
                ("id", "ФИО", "email", "группа", "стипендия"))


def update_student(conn, student_id, **fields):
    """Обновляет переданные поля одной записи.

    Возвращает число изменённых строк: 1 — успех, 0 — записи нет.
    """
    unknown = set(fields) - set(UPDATABLE)
    if unknown:
        raise ValueError(f"Эти поля менять нельзя: {', '.join(sorted(unknown))}")
    if not fields:
        return 0

    assignments = ", ".join(f"{column} = ?" for column in fields)
    sql = f"UPDATE students SET {assignments} WHERE id = ?"
    cursor = conn.execute(sql, (*fields.values(), student_id))
    conn.commit()
    return cursor.rowcount


def move_to_group(conn, student_id, group_code):
    """Перевод в другую группу: id группы ищется подзапросом по её коду."""
    cursor = conn.execute(
        "UPDATE students SET group_id = (SELECT id FROM groups WHERE code = ?) "
        "WHERE id = ? AND EXISTS (SELECT 1 FROM groups WHERE code = ?)",
        (group_code, student_id, group_code))
    conn.commit()
    return cursor.rowcount


def raise_scholarship_for_excellent(conn, percent, min_average=4.5):
    """Массовое обновление: +percent% стипендии всем со средним баллом ≥ min_average."""
    cursor = conn.execute(
        "UPDATE students "
        "SET scholarship = ROUND(scholarship * (1 + ? / 100.0), 2) "
        "WHERE scholarship > 0 AND id IN ("
        "    SELECT student_id FROM grades "
        "    GROUP BY student_id HAVING AVG(grade) >= ?)",
        (percent, min_average))
    conn.commit()
    return cursor.rowcount


def main():
    conn = create_database(reset=True)

    print("1. Изменить одно поле одной записи (email студента id=2)")
    print("   До:")
    show_student(conn, 2)
    changed = update_student(conn, 2, email="p.petrov@stud.tsu.tula.ru")
    print(f"   После (изменено строк: {changed}):")
    show_student(conn, 2)

    print("\n2. Изменить несколько полей сразу (ФИО и стипендию, id=7)")
    changed = update_student(conn, 7, full_name="Морозова-Белова Ольга",
                             scholarship=2500)
    print(f"   Изменено строк: {changed}")
    show_student(conn, 7)

    print("\n3. Перевести студента id=4 в группу 220042-12 (подзапрос в SET)")
    changed = move_to_group(conn, 4, "220042-12")
    print(f"   Изменено строк: {changed}")
    show_student(conn, 4)

    print("\n4. Массовое обновление: +10% стипендии отличникам (средний ≥ 4.5)")
    before = conn.execute("SELECT full_name, scholarship FROM students "
                          "WHERE scholarship > 0 ORDER BY id").fetchall()
    changed = raise_scholarship_for_excellent(conn, 10)
    after = conn.execute("SELECT scholarship FROM students "
                         "WHERE scholarship > 0 ORDER BY id").fetchall()
    print(f"   Изменено строк: {changed}")
    print_table([(b["full_name"], b["scholarship"], a["scholarship"])
                 for b, a in zip(before, after)],
                ("ФИО", "было", "стало"))

    print("\n5. Обновление несуществующей записи (id=999)")
    changed = update_student(conn, 999, scholarship=100)
    print(f"   Изменено строк: {changed} — запись не найдена, ошибки нет. "
          "Поэтому rowcount надо проверять.")

    print("\n6. Нарушение ограничения: email, который уже занят")
    try:
        update_student(conn, 1, email="sidorova@stud.tsu.tula.ru")
    except sqlite3.IntegrityError as error:
        conn.rollback()
        print(f"   IntegrityError: {error}")
        print("   Изменения отменены, запись осталась прежней:")
        show_student(conn, 1)

    print("\n7. Попытка изменить запрещённое поле")
    try:
        update_student(conn, 1, id=100)
    except ValueError as error:
        print(f"   ValueError: {error}")

    conn.close()


if __name__ == "__main__":
    main()

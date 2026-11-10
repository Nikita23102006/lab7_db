"""Задание средней сложности №8: выполнить JOIN.

Запуск:  python3 task08_join.py
"""

from db_setup import create_database, print_table


def students_with_groups(conn):
    """INNER JOIN: только пары, где совпадение нашлось в обеих таблицах."""
    return conn.execute(
        "SELECT s.full_name, g.code, g.speciality "
        "FROM students AS s "
        "INNER JOIN groups AS g ON g.id = s.group_id "
        "ORDER BY g.code, s.full_name").fetchall()


def groups_with_student_count(conn):
    """LEFT JOIN: все группы, даже без студентов.

    COUNT(s.id), а не COUNT(*): для пустой группы LEFT JOIN даёт одну
    строку с NULL вместо студента, и COUNT(*) насчитал бы 1.
    """
    return conn.execute(
        "SELECT g.code, COUNT(s.id) AS students "
        "FROM groups AS g "
        "LEFT JOIN students AS s ON s.group_id = g.id "
        "GROUP BY g.id "
        "ORDER BY g.code").fetchall()


def gradebook(conn):
    """JOIN четырёх таблиц: ведомость «группа — студент — дисциплина — оценка»."""
    return conn.execute(
        "SELECT g.code, s.full_name, c.title, gr.grade "
        "FROM grades AS gr "
        "JOIN students AS s ON s.id = gr.student_id "
        "JOIN courses  AS c ON c.id = gr.course_id "
        "JOIN groups   AS g ON g.id = s.group_id "
        "ORDER BY g.code, s.full_name, c.title").fetchall()


def students_without_grades(conn):
    """LEFT JOIN + IS NULL: у кого нет ни одной оценки."""
    return conn.execute(
        "SELECT s.full_name "
        "FROM students AS s "
        "LEFT JOIN grades AS gr ON gr.student_id = s.id "
        "WHERE gr.student_id IS NULL").fetchall()


def course_statistics(conn):
    """LEFT JOIN + агрегаты: по каждой дисциплине — число оценок и средний балл."""
    return conn.execute(
        "SELECT c.title, COUNT(gr.grade) AS marks, "
        "       ROUND(AVG(gr.grade), 2) AS average "
        "FROM courses AS c "
        "LEFT JOIN grades AS gr ON gr.course_id = c.id "
        "GROUP BY c.id "
        "ORDER BY average DESC").fetchall()


def group_averages(conn, min_average=0):
    """JOIN + GROUP BY + HAVING: средний балл групп не ниже порога."""
    return conn.execute(
        "SELECT g.code, COUNT(DISTINCT s.id) AS students, "
        "       ROUND(AVG(gr.grade), 2) AS average "
        "FROM groups AS g "
        "JOIN students AS s ON s.group_id = g.id "
        "JOIN grades   AS gr ON gr.student_id = s.id "
        "GROUP BY g.id "
        "HAVING AVG(gr.grade) >= ? "
        "ORDER BY average DESC", (min_average,)).fetchall()


def main():
    conn = create_database(reset=True)

    print("1. INNER JOIN — студенты и их группы")
    print_table(students_with_groups(conn), ("ФИО", "группа", "направление"))

    print("\n2. LEFT JOIN — все группы и число студентов (есть пустая группа)")
    print_table(groups_with_student_count(conn), ("группа", "студентов"))

    inner = conn.execute(
        "SELECT COUNT(*) FROM groups g "
        "JOIN students s ON s.group_id = g.id").fetchone()[0]
    left = conn.execute(
        "SELECT COUNT(*) FROM groups g "
        "LEFT JOIN students s ON s.group_id = g.id").fetchone()[0]
    print(f"   Строк при INNER JOIN: {inner}, при LEFT JOIN: {left} "
          f"(+1 строка для группы без студентов)")

    print("\n3. JOIN четырёх таблиц — ведомость")
    print_table(gradebook(conn), ("группа", "студент", "дисциплина", "оценка"))

    print("\n4. LEFT JOIN + IS NULL — студенты без оценок")
    print_table(students_without_grades(conn), ("ФИО",))

    print("\n5. Статистика по дисциплинам (курс без оценок тоже виден)")
    print_table(course_statistics(conn), ("дисциплина", "оценок", "средний"))

    print("\n6. Средний балл групп, HAVING ≥ 4.0")
    print_table(group_averages(conn, 4.0), ("группа", "студентов", "средний"))

    conn.close()


if __name__ == "__main__":
    main()

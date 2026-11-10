"""Лабораторная работа №7. Вариант 8. Запуск всех заданий подряд.

Запуск:  python3 main.py
"""

from sqlalchemy.orm import Session

import adv01_sqlalchemy_relations
import adv08_query_cache
import task04_update
import task08_join
import task10_sqlalchemy_single
from db_setup import create_database

TASKS = [
    ("Средн. №8 — выполнить JOIN", task08_join.main),
    ("Средн. №10 — SQLAlchemy для одной таблицы", task10_sqlalchemy_single.main),
    ("Средн. №4 — обновить запись", task04_update.main),
    ("Повыш. №8 — кэширование запросов", adv08_query_cache.main),
    ("Повыш. №1 — SQLAlchemy с несколькими таблицами", adv01_sqlalchemy_relations.main),
]


def compare_sql_and_orm():
    """Одна и та же ведомость двумя способами: JOIN на SQL и связи ORM."""
    conn = create_database(reset=True)
    by_sql = sorted(tuple(row) for row in task08_join.gradebook(conn))
    conn.close()

    engine = adv01_sqlalchemy_relations.make_engine()
    adv01_sqlalchemy_relations.reset(engine)
    with Session(engine) as session:
        by_orm = adv01_sqlalchemy_relations.gradebook(session)
    engine.dispose()

    print(f"  Строк через JOIN на SQL:   {len(by_sql)}")
    print(f"  Строк через связи ORM:     {len(by_orm)}")
    print(f"  Ведомости совпадают:       {'да' if by_sql == by_orm else 'НЕТ'}")
    return by_sql == by_orm


def main():
    for title, run in TASKS:
        print("\n" + "=" * 72)
        print(title)
        print("=" * 72)
        run()

    print("\n" + "=" * 72)
    print("Сверка: JOIN из задания №8 и связи ORM из повышенного №1")
    print("=" * 72)
    compare_sql_and_orm()


if __name__ == "__main__":
    main()

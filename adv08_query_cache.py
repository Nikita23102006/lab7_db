"""Задание повышенной сложности №8: кэширование запросов.

Запуск:  python3 adv08_query_cache.py

Идея: результат тяжёлого SELECT запоминается в памяти, и повторный
одинаковый запрос отдаётся без обращения к базе. Главная трудность —
вовремя забыть результат, когда данные изменились. Здесь это решается
тремя способами одновременно:
  1) запись в таблицу сбрасывает все закэшированные запросы к ней;
  2) у каждой записи есть срок жизни (TTL);
  3) размер кэша ограничен, старые записи вытесняются (LRU).
"""

import random
import re
import time
from collections import OrderedDict
from functools import lru_cache

from db_setup import create_database

# Ищет имена таблиц после FROM, JOIN, UPDATE, INTO.
# Для учебных запросов достаточно; полноценный разбор SQL — отдельная задача.
TABLE_PATTERN = re.compile(r"\b(?:FROM|JOIN|UPDATE|INTO)\s+([A-Za-z_][A-Za-z0-9_]*)",
                           re.IGNORECASE)


def tables_in(sql):
    return {name.lower() for name in TABLE_PATTERN.findall(sql)}


class QueryCache:
    """Кэш результатов запросов с TTL, ограничением размера и сбросом по таблице."""

    def __init__(self, ttl=60.0, max_size=128):
        self.ttl = ttl
        self.max_size = max_size
        self._store = OrderedDict()   # ключ -> (время записи, строки, таблицы)
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(sql, params):
        # Лишние пробелы и переносы не должны давать разные ключи.
        return " ".join(sql.split()).lower(), tuple(params)

    def get(self, key):
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None

        saved_at, rows, _ = entry
        if time.monotonic() - saved_at > self.ttl:
            del self._store[key]           # просрочено — как будто не было
            self.misses += 1
            return None

        self._store.move_to_end(key)       # недавно использованные — в конец
        self.hits += 1
        return rows

    def put(self, key, rows, tables):
        self._store[key] = (time.monotonic(), rows, tables)
        self._store.move_to_end(key)
        while len(self._store) > self.max_size:
            self._store.popitem(last=False)   # вытесняем самую старую запись

    def invalidate(self, table):
        """Удаляет все записи, которые читали из table. Возвращает их число."""
        stale = [key for key, (_, _, tables) in self._store.items()
                 if table in tables]
        for key in stale:
            del self._store[key]
        return len(stale)

    def clear(self):
        self._store.clear()

    def __len__(self):
        return len(self._store)

    def __contains__(self, key):
        return key in self._store

    @property
    def hit_rate(self):
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class CachedDatabase:
    """Обёртка над соединением: SELECT идут через кэш, запись его сбрасывает."""

    def __init__(self, conn, cache):
        self.conn = conn
        self.cache = cache

    def query(self, sql, params=()):
        key = self.cache.make_key(sql, params)
        rows = self.cache.get(key)
        if rows is None:
            rows = [tuple(row) for row in self.conn.execute(sql, params)]
            self.cache.put(key, rows, tables_in(sql))
        return rows

    def execute(self, sql, params=()):
        cursor = self.conn.execute(sql, params)
        self.conn.commit()
        for table in tables_in(sql):
            self.cache.invalidate(table)
        return cursor.rowcount


# ============================== Демонстрация ==============================

HEAVY_SQL = """
    SELECT s.full_name,
           COUNT(*)                       AS lessons,
           ROUND(100.0 * SUM(a.present) / COUNT(*), 1) AS percent
    FROM attendance AS a
    JOIN students   AS s ON s.id = a.student_id
    GROUP BY s.id
    ORDER BY percent DESC
"""


def build_demo_database(rows=300_000):
    """Учебная база в памяти + большая таблица посещаемости для тяжёлого запроса."""
    conn = create_database(":memory:")
    conn.execute("CREATE TABLE attendance (student_id INTEGER, day INTEGER, "
                 "present INTEGER)")
    ids = [row[0] for row in conn.execute("SELECT id FROM students")]
    rng = random.Random(8)   # фиксированное зерно — одинаковые данные при каждом запуске
    conn.executemany(
        "INSERT INTO attendance VALUES (?, ?, ?)",
        ((rng.choice(ids), day, int(rng.random() < 0.85)) for day in range(rows)))
    conn.commit()
    return conn


def timed(function, *args):
    start = time.perf_counter()
    result = function(*args)
    return result, (time.perf_counter() - start) * 1000


def main():
    conn = build_demo_database()
    db = CachedDatabase(conn, QueryCache(ttl=60, max_size=128))

    print("1. Тяжёлый запрос: процент посещаемости по 300 000 записей")
    first, t1 = timed(db.query, HEAVY_SQL)
    second, t2 = timed(db.query, HEAVY_SQL)
    print(f"   Первый вызов (из базы): {t1:8.2f} мс")
    print(f"   Второй вызов (из кэша): {t2:8.3f} мс   — быстрее в {t1 / t2:,.0f} раз"
          .replace(",", " "))
    print(f"   Результаты совпадают: {first == second}")
    print(f"   Лидер посещаемости: {first[0][0]} — {first[0][2]}%")

    print("\n2. Одинаковый запрос с другим форматированием — тот же ключ кэша")
    db.query("   " + HEAVY_SQL.replace("\n", "\n\n") + "  ")
    print(f"   Попаданий: {db.cache.hits}, промахов: {db.cache.misses}")

    print("\n3. Параметры — часть ключа: разные параметры = разные записи кэша")
    sql = "SELECT full_name, scholarship FROM students WHERE scholarship >= ?"
    print(f"   >= 3000: студентов {len(db.query(sql, (3000,)))}")
    print(f"   >= 4000: студентов {len(db.query(sql, (4000,)))}")
    print(f"   >= 3000 ещё раз: студентов {len(db.query(sql, (3000,)))} (из кэша)")
    print(f"   Записей в кэше: {len(db.cache)}")

    print("\n4. Изменение данных сбрасывает кэш только нужной таблицы")
    print(f"   Таблицы, найденные в тяжёлом запросе: {sorted(tables_in(HEAVY_SQL))}")
    courses_sql = "SELECT title FROM courses ORDER BY title"
    db.query(courses_sql)                     # запрос к другой таблице
    before = db.query(sql, (3000,))
    size_before = len(db.cache)
    db.execute("UPDATE students SET scholarship = 5000 WHERE full_name = ?",
               ("Петров Пётр",))
    size_after = len(db.cache)
    courses_kept = db.cache.make_key(courses_sql, ()) in db.cache
    after = db.query(sql, (3000,))
    print(f"   Записей в кэше до UPDATE: {size_before}, после: {size_after}")
    print(f"   Сброшены все {size_before - size_after} запроса к students "
          "(и тяжёлый — он тоже читает students)")
    print(f"   Запрос к courses остался в кэше: {courses_kept}")
    print(f"   Стипендия ≥ 3000 до UPDATE: студентов {len(before)}, "
          f"после: {len(after)} — свежие данные, а не старый кэш")

    print("\n5. Срок жизни записи (TTL)")
    short = CachedDatabase(conn, QueryCache(ttl=0.3))
    count_sql = "SELECT COUNT(*) FROM students"
    short.query(count_sql)
    short.query(count_sql)
    time.sleep(0.4)
    short.query(count_sql)
    print(f"   Запрос, повтор, пауза 0.4 с, запрос: "
          f"попаданий {short.cache.hits}, промахов {short.cache.misses}")

    print("\n6. Ограничение размера (LRU): кэш на 2 записи, три разных запроса")
    small = CachedDatabase(conn, QueryCache(max_size=2))
    small.query("SELECT COUNT(*) FROM groups")
    small.query("SELECT COUNT(*) FROM courses")
    small.query("SELECT COUNT(*) FROM groups")      # groups стал «свежим»
    small.query("SELECT COUNT(*) FROM grades")      # вытесняет courses
    small.query("SELECT COUNT(*) FROM courses")     # промах: courses уже вытеснен
    print(f"   Попаданий {small.cache.hits}, промахов {small.cache.misses}, "
          f"в кэше {len(small.cache)} записи")

    print("\n7. Почему нельзя просто взять functools.lru_cache")

    @lru_cache(maxsize=None)
    def count_rich():
        return conn.execute("SELECT COUNT(*) FROM students "
                            "WHERE scholarship >= 3000").fetchone()[0]

    stale_before = count_rich()
    conn.execute("UPDATE students SET scholarship = 3000 WHERE full_name = ?",
                 ("Орлов Сергей",))
    conn.commit()
    stale_after = count_rich()
    real = conn.execute("SELECT COUNT(*) FROM students "
                        "WHERE scholarship >= 3000").fetchone()[0]
    print(f"   lru_cache до UPDATE: {stale_before}, после UPDATE: {stale_after}, "
          f"а на самом деле в базе: {real}")
    print("   lru_cache не знает, что данные изменились, — и отдаёт устаревший ответ.")

    print(f"\nИтог по основному кэшу: попаданий {db.cache.hits}, "
          f"промахов {db.cache.misses}, доля попаданий {db.cache.hit_rate:.0%}")
    conn.close()


if __name__ == "__main__":
    main()

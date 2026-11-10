"""Задание средней сложности №10: SQLAlchemy для одной таблицы.

Запуск:  python3 task10_sqlalchemy_single.py

Используется стиль SQLAlchemy 2.0: аннотации Mapped[...] и запросы через select().
"""

import os

from sqlalchemy import (
    CheckConstraint, String, create_engine, delete, func, select, update,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_URL = "sqlite:///" + os.path.join(BASE_DIR, "warehouse.db")


class Base(DeclarativeBase):
    """Базовый класс: от него наследуются все модели."""


class Product(Base):
    """Модель — класс Python, которому соответствует таблица products."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint("quantity >= 0", name="quantity_not_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    category: Mapped[str] = mapped_column(String(50), index=True)
    price: Mapped[float]
    quantity: Mapped[int] = mapped_column(default=0)

    def __repr__(self):
        return f"Product({self.name!r}, {self.price} ₽, {self.quantity} шт.)"


SEED = [
    Product(name="Ноутбук", category="Электроника", price=72990, quantity=5),
    Product(name="Мышь", category="Электроника", price=1290, quantity=40),
    Product(name="Клавиатура", category="Электроника", price=3490, quantity=18),
    Product(name="Тетрадь", category="Канцелярия", price=89, quantity=300),
    Product(name="Ручка", category="Канцелярия", price=35, quantity=0),
    Product(name="Рюкзак", category="Аксессуары", price=2990, quantity=12),
]


def make_engine(url=DB_URL, echo=False):
    """Engine — точка подключения к базе. echo=True печатает весь SQL."""
    return create_engine(url, echo=echo)


def reset(engine):
    """Пересоздаёт таблицу и заполняет её — для повторяемого запуска."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            Product(name=p.name, category=p.category,
                    price=p.price, quantity=p.quantity) for p in SEED)
        session.commit()


def print_products(products):
    for p in products:
        print(f"  {p.id:>2}. {p.name:<12} {p.category:<12} "
              f"{p.price:>9.2f} ₽  {p.quantity:>4} шт.")


def main():
    engine = make_engine()
    reset(engine)

    with Session(engine) as session:
        print("1. SELECT — все товары по цене")
        stmt = select(Product).order_by(Product.price.desc())
        print_products(session.scalars(stmt))

        print("\n   SQL, который построил SQLAlchemy:")
        print("   " + str(stmt).replace("\n", "\n   "))

        print("\n2. WHERE — электроника дешевле 5000 ₽")
        stmt = (select(Product)
                .where(Product.category == "Электроника", Product.price < 5000)
                .order_by(Product.name))
        print_products(session.scalars(stmt))

        print("\n3. Поиск по части названия (LIKE) и товары, которых нет в наличии")
        print_products(session.scalars(
            select(Product).where(Product.name.like("%ш%"))))
        print("   Нет в наличии:",
              [p.name for p in session.scalars(
                  select(Product).where(Product.quantity == 0))])

        print("\n4. Получить один объект по первичному ключу — session.get()")
        notebook = session.get(Product, 1)
        print(f"  {notebook!r}")

        print("\n5. UPDATE через объект: меняем атрибут и делаем commit")
        notebook.price = 69990
        notebook.quantity -= 1
        session.commit()
        print(f"  {session.get(Product, 1)!r}")

        print("\n6. INSERT — новый товар")
        session.add(Product(name="Монитор", category="Электроника",
                            price=15990, quantity=7))
        session.commit()
        print(f"  Товаров стало: {session.scalar(select(func.count(Product.id)))}")

        print("\n7. Массовый UPDATE без загрузки объектов — скидка 10% на канцелярию")
        result = session.execute(
            update(Product)
            .where(Product.category == "Канцелярия")
            .values(price=Product.price * 0.9))
        session.commit()
        print(f"  Изменено строк: {result.rowcount}")
        print_products(session.scalars(
            select(Product).where(Product.category == "Канцелярия")))

        print("\n8. DELETE — удалить товары, которых нет на складе")
        result = session.execute(delete(Product).where(Product.quantity == 0))
        session.commit()
        print(f"  Удалено строк: {result.rowcount}")

        print("\n9. Агрегаты — стоимость склада по категориям")
        stmt = (select(Product.category,
                       func.count(Product.id),
                       func.sum(Product.price * Product.quantity))
                .group_by(Product.category)
                .order_by(func.sum(Product.price * Product.quantity).desc()))
        for category, count, total in session.execute(stmt):
            print(f"  {category:<12} {count} поз.  {total:>12,.2f} ₽".replace(",", " "))

    engine.dispose()


if __name__ == "__main__":
    main()

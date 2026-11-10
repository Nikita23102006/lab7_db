"""Задание повышенной сложности №1: SQLAlchemy с несколькими таблицами (связи).

Запуск:  python3 adv01_sqlalchemy_relations.py

Модели:
    Group 1 ─── N Student          один-ко-многим
    Student N ─── M Course         многие-ко-многим через Enrollment
                                   (в связующей таблице хранится оценка)
"""

import os

from sqlalchemy import (
    CheckConstraint, ForeignKey, String, create_engine, event, func, select,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, Session, mapped_column, relationship,
    selectinload,
)

from university_data import COURSES, GRADES, GROUPS, STUDENTS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_URL = "sqlite:///" + os.path.join(BASE_DIR, "university_orm.db")


class Base(DeclarativeBase):
    pass


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    speciality: Mapped[str] = mapped_column(String(100))

    # Обратная сторона связи: group.students — список объектов Student.
    students: Mapped[list["Student"]] = relationship(
        back_populates="group", order_by="Student.full_name")

    def __repr__(self):
        return f"Group({self.code!r})"


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(100), unique=True)
    scholarship: Mapped[float] = mapped_column(default=0)
    # Внешний ключ — столбец в таблице.
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))

    # relationship — уже не столбец, а удобный доступ к связанному объекту.
    group: Mapped[Group | None] = relationship(back_populates="students")

    # cascade="all, delete-orphan": удалили студента — удалились его оценки.
    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="student", cascade="all, delete-orphan")

    @property
    def courses(self):
        return [enrollment.course for enrollment in self.enrollments]

    @property
    def average(self):
        grades = [enrollment.grade for enrollment in self.enrollments]
        return round(sum(grades) / len(grades), 2) if grades else None

    def __repr__(self):
        return f"Student({self.full_name!r})"


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), unique=True)
    credits: Mapped[int]

    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="course")

    def __repr__(self):
        return f"Course({self.title!r})"


class Enrollment(Base):
    """Связующая модель «студент — дисциплина» с дополнительным полем grade.

    Если бы хранить было нечего, хватило бы простой таблицы и
    relationship(secondary=...). Но оценка — это данные самой связи,
    поэтому связь оформлена отдельной моделью (association object).
    """

    __tablename__ = "enrollments"
    __table_args__ = (CheckConstraint("grade BETWEEN 2 AND 5"),)

    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"),
                                            primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"),
                                           primary_key=True)
    grade: Mapped[int]

    student: Mapped[Student] = relationship(back_populates="enrollments")
    course: Mapped[Course] = relationship(back_populates="enrollments")


# ============================== Подготовка ==============================

def make_engine(url=DB_URL):
    return create_engine(url)


def reset(engine):
    """Пересоздаёт таблицы и заполняет теми же данными, что и sqlite3-задания."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        groups = {code: Group(code=code, speciality=spec) for code, spec in GROUPS}
        courses = {title: Course(title=title, credits=credits)
                   for title, credits in COURSES}
        students = {}
        for name, group_code, email, money in STUDENTS:
            # Присваиваем объект, а не id — внешний ключ ORM проставит сам.
            students[name] = Student(full_name=name, email=email,
                                     scholarship=money,
                                     group=groups[group_code])
        for name, title, grade in GRADES:
            students[name].enrollments.append(
                Enrollment(course=courses[title], grade=grade))

        session.add_all([*groups.values(), *courses.values()])
        session.commit()


class QueryCounter:
    """Считает SQL-запросы, которые реально ушли в базу."""

    def __init__(self, engine):
        self.count = 0
        event.listen(engine, "before_cursor_execute", self._on_execute)

    def _on_execute(self, *args):
        self.count += 1


# ================================ Запросы ================================

def gradebook(session):
    """Та же ведомость, что в task08_join.py, но через связи ORM.

    Ни одного JOIN вручную — переходим по атрибутам объектов.
    """
    rows = []
    students = session.scalars(
        select(Student).options(
            selectinload(Student.group),
            selectinload(Student.enrollments).selectinload(Enrollment.course)))
    for student in students:
        for enrollment in student.enrollments:
            rows.append((student.group.code, student.full_name,
                         enrollment.course.title, enrollment.grade))
    return sorted(rows)


def main():
    engine = make_engine()
    reset(engine)
    counter = QueryCounter(engine)

    with Session(engine) as session:
        print("1. Один-ко-многим: группа -> студенты")
        for group in session.scalars(select(Group).order_by(Group.code)):
            names = ", ".join(s.full_name for s in group.students) or "нет студентов"
            print(f"   {group.code}: {names}")

        print("\n2. Обратный переход: студент -> группа -> направление")
        sidorova = session.scalar(
            select(Student).where(Student.full_name == "Сидорова Анна"))
        print(f"   {sidorova.full_name}: группа {sidorova.group.code}, "
              f"{sidorova.group.speciality}")

        print("\n3. Многие-ко-многим: дисциплины и оценки студента")
        for enrollment in sidorova.enrollments:
            print(f"   {enrollment.course.title:<38} {enrollment.grade}")
        print(f"   Средний балл: {sidorova.average}")

        print("\n4. С другой стороны связи: кто сдавал «Базы данных»")
        course = session.scalar(select(Course).where(Course.title == "Базы данных"))
        for enrollment in sorted(course.enrollments, key=lambda e: -e.grade):
            print(f"   {enrollment.student.full_name:<18} {enrollment.grade}")

        print("\n5. JOIN через связь: студенты 220042-11 со средним баллом")
        stmt = (select(Student.full_name, func.avg(Enrollment.grade))
                .join(Student.group)
                .join(Student.enrollments)
                .where(Group.code == "220042-11")
                .group_by(Student.id)
                .order_by(func.avg(Enrollment.grade).desc()))
        for name, average in session.execute(stmt):
            print(f"   {name:<18} {average:.2f}")

    print("\n6. Проблема N+1 и её решение")
    with Session(engine) as session:
        counter.count = 0
        for student in session.scalars(select(Student)):
            _ = len(student.enrollments)   # ленивая загрузка — запрос на каждого
        lazy = counter.count
        students_total = session.scalar(select(func.count(Student.id)))

    with Session(engine) as session:
        counter.count = 0
        for student in session.scalars(
                select(Student).options(selectinload(Student.enrollments))):
            _ = len(student.enrollments)
        eager = counter.count
    print(f"   Студентов: {students_total}. Обращаемся к оценкам каждого.")
    print(f"   Ленивая загрузка (по умолчанию): {lazy} запросов — 1 + {lazy - 1}")
    print(f"   selectinload:                    {eager} запроса — 1 + 1")

    print("\n7. Добавление через связь: новый студент в пустую группу")
    with Session(engine) as session:
        group = session.scalar(select(Group).where(Group.code == "220051-11"))
        group.students.append(Student(full_name="Новиков Артём",
                                      email="novikov@stud.tsu.tula.ru"))
        session.commit()
        newcomer = group.students[0]
        print(f"   {newcomer.full_name}: group_id={newcomer.group_id} "
              f"проставлен автоматически")

    print("\n8. Каскадное удаление: удаляем студента — исчезают его оценки")
    with Session(engine) as session:
        before = session.scalar(select(func.count()).select_from(Enrollment))
        petrov = session.scalar(
            select(Student).where(Student.full_name == "Петров Пётр"))
        own = len(petrov.enrollments)
        session.delete(petrov)
        session.commit()
        after = session.scalar(select(func.count()).select_from(Enrollment))
        print(f"   Оценок было {before}, у Петрова {own}, стало {after}")

    engine.dispose()


if __name__ == "__main__":
    main()

from sqlalchemy import ForeignKey, String, BigInteger, Text, Integer, Boolean, DateTime, select
from sqlalchemy.orm import Mapped, DeclarativeBase, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from datetime import datetime

DATABASE_URL = 'postgresql+asyncpg://botadmin:12345678@postgres:5432/playex_db'

engine = create_async_engine(url=DATABASE_URL, echo=True)
async_session = async_sessionmaker(bind=engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)


class Category(Base):
    """Таблица категорий задач (например: 'Задачи 1 типа', 'Задачи 2 типа')"""
    __tablename__ = 'categories'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)  # Например: "Задачи 1 типа"
    subject: Mapped[str] = mapped_column(String(50), nullable=False)  # "math" или "informatics"
    description: Mapped[str] = mapped_column(Text, nullable=True)


class Problem(Base):
    """Таблица задач (теперь без Enum)"""
    __tablename__ = 'problems'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(String(50), nullable=False)  # "math" или "informatics"
    difficulty: Mapped[str] = mapped_column(String(50), nullable=False)  # "easy", "medium", "hard"
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'), nullable=True)  # НОВОЕ!
    correct_answer: Mapped[str] = mapped_column(String(256), nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=10)


class UserSolution(Base):
    """Таблица решений пользователей"""
    __tablename__ = 'user_solutions'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    problem_id: Mapped[int] = mapped_column(ForeignKey('problems.id'), nullable=False)
    user_answer: Mapped[str] = mapped_column(String(256), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    solved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def init_db():
    """
    Создаёт все таблицы и добавляет тестовые данные.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Добавим тестовые данные, если таблица categories пуста
    async with async_session() as session:
        existing = await session.scalar(select(Category).limit(1))
        if not existing:
            # Создаём категории
            categories = [
                # Категории математики
                Category(name="Задачи 1 типа", subject="math", description="Простые задачи математики"),
                Category(name="Задачи 2 типа", subject="math", description="Средние задачи математики"),
                Category(name="Задачи 3 типа", subject="math", description="Сложные задачи математики"),

                # Категории информатики
                Category(name="Задачи 1 типа", subject="informatics", description="Простые задачи информатики"),
                Category(name="Задачи 2 типа", subject="informatics", description="Средние задачи информатики"),
                Category(name="Задачи 3 типа", subject="informatics", description="Сложные задачи информатики"),
            ]
            session.add_all(categories)
            await session.commit()

        # Добавляем тестовые задачи, если таблица problems пуста
        existing_problem = await session.scalar(select(Problem).limit(1))
        if not existing_problem:
            # Получаем категории
            categories = await session.scalars(select(Category))
            categories_list = list(categories)

            # Находим категории по subject
            math_cat_1 = next((c for c in categories_list if c.subject == "math" and "1 типа" in c.name), None)
            math_cat_2 = next((c for c in categories_list if c.subject == "math" and "2 типа" in c.name), None)
            info_cat_1 = next((c for c in categories_list if c.subject == "informatics" and "1 типа" in c.name), None)
            info_cat_2 = next((c for c in categories_list if c.subject == "informatics" and "2 типа" in c.name), None)

            problems = [
                # Математика
                Problem(
                    title="Квадратное уравнение",
                    description="Решите уравнение: x² - 5x + 6 = 0",
                    subject="math",
                    difficulty="easy",
                    category_id=math_cat_1.id if math_cat_1 else None,
                    correct_answer="2;3",
                    points=10
                ),
                Problem(
                    title="Площадь треугольника",
                    description="Найдите площадь треугольника со сторонами 5, 12, 13",
                    subject="math",
                    difficulty="medium",
                    category_id=math_cat_2.id if math_cat_2 else None,
                    correct_answer="30",
                    points=20
                ),

                # Информатика
                Problem(
                    title="Бинарный поиск",
                    description="Какая сложность у бинарного поиска?",
                    subject="informatics",
                    difficulty="easy",
                    category_id=info_cat_1.id if info_cat_1 else None,
                    correct_answer="O(log n)",
                    points=10
                ),
                Problem(
                    title="Алгоритмы сортировки",
                    description="Какой алгоритм сортировки имеет сложность O(n²)?",
                    subject="informatics",
                    difficulty="medium",
                    category_id=info_cat_2.id if info_cat_2 else None,
                    correct_answer="пузырьковая сортировка",
                    points=20
                ),
            ]
            session.add_all(problems)
            await session.commit()

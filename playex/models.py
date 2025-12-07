from sqlalchemy import ForeignKey, String, BigInteger, Text, Integer, Enum, Boolean, DateTime, select
from sqlalchemy.orm import Mapped, DeclarativeBase, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
import enum
from datetime import datetime

DATABASE_URL = 'postgresql+asyncpg://botadmin:12345678@postgres:5432/playex_db'
engine = create_async_engine(url=DATABASE_URL, echo=True)
async_session = async_sessionmaker(bind=engine, expire_on_commit=False)

class Base(AsyncAttrs, DeclarativeBase):
    pass

class Subject(enum.Enum):
    MATH = "math"
    INFORMATICS = "informatics"

class Difficulty(enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)

class Problem(Base):
    __tablename__ = 'problems'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    subject: Mapped[Subject] = mapped_column(Enum(Subject))
    difficulty: Mapped[Difficulty] = mapped_column(Enum(Difficulty))
    correct_answer: Mapped[str] = mapped_column(String(256))
    points: Mapped[int] = mapped_column(Integer, default=10)

class UserSolution(Base):
    __tablename__ = 'user_solutions'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    problem_id: Mapped[int] = mapped_column(ForeignKey('problems.id'))
    user_answer: Mapped[str] = mapped_column(String(256))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    solved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def init_db():
    """
    Создаёт все таблицы и добавляет тестовые задачи, если их ещё нет.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Добавим несколько задач, если таблица problems пуста.
    async with async_session() as session:
        existing = await session.scalar(select(Problem).limit(1))
        if not existing:
            math_problems = [
                Problem(
                    title="Квадратное уравнение",
                    description="Решите уравнение: x² - 5x + 6 = 0",
                    subject=Subject.MATH,
                    difficulty=Difficulty.EASY,
                    correct_answer="2;3",
                    points=10
                ),
                Problem(
                    title="Площадь треугольника",
                    description="Найдите площадь треугольника со сторонами 5, 12, 13",
                    subject=Subject.MATH,
                    difficulty=Difficulty.MEDIUM,
                    correct_answer="30",
                    points=20
                )
            ]

            informatics_problems = [
                Problem(
                    title="Бинарный поиск",
                    description="Какая сложность у бинарного поиска?",
                    subject=Subject.INFORMATICS,
                    difficulty=Difficulty.EASY,
                    correct_answer="O(log n)",
                    points=10
                ),
                Problem(
                    title="Алгоритмы сортировки",
                    description="Какой алгоритм сортировки имеет сложность O(n²) в худшем случае?",
                    subject=Subject.INFORMATICS,
                    difficulty=Difficulty.MEDIUM,
                    correct_answer="пузырьковая сортировка",
                    points=20
                )
            ]

            session.add_all(math_problems + informatics_problems)
            await session.commit()

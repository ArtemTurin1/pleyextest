from sqlalchemy import ForeignKey, String, Integer, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, DeclarativeBase, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

DATABASE_URL = 'postgresql+asyncpg://botadmin:12345678@postgres:5432/playex_db'

engine = create_async_engine(url=DATABASE_URL, echo=False)
async_session = async_sessionmaker(bind=engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    solved_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Category(Base):
    __tablename__ = 'categories'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    subject: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)


class Problem(Base):
    __tablename__ = 'problems'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(String(50), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(50), nullable=False)
    category_id: Mapped[int] = mapped_column(Integer, nullable=True)
    correct_answer: Mapped[str] = mapped_column(String(256), nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=10)


class UserSolution(Base):
    __tablename__ = 'user_solutions'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=True)
    tg_id: Mapped[int] = mapped_column(Integer, nullable=True)
    email: Mapped[str] = mapped_column(String(256), nullable=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey('problems.id'), nullable=False)
    user_answer: Mapped[str] = mapped_column(String(256), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    solved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = 'tasks'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=True)
    tg_id: Mapped[int] = mapped_column(Integer, nullable=True)
    email: Mapped[str] = mapped_column(String(256), nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ===== PYDANTIC MODELS =====

class RegisterRequest(BaseModel):
    tg_id: Optional[int] = None
    email: Optional[str] = None
    name: Optional[str] = None
    password: Optional[str] = None


class SolveProblemRequest(BaseModel):
    problem_id: int
    user_answer: str


class SolveProblemResponse(BaseModel):
    correct: bool
    correct_answer: Optional[str] = None
    points_earned: Optional[int] = None
    message: str
    already_solved: Optional[bool] = False
    new_score: Optional[int] = None


class TaskRequest(BaseModel):
    title: str


async def init_db():
    """Создание всех таблиц"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ База данных инициализирована")

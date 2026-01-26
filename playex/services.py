from sqlalchemy import select, update, delete, func, desc, and_
from playex.models import async_session, User, Problem, UserSolution, Category
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import re

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(password: str) -> str:
    return pwd_ctx.hash(password)


def _verify_password(password: str, hashed: str) -> bool:
    return pwd_ctx.verify(password, hashed)


def _normalize_answer(s: str) -> str:
    if s is None:
        return ""
    return re.sub(r'\s+', '', s.lower()).replace(',', '.').strip()


def _answer_to_set(s: str):
    """Если ответ содержит разделители (; ,), вернём множество вариантов."""
    if s is None:
        return set()
    parts = re.split(r'[;,]', s)
    return set(_normalize_answer(p) for p in parts if p != '')


# ==================== USER FUNCTIONS ====================

async def get_user_by_tg(tg_id: int) -> Optional[User]:
    async with async_session() as session:
        return await session.scalar(select(User).where(User.tg_id == tg_id))


async def get_user_by_email(email: str) -> Optional[User]:
    async with async_session() as session:
        return await session.scalar(select(User).where(User.email == email))


async def add_user(tg_id: int = None, name: str = None, email: str = None, password: str = None):
    """
    Создаёт пользователя если не существует.
    """
    async with async_session() as session:
        if tg_id:
            user = await session.scalar(select(User).where(User.tg_id == tg_id))
            if user:
                return user

            new_user = User(tg_id=tg_id, name=name)
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            return new_user

        if email:
            user = await session.scalar(select(User).where(User.email == email))
            if user:
                return None

            new_user = User(email=email, name=name, password_hash=_hash_password(password))
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            return new_user


async def register_user_via_email(email: str, password: str, name: str = None):
    existing = await get_user_by_email(email)
    if existing:
        return None
    return await add_user(email=email, password=password, name=name)


async def check_credentials(email: str, password: str):
    user = await get_user_by_email(email)
    if not user or not user.password_hash:
        return None
    if _verify_password(password, user.password_hash):
        return user
    return None


# ==================== PROBLEM FUNCTIONS ====================

async def get_categories(subject: str = None) -> List[dict]:
    """Получает категории, опционально фильтрует по предмету"""
    async with async_session() as session:
        query = select(Category)
        if subject:
            query = query.where(Category.subject == subject)

        categories = await session.scalars(query)
        return [
            {
                'id': c.id,
                'name': c.name,
                'subject': c.subject,
                'description': c.description
            }
            for c in categories
        ]


async def get_problems(subject: str = None, difficulty: str = None, category_id: int = None) -> List[dict]:
    """Получает задачи с фильтрацией"""
    async with async_session() as session:
        query = select(Problem)

        conditions = []
        if subject:
            conditions.append(Problem.subject == subject)
        if difficulty:
            conditions.append(Problem.difficulty == difficulty)
        if category_id:
            conditions.append(Problem.category_id == category_id)

        if conditions:
            query = query.where(and_(*conditions))

        problems = await session.scalars(query)
        return [
            {
                'id': p.id,
                'title': p.title,
                'description': p.description,
                'subject': p.subject,
                'difficulty': p.difficulty,
                'category_id': p.category_id,
                'points': p.points
            }
            for p in problems
        ]


async def get_random_problem(subject: str, category_id: int) -> Optional[dict]:
    """Получает случайную задачу из предмета и категории"""
    async with async_session() as session:
        problem = await session.scalar(
            select(Problem)
            .where(
                and_(
                    Problem.subject == subject,
                    Problem.category_id == category_id
                )
            )
            .order_by(func.random())
        )

        if not problem:
            return None

        return {
            'id': problem.id,
            'title': problem.title,
            'description': problem.description,
            'subject': problem.subject,
            'difficulty': problem.difficulty,
            'category_id': problem.category_id,
            'points': problem.points
        }


# ==================== SOLUTION FUNCTIONS ====================

async def has_user_solved_problem(user_id: int, problem_id: int) -> bool:
    """Проверяет, решил ли пользователь уже эту задачу"""
    async with async_session() as session:
        existing_solution = await session.scalar(
            select(UserSolution).where(
                and_(
                    UserSolution.user_id == user_id,
                    UserSolution.problem_id == problem_id,
                    UserSolution.is_correct == True
                )
            )
        )
        return existing_solution is not None


async def check_solution(user_id: int, problem_id: int, user_answer: str):
    """Проверяет ответ и сохраняет решение"""
    async with async_session() as session:
        already_solved = await has_user_solved_problem(user_id, problem_id)

        if already_solved:
            return {
                'correct': False,
                'already_solved': True,
                'message': 'Вы уже решили эту задачу ранее',
                'points_earned': 0,
                'new_score': 0
            }

        problem = await session.scalar(select(Problem).where(Problem.id == problem_id))
        user = await session.scalar(select(User).where(User.id == user_id))

        if not problem or not user:
            return {'error': 'user or problem not found'}

        correct_raw = problem.correct_answer or ""

        if re.search(r'[;,]', correct_raw):
            is_correct = _answer_to_set(user_answer) == _answer_to_set(correct_raw)
        else:
            is_correct = _normalize_answer(user_answer) == _normalize_answer(correct_raw)

        solution = UserSolution(
            user_id=user_id,
            problem_id=problem_id,
            user_answer=user_answer,
            is_correct=is_correct
        )

        if is_correct:
            user.score = (user.score or 0) + (problem.points or 0)
            user.level = (user.score // 100) + 1

        session.add(solution)
        await session.commit()
        await session.refresh(user)

        return {
            'correct': is_correct,
            'already_solved': False,
            'correct_answer': None if is_correct else problem.correct_answer,
            'points_earned': problem.points if is_correct else 0,
            'new_score': user.score
        }


# ==================== STATS FUNCTIONS ====================

async def get_weekly_stats(user_id: int):
    """Получает статистику за последние 7 дней"""
    async with async_session() as session:
        week_ago = datetime.utcnow() - timedelta(days=7)

        solved_count = await session.scalar(
            select(func.count(UserSolution.id))
            .where(
                and_(
                    UserSolution.user_id == user_id,
                    UserSolution.is_correct == True,
                    UserSolution.solved_at >= week_ago
                )
            )
        ) or 0

        return {'solved_count': int(solved_count)}


async def get_user_stats(user_id: int):
    """Получает полную статистику пользователя"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        if not user:
            return None

        # Всего решено
        solved_count = await session.scalar(
            select(func.count(UserSolution.id))
            .where(
                and_(
                    UserSolution.user_id == user_id,
                    UserSolution.is_correct == True
                )
            )
        ) or 0

        # Решено математики
        math_solved = await session.scalar(
            select(func.count(UserSolution.id))
            .join(Problem, Problem.id == UserSolution.problem_id)
            .where(
                and_(
                    UserSolution.user_id == user_id,
                    UserSolution.is_correct == True,
                    Problem.subject == "math"
                )
            )
        ) or 0

        # Решено информатики
        informatics_solved = await session.scalar(
            select(func.count(UserSolution.id))
            .join(Problem, Problem.id == UserSolution.problem_id)
            .where(
                and_(
                    UserSolution.user_id == user_id,
                    UserSolution.is_correct == True,
                    Problem.subject == "informatics"
                )
            )
        ) or 0

        return {
            'score': user.score or 0,
            'level': user.level or 1,
            'solved_count': int(solved_count),
            'math_solved': int(math_solved),
            'informatics_solved': int(informatics_solved),
            'total_attempts': int(solved_count)
        }

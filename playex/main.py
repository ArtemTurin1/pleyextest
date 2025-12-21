from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import hashlib
import os

from models import (
    engine, async_session, init_db,
    User, Category, Problem, UserSolution, TimedAttempt, Task,
    RegisterRequest, LoginRequest, SolveProblemRequest, SolveProblemResponse,
    TaskRequest
)

app = FastAPI()

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== DATABASE =====
async def get_db():
    async with async_session() as session:
        yield session


# ===== STARTUP =====
@app.on_event("startup")
async def startup():
    await init_db()
    print("✅ База данных инициализирована")


# ===== UTILS =====
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ===== USERS / REGISTRATION =====

@app.post('/api/users/register')
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Регистрация пользователя"""
    try:
        # Проверяем, существует ли уже пользователь
        result = await db.execute(select(User).where(User.email == data.email))
        existing_user = result.scalars().first()

        if existing_user:
            raise HTTPException(status_code=400, detail='❌ Пользователь уже существует')

        # Создаём нового пользователя
        password_hash = hash_password(data.password)
        user = User(
            email=data.email,
            name=data.name,
            password_hash=password_hash,
            level=1
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "message": "✅ Пользователь создан"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ Ошибка регистрации: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


@app.post('/api/login/')
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Вход пользователя"""
    try:
        result = await db.execute(select(User).where(User.email == data.email))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        password_hash = hash_password(data.password)
        if user.password_hash != password_hash:
            raise HTTPException(status_code=401, detail='❌ Неверный пароль')

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "level": user.level,
            "message": "✅ Успешный вход"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка входа: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== PROFILE =====

@app.get('/api/profile/email/{email}')
async def get_profile(email: str, db: AsyncSession = Depends(get_db)):
    """Получить профиль пользователя"""
    try:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "level": user.level,
            "created_at": str(user.created_at)
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения профиля: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


@app.put('/api/profile/update')
async def update_profile(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    """Обновить профиль пользователя"""
    try:
        email = request.headers.get('X-EMAIL')

        if not email:
            raise HTTPException(status_code=400, detail='❌ Не авторизованы')

        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        if 'name' in data:
            user.name = data['name']

        await db.commit()
        await db.refresh(user)

        return {
            "id": user.id,
            "name": user.name,
            "message": "✅ Профиль обновлён"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ Ошибка обновления профиля: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== STATS =====

@app.get('/api/stats/email/{email}')
async def get_stats(email: str, db: AsyncSession = Depends(get_db)):
    """Получить статистику пользователя"""
    try:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        # Получаем все решения
        result = await db.execute(
            select(UserSolution).where(UserSolution.user_id == user.id)
        )
        solutions = result.scalars().all()

        # Подсчитываем статистику
        total_solved = len(solutions)
        correct_count = sum(1 for s in solutions if s.is_correct)

        # Подсчитываем по предметам
        math_solved = sum(1 for s in solutions if s.problem_id in [
            p.id for p in await db.execute(
                select(Problem).where(Problem.subject == 'math')
            ).then(lambda x: x.scalars().all())
        ])

        informatics_solved = sum(1 for s in solutions if s.problem_id in [
            p.id for p in await db.execute(
                select(Problem).where(Problem.subject == 'informatics')
            ).then(lambda x: x.scalars().all())
        ])

        return {
            "solved_count": correct_count,
            "total_attempts": total_solved,
            "math_solved": math_solved,
            "informatics_solved": informatics_solved
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


@app.get('/api/timed-stats/')
async def get_timed_stats(subject: Optional[str] = None, request: Request = None, db: AsyncSession = Depends(get_db)):
    """Получить статистику тренировок на время"""
    try:
        email = request.headers.get('X-EMAIL') if request else None

        if not email:
            raise HTTPException(status_code=400, detail='❌ Не авторизованы')

        # Получаем пользователя
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        # Получаем попытки
        query = select(TimedAttempt).where(TimedAttempt.user_id == user.id)

        if subject:
            query = query.where(TimedAttempt.subject == subject)

        result = await db.execute(query)
        attempts_list = result.scalars().all()

        # Подсчитываем статистику
        total = len(attempts_list)
        correct = sum(1 for a in attempts_list if a.is_correct)
        incorrect = total - correct
        success_rate = (correct / total * 100) if total > 0 else 0

        # Подсчитываем время и среднюю скорость
        total_time = sum(a.time_spent_seconds for a in attempts_list)
        avg_problems_per_minute = (total / (total_time / 60)) if total_time > 0 else 0

        return {
            "total_attempts": total,
            "correct_answers": correct,
            "incorrect_answers": incorrect,
            "success_rate": round(success_rate, 1),
            "avg_problems_per_minute": round(avg_problems_per_minute, 2),
            "total_time_seconds": total_time
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {str(e)}")
        return {
            "total_attempts": 0,
            "correct_answers": 0,
            "incorrect_answers": 0,
            "success_rate": 0,
            "avg_problems_per_minute": 0,
            "total_time_seconds": 0
        }


# ===== CATEGORIES =====

@app.get('/api/categories/')
async def get_categories(subject: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Получить категории"""
    try:
        query = select(Category)
        if subject:
            query = query.where(Category.subject == subject)

        result = await db.execute(query)
        categories = result.scalars().all()

        return [
            {
                "id": c.id,
                "name": c.name,
                "subject": c.subject,
                "description": c.description
            }
            for c in categories
        ]

    except Exception as e:
        print(f"❌ Ошибка загрузки категорий: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== PROBLEMS =====

@app.get('/api/problems/')
async def get_problems(
        subject: Optional[str] = None,
        difficulty: Optional[str] = None,
        category_id: Optional[int] = None,
        db: AsyncSession = Depends(get_db)
):
    """Получить задачи"""
    try:
        query = select(Problem)

        if subject:
            query = query.where(Problem.subject == subject)
        if difficulty:
            query = query.where(Problem.difficulty == difficulty)
        if category_id:
            query = query.where(Problem.category_id == category_id)

        result = await db.execute(query)
        problems = result.scalars().all()

        return [
            {
                "id": p.id,
                "title": p.title,
                "description": p.solution or "",
                "subject": p.subject,
                "difficulty": p.difficulty,
                "category_id": p.category_id,
                "correct_answer": p.correct_answer
            }
            for p in problems
        ]

    except Exception as e:
        print(f"❌ Ошибка загрузки задач: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


@app.get('/api/problems/random/')
async def get_random_problem(
        subject: str,
        category_id: Optional[int] = None,
        db: AsyncSession = Depends(get_db)
):
    """Получить случайную задачу"""
    try:
        query = select(Problem).where(Problem.subject == subject)

        if category_id:
            query = query.where(Problem.category_id == category_id)

        result = await db.execute(query)
        problems = result.scalars().all()

        if not problems:
            return None

        import random
        problem = random.choice(problems)

        return {
            "id": problem.id,
            "title": problem.title,
            "description": problem.solution or "",
            "subject": problem.subject,
            "difficulty": problem.difficulty,
            "category_id": problem.category_id,
            "correct_answer": problem.correct_answer
        }

    except Exception as e:
        print(f"❌ Ошибка загрузки задачи: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== SOLVE =====

@app.post('/api/solve/')
async def solve_problem(data: SolveProblemRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Проверить ответ на задачу"""
    try:
        email = request.headers.get('X-EMAIL')

        if not email:
            raise HTTPException(status_code=400, detail='❌ Не авторизованы')

        # Получаем пользователя
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        # Получаем задачу
        result = await db.execute(select(Problem).where(Problem.id == data.problem_id))
        problem = result.scalars().first()

        if not problem:
            raise HTTPException(status_code=404, detail='❌ Задача не найдена')

        # Проверяем ответ
        user_answer = str(data.user_answer).strip().lower()
        correct_answer = str(problem.correct_answer).strip().lower()
        is_correct = user_answer == correct_answer

        # Проверяем, решена ли уже задача
        result = await db.execute(
            select(UserSolution).where(
                (UserSolution.user_id == user.id) &
                (UserSolution.problem_id == problem.id)
            )
        )
        existing_solution = result.scalars().first()

        already_solved = existing_solution is not None and existing_solution.is_correct

        # Если задача не решена или решена неправильно, сохраняем новое решение
        if not already_solved:
            solution = UserSolution(
                user_id=user.id,
                problem_id=problem.id,
                user_answer=data.user_answer,
                is_correct=is_correct
            )
            db.add(solution)
            await db.commit()

        return SolveProblemResponse(
            correct=is_correct,
            correct_answer=problem.correct_answer if not is_correct else None,
            message="✅ Правильно!" if is_correct else "❌ Неправильно",
            already_solved=already_solved
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ Ошибка проверки ответа: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== TIMED ATTEMPT =====

@app.post('/api/timed-attempt/')
async def save_timed_attempt(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    """Сохранить попытку тренировки на время"""
    try:
        email = request.headers.get('X-EMAIL')

        if not email:
            raise HTTPException(status_code=400, detail='❌ Не авторизованы')

        # Получаем пользователя
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        # Создаём запись попытки
        attempt = TimedAttempt(
            user_id=user.id,
            problem_id=data.get('problem_id'),
            subject=data.get('subject', ''),
            user_answer=data.get('user_answer', ''),
            is_correct=data.get('is_correct', False),
            time_spent_seconds=data.get('time_spent_seconds', 0)
        )

        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)

        return {
            "id": attempt.id,
            "message": "✅ Попытка сохранена"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ Ошибка сохранения попытки: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== ЗАДАЧИ ПОЛЬЗОВАТЕЛЯ =====

@app.get('/api/tasks/')
async def get_tasks(request: Request, db: AsyncSession = Depends(get_db)):
    """Получить задачи пользователя"""
    try:
        email = request.headers.get('X-EMAIL')
        if not email:
            raise HTTPException(status_code=400, detail='❌ Не авторизованы')

        # Получаем пользователя
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        # Получаем задачи
        result = await db.execute(select(Task).where(Task.user_id == user.id))
        tasks_list = result.scalars().all()

        return [
            {
                "id": t.id,
                "title": t.title,
                "is_completed": t.is_completed,
                "created_at": str(t.created_at)
            }
            for t in tasks_list
        ]

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка загрузки задач: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка загрузки задач: {str(e)}')


@app.post('/api/tasks/')
async def create_task(data: TaskRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Создать задачу"""
    try:
        email = request.headers.get('X-EMAIL')
        if not email:
            raise HTTPException(status_code=400, detail='❌ Не авторизованы')

        # Получаем пользователя
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        task = Task(user_id=user.id, title=data.title)
        db.add(task)
        await db.commit()
        await db.refresh(task)

        return {
            "id": task.id,
            "title": task.title,
            "message": "✅ Задача создана"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ Ошибка создания задачи: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


@app.patch('/api/tasks/{task_id}/complete')
async def complete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Отметить задачу как выполненную"""
    try:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalars().first()

        if not task:
            raise HTTPException(status_code=404, detail='❌ Задача не найдена')

        task.is_completed = True
        await db.commit()

        return {
            "id": task.id,
            "is_completed": task.is_completed,
            "message": "✅ Задача выполнена"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ Ошибка отметки задачи: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


@app.delete('/api/tasks/{task_id}')
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить задачу"""
    try:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalars().first()

        if not task:
            raise HTTPException(status_code=404, detail='❌ Задача не найдена')

        await db.delete(task)
        await db.commit()

        return {
            "message": "✅ Задача удалена"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ Ошибка удаления задачи: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== HEALTH CHECK =====

@app.get('/health')
async def health_check():
    """Проверка здоровья сервера"""
    return {"status": "✅ Server is running"}

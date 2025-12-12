from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import uvicorn
import re
from passlib.context import CryptContext

from models import (
    async_session, init_db,
    User, Problem, UserSolution, Category, Task,
    RegisterRequest, SolveProblemRequest, SolveProblemResponse, TaskRequest
)

app = FastAPI(title="PlayEx API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== ХЕШИРОВАНИЕ ПАРОЛЕЙ =====
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ===== HELPER FUNCTIONS =====
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


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


@app.on_event("startup")
async def startup():
    await init_db()
    print("✅ Приложение запущено")


@app.get('/api/health')
async def health_check():
    return {"status": "ok"}


# ===== РЕГИСТРАЦИЯ =====
@app.post('/api/users/register')
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Регистрация через TG или Email"""
    try:
        # Регистрация через Telegram
        if data.tg_id:
            result = await db.execute(select(User).filter(User.tg_id == data.tg_id))
            existing = result.scalars().first()
            if existing:
                return {
                    "id": existing.id,
                    "tg_id": existing.tg_id,
                    "name": existing.name,
                    "score": existing.score,
                    "message": "Уже зарегистрирован"
                }

            user = User(tg_id=data.tg_id, name=data.name)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return {
                "id": user.id,
                "tg_id": user.tg_id,
                "name": user.name,
                "score": user.score,
                "message": "Успешно зарегистрирован через Telegram"
            }

        # Регистрация через Email
        elif data.email:
            result = await db.execute(select(User).filter(User.email == data.email))
            existing = result.scalars().first()
            if existing:
                return {
                    "id": existing.id,
                    "email": existing.email,
                    "name": existing.name,
                    "score": existing.score,
                    "message": "Уже зарегистрирован"
                }

            hashed_password = hash_password(data.password)
            user = User(email=data.email, name=data.name, password_hash=hashed_password)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "score": user.score,
                "message": "Успешно зарегистрирован через Email"
            }

        else:
            raise HTTPException(status_code=400, detail='Укажите tg_id или email')
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ===== ЛОГИН =====
@app.post('/api/login/')
async def login(data: dict, db: AsyncSession = Depends(get_db)):
    """Вход через Email"""
    try:
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            raise HTTPException(status_code=400, detail='Укажите email и пароль')

        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalars().first()

        if not user or not user.password_hash or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail='Неверный email или пароль')

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "score": user.score,
            "message": "Успешно вошли"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== ПОЛУЧЕНИЕ ПОЛЬЗОВАТЕЛЯ =====
@app.get('/api/users/by-tg/{tg_id}')
async def get_user_by_tg(tg_id: int, db: AsyncSession = Depends(get_db)):
    """Получить пользователя по TG ID"""
    try:
        result = await db.execute(select(User).filter(User.tg_id == tg_id))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='Не найден')

        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "name": user.name,
            "score": user.score,
            "solved_count": user.solved_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/users/by-email/{email}')
async def get_user_by_email(email: str, db: AsyncSession = Depends(get_db)):
    """Получить пользователя по Email"""
    try:
        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='Не найден')

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "score": user.score,
            "solved_count": user.solved_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== ПРОФИЛЬ =====
@app.get('/api/profile/tg/{tg_id}')
async def get_profile_tg(tg_id: int, db: AsyncSession = Depends(get_db)):
    """Получить профиль по TG ID"""
    try:
        result = await db.execute(select(User).filter(User.tg_id == tg_id))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='Пользователь не найден')

        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "name": user.name,
            "score": user.score or 0,
            "level": user.level or 1,
            "solved_count": user.solved_count or 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/profile/email/{email}')
async def get_profile_email(email: str, db: AsyncSession = Depends(get_db)):
    """Получить профиль по Email"""
    try:
        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='Пользователь не найден')

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "score": user.score or 0,
            "level": user.level or 1,
            "solved_count": user.solved_count or 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== КАТЕГОРИИ =====
@app.get('/api/categories/')
async def get_categories(subject: str = None, db: AsyncSession = Depends(get_db)):
    """Получить категории"""
    try:
        query = select(Category)
        if subject:
            query = query.filter(Category.subject == subject)

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
        raise HTTPException(status_code=500, detail=str(e))


# ===== ЗАДАЧИ =====
@app.get('/api/problems/')
async def get_problems(subject: str = None, difficulty: str = None, category_id: int = None,
                       db: AsyncSession = Depends(get_db)):
    """Получить задачи"""
    try:
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

        result = await db.execute(query)
        problems = result.scalars().all()

        return [
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "subject": p.subject,
                "difficulty": p.difficulty,
                "category_id": p.category_id,
                "points": p.points
            }
            for p in problems
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/problems/random/')
async def get_random_problem(subject: str, category_id: int = None, db: AsyncSession = Depends(get_db)):
    """Получить случайную задачу"""
    try:
        query = select(Problem).filter(Problem.subject == subject)
        if category_id:
            query = query.filter(Problem.category_id == category_id)

        query = query.order_by(func.random())
        result = await db.execute(query)
        problem = result.scalars().first()

        if not problem:
            raise HTTPException(status_code=404, detail='Не найдено')

        return {
            "id": problem.id,
            "title": problem.title,
            "description": problem.description,
            "points": problem.points,
            "difficulty": problem.difficulty,
            "subject": problem.subject,
            "category_id": problem.category_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== РЕШЕНИЕ ЗАДАЧ =====
# ===== РЕШЕНИЕ ЗАДАЧ =====
@app.post('/api/solve/')
async def solve_problem(data: SolveProblemRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Проверить решение задачи.
    """
    try:
        problem_id = data.problem_id
        user_answer = data.user_answer.strip()

        # Получаем идентификатор пользователя из headers
        tg_id = request.headers.get('X-TG-ID')
        email = request.headers.get('X-EMAIL')

        print(f"🔍 DEBUG: problem_id={problem_id}, answer={user_answer}, tg_id={tg_id}, email={email}")

        # ПРОВЕРЯЕМ ЗАДАЧУ
        result = await db.execute(select(Problem).where(Problem.id == problem_id))
        problem = result.scalars().first()

        if not problem:
            raise HTTPException(status_code=404, detail='Задача не найдена')

        # ===== ЕСЛИ ГОСТЬ =====
        if not tg_id and not email:
            correct_raw = problem.correct_answer or ""

            if re.search(r'[;,]', correct_raw):
                is_correct = _answer_to_set(user_answer) == _answer_to_set(correct_raw)
            else:
                is_correct = _normalize_answer(user_answer) == _normalize_answer(correct_raw)

            return {
                "correct": is_correct,
                "already_solved": False,
                "correct_answer": None if is_correct else problem.correct_answer,
                "points_earned": 0,
                "new_score": 0,
                "message": "Правильно!" if is_correct else "Неправильно"
            }

        # ===== ЕСЛИ АВТОРИЗОВАН =====
        user = None
        if tg_id:
            result = await db.execute(select(User).where(User.tg_id == int(tg_id)))
            user = result.scalars().first()
        elif email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='Пользователь не найден')

        # Проверяем, уже ли решал эту задачу
        existing = await db.execute(
            select(UserSolution).where(
                (UserSolution.user_id == user.id) &
                (UserSolution.problem_id == problem_id) &
                (UserSolution.is_correct == True)
            )
        )

        if existing.scalars().first():
            return {
                "correct": False,
                "already_solved": True,
                "message": "Вы уже решили эту задачу ранее",
                "points_earned": 0,
                "new_score": user.score or 0
            }

        # Проверяем ответ
        correct_raw = problem.correct_answer or ""

        if re.search(r'[;,]', correct_raw):
            is_correct = _answer_to_set(user_answer) == _answer_to_set(correct_raw)
        else:
            is_correct = _normalize_answer(user_answer) == _normalize_answer(correct_raw)

        # Сохраняем решение
        solution = UserSolution(
            user_id=user.id,
            problem_id=problem_id,
            user_answer=user_answer,
            is_correct=is_correct,
            tg_id=int(tg_id) if tg_id else None,
            email=email
        )

        db.add(solution)

        # Если правильно - добавляем баллы
        if is_correct:
            user.score = (user.score or 0) + (problem.points or 0)
            user.level = (user.score // 100) + 1
            user.solved_count = (user.solved_count or 0) + 1

        await db.commit()
        await db.refresh(user)

        return {
            "correct": is_correct,
            "already_solved": False,
            "correct_answer": None if is_correct else problem.correct_answer,
            "points_earned": problem.points if is_correct else 0,
            "new_score": user.score,
            "message": "Правильно!" if is_correct else "Неправильно"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR in solve_problem: {str(e)}")
        import traceback
        traceback.print_exc()
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ===== СТАТИСТИКА =====
@app.get('/api/stats/tg/{tg_id}')
async def get_stats_tg(tg_id: int, db: AsyncSession = Depends(get_db)):
    """Статистика по TG"""
    try:
        result = await db.execute(select(User).filter(User.tg_id == tg_id))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='Не найден')

        result = await db.execute(
            select(UserSolution).filter(
                UserSolution.user_id == user.id,
                UserSolution.is_correct == True
            )
        )
        solved = result.scalars().all()

        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "name": user.name,
            "score": user.score or 0,
            "level": user.level or 1,
            "solved_count": user.solved_count or 0,
            "solved_problems": [s.problem_id for s in solved]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/stats/email/{email}')
async def get_stats_email(email: str, db: AsyncSession = Depends(get_db)):
    """Статистика по Email"""
    try:
        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='Не найден')

        result = await db.execute(
            select(UserSolution).filter(
                UserSolution.user_id == user.id,
                UserSolution.is_correct == True
            )
        )
        solved = result.scalars().all()

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "score": user.score or 0,
            "level": user.level or 1,
            "solved_count": user.solved_count or 0,
            "solved_problems": [s.problem_id for s in solved]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== ЗАДАЧИ ПОЛЬЗОВАТЕЛЯ =====
@app.get('/api/tasks/tg/{tg_id}')
async def get_tasks_tg(tg_id: int, db: AsyncSession = Depends(get_db)):
    """Задачи по TG"""
    try:
        result = await db.execute(select(Task).filter(Task.tg_id == tg_id))
        tasks = result.scalars().all()

        return [{"id": t.id, "title": t.title, "is_completed": t.is_completed} for t in tasks]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/tasks/email/{email}')
async def get_tasks_email(email: str, db: AsyncSession = Depends(get_db)):
    """Задачи по Email"""
    try:
        result = await db.execute(select(Task).filter(Task.email == email))
        tasks = result.scalars().all()

        return [{"id": t.id, "title": t.title, "is_completed": t.is_completed} for t in tasks]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/tasks/tg/{tg_id}')
async def create_task_tg(tg_id: int, data: TaskRequest, db: AsyncSession = Depends(get_db)):
    """Создать задачу для TG пользователя"""
    try:
        task = Task(tg_id=tg_id, title=data.title)
        db.add(task)
        await db.commit()
        await db.refresh(task)

        return {"id": task.id, "title": task.title, "is_completed": task.is_completed}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/tasks/email/{email}')
async def create_task_email(email: str, data: TaskRequest, db: AsyncSession = Depends(get_db)):
    """Создать задачу для Email пользователя"""
    try:
        task = Task(email=email, title=data.title)
        db.add(task)
        await db.commit()
        await db.refresh(task)

        return {"id": task.id, "title": task.title, "is_completed": task.is_completed}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.patch('/api/tasks/{task_id}/complete')
async def complete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Завершить задачу"""
    try:
        result = await db.execute(select(Task).filter(Task.id == task_id))
        task = result.scalars().first()

        if not task:
            raise HTTPException(status_code=404, detail='Не найдена')

        task.is_completed = True
        await db.commit()

        return {"id": task.id, "title": task.title, "is_completed": task.is_completed}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete('/api/tasks/{task_id}')
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить задачу"""
    try:
        result = await db.execute(select(Task).filter(Task.id == task_id))
        task = result.scalars().first()

        if not task:
            raise HTTPException(status_code=404, detail='Не найдена')

        await db.delete(task)
        await db.commit()

        return {"message": "Удалена"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

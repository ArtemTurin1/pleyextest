from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import uvicorn

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
                    "points": existing.points,
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
                "points": user.points,
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
                    "points": existing.points,
                    "message": "Уже зарегистрирован"
                }

            user = User(email=data.email, name=data.name, password_hash=data.password)
            db.add(user)
            await db.commit()
            await db.refresh(user)

            return {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "points": user.points,
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

        if not user or user.password_hash != password:
            raise HTTPException(status_code=401, detail='Неверный email или пароль')

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "points": user.points,
            "message": "Успешно вошли"
        }

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
            "points": user.points,
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
            "points": user.points,
            "solved_count": user.solved_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== ПРОФИЛЬ =====
@app.get('/api/profile/tg/{tg_id}')
async def get_profile_tg(tg_id: int, db: AsyncSession = Depends(get_db)):
    """Профиль по TG"""
    try:
        result = await db.execute(select(User).filter(User.tg_id == tg_id))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='Не найден')

        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "name": user.name,
            "points": user.points,
            "solved_count": user.solved_count,
            "created_at": user.created_at
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/profile/email/{email}')
async def get_profile_email(email: str, db: AsyncSession = Depends(get_db)):
    """Профиль по Email"""
    try:
        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='Не найден')

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "points": user.points,
            "solved_count": user.solved_count,
            "created_at": user.created_at
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== КАТЕГОРИИ =====
@app.get('/api/categories/')
async def get_categories(subject: str = None, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Category)
        if subject:
            query = query.filter(Category.subject == subject)

        result = await db.execute(query)
        categories = result.scalars().all()

        return [
            {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "subject": cat.subject
            }
            for cat in categories
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== ЗАДАЧИ =====
@app.get('/api/problems/')
async def get_problems(
    subject: str = None,
    difficulty: str = None,
    category_id: int = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(Problem)

        if subject:
            query = query.filter(Problem.subject == subject)
        if difficulty:
            query = query.filter(Problem.difficulty == difficulty)
        if category_id:
            query = query.filter(Problem.category_id == category_id)

        result = await db.execute(query)
        problems = result.scalars().all()

        return [
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "points": p.points,
                "difficulty": p.difficulty,
                "subject": p.subject,
                "category_id": p.category_id
            }
            for p in problems
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/problems/random/')
async def get_random_problem(subject: str, category_id: int = None, db: AsyncSession = Depends(get_db)):
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
@app.post('/api/solve/')
async def solve_problem(
    data: SolveProblemRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Решить задачу (TG / Email / Гость)"""
    problem_id = data.problem_id
    user_answer = data.user_answer.strip()

    # Получаем ID из заголовков
    tg_id = request.headers.get('X-TG-ID')
    email = request.headers.get('X-EMAIL')

    # Получаем задачу
    result = await db.execute(select(Problem).filter(Problem.id == problem_id))
    problem = result.scalars().first()

    if not problem:
        raise HTTPException(status_code=404, detail='Не найдена')

    correct = user_answer.lower() == problem.correct_answer.lower()

    # ГОСТЬ (нет ни tg_id ни email)
    if tg_id is None and email is None:
        return SolveProblemResponse(
            correct=correct,
            correct_answer=problem.correct_answer if not correct else '',
            message='Правильно!' if correct else 'Неправильно'
        )

    # АВТОРИЗОВАННЫЙ (TG или Email)
    try:
        # Проверяем, не решал ли уже
        if tg_id:
            result = await db.execute(
                select(UserSolution).filter(
                    UserSolution.tg_id == int(tg_id),
                    UserSolution.problem_id == problem_id,
                    UserSolution.is_correct == True
                )
            )
        else:
            result = await db.execute(
                select(UserSolution).filter(
                    UserSolution.email == email,
                    UserSolution.problem_id == problem_id,
                    UserSolution.is_correct == True
                )
            )

        existing = result.scalars().first()

        if existing:
            return SolveProblemResponse(
                correct=False,
                already_solved=True,
                message='Уже решена'
            )

        if correct:
            solution = UserSolution(
                tg_id=int(tg_id) if tg_id else None,
                email=email,
                problem_id=problem_id,
                user_answer=user_answer,
                is_correct=True
            )
            db.add(solution)

            # Обновляем статистику пользователя
            if tg_id:
                user_result = await db.execute(select(User).filter(User.tg_id == int(tg_id)))
            else:
                user_result = await db.execute(select(User).filter(User.email == email))

            user = user_result.scalars().first()

            if user:
                user.points += problem.points
                user.solved_count += 1

            await db.commit()

            return SolveProblemResponse(
                correct=True,
                points_earned=problem.points,
                message='Правильно!'
            )
        else:
            return SolveProblemResponse(
                correct=False,
                correct_answer=problem.correct_answer,
                message='Неправильно'
            )
    except Exception as e:
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
                UserSolution.tg_id == tg_id,
                UserSolution.is_correct == True
            )
        )
        solved = result.scalars().all()

        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "name": user.name,
            "points": user.points,
            "solved_count": user.solved_count,
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
                UserSolution.email == email,
                UserSolution.is_correct == True
            )
        )
        solved = result.scalars().all()

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "points": user.points,
            "solved_count": user.solved_count,
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

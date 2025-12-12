from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from models import (
    engine, async_session, User, Problem, Category, UserSolution, Task,
    RegisterRequest, SolveProblemRequest, TaskRequest, init_db
)
import re
from datetime import datetime

# ===== FASTAPI APP =====
app = FastAPI(title="PlayEx API", version="1.0.0")

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== ЗАВИСИМОСТЬ БД =====
async def get_db():
    async with async_session() as session:
        yield session


# ===== HELPER ФУНКЦИИ =====
def _normalize_answer(answer: str) -> str:
    """Нормализует ответ для сравнения"""
    return answer.strip().lower().replace(' ', '')


def _answer_to_set(answer: str) -> set:
    """Преобразует ответ в множество (для множественных ответов)"""
    parts = re.split(r'[;,]', answer.strip())
    return {_normalize_answer(p) for p in parts if p.strip()}


# ===== STARTUP =====
@app.on_event("startup")
async def startup():
    """Инициализация БД при старте"""
    try:
        print("✅ Приложение запущено")
    except Exception as e:
        print(f"❌ Ошибка при запуске: {str(e)}")
        import traceback
        traceback.print_exc()


# ===== HEALTH CHECK =====
@app.get('/health')
async def health_check():
    """Проверка здоровья сервера"""
    return {"status": "ok", "message": "✅ API работает"}


# ===== РЕГИСТРАЦИЯ =====
@app.post('/api/users/register')
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Регистрация через TG или Email"""
    try:
        # Регистрация через Telegram
        if data.tg_id:
            if not data.name:
                raise HTTPException(status_code=400, detail='❌ Укажите имя')

            result = await db.execute(select(User).where(User.tg_id == data.tg_id))
            existing = result.scalars().first()

            if existing:
                return {
                    "id": existing.id,
                    "tg_id": existing.tg_id,
                    "name": existing.name,
                    "score": existing.score,
                    "message": "Вы уже зарегистрированы"
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
                "message": "✅ Успешно зарегистрированы через Telegram"
            }

        # Регистрация через Email
        elif data.email:
            if not data.email:
                raise HTTPException(status_code=400, detail='❌ Укажите email')
            if not data.password:
                raise HTTPException(status_code=400, detail='❌ Укажите пароль')
            if not data.name:
                raise HTTPException(status_code=400, detail='❌ Укажите имя')

            if len(data.password) < 6:
                raise HTTPException(status_code=400, detail='❌ Пароль должен быть минимум 6 символов')

            result = await db.execute(select(User).where(User.email == data.email))
            existing = result.scalars().first()

            if existing:
                return {
                    "id": existing.id,
                    "email": existing.email,
                    "name": existing.name,
                    "score": existing.score,
                    "message": "⚠️ Этот email уже зарегистрирован"
                }

            # ПРОСТО СОХРАНЯЕМ ПАРОЛЬ БЕЗ ХЕШИРОВАНИЯ
            user = User(email=data.email, name=data.name, password_hash=data.password)
            db.add(user)
            await db.commit()
            await db.refresh(user)

            return {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "score": user.score,
                "message": "✅ Успешно зарегистрированы через Email"
            }

        else:
            raise HTTPException(status_code=400, detail='❌ Укажите Telegram ID или Email')

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ Ошибка регистрации: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== ЛОГИН =====
@app.post('/api/login/')
async def login(data: dict, db: AsyncSession = Depends(get_db)):
    """Вход через Email"""
    try:
        email = data.get('email')
        password = data.get('password')

        if not email:
            raise HTTPException(status_code=400, detail='❌ Укажите email')
        if not password:
            raise HTTPException(status_code=400, detail='❌ Укажите пароль')

        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=401, detail='❌ Email не найден')

        # ПРОСТО СРАВНИВАЕМ БЕЗ ХЕШИРОВАНИЯ
        if user.password_hash != password:
            raise HTTPException(status_code=401, detail='❌ Неверный пароль')

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "score": user.score,
            "message": "✅ Вы успешно вошли"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка логина: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== ПОЛУЧИТЬ ПРОФИЛЬ =====
@app.get('/api/profile/tg/{tg_id}')
async def get_profile_tg(tg_id: int, db: AsyncSession = Depends(get_db)):
    """Получить профиль по TG ID"""
    try:
        result = await db.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "name": user.name,
            "score": user.score,
            "level": user.level,
            "solved_count": user.solved_count
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения профиля: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


@app.get('/api/profile/email/{email}')
async def get_profile_email(email: str, db: AsyncSession = Depends(get_db)):
    """Получить профиль по Email"""
    try:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "score": user.score,
            "level": user.level,
            "solved_count": user.solved_count
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения профиля: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== СТАТИСТИКА =====
@app.get('/api/stats/tg/{tg_id}')
async def get_stats_tg(tg_id: int, db: AsyncSession = Depends(get_db)):
    """Получить статистику по TG ID"""
    try:
        result = await db.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        return {
            "id": user.id,
            "score": user.score,
            "level": user.level,
            "solved_count": user.solved_count
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


@app.get('/api/stats/email/{email}')
async def get_stats_email(email: str, db: AsyncSession = Depends(get_db)):
    """Получить статистику по Email"""
    try:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        return {
            "id": user.id,
            "score": user.score,
            "level": user.level,
            "solved_count": user.solved_count
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== КАТЕГОРИИ =====
@app.get('/api/categories/')
async def get_categories(subject: str = None, db: AsyncSession = Depends(get_db)):
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
        raise HTTPException(status_code=500, detail=f'❌ Ошибка загрузки категорий: {str(e)}')


@app.post('/api/categories/')
async def create_category(data: dict, db: AsyncSession = Depends(get_db)):
    """Создать категорию"""
    try:
        if not data.get('name'):
            raise HTTPException(status_code=400, detail='❌ Укажите название категории')
        if not data.get('subject'):
            raise HTTPException(status_code=400, detail='❌ Укажите предмет (subject)')

        category = Category(
            name=data['name'],
            subject=data['subject'],
            description=data.get('description')
        )
        db.add(category)
        await db.commit()
        await db.refresh(category)

        return {
            "id": category.id,
            "name": category.name,
            "subject": category.subject,
            "message": "✅ Категория создана"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ Ошибка создания категории: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


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
        print(f"❌ Ошибка загрузки задач: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка загрузки задач: {str(e)}')


@app.get('/api/problems/random/')
async def get_random_problem(subject: str = None, category_id: int = None, db: AsyncSession = Depends(get_db)):
    """Получить случайную задачу"""
    try:
        query = select(Problem)
        conditions = []

        if subject:
            conditions.append(Problem.subject == subject)
        if category_id:
            conditions.append(Problem.category_id == category_id)

        if conditions:
            query = query.where(and_(*conditions))

        result = await db.execute(query)
        problems = result.scalars().all()

        if not problems:
            raise HTTPException(status_code=404, detail='❌ Задачи не найдены')

        import random
        problem = random.choice(problems)

        return {
            "id": problem.id,
            "title": problem.title,
            "description": problem.description,
            "subject": problem.subject,
            "difficulty": problem.difficulty,
            "category_id": problem.category_id,
            "points": problem.points
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка загрузки задачи: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


@app.post('/api/problems/')
async def create_problem(data: dict, db: AsyncSession = Depends(get_db)):
    """Создать задачу"""
    try:
        if not data.get('title'):
            raise HTTPException(status_code=400, detail='❌ Укажите название задачи')
        if not data.get('description'):
            raise HTTPException(status_code=400, detail='❌ Укажите описание')
        if not data.get('subject'):
            raise HTTPException(status_code=400, detail='❌ Укажите предмет (subject)')
        if not data.get('difficulty'):
            raise HTTPException(status_code=400, detail='❌ Укажите сложность (easy/medium/hard)')
        if not data.get('correct_answer'):
            raise HTTPException(status_code=400, detail='❌ Укажите правильный ответ')

        problem = Problem(
            title=data['title'],
            description=data['description'],
            subject=data['subject'],
            difficulty=data['difficulty'],
            category_id=data.get('category_id'),
            correct_answer=data['correct_answer'],
            points=data.get('points', 10)
        )
        db.add(problem)
        await db.commit()
        await db.refresh(problem)

        return {
            "id": problem.id,
            "title": problem.title,
            "message": "✅ Задача создана"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ Ошибка создания задачи: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== РЕШЕНИЕ ЗАДАЧ =====
@app.post('/api/solve/')
async def solve_problem(data: SolveProblemRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Проверить решение задачи"""
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
            raise HTTPException(status_code=404, detail='❌ Задача не найдена')

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
                "message": "✅ Правильно!" if is_correct else "❌ Неправильно"
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
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

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
                "message": "⚠️ Вы уже решили эту задачу ранее",
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
            "message": "✅ Правильно!" if is_correct else "❌ Неправильно"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR in solve_problem: {str(e)}")
        import traceback
        traceback.print_exc()
        await db.rollback()
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== ЗАДАЧИ  =====
@app.get('/api/tasks/tg/{tg_id}')
async def get_tasks_tg(tg_id: int, db: AsyncSession = Depends(get_db)):
    """Получить задачи пользователя по TG ID"""
    try:
        result = await db.execute(select(Task).where(Task.tg_id == tg_id))
        tasks = result.scalars().all()

        return [
            {
                "id": t.id,
                "title": t.title,
                "is_completed": t.is_completed,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in tasks
        ]
    except Exception as e:
        print(f"❌ Ошибка загрузки задач: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


@app.get('/api/tasks/email/{email}')
async def get_tasks_email(email: str, db: AsyncSession = Depends(get_db)):
    """Получить задачи пользователя по Email"""
    try:
        result = await db.execute(select(Task).where(Task.email == email))
        tasks = result.scalars().all()

        return [
            {
                "id": t.id,
                "title": t.title,
                "is_completed": t.is_completed,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in tasks
        ]
    except Exception as e:
        print(f"❌ Ошибка загрузки задач: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


@app.post('/api/tasks/tg/{tg_id}')
async def create_task_tg(tg_id: int, data: TaskRequest, db: AsyncSession = Depends(get_db)):
    """Создать задачу для пользователя (TG)"""
    try:
        if not data.title:
            raise HTTPException(status_code=400, detail='❌ Укажите название задачи')

        task = Task(tg_id=tg_id, title=data.title)
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


@app.post('/api/tasks/email/{email}')
async def create_task_email(email: str, data: TaskRequest, db: AsyncSession = Depends(get_db)):
    """Создать задачу для пользователя (Email)"""
    try:
        if not data.title:
            raise HTTPException(status_code=400, detail='❌ Укажите название задачи')

        task = Task(email=email, title=data.title)
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
    """Завершить задачу"""
    try:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalars().first()

        if not task:
            raise HTTPException(status_code=404, detail='❌ Задача не найдена')

        task.is_completed = True
        await db.commit()
        await db.refresh(task)

        return {
            "id": task.id,
            "is_completed": task.is_completed,
            "message": "✅ Задача завершена"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ Ошибка завершения задачи: {str(e)}")
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

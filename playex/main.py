from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from models import (
    engine, async_session, User, Problem, Category, UserSolution, Task, TimedAttempt,
    RegisterRequest, SolveProblemRequest, TaskRequest, init_db
)
import re
from datetime import datetime
import asyncio
import random

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
        max_retries = 5
        retry_count = 0
        while retry_count < max_retries:
            try:
                await init_db()
                print("✅ База данных инициализирована")
                print("✅ Приложение запущено")
                return
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    print(f"⚠️ Попытка подключения {retry_count}/{max_retries} не удалась, ждём 2 сек...")
                    await asyncio.sleep(2)
                else:
                    print(f"❌ Не удалось подключиться к БД после {max_retries} попыток")
                    raise
    except Exception as e:
        print(f"❌ Критическая ошибка при запуске: {str(e)}")
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
    """Регистрация через TG username или Email"""
    try:
        # Регистрация через Telegram username
        if data.tg_username:
            if not data.name:
                raise HTTPException(status_code=400, detail='❌ Укажите имя')

            # Проверяем, существует ли такой пользователь в Telegram
            # ВАЖНО: Здесь вы можете добавить проверку через Telegram Bot API
            # Сейчас просто сохраняем username

            result = await db.execute(select(User).where(User.tg_username == data.tg_username))
            existing = result.scalars().first()

            if existing:
                return {
                    "id": existing.id,
                    "tg_username": existing.tg_username,
                    "tg_id": existing.tg_id,
                    "name": existing.name,
                    "user_type": existing.user_type,
                    "message": "Вы уже зарегистрированы"
                }

            user = User(tg_username=data.tg_username, name=data.name, user_type='telegram')
            db.add(user)
            await db.commit()
            await db.refresh(user)

            return {
                "id": user.id,
                "tg_username": user.tg_username,
                "tg_id": user.tg_id,
                "name": user.name,
                "user_type": user.user_type,
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
                    "user_type": existing.user_type,
                    "message": "⚠️ Этот email уже зарегистрирован"
                }

            user = User(email=data.email, name=data.name, password_hash=data.password, user_type='email')
            db.add(user)
            await db.commit()
            await db.refresh(user)

            return {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "user_type": user.user_type,
                "message": "✅ Успешно зарегистрированы через Email"
            }

        else:
            raise HTTPException(status_code=400, detail='❌ Укажите Telegram username или Email')

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

        if user.password_hash != password:
            raise HTTPException(status_code=401, detail='❌ Неверный пароль')

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "user_type": user.user_type,
            "message": "✅ Вы успешно вошли"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка логина: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== ПОЛУЧИТЬ ПРОФИЛЬ =====
@app.get('/api/profile/tg/{identifier}')
async def get_profile_tg(identifier: str, db: AsyncSession = Depends(get_db)):
    """Получить профиль по TG ID или username"""
    try:
        # Пробуем как ID
        try:
            tg_id = int(identifier)
            result = await db.execute(select(User).where(User.tg_id == tg_id))
            user = result.scalars().first()
        except ValueError:
            # Иначе ищем по username
            result = await db.execute(select(User).where(User.tg_username == identifier))
            user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "tg_username": user.tg_username,
            "name": user.name,
            "level": user.level,
            "user_type": user.user_type
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
            "level": user.level,
            "user_type": user.user_type
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения профиля: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== ОБНОВИТЬ ИМЯ ПОЛЬЗОВАТЕЛЯ =====
@app.put('/api/profile/update')
async def update_profile(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    """Обновить имя пользователя"""
    try:
        tg_id = request.headers.get('X-TG-ID')
        email = request.headers.get('X-EMAIL')
        new_name = data.get('name')

        if not new_name:
            raise HTTPException(status_code=400, detail='❌ Укажите новое имя')

        user = None
        if tg_id:
            result = await db.execute(select(User).where(User.tg_id == int(tg_id)))
            user = result.scalars().first()
        elif email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        user.name = new_name
        await db.commit()
        await db.refresh(user)

        return {
            "id": user.id,
            "name": user.name,
            "message": "✅ Имя обновлено"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== СТАТИСТИКА =====
@app.get('/api/stats/tg/{identifier}')
async def get_stats_tg(identifier: str, db: AsyncSession = Depends(get_db)):
    """Получить статистику по TG ID или username"""
    try:
        user = None
        try:
            tg_id = int(identifier)
            result = await db.execute(select(User).where(User.tg_id == tg_id))
            user = result.scalars().first()
        except ValueError:
            result = await db.execute(select(User).where(User.tg_username == identifier))
            user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        # Подсчитываем решенные задачи
        from sqlalchemy import func

        total_solved = await db.scalar(
            select(func.count(UserSolution.id))
            .where(
                and_(
                    UserSolution.user_id == user.id,
                    UserSolution.is_correct == True
                )
            )
        ) or 0

        math_solved = await db.scalar(
            select(func.count(UserSolution.id))
            .join(Problem, Problem.id == UserSolution.problem_id)
            .where(
                and_(
                    UserSolution.user_id == user.id,
                    UserSolution.is_correct == True,
                    Problem.subject == "math"
                )
            )
        ) or 0

        informatics_solved = await db.scalar(
            select(func.count(UserSolution.id))
            .join(Problem, Problem.id == UserSolution.problem_id)
            .where(
                and_(
                    UserSolution.user_id == user.id,
                    UserSolution.is_correct == True,
                    Problem.subject == "informatics"
                )
            )
        ) or 0

        return {
            "id": user.id,
            "level": user.level,
            "solved_count": int(total_solved),
            "math_solved": int(math_solved),
            "informatics_solved": int(informatics_solved),
            "solved_problems": []
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

        from sqlalchemy import func

        total_solved = await db.scalar(
            select(func.count(UserSolution.id))
            .where(
                and_(
                    UserSolution.user_id == user.id,
                    UserSolution.is_correct == True
                )
            )
        ) or 0

        math_solved = await db.scalar(
            select(func.count(UserSolution.id))
            .join(Problem, Problem.id == UserSolution.problem_id)
            .where(
                and_(
                    UserSolution.user_id == user.id,
                    UserSolution.is_correct == True,
                    Problem.subject == "math"
                )
            )
        ) or 0

        informatics_solved = await db.scalar(
            select(func.count(UserSolution.id))
            .join(Problem, Problem.id == UserSolution.problem_id)
            .where(
                and_(
                    UserSolution.user_id == user.id,
                    UserSolution.is_correct == True,
                    Problem.subject == "informatics"
                )
            )
        ) or 0

        return {
            "id": user.id,
            "level": user.level,
            "solved_count": int(total_solved),
            "math_solved": int(math_solved),
            "informatics_solved": int(informatics_solved),
            "solved_problems": []
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
            raise HTTPException(status_code=400, detail='❌ Укажите предмет (math или informatics)')

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
                "category_id": p.category_id
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

        problem = random.choice(problems)

        return {
            "id": problem.id,
            "title": problem.title,
            "description": problem.description,
            "subject": problem.subject,
            "difficulty": problem.difficulty,
            "category_id": problem.category_id
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
            raise HTTPException(status_code=400, detail='❌ Укажите предмет (math или informatics)')
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
            correct_answer=data['correct_answer']
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

        # Проверяем задачу
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
                "new_score": user.level
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
            is_correct=is_correct
        )

        db.add(solution)

        # Если правильно - увеличиваем уровень
        if is_correct:
            user.level = (user.level or 0) + 1

        await db.commit()
        await db.refresh(user)

        return {
            "correct": is_correct,
            "already_solved": False,
            "correct_answer": None if is_correct else problem.correct_answer,
            "points_earned": 0,
            "new_score": user.level,
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


# ===== ТРЕНИРОВКА НА ВРЕМЯ =====
@app.post('/api/timed-attempt/')
async def save_timed_attempt(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    """Сохранить попытку решения задачи на время"""
    try:
        tg_id = request.headers.get('X-TG-ID')
        email = request.headers.get('X-EMAIL')

        if not tg_id and not email:
            raise HTTPException(status_code=401, detail='❌ Требуется авторизация')

        user = None
        if tg_id:
            result = await db.execute(select(User).where(User.tg_id == int(tg_id)))
            user = result.scalars().first()
        elif email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        attempt = TimedAttempt(
            user_id=user.id,
            problem_id=data.get('problem_id'),
            subject=data.get('subject'),
            user_answer=data.get('user_answer'),
            is_correct=data.get('is_correct', False),
            time_spent_seconds=data.get('time_spent_seconds', 0)
        )

        db.add(attempt)
        await db.commit()

        return {"message": "✅ Попытка сохранена"}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== СТАТИСТИКА ПО ВРЕМЕНИ =====
@app.get('/api/timed-stats/')
async def get_timed_stats(subject: str = None, request: Request = None, db: AsyncSession = Depends(get_db)):
    """Получить статистику тренировок на время"""
    try:
        tg_id = request.headers.get('X-TG-ID') if request else None
        email = request.headers.get('X-EMAIL') if request else None

        if not tg_id and not email:
            raise HTTPException(status_code=401, detail='❌ Требуется авторизация')

        user = None
        if tg_id:
            result = await db.execute(select(User).where(User.tg_id == int(tg_id)))
            user = result.scalars().first()
        elif email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        query = select(TimedAttempt).where(TimedAttempt.user_id == user.id)

        if subject:
            query = query.where(TimedAttempt.subject == subject)

        result = await db.execute(query)
        attempts = result.scalars().all()

        if not attempts:
            return {
                "total_attempts": 0,
                "correct_answers": 0,
                "incorrect_answers": 0,
                "avg_problems_per_minute": 0,
                "total_time_seconds": 0,
                "success_rate": 0
            }

        correct = sum(1 for a in attempts if a.is_correct)
        incorrect = len(attempts) - correct
        total_time = sum(a.time_spent_seconds for a in attempts)

        avg_per_minute = (len(attempts) / (total_time / 60)) if total_time > 0 else 0
        success_rate = (correct / len(attempts) * 100) if attempts else 0

        return {
            "total_attempts": len(attempts),
            "correct_answers": correct,
            "incorrect_answers": incorrect,
            "avg_problems_per_minute": round(avg_per_minute, 2),
            "total_time_seconds": total_time,
            "success_rate": round(success_rate, 2)
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


# ===== ЗАДАЧИ ПОЛЬЗОВАТЕЛЯ =====
@app.get('/api/tasks/')
async def get_tasks(request: Request, db: AsyncSession = Depends(get_db)):
    """Получить задачи пользователя"""
    try:
        tg_id = request.headers.get('X-TG-ID')
        email = request.headers.get('X-EMAIL')

        user = None
        if tg_id:
            result = await db.execute(select(User).where(User.tg_id == int(tg_id)))
            user = result.scalars().first()
        elif email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail='❌ Пользователь не найден')

        result = await db.execute(select(Task).where(Task.user_id == user.id))
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

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка загрузки задач: {str(e)}")
        raise HTTPException(status_code=500, detail=f'❌ Ошибка: {str(e)}')


@app.post('/api/tasks/')
async def create_task(data: TaskRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Создать задачу для пользователя"""
    try:
        tg_id = request.headers.get('X-TG-ID')
        email = request.headers.get('X-EMAIL')

        if not data.title:
            raise HTTPException(status_code=400, detail='❌ Укажите название задачи')

        user = None
        if tg_id:
            result = await db.execute(select(User).where(User.tg_id == int(tg_id)))
            user = result.scalars().first()
        elif email:
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

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from datetime import datetime
import uvicorn

# ===== DATABASE =====
DATABASE_URL = "postgresql://user:password@playex_postgres:5432/playex_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ===== FASTAPI =====
app = FastAPI()

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== DATABASE MODELS =====
class Problem(Base):
    __tablename__ = 'problems'
    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(String)
    correct_answer = Column(String)
    points = Column(Integer, default=1)
    difficulty = Column(String)
    subject = Column(String)
    category_id = Column(Integer)


class User(Base):
    __tablename__ = 'users'
    tg_id = Column(Integer, primary_key=True)
    name = Column(String)
    points = Column(Integer, default=0)
    solved_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserSolution(Base):
    __tablename__ = 'user_solutions'
    id = Column(Integer, primary_key=True)
    tg_id = Column(Integer, ForeignKey('users.tg_id'), nullable=True)
    problem_id = Column(Integer, ForeignKey('problems.id'))
    user_answer = Column(String)
    is_correct = Column(Boolean, default=False)
    solved_at = Column(DateTime, default=datetime.utcnow)


class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    subject = Column(String)


class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    tg_id = Column(Integer, ForeignKey('users.tg_id'))
    title = Column(String)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===== PYDANTIC MODELS =====
class SolveProblemRequest(BaseModel):
    tg_id: Optional[int] = None
    problem_id: int
    user_answer: str


class SolveProblemResponse(BaseModel):
    correct: bool
    correct_answer: Optional[str] = None
    points_earned: Optional[int] = None
    message: str
    already_solved: Optional[bool] = False


class RegisterRequest(BaseModel):
    tg_id: int
    name: str
    email: Optional[str] = None
    password: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    tg_id: int
    name: str
    points: int
    solved_count: int


class ProblemResponse(BaseModel):
    id: int
    title: str
    description: str
    points: int
    difficulty: str
    subject: str
    category_id: int


class CategoryResponse(BaseModel):
    id: int
    name: str
    description: str
    subject: str


class StatsResponse(BaseModel):
    tg_id: int
    name: str
    points: int
    solved_count: int
    solved_problems: List[int]


class TaskRequest(BaseModel):
    title: str


class TaskResponse(BaseModel):
    id: int
    title: str
    is_completed: bool


# ===== ROUTES =====

# ===== HEALTH CHECK =====
@app.get('/api/health')
async def health_check():
    return {"status": "ok"}


# ===== USERS =====
@app.post('/api/users/register')
async def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Регистрация нового пользователя"""
    try:
        # Проверяем, существует ли уже
        existing = db.query(User).filter(User.tg_id == data.tg_id).first()
        if existing:
            print(f'⚠️ Пользователь {data.tg_id} уже существует')
            return {
                "tg_id": existing.tg_id,
                "name": existing.name,
                "points": existing.points,
                "message": "Пользователь уже зарегистрирован"
            }

        # Создаём нового пользователя
        user = User(tg_id=data.tg_id, name=data.name)
        db.add(user)
        db.commit()
        db.refresh(user)

        print(f'✅ Пользователь {data.tg_id} зарегистрирован')
        return {
            "tg_id": user.tg_id,
            "name": user.name,
            "points": user.points,
            "message": "Успешно зарегистрирован"
        }
    except Exception as e:
        db.rollback()
        print(f'❌ Ошибка регистрации: {e}')
        raise HTTPException(status_code=500, detail=f'Ошибка: {str(e)}')


@app.get('/api/users/{tg_id}')
async def get_user(tg_id: int, db: Session = Depends(get_db)):
    """Получить пользователя по tg_id"""
    try:
        user = db.query(User).filter(User.tg_id == tg_id).first()
        if not user:
            raise HTTPException(status_code=404, detail='Пользователь не найден')

        return {
            "tg_id": user.tg_id,
            "name": user.name,
            "points": user.points,
            "solved_count": user.solved_count
        }
    except Exception as e:
        print(f'❌ Ошибка получения пользователя: {e}')
        raise HTTPException(status_code=500, detail=f'Ошибка: {str(e)}')


@app.get('/api/profile/{tg_id}')
async def get_profile(tg_id: int, db: Session = Depends(get_db)):
    """Получить профиль пользователя"""
    try:
        user = db.query(User).filter(User.tg_id == tg_id).first()
        if not user:
            raise HTTPException(status_code=404, detail='Пользователь не найден')

        return {
            "tg_id": user.tg_id,
            "name": user.name,
            "points": user.points,
            "solved_count": user.solved_count,
            "created_at": user.created_at
        }
    except Exception as e:
        print(f'❌ Ошибка получения профиля: {e}')
        raise HTTPException(status_code=500, detail=f'Ошибка: {str(e)}')


@app.post('/api/login/')
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Вход по email и пароль"""
    try:
        # Здесь добавьте логику проверки email/пароля
        # Это заглушка - адаптируйте под вашу систему
        print(f'🔐 Попытка входа: {data.email}')
        raise HTTPException(status_code=401, detail='Некорректные данные')
    except Exception as e:
        print(f'❌ Ошибка входа: {e}')
        raise HTTPException(status_code=500, detail=f'Ошибка: {str(e)}')


# ===== CATEGORIES =====
@app.get('/api/categories/')
async def get_categories(subject: Optional[str] = None, db: Session = Depends(get_db)):
    """Получить категории"""
    try:
        query = db.query(Category)
        if subject:
            query = query.filter(Category.subject == subject)

        categories = query.all()
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
        print(f'❌ Ошибка получения категорий: {e}')
        raise HTTPException(status_code=500, detail=f'Ошибка: {str(e)}')


# ===== PROBLEMS =====
@app.get('/api/problems/')
async def get_problems(
        subject: Optional[str] = None,
        difficulty: Optional[str] = None,
        category_id: Optional[int] = None,
        db: Session = Depends(get_db)
):
    """Получить задачи"""
    try:
        query = db.query(Problem)

        if subject:
            query = query.filter(Problem.subject == subject)
        if difficulty:
            query = query.filter(Problem.difficulty == difficulty)
        if category_id:
            query = query.filter(Problem.category_id == category_id)

        problems = query.all()
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
        print(f'❌ Ошибка получения задач: {e}')
        raise HTTPException(status_code=500, detail=f'Ошибка: {str(e)}')


@app.get('/api/problems/random/')
async def get_random_problem(
        subject: str,
        category_id: Optional[int] = None,
        db: Session = Depends(get_db)
):
    """Получить случайную задачу"""
    try:
        query = db.query(Problem).filter(Problem.subject == subject)
        if category_id:
            query = query.filter(Problem.category_id == category_id)

        from sqlalchemy import func
        problem = query.order_by(func.random()).first()

        if not problem:
            raise HTTPException(status_code=404, detail='Задач не найдено')

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
        print(f'❌ Ошибка получения случайной задачи: {e}')
        raise HTTPException(status_code=500, detail=f'Ошибка: {str(e)}')


# ===== SOLVE PROBLEM =====
@app.post('/api/solve/')
async def solve_problem(data: SolveProblemRequest, db: Session = Depends(get_db)):
    """
    Решить задачу
    - Если tg_id = None, то гость (не сохраняем прогресс, только проверяем)
    - Если tg_id = число, то авторизованный пользователь (сохраняем прогресс)
    """
    problem_id = data.problem_id
    user_answer = data.user_answer.strip()
    tg_id = data.tg_id

    print(f'🔍 Попытка решить задачу: tg_id={tg_id}, problem_id={problem_id}, answer={user_answer}')

    # Получаем задачу
    try:
        problem = db.query(Problem).filter(Problem.id == problem_id).first()
    except Exception as e:
        print(f'❌ Ошибка БД при получении задачи: {e}')
        raise HTTPException(status_code=500, detail=f'Ошибка БД: {str(e)}')

    if not problem:
        print(f'❌ Задача {problem_id} не найдена')
        raise HTTPException(status_code=404, detail='Задача не найдена')

    # Проверяем ответ (case-insensitive)
    correct = user_answer.lower() == problem.correct_answer.lower()
    print(f'📝 Проверка ответа: "{user_answer}" vs "{problem.correct_answer}" = {correct}')

    # Если авторизованный пользователь - сохраняем прогресс
    if tg_id is not None:
        try:
            # Проверяем, не решал ли уже
            existing = db.query(UserSolution).filter(
                UserSolution.tg_id == tg_id,
                UserSolution.problem_id == problem_id,
                UserSolution.is_correct == True
            ).first()

            if existing:
                print(f'⚠️ Пользователь {tg_id} уже решал задачу {problem_id}')
                return SolveProblemResponse(
                    correct=False,
                    already_solved=True,
                    message='Вы уже решили эту задачу'
                )

            # Если правильно - сохраняем решение
            if correct:
                print(f'✅ Правильный ответ! Сохраняем для пользователя {tg_id}')

                solution = UserSolution(
                    tg_id=tg_id,
                    problem_id=problem_id,
                    user_answer=user_answer,
                    is_correct=True
                )
                db.add(solution)

                # Обновляем статистику пользователя
                user = db.query(User).filter(User.tg_id == tg_id).first()
                if user:
                    user.points += problem.points
                    user.solved_count += 1
                    print(f'📊 Обновлена статистика пользователя {tg_id}: +{problem.points} очков')

                db.commit()

                return SolveProblemResponse(
                    correct=True,
                    points_earned=problem.points,
                    message='Правильно!'
                )
            else:
                print(f'❌ Неправильный ответ для пользователя {tg_id}')
                return SolveProblemResponse(
                    correct=False,
                    correct_answer=problem.correct_answer,
                    message='Неправильно'
                )
        except Exception as e:
            db.rollback()
            print(f'❌ Ошибка при сохранении: {e}')
            raise HTTPException(status_code=500, detail=f'Ошибка: {str(e)}')
    else:
        # Гость - просто проверяем ответ без сохранения
        print(f'👤 Гость проверяет ответ (не сохраняем)')
        return SolveProblemResponse(
            correct=correct,
            correct_answer=problem.correct_answer if not correct else '',
            message='Правильно!' if correct else 'Неправильно'
        )


# ===== STATS =====
@app.get('/api/stats/{tg_id}')
async def get_stats(tg_id: int, db: Session = Depends(get_db)):
    """Получить статистику пользователя"""
    try:
        user = db.query(User).filter(User.tg_id == tg_id).first()
        if not user:
            raise HTTPException(status_code=404, detail='Пользователь не найден')

        # Получаем решённые задачи
        solved = db.query(UserSolution).filter(
            UserSolution.tg_id == tg_id,
            UserSolution.is_correct == True
        ).all()

        solved_problems = [s.problem_id for s in solved]

        return {
            "tg_id": user.tg_id,
            "name": user.name,
            "points": user.points,
            "solved_count": user.solved_count,
            "solved_problems": solved_problems
        }
    except Exception as e:
        print(f'❌ Ошибка получения статистики: {e}')
        raise HTTPException(status_code=500, detail=f'Ошибка: {str(e)}')


# ===== TASKS =====
@app.get('/api/tasks/{tg_id}')
async def get_tasks(tg_id: int, db: Session = Depends(get_db)):
    """Получить задачи пользователя"""
    try:
        tasks = db.query(Task).filter(Task.tg_id == tg_id).all()
        return [
            {
                "id": t.id,
                "title": t.title,
                "is_completed": t.is_completed
            }
            for t in tasks
        ]
    except Exception as e:
        print(f'❌ Ошибка получения задач: {e}')
        raise HTTPException(status_code=500, detail=f'Ошибка: {str(e)}')


@app.post('/api/tasks')
async def create_task(data: TaskRequest, tg_id: int, db: Session = Depends(get_db)):
    """Создать задачу"""
    try:
        task = Task(tg_id=tg_id, title=data.title)
        db.add(task)
        db.commit()
        db.refresh(task)

        return {
            "id": task.id,
            "title": task.title,
            "is_completed": task.is_completed
        }
    except Exception as e:
        db.rollback()
        print(f'❌ Ошибка создания задачи: {e}')
        raise HTTPException(status_code=500, detail=f'Ошибка: {str(e)}')


@app.patch('/api/tasks/{task_id}/complete')
async def complete_task(task_id: int, db: Session = Depends(get_db)):
    """Завершить задачу"""
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail='Задача не найдена')

        task.is_completed = True
        db.commit()

        return {
            "id": task.id,
            "title": task.title,
            "is_completed": task.is_completed
        }
    except Exception as e:
        db.rollback()
        print(f'❌ Ошибка завершения задачи: {e}')
        raise HTTPException(status_code=500, detail=f'Ошибка: {str(e)}')


@app.delete('/api/tasks/{task_id}')
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    """Удалить задачу"""
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail='Задача не найдена')

        db.delete(task)
        db.commit()

        return {"message": "Задача удалена"}
    except Exception as e:
        db.rollback()
        print(f'❌ Ошибка удаления задачи: {e}')
        raise HTTPException(status_code=500, detail=f'Ошибка: {str(e)}')


# ===== MAIN =====
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

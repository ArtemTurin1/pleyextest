from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from datetime import datetime

app = FastAPI()

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== MODELS =====
Base = declarative_base()


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
    tg_id = Column(Integer, ForeignKey('users.tg_id'))
    problem_id = Column(Integer, ForeignKey('problems.id'))
    user_answer = Column(String)
    is_correct = Column(Boolean, default=False)
    solved_at = Column(DateTime, default=datetime.utcnow)


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


# ===== ROUTES =====
@app.post('/api/solve/', response_model=SolveProblemResponse)
async def solve_problem(data: SolveProblemRequest, db: Session = None):
    """
    Решить задачу
    - Если tg_id = None, то гость (не сохраняем прогресс)
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

from contextlib import asynccontextmanager
from pydantic import BaseModel
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import services
from models import init_db


# ==================== REQUEST MODELS ====================

class SolutionRequest(BaseModel):
    tg_id: int
    problem_id: int
    user_answer: str


class RegisterRequest(BaseModel):
    tg_id: int | None = None
    name: str | None = None
    email: str | None = None
    password: str | None = None


class TaskCreateRequest(BaseModel):
    tg_id: int
    title: str


# ==================== LIFESPAN ====================

@asynccontextmanager
async def lifespan(app_: FastAPI):
    await init_db()
    print('Bot is ready / DB initialized')
    yield


app = FastAPI(title="Math & Informatics App", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== USERS / REGISTRATION ====================

@app.post("/api/users/register")
async def register_user(payload: RegisterRequest):
    if payload.tg_id:
        user = await services.add_user(tg_id=payload.tg_id, name=payload.name)
        return {'id': user.id, 'tg_id': user.tg_id, 'name': user.name}

    if payload.email and payload.password:
        user = await services.register_user_via_email(payload.email, payload.password, payload.name)
        if not user:
            raise HTTPException(status_code=400, detail="email already exists")
        return {'id': user.id, 'email': user.email, 'name': user.name}

    raise HTTPException(status_code=400, detail="invalid payload")


@app.get("/api/users/{tg_id}")
async def get_user_by_tg(tg_id: int):
    user = await services.get_user_by_tg(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return {
        'id': user.id,
        'tg_id': user.tg_id,
        'name': user.name,
        'score': user.score,
        'level': user.level
    }


# ==================== CATEGORIES (НОВОЕ!) ====================

@app.get("/api/categories/")
async def get_categories(subject: str = Query(None, description="Subject filter")):
    """
    Получает категории по предмету.

    Примеры:
    - GET /api/categories/?subject=math → категории математики
    - GET /api/categories/?subject=informatics → категории информатики
    - GET /api/categories/ → все категории
    """
    return await services.get_categories(subject)


# ==================== PROBLEMS ====================

@app.get("/api/problems/")
async def get_problems(
        subject: str = Query(None, description="Subject filter"),
        difficulty: str = Query(None, description="Difficulty filter"),
        category_id: int = Query(None, description="Category ID filter")
):
    """
    Получает задачи с фильтрацией.

    Примеры:
    - GET /api/problems/?subject=math&category_id=1
    - GET /api/problems/?subject=informatics&difficulty=hard
    """
    return await services.get_problems(subject, difficulty, category_id)


@app.get("/api/problems/random/")
async def get_random_problem(
        subject: str = Query(..., description="Subject"),
        category_id: int = Query(..., description="Category ID")
):
    """
    Получает случайную задачу из предмета и категории.

    Примеры:
    - GET /api/problems/random/?subject=math&category_id=1
    """
    problem = await services.get_random_problem(subject, category_id)
    if not problem:
        raise HTTPException(status_code=404, detail="no problems found")
    return problem


# ==================== SOLVE ====================

@app.post("/api/solve/")
async def solve_problem(solution: SolutionRequest):
    user = await services.add_user(tg_id=solution.tg_id)
    result = await services.check_solution(user.id, solution.problem_id, solution.user_answer)
    return result


# ==================== STATS / PROFILE ====================

@app.get("/api/stats/{tg_id}")
async def get_stats(tg_id: int):
    user = await services.get_user_by_tg(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    stats = await services.get_user_stats(user.id)
    return stats


@app.get("/api/profile/{tg_id}")
async def profile(tg_id: int):
    user = await services.get_user_by_tg(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    stats = await services.get_user_stats(user.id)
    return {
        'id': user.id,
        'tg_id': user.tg_id,
        'name': user.name,
        'score': user.score,
        'level': user.level,
        'stats': stats
    }


@app.get("/api/stats/{tg_id}/weekly")
async def get_weekly_stats(tg_id: int):
    user = await services.get_user_by_tg(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    stats = await services.get_weekly_stats(user.id)
    return stats

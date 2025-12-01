from contextlib import asynccontextmanager
from pydantic import BaseModel
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import services
from models import init_db

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

class TaskCompleteRequest(BaseModel):
    id: int

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

# --- Users / Registration ---

@app.post("/api/users/register")
async def register_user(payload: RegisterRequest):
    # Если пришёл tg_id — создаём/возвращаем пользователя по tg
    if payload.tg_id:
        user = await services.add_user(tg_id=payload.tg_id, name=payload.name)
        return {'id': user.id, 'tg_id': user.tg_id, 'name': user.name}
    # Классическая регистрация
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

# --- Problems / Solve ---

@app.get("/api/problems/")
async def get_problems(subject: str = Query(None, description="Subject filter"), difficulty: str = Query(None, description="Difficulty filter")):
    return await services.get_problems(subject, difficulty)

@app.post("/api/solve/")
async def solve_problem(solution: SolutionRequest):
    # ensure user exists
    user = await services.add_user(tg_id=solution.tg_id)
    result = await services.check_solution(user.id, solution.problem_id, solution.user_answer)
    return result

# --- Stats / Profile ---

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

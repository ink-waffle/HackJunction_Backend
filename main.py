from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import uuid
from database_service import DatabaseService
import asyncio
from telegram_bot import TelegramBot
from keys import *
import json
from openai import OpenAI
import os
from pydantic import BaseModel
from keys import OPENAI_KEY
from models import *


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    difficulty: Optional[int] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None

class TaskResponse(TaskBase):
    id: str
    completed: bool

    class Config:
        from_attributes = True

db = DatabaseService("sqlite+aiosqlite:///./todo.db")

# Initialize bot with your token
bot = TelegramBot(TG_KEY, db)

@app.on_event("startup")
async def startup():
    await db.create_database_tables()
    asyncio.create_task(bot.start())

@app.get("/getTasks")
async def get_tasks(user_id: str):
    tasks = await db.get_user_tasks(user_id)
    if tasks is None:
        return []
    return tasks

@app.get("/getTask")
async def get_task(task_id: str, user_id: str):
    task = await db.get_user_task(task_id, user_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/createTask")
async def create_task(task: TaskCreate, user_id: str):
    try:
        task_id = str(uuid.uuid4())
        new_task = await db.create_task(
            user_id=user_id,
            task_id=task_id,
            title=task.title,
            difficulty=task.difficulty,
            description=task.description,
            start_datetime=task.start_datetime,
            end_datetime=task.end_datetime
        )
        return new_task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/updateTask")
async def update_task(task_id: str, task: TaskUpdate, user_id: str):
    updates = task.dict(exclude_unset=True)
    updated_task = await db.update_task(task_id, user_id, updates)
    if updated_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated_task

@app.post("/deleteTask")
async def delete_task(task_id: str, user_id: str):
    success = await db.delete_task(task_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}

@app.post("/shareTask")
async def share_task(task_id: str, shared_user_id: str):
    try:
        await db.share_task(shared_user_id, task_id)
        return {"message": "Task shared successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/createUser")
async def create_user(user_id: str):
    try:
        user = await db.create_user(user_id)
        return {"message": "User created successfully", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class GeneratedTask(BaseModel):
    title: str
    description: str
    estimated_hours: float

class BreakDown(BaseModel):
    tasks: list[GeneratedTask]


class GenerateTasksRequest(BaseModel):
    prompt: str
    user_id: str

@app.post("/generateTasks")
async def generate_tasks(request: GenerateTasksRequest):
    """Generate and create project tasks from a prompt"""
    try:
        tasks: BreakDown = await generate_project_tasks(request.prompt)
        
        # Create all tasks for user
        created_tasks = []
        current_time = datetime.utcnow()
        
        for task in tasks.tasks:
            task_id = str(uuid.uuid4())
            db_task = await db.create_task(
                user_id=request.user_id,
                task_id=task_id,
                title=task.title,
                description=task.description,
                start_datetime=current_time,
                end_datetime=current_time + timedelta(hours=task.estimated_hours)
            )
            created_tasks.append(db_task)
            current_time = current_time + timedelta(hours=task.estimated_hours)
            
        return created_tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def generate_project_tasks(prompt: str):
    """Generate project tasks using OpenAI"""
    client = OpenAI(api_key=OPENAI_KEY)
    response = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": """Break down the project into specific, actionable tasks. 
             For each task include a clear title, detailed description, and realistic time estimate.
             Tasks should be sequential and cover the complete project lifecycle."""},
            {"role": "user", "content": f"Create a task list for this project: {prompt}"}
        ],
        response_format=BreakDown,
    )

    return json.loads(
        response.choices[0].message.parsed
    )["tasks"]


class BulkTaskCreate(BaseModel):
    tasks: List[TaskCreate]
    user_id: str

@app.post("/bulkCreateTasks")
async def bulk_create_tasks(task_create: BulkTaskCreate):
    """Create multiple tasks at once with automatic scheduling"""
    try:
        resp = []
        for task in task_create.tasks:
            task_id = str(uuid.uuid4())
            new_task = await db.create_task(
                user_id=task_create.user_id,
                task_id=task_id,
                title=task.title,
                difficulty=task.difficulty,
                description=task.description,
                start_datetime=task.start_datetime,
                end_datetime=task.end_datetime
            )
            resp.append(new_task)
        return resp
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
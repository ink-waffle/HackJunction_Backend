from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import Column, BigInteger, Integer, String, Boolean, ForeignKey, DateTime, Table, JSON
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List

class Base(AsyncAttrs, DeclarativeBase):
    pass

# Association table
user_task = Table(
    'user_task',
    Base.metadata,
    Column('user_id', String, ForeignKey('users.id')),
    Column('task_id', String, ForeignKey('tasks.id'))
)

# SQLAlchemy Models
class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True)  # Added telegram_id
    tasks = relationship("TaskModel", secondary=user_task, back_populates="owners")

class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    difficulty = Column(Integer, nullable=True)
    completed = Column(Boolean, default=False)
    start_datetime = Column(DateTime, nullable=True)
    end_datetime = Column(DateTime, nullable=True)
    notifications_sent = Column(JSON, default=dict)  # Track notifications: {"60": true, "30": true, "10": false}
    owners = relationship("UserModel", secondary=user_task, back_populates="tasks")
    
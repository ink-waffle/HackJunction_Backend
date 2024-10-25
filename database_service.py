from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import sessionmaker, selectinload, joinedload
from sqlalchemy import select, and_, Result
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from models import *
from sqlalchemy.sql.expression import func

class DatabaseService:
    def __init__(self, db_url: str):
        self.engine: AsyncEngine = create_async_engine(db_url)
        self.AsyncSessionLocal: AsyncSession = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def create_database_tables(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self):
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except:
                await session.rollback()
                raise

    async def get_user(self, user_id: str) -> UserModel:
        async with self.session() as session:
            result = await session.execute(select(UserModel).filter(UserModel.id == user_id))
            return result.scalar_one_or_none()
    
    async def get_user_by_tgid(self, user_id: str) -> UserModel:
        async with self.session() as session:
            result = await session.execute(select(UserModel).filter(UserModel.telegram_id == user_id))
            return result.scalar_one_or_none()

    async def create_user(self, id: str) -> UserModel:
        async with self.session() as session:
            user_result: Result = await session.execute(
                select(UserModel).filter(UserModel.id == id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                user = UserModel(id=id)
                session.add(user)
                await session.commit()
                await session.refresh(user)
            
            return user

    async def get_user_tasks(self, user_id: str):
        async with self.session() as session:
            result: Result = await session.execute(
                select(TaskModel)
                .filter(TaskModel.owners.any(UserModel.id == user_id))
                .order_by(TaskModel.end_datetime, TaskModel.start_datetime)
            )
            return result.scalars().all()

    async def update_user_telegram_id(self, user_id: str, telegram_id: int):
        async with self.session() as session:
            user = await session.execute(
                select(UserModel).filter(UserModel.id == user_id)
            )
            user = user.scalar_one_or_none()
            if user:
                user.telegram_id = telegram_id
                await session.commit()
                return user
            raise ValueError("User not found")

    async def get_task(self, id: str) -> TaskModel:
        async with self.session() as session:
            result = await session.execute(select(TaskModel).filter(TaskModel.id == id))
            return result.scalar_one_or_none()

    async def get_user_task(self, task_id: str, user_id: str) -> TaskModel:
        async with self.session() as session:
            result = await session.execute(
                select(TaskModel).filter(and_(
                    TaskModel.id == task_id,
                    TaskModel.owners.any(UserModel.id == user_id)
                ))
            )
            return result.scalar_one_or_none()

    # async def create_task(self, user_id: str, task_id: str, title: str, description: Optional[str] = None, 
    #                      start_datetime: Optional[datetime] = None, end_datetime: Optional[datetime] = None) -> TaskModel:
    #     async with self.session() as session:
    #         # Get the user with tasks preloaded
    #         user_result = await session.execute(
    #             select(UserModel)
    #             .options(joinedload(UserModel.tasks))
    #             .filter(UserModel.id == user_id)
    #         )
    #         user = user_result.unique().scalar_one_or_none()
            
    #         if not user:
    #             raise ValueError("User not found")
            
    #         task = TaskModel(
    #             id=task_id,
    #             title=title,
    #             description=description,
    #             start_datetime=start_datetime,
    #             end_datetime=end_datetime
    #         )
    #         user.tasks.append(task)
    #         session.add(task)
            
    #         await session.commit()
    #         await session.refresh(task)
    #         return task

    async def share_task(self, user_id: str, task_id: str):
        async with self.session() as session:
            # Get the user with tasks preloaded
            user_result = await session.execute(
                select(UserModel)
                .options(joinedload(UserModel.tasks))
                .filter(UserModel.id == user_id)
            )
            user = user_result.unique().scalar_one_or_none()
            
            if not user:
                raise ValueError("User not found")
            
            # Check if the task exists
            task_result = await session.execute(
                select(TaskModel).filter(TaskModel.id == task_id)
            )
            task = task_result.scalar_one_or_none()
            
            if task is None:
                raise ValueError("Task not found")
            
            # Add the task to the user if it's not already associated
            if task not in user.tasks:
                user.tasks.append(task)
            
            await session.commit()
            return task

    async def update_task(self, task_id: str, user_id: str, updates: dict) -> TaskModel:
        async with self.session() as session:
            result = await session.execute(
                select(TaskModel).filter(and_(
                    TaskModel.id == task_id,
                    TaskModel.owners.any(UserModel.id == user_id)
                ))
            )
            task = result.scalar_one_or_none()
            
            if task:
                for key, value in updates.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                await session.commit()
                await session.refresh(task)
            
            return task

    async def delete_task(self, task_id: str, user_id: str) -> bool:
        async with self.session() as session:
            result = await session.execute(
                select(TaskModel).filter(and_(
                    TaskModel.id == task_id,
                    TaskModel.owners.any(UserModel.id == user_id)
                ))
            )
            task = result.scalar_one_or_none()
            
            if task:
                await session.delete(task)
                await session.commit()
                return True
            return False

    async def get_tasks_with_pending_notifications(self):
        async with self.session() as session:
            result = await session.execute(
                select(TaskModel)
                .filter(
                    TaskModel.completed == False,
                    TaskModel.end_datetime.isnot(None),
                    # Get all tasks with upcoming deadlines
                    TaskModel.end_datetime >= datetime.utcnow(),
                    TaskModel.end_datetime <= datetime.utcnow() + timedelta(hours=1, minutes=5)
                )
                .options(joinedload(TaskModel.owners))
            )
            return result.unique().scalars().all()
        
    
    async def get_random_active_task(self, user_id: str) -> Optional[TaskModel]:
        """Get a random incomplete task for a user"""
        async with self.session() as session:
            result = await session.execute(
                select(TaskModel)
                .join(user_task)
                .where(
                    and_(
                        user_task.c.user_id == user_id,
                        TaskModel.completed == False,
                        TaskModel.end_datetime.isnot(None),
                        TaskModel.end_datetime > datetime.utcnow()
                    )
                )
                .order_by(func.random())
                .limit(1)
                .options(joinedload(TaskModel.owners))
            )
            return result.unique().scalar_one_or_none()
        
    async def get_users_with_active_tasks(self) -> List[UserModel]:
        """Get all users who have incomplete tasks"""
        async with self.session() as session:
            result = await session.execute(
                select(UserModel)
                .distinct()
                .join(user_task)
                .join(TaskModel)
                .where(
                    and_(
                        TaskModel.completed == False,
                        TaskModel.end_datetime.isnot(None),
                        TaskModel.end_datetime > datetime.utcnow()
                    )
                )
            )
            return result.scalars().all()

    async def mark_notification_sent(self, task_id: str, minutes: int):
        async with self.session() as session:
            task = await session.execute(
                select(TaskModel).filter(TaskModel.id == task_id)
            )
            task = task.scalar_one_or_none()
            if task:
                notifications = task.notifications_sent or {}
                notifications[str(minutes)] = True
                task.notifications_sent = notifications
                await session.commit()
                
    

    # Add method to initialize notifications tracking
    async def create_task(self, user_id: str, task_id: str, title: str, difficulty: int,
                         description: Optional[str] = None,
                         start_datetime: Optional[datetime] = None, 
                         end_datetime: Optional[datetime] = None) -> TaskModel:
        async with self.session() as session:
            user_result = await session.execute(
                select(UserModel)
                .options(joinedload(UserModel.tasks))
                .filter(UserModel.id == user_id)
            )
            user = user_result.unique().scalar_one_or_none()
            
            if not user:
                raise ValueError("User not found")
            
            # Initialize notifications tracking for all thresholds
            notifications = {
                "60": False,  # 1 hour
                "30": False,  # 30 minutes
                "10": False   # 10 minutes
            }
            
            task = TaskModel(
                id=task_id,
                title=title,
                description=description,
                difficulty=difficulty,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                notifications_sent=notifications
            )
            user.tasks.append(task)
            session.add(task)
            
            await session.commit()
            await session.refresh(task)
            return task
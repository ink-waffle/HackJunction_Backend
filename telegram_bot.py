from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from datetime import datetime, timedelta
import asyncio
from database_service import DatabaseService
import logging

class TelegramBot:
    def __init__(self, token: str, db: DatabaseService):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.db = db
        self.notification_thresholds = [60, 30, 10]
        self.setup_handlers()
        self.last_random_reminder = {}  # user_id: last_reminder_time

    def setup_handlers(self):
        @self.dp.message(Command("start"))
        async def start_cmd(message: types.Message):
            await message.answer(
                "Welcome to Task Reminder Bot!\n"
                "Use /link <your_username> to connect your account."
            )

        @self.dp.message(Command("link"))
        async def link_account(message: types.Message):
            try:
                # Extract username from command
                _, username = message.text.split(maxsplit=1)
                user = await self.db.get_user(username)
                
                if user:
                    await self.db.update_user_telegram_id(user.id, message.from_user.id)
                    await message.answer(f"Successfully linked to account: {username}")
                else:
                    await message.answer("User not found. Please check your username.")
            except ValueError:
                await message.answer("Please provide your username: /link <username>")
                
        @self.dp.message(Command("next"))
        async def send_random(message: types.Message):
            """Manual trigger for random task reminder"""
            user = await self.db.get_user_by_tgid(message.from_user.id)
            if user:
                task = await self.db.get_random_active_task(user.id)
                if task:
                    time_until = self.format_time_until(task.end_datetime)
                    await message.answer(
                        f"🎲 Random Task:\n"
                        f"{task.title}\n"
                        f"Due in: {time_until}\n"
                        f"Deadline: {task.end_datetime.strftime('%Y-%m-%d %H:%M')}"
                    )
                else:
                    await message.answer("No active tasks found!")
            else:
                await message.answer("Please link your account first using /link <username>")

    async def check_deadlines(self):
        while True:
            try:
                # Get all incomplete tasks with deadlines
                tasks = await self.db.get_tasks_with_pending_notifications()
                current_time = datetime.now()
                
                for task in tasks:
                    if task.end_datetime:
                        time_until_deadline = task.end_datetime - current_time
                        minutes_until_deadline = time_until_deadline.total_seconds() / 60
                        
                        # Get or initialize notifications tracking
                        notifications = task.notifications_sent or {}
                        
                        for threshold in self.notification_thresholds:
                            # Check if we need to send this notification
                            if (threshold-1) <= minutes_until_deadline <= threshold and \
                               not notifications.get(str(threshold)):
                                
                                # Send notification to all task owners
                                for owner in task.owners:
                                    if owner.telegram_id:
                                        await self.send_deadline_notification(
                                            owner.telegram_id,
                                            task.title,
                                            task.end_datetime,
                                            threshold
                                        )
                                
                                # Mark this notification as sent
                                await self.db.mark_notification_sent(task.id, threshold)
                
            except Exception as e:
                logging.error(f"Error in deadline checker: {e}")
            
            # Check every minute
            await asyncio.sleep(60)

    async def send_deadline_notification(self, telegram_id: int, task_title: str, 
                                      deadline: datetime, minutes: int):
        # Different message styles for different timeframes
        if minutes == 60:
            emoji = "⚠️"
            timeframe = "1 hour"
        elif minutes == 30:
            emoji = "⏰"
            timeframe = "30 minutes"
        else:  # 10 minutes
            emoji = "🚨"
            timeframe = "10 minutes"

        message = (
            f"{emoji} Deadline Reminder {emoji}\n"
            f"Task: {task_title}\n"
            f"Due in {timeframe} (at {deadline.strftime('%H:%M')})\n"
            f"Status: /complete_{task_title.replace(' ', '_')}"
        )
        await self.bot.send_message(telegram_id, message)

    def format_time_until(self, target_time: datetime) -> str:
        """Format the time until target in a human readable way"""
        now = datetime.utcnow()
        diff = target_time - now
        
        days = diff.days
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days} days")
        if hours > 0:
            parts.append(f"{hours} hours")
        if minutes > 0:
            parts.append(f"{minutes} minutes")
            
        return " and ".join(parts) if parts else "less than a minute"

    async def send_random_task_reminder(self, user_id: int, telegram_id: int):
        """Send reminder about a random task"""
        # Check if we should send reminder (not more often than once per hour per user)
        now = datetime.now()
        last_reminder = self.last_random_reminder.get(user_id)
        if last_reminder and (now - last_reminder) < timedelta(hours=1):
            return

        task = await self.db.get_random_active_task(user_id)
        if task:
            time_until = self.format_time_until(task.end_datetime)
            message = (
                f"🎲 Random Task Reminder 🎲\n"
                f"Don't forget about: {task.title}\n"
                f"Due in: {time_until}\n"
                f"Deadline: {task.end_datetime.strftime('%Y-%m-%d %H:%M')}"
            )
            if task.description:
                message += f"\nDescription: {task.description}"
            
            await self.bot.send_message(telegram_id, message)
            self.last_random_reminder[user_id] = now

    async def random_reminder_checker(self):
        """Periodic checker for sending random task reminders"""
        while True:
            try:
                # Get all users with active tasks
                users = await self.db.get_users_with_active_tasks()
                
                for user in users:
                    if user.telegram_id:  # Only for users with linked Telegram
                        await self.send_random_task_reminder(user.id, user.telegram_id)
                        
            except Exception as e:
                logging.error(f"Error in random reminder checker: {e}")
            
            # Run every 20 minutes
            await asyncio.sleep(1200)  # 20 minutes in seconds
    async def start(self):
        asyncio.create_task(self.check_deadlines())
        asyncio.create_task(self.random_reminder_checker())
        await self.dp.start_polling(self.bot)
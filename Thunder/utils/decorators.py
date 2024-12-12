# Thunder/utils/decorators.py

import asyncio
from functools import wraps
from typing import Callable, Any, List

from pyrogram import Client
from pyrogram.types import Message

from Thunder.utils.shared import handle_user_error, notify_channel

def command_handler(allowed_users: List[int] = None):
    """
    Decorator to handle common command tasks such as permission checks and error handling.
    
    Args:
        allowed_users (List[int], optional): List of user IDs allowed to execute the command.
    
    Returns:
        Callable: The decorated function.
    """
    def decorator(func: Callable[..., Any]):
        @wraps(func)
        async def wrapper(client: Client, message: Message, *args, **kwargs):
            try:
                if allowed_users and message.from_user and message.from_user.id not in allowed_users:
                    await message.reply_text("⚠️ You don't have permission to use this command.", quote=True)
                    return
                return await func(client, message, *args, **kwargs)
            except Exception as e:
                await handle_user_error(message, "🚨 An unexpected error occurred.")
                await notify_channel(client, f"Error in {func.__name__}: {e}")
        return wrapper
    return decorator

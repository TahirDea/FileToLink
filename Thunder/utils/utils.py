# Thunder/utils/utils.py

import asyncio
from typing import Union
from pyrogram import Client
from pyrogram.types import Message, User
from Thunder.utils.logger import logger
from Thunder.vars import Var
from Thunder.constraints import BANNED_CHANNELS

async def notify_channel(bot: Client, text: str):
    """Send a notification to the BIN_CHANNEL."""
    if hasattr(Var, 'BIN_CHANNEL') and isinstance(Var.BIN_CHANNEL, int) and Var.BIN_CHANNEL != 0:
        try:
            await bot.send_message(chat_id=Var.BIN_CHANNEL, text=text)
        except Exception as e:
            logger.error(f"Failed to notify BIN_CHANNEL: {e}", exc_info=True)
            await notify_owner(bot, f"Error notifying BIN_CHANNEL: {e}")

async def notify_owner(client: Client, text: str):
    """Send a notification to the bot owner(s)."""
    owner_ids = Var.OWNER_ID if isinstance(Var.OWNER_ID, (list, tuple)) else [Var.OWNER_ID]
    for owner_id in owner_ids:
        try:
            await client.send_message(chat_id=owner_id, text=text)
        except Exception as e:
            logger.error(f"Failed to notify owner {owner_id}: {e}", exc_info=True)

async def handle_user_error(message: Message, error_msg: str):
    """Handle user errors."""
    try:
        await message.reply_text(f"❌ {error_msg}\nPlease try again or contact support.", quote=True)
    except Exception as e:
        logger.error(f"Failed to handle user error: {e}", exc_info=True)
        await notify_owner(message._client, f"Error handling user error: {e}")

async def handle_critical_error(client: Client, error_msg: str):
    """Handle critical errors by notifying the owner."""
    await notify_owner(client, f"⚠️ Critical Error: {error_msg}")

async def forward_media(media_message: Message) -> Message:
    """Forward media to BIN_CHANNEL."""
    try:
        return await media_message.copy(chat_id=Var.BIN_CHANNEL)
    except Exception as e:
        logger.error(f"Error forwarding media: {e}", exc_info=True)
        await handle_critical_error(media_message._client, f"Error forwarding media: {e}")
        raise

async def leave_banned_channel(client: Client, chat_id: int):
    """Handle leaving a banned channel."""
    if chat_id in BANNED_CHANNELS:
        try:
            await client.leave_chat(chat_id)
            logger.info(f"Left banned channel: {chat_id}")
        except Exception as e:
            logger.error(f"Failed to leave banned channel {chat_id}: {e}", exc_info=True)
            await handle_critical_error(client, f"Failed to leave banned channel {chat_id}: {e}")
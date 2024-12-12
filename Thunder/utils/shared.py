# Thunder/utils/shared.py

import time
import asyncio
import html
import random
import string
from urllib.parse import quote_plus
from typing import Tuple, List, Dict, Union, Optional

from pyrogram import Client, enums
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
    Chat
)
from pyrogram.errors import FloodWait, RPCError

from Thunder.vars import Var
from Thunder.utils.logger import logger, LOG_FILE
from Thunder.utils.human_readable import humanbytes
from Thunder.utils.time_format import get_readable_time
from Thunder.utils.file_properties import get_hash, get_media_file_size, get_name
from Thunder.utils.database import Database
from Thunder.utils.constants import (
    INVALID_ARG_MSG,
    FAILED_USER_INFO_MSG,
    REPLY_DOES_NOT_CONTAIN_USER_MSG,
    LINKS_READY_MESSAGE_TEMPLATE,
    BROADCAST_MESSAGE_TEMPLATE
)

db = Database(Var.DATABASE_URL, Var.NAME)

async def notify_channel(bot: Client, text: str):
    try:
        if hasattr(Var, 'BIN_CHANNEL') and isinstance(Var.BIN_CHANNEL, int) and Var.BIN_CHANNEL != 0:
            await bot.send_message(chat_id=Var.BIN_CHANNEL, text=text)
    except Exception as e:
        logger.error(f"Failed to send message to BIN_CHANNEL: {e}", exc_info=True)

async def notify_owner(client: Client, text: str):
    try:
        owner_ids = Var.OWNER_ID
        if isinstance(owner_ids, (list, tuple, set)):
            tasks = [client.send_message(chat_id=owner_id, text=text) for owner_id in owner_ids]
            await asyncio.gather(*tasks)
        else:
            await client.send_message(chat_id=owner_ids, text=text)

        if hasattr(Var, 'BIN_CHANNEL') and isinstance(Var.BIN_CHANNEL, int) and Var.BIN_CHANNEL != 0:
            await client.send_message(chat_id=Var.BIN_CHANNEL, text=text)
    except Exception as e:
        logger.error(f"Failed to send message to owner: {e}", exc_info=True)

async def handle_user_error(message: Message, error_msg: str):
    try:
        await message.reply_text(f"❌ {error_msg}\nPlease try again or contact support.", quote=True)
    except Exception as e:
        logger.error(f"Failed to send error message to user: {e}", exc_info=True)

async def log_new_user(bot: Client, user_id: int, first_name: str):
    try:
        if not await db.is_user_exist(user_id):
            await db.add_user(user_id)
            try:
                if hasattr(Var, 'BIN_CHANNEL') and isinstance(Var.BIN_CHANNEL, int) and Var.BIN_CHANNEL != 0:
                    await bot.send_message(
                        Var.BIN_CHANNEL,
                        f"👋 **New User Alert!**\n\n"
                        f"✨ **Name:** [{first_name}](tg://user?id={user_id})\n"
                        f"🆔 **User ID:** `{user_id}`\n\n"
                        "has started the bot!"
                    )
                logger.info(f"New user added: {user_id} - {first_name}")
            except Exception as e:
                logger.error(f"Failed to send new user alert to BIN_CHANNEL: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error logging new user {user_id}: {e}", exc_info=True)

async def generate_media_links(log_msg: Message) -> Tuple[str, str, str, str]:
    try:
        base_url = Var.URL.rstrip("/")
        file_id = log_msg.id
        media_name = get_name(log_msg)
        if isinstance(media_name, bytes):
            media_name = media_name.decode('utf-8', errors='replace')
        else:
            media_name = str(media_name)
        media_size = humanbytes(get_media_file_size(log_msg))
        file_name_encoded = quote_plus(media_name)
        hash_value = get_hash(log_msg)
        stream_link = f"{base_url}/watch/{file_id}/{file_name_encoded}?hash={hash_value}"
        online_link = f"{base_url}/{file_id}/{file_name_encoded}?hash={hash_value}"
        logger.info(f"Generated media links for file_id {file_id}")
        return stream_link, online_link, media_name, media_size
    except Exception as e:
        error_text = f"Error generating media links: {e}"
        logger.error(error_text, exc_info=True)
        if hasattr(log_msg, "_client"):
            await notify_channel(log_msg._client, error_text)
        raise

async def generate_links_ready_message(media_name: str, media_size: str, online_link: str, stream_link: str) -> str:
    return LINKS_READY_MESSAGE_TEMPLATE.format(
        media_name=media_name,
        media_size=media_size,
        online_link=online_link,
        stream_link=stream_link
    )

async def generate_broadcast_message(media_name: str, media_size: str, online_link: str, stream_link: str) -> str:
    return BROADCAST_MESSAGE_TEMPLATE.format(
        media_name=media_name,
        media_size=media_size,
        online_link=online_link,
        stream_link=stream_link
    )

def generate_links_keyboard(stream_link: str, online_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖥️ Watch Now", url=stream_link),
            InlineKeyboardButton("📥 Download", url=online_link)
        ]
    ])

async def send_links_to_user(client: Client, command_message: Message, media_name: str,
                             media_size: str, stream_link: str, online_link: str):
    msg_text = await generate_links_ready_message(media_name, media_size, online_link, stream_link)
    links_keyboard = generate_links_keyboard(stream_link, online_link)
    try:
        await command_message.reply_text(
            msg_text,
            quote=True,
            disable_web_page_preview=True,
            reply_markup=links_keyboard
        )
        logger.info(f"Sent links to user {command_message.from_user.id}")
    except Exception as e:
        error_text = f"Error sending links to user: {e}"
        logger.error(error_text, exc_info=True)
        await notify_owner(client, error_text)
        raise

async def log_request(log_msg: Message, user: Union[User, Chat], stream_link: str, online_link: str):
    try:
        await log_msg.reply_text(
            f"👤 **Requested by:** [{user.first_name}](tg://user?id={user.id})\n"
            f"🆔 **User ID:** `{user.id}`\n\n"
            f"📥 **Download Link:** `{online_link}`\n"
            f"🖥️ **Watch Now Link:** `{stream_link}`",
            disable_web_page_preview=True,
            quote=True
        )
        logger.info(f"Logged request in BIN_CHANNEL for user {user.id}")
    except Exception as e:
        error_text = f"Error logging request: {e}"
        logger.error(error_text, exc_info=True)

async def check_admin_privileges(client: Client, chat_id: int) -> bool:
    try:
        chat = await client.get_chat(chat_id)
        if chat.type == 'private':
            return True
        member = await client.get_chat_member(chat_id, client.me.id)
        is_admin_or_creator = member.status in ["administrator", "creator"]
        logger.info(f"Bot admin status in chat {chat_id}: {is_admin_or_creator}")
        return is_admin_or_creator
    except Exception as e:
        error_text = f"Error checking admin privileges: {e}"
        logger.error(error_text, exc_info=True)
        await notify_channel(client, error_text)
        return False

async def handle_flood_wait(e: FloodWait) -> None:
    logger.warning(f"FloodWait encountered. Sleeping for {e.value} seconds.")
    await asyncio.sleep(e.value + 1)

def generate_unique_id(broadcast_ids: Dict[str, any]) -> str:
    while True:
        random_id = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        if random_id not in broadcast_ids:
            return random_id

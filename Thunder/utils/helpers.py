# Thunder/bot/utils/helpers.py

import asyncio
from typing import Union, Tuple, Dict

from pyrogram import Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, User, Chat
from pyrogram.errors import RPCError

from Thunder.vars import Var
from Thunder.utils.database import Database
from Thunder.utils.human_readable import humanbytes
from Thunder.utils.time_format import get_readable_time
from Thunder.utils.file_properties import get_hash, get_media_file_size, get_name
from Thunder.utils.logger import logger

db = Database(Var.DATABASE_URL, Var.NAME)

# ==============================
# Helper Functions Shared by Admin and Stream Plugins
# ==============================

async def notify_channel(bot: Client, text: str):
    """
    Send a notification message to the BIN_CHANNEL.

    Args:
        bot (Client): The Pyrogram client instance.
        text (str): The text message to send.
    """
    try:
        if hasattr(Var, 'BIN_CHANNEL') and isinstance(Var.BIN_CHANNEL, int) and Var.BIN_CHANNEL != 0:
            await bot.send_message(chat_id=Var.BIN_CHANNEL, text=text)
    except Exception as e:
        logger.error(f"Failed to send message to BIN_CHANNEL: {e}", exc_info=True)


async def notify_owner(client: Client, text: str):
    """
    Send a notification message to the bot owner(s).

    Args:
        client (Client): The Pyrogram client instance.
        text (str): The text message to send.
    """
    try:
        owner_ids = Var.OWNER_ID
        if isinstance(owner_ids, (list, tuple, set)):
            tasks = [
                client.send_message(chat_id=owner_id, text=text)
                for owner_id in owner_ids
            ]
            await asyncio.gather(*tasks)
        else:
            await client.send_message(chat_id=owner_ids, text=text)

        if hasattr(Var, 'BIN_CHANNEL') and isinstance(Var.BIN_CHANNEL, int) and Var.BIN_CHANNEL != 0:
            await client.send_message(chat_id=Var.BIN_CHANNEL, text=text)
    except Exception as e:
        logger.error(f"Failed to send message to owner or BIN_CHANNEL: {e}", exc_info=True)


async def handle_user_error(message: Message, error_msg: str, include_support: bool = True):
    """
    Send a standardized error message to the user.

    Args:
        message (Message): The incoming message triggering the error.
        error_msg (str): The error message to send.
        include_support (bool): Whether to include support contact info.
    """
    try:
        if include_support:
            await message.reply_text(f"❌ {error_msg}\nPlease try again or contact support.", quote=True)
        else:
            await message.reply_text(f"❌ {error_msg}", quote=True)
    except Exception as e:
        logger.error(f"Failed to send error message to user: {e}", exc_info=True)


async def log_new_user(bot: Client, user_id: int, first_name: str):
    """
    Log a new user and send a notification to the BIN_CHANNEL if the user is new.

    Args:
        bot (Client): The Pyrogram client instance.
        user_id (int): The Telegram user ID.
        first_name (str): The first name of the user.
    """
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
    """
    Generate stream and download links for media in admin and stream plugins.

    Args:
        log_msg (Message): The message in BIN_CHANNEL containing media.

    Returns:
        Tuple[str, str, str, str]: A tuple containing the stream link, download link,
                                   media name, and media size.
    """
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
        await notify_channel(log_msg._client, error_text)
        raise


async def send_links_to_user(
    client: Client,
    command_message: Message,
    media_name: str,
    media_size: str,
    stream_link: str,
    online_link: str
) -> None:
    """
    Send the generated links to the user via a reply message.

    Args:
        client (Client): The Pyrogram client instance.
        command_message (Message): The original command message from the user.
        media_name (str): The name of the media file.
        media_size (str): The size of the media file.
        stream_link (str): The streaming link.
        online_link (str): The direct download link.
    """
    msg_text = (
        "🔗 **Your Links are Ready!**\n\n"
        f"📄 **File Name:** `{media_name}`\n"
        f"📂 **File Size:** `{media_size}`\n\n"
        f"📥 **Download Link:**\n`{online_link}`\n\n"
        f"🖥️ **Watch Now:**\n`{stream_link}`\n\n"
        "⏰ **Note:** Links are available as long as the bot is active."
    )
    try:
        await command_message.reply_text(
            msg_text,
            quote=True,
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🖥️ Watch Now", url=stream_link),
                    InlineKeyboardButton("📥 Download", url=online_link)
                ]
            ]),
        )
        logger.info(f"Sent links to user {command_message.from_user.id}")
    except Exception as e:
        error_text = f"Error sending links to user: {e}"
        logger.error(error_text, exc_info=True)
        await notify_owner(client, error_text)
        raise


async def log_request(
    log_msg: Message,
    user: Union[User, Chat],
    stream_link: str,
    online_link: str
) -> None:
    """
    Log the user's request in BIN_CHANNEL by replying to the forwarded message.

    Args:
        log_msg (Message): The forwarded message in BIN_CHANNEL.
        user (Union[User, Chat]): The user who requested the links.
        stream_link (str): The streaming link generated for the media.
        online_link (str): The direct download link generated for the media.
    """
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
    """
    Check if the bot is an admin in the chat; skip for private chats.

    Args:
        client (Client): The Pyrogram client instance.
        chat_id (int): The ID of the chat to check.

    Returns:
        bool: True if the bot is an admin or the chat is private, False otherwise.
    """
    try:
        chat = await client.get_chat(chat_id)
        if chat.type == enums.ChatType.PRIVATE:
            return True  # Admin check not needed in private chats

        # Get the bot's status in the chat
        member = await client.get_chat_member(chat_id, client.me.id)
        # Check if the bot is either an administrator or the creator
        is_admin_or_creator = member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]

        # Log and return the privilege check result
        logger.info(f"Bot admin status in chat {chat_id}: {is_admin_or_creator}")
        return is_admin_or_creator

    except Exception as e:
        # Log the error if checking admin privileges fails
        error_text = f"Error checking admin privileges: {e}"
        logger.error(error_text, exc_info=True)
        await notify_channel(client, error_text)
        return False

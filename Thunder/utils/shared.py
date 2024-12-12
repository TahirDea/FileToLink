# Thunder/utils/shared.py

import asyncio
from typing import Optional, Dict, Any
from pyrogram import Client
from pyrogram.errors import RPCError
from pyrogram.types import ChatMember
from Thunder.utils.logger import logger
from Thunder.vars import Var

# Simple in-memory cache
_cache: Dict[str, Dict[str, Any]] = {}


def get_cached_data(key: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached data for a given key.

    Args:
        key (str): The cache key.

    Returns:
        Optional[Dict[str, Any]]: The cached data if exists and not expired, else None.
    """
    data = _cache.get(key)
    if data:
        if data['expiry'] > asyncio.get_event_loop().time():
            return data['data']
        else:
            # Cache expired
            del _cache[key]
    return None


def set_cache(key: str, data: Dict[str, Any], expiry: int = 86400) -> None:
    """
    Set cache data for a given key with an expiry time.

    Args:
        key (str): The cache key.
        data (Dict[str, Any]): The data to cache.
        expiry (int): Time in seconds after which the cache expires.
    """
    _cache[key] = {
        'data': data,
        'expiry': asyncio.get_event_loop().time() + expiry
    }


def clean_cache() -> None:
    """
    Clean expired cache entries.
    """
    current_time = asyncio.get_event_loop().time()
    keys_to_delete = [key for key, value in _cache.items() if value['expiry'] <= current_time]
    for key in keys_to_delete:
        del _cache[key]
    logger.info(f"Cleaned {len(keys_to_delete)} expired cache entries.")


async def check_admin_privileges(client: Client, chat_id: int) -> bool:
    """
    Check if the bot has admin privileges in the specified chat.

    Args:
        client (Client): The Pyrogram client.
        chat_id (int): The ID of the chat to check.

    Returns:
        bool: True if the bot is an admin, False otherwise.
    """
    try:
        logger.debug(f"Checking admin privileges for bot in chat {chat_id}")
        member: ChatMember = await client.get_chat_member(chat_id, client.me.id)
        logger.debug(f"Bot status in chat {chat_id}: {member.status}")
        if member.status in ["administrator", "creator"]:
            logger.debug(f"Bot is an admin in chat {chat_id}")
            return True
        else:
            logger.warning(f"Bot is not an admin in chat {chat_id}. Status: {member.status}")
            return False
    except RPCError as e:
        logger.error(f"RPCError while checking admin privileges in chat {chat_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while checking admin privileges in chat {chat_id}: {e}", exc_info=True)
        return False


async def notify_owner(client: Client, text: str) -> None:
    """
    Notify the bot owner with a message.

    Args:
        client (Client): The Pyrogram client.
        text (str): The message text.
    """
    try:
        await client.send_message(chat_id=Var.OWNER_ID[0], text=text, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Failed to notify owner: {e}", exc_info=True)


async def notify_channel(client: Client, text: str) -> None:
    """
    Notify the specified channel with a message.

    Args:
        client (Client): The Pyrogram client.
        text (str): The message text.
    """
    try:
        await client.send_message(chat_id=Var.LOG_CHANNEL, text=text, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Failed to notify channel: {e}", exc_info=True)


async def handle_flood_wait(e: FloodWait) -> None:
    """
    Handle FloodWait errors by sleeping for the required duration.

    Args:
        e (FloodWait): The FloodWait exception.
    """
    logger.warning(f"FloodWait: Sleeping for {e.value} seconds.")
    await asyncio.sleep(e.value + 1)


async def handle_user_error(message: Message, error_text: str) -> None:
    """
    Handle errors by sending an error message to the user.

    Args:
        message (Message): The message to reply to.
        error_text (str): The error message to send.
    """
    try:
        await message.reply_text(
            error_text,
            parse_mode=enums.ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Failed to send error message to user: {e}", exc_info=True)


async def log_new_user(user: User) -> None:
    """
    Log the addition of a new user.

    Args:
        user (User): The Pyrogram User object.
    """
    logger.info(f"New user added: {user.id} - {user.first_name}")


async def generate_media_links(log_msg: Message) -> Tuple[str, str, str, str]:
    """
    Generate streaming and online download links for a forwarded media message.

    Args:
        log_msg (Message): The forwarded message in BIN_CHANNEL.

    Returns:
        Tuple[str, str, str, str]: Streaming link, online download link, media name, media size.
    """
    # Placeholder implementation. Replace with actual link generation logic.
    media_name = log_msg.file_name or "Unknown"
    media_size = humanbytes(get_media_file_size(log_msg))
    stream_link = f"https://streaming.service/{quote(media_name)}"
    online_link = f"https://download.service/{quote(media_name)}"
    return stream_link, online_link, media_name, media_size


async def send_links_to_user(
    client: Client,
    message: Message,
    media_name: str,
    media_size: str,
    stream_link: str,
    online_link: str
) -> None:
    """
    Send the generated links to the user.

    Args:
        client (Client): The Pyrogram client.
        message (Message): The message to reply to.
        media_name (str): The name of the media.
        media_size (str): The size of the media.
        stream_link (str): The streaming link.
        online_link (str): The online download link.
    """
    try:
        links_keyboard = generate_links_keyboard(stream_link, online_link)
        await message.reply_text(
            f"📁 **{media_name}**\n🗂️ **Size:** {media_size}\n\n🔗 **Links:**",
            reply_markup=links_keyboard,
            parse_mode=enums.ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Failed to send links to user: {e}", exc_info=True)


async def log_request(
    log_msg: Message,
    user: Union[User, Chat],
    stream_link: str,
    online_link: str
) -> None:
    """
    Log the link generation request.

    Args:
        log_msg (Message): The forwarded message in BIN_CHANNEL.
        user (Union[User, Chat]): The user or chat requesting the links.
        stream_link (str): The streaming link.
        online_link (str): The online download link.
    """
    logger.info(f"Links generated for user {user.id}: Stream Link - {stream_link}, Online Link - {online_link}")


def generate_links_ready_message(
    media_name: str,
    media_size: str,
    online_link: str,
    stream_link: str
) -> str:
    """
    Generate a message indicating that links are ready.

    Args:
        media_name (str): The name of the media.
        media_size (str): The size of the media.
        online_link (str): The online download link.
        stream_link (str): The streaming link.

    Returns:
        str: The formatted message.
    """
    return f"📁 **{media_name}**\n🗂️ **Size:** {media_size}\n\n🔗 **Links:**\n[Stream Link]({stream_link}) | [Download Link]({online_link})"


def generate_links_keyboard(stream_link: str, online_link: str) -> InlineKeyboardMarkup:
    """
    Generate an inline keyboard with streaming and download links.

    Args:
        stream_link (str): The streaming link.
        online_link (str): The online download link.

    Returns:
        InlineKeyboardMarkup: The generated keyboard.
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 Stream Link", url=stream_link),
            InlineKeyboardButton("📥 Download Link", url=online_link)
        ]
    ])

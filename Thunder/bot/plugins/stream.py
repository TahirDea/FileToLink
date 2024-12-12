# Thunder/bot/plugins/stream.py

import time
import asyncio
from urllib.parse import quote
from typing import Optional, Tuple, Dict, Union, List

from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, RPCError
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
    Chat
)

from Thunder.bot import StreamBot
from Thunder.utils.database import Database
from Thunder.utils.file_properties import get_hash, get_media_file_size, get_name
from Thunder.utils.human_readable import humanbytes
from Thunder.utils.logger import logger
from Thunder.vars import Var

from Thunder.utils.helpers import (
    notify_channel,
    notify_owner,
    handle_user_error,
    log_new_user,
    generate_media_links,
    send_links_to_user,
    log_request,
    check_admin_privileges
)

# ==============================
# Database Initialization
# ==============================

db: Database = Database(Var.DATABASE_URL, Var.NAME)

# ==============================
# Cache Configurations
# ==============================

CACHE: Dict[str, Dict[str, Union[str, float]]] = {}
CACHE_EXPIRY: int = 86400  # 24 hours

# ==============================
# Helper Functions Unique to Stream Plugin
# ==============================

async def handle_flood_wait(e: FloodWait) -> None:
    """
    Handles FloodWait exceptions by logging a warning and sleeping for the required duration.

    Args:
        e (FloodWait): The FloodWait exception containing the wait duration.
    """
    logger.warning(f"FloodWait encountered. Sleeping for {e.value} seconds.")
    await asyncio.sleep(e.value + 1)


# ==============================
# Command Handlers
# ==============================

@StreamBot.on_message(filters.command("link") & ~filters.private)
async def link_handler(client: Client, message: Message) -> None:
    """
    Handles the /link command in groups and ensures the bot has admin privileges
    before proceeding with the command execution.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The incoming message triggering the command.
    """
    user_id: int = message.from_user.id

    # Check if the user has started the bot in private (registration check)
    if not await db.is_user_exist(user_id):
        try:
            invite_link: str = f"https://t.me/{client.me.username}?start=start"
            await message.reply_text(
                "⚠️ You need to start the bot in private first to use this command.\n"
                f"👉 [Click here]({invite_link}) to start a private chat.",
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📩 Start Chat", url=invite_link)]
                ]),
                quote=True
            )
            logger.info(f"User {user_id} prompted to start bot in private.")
        except Exception as e:
            logger.error(
                f"Error sending start prompt to user: {e}",
                exc_info=True
            )
            await message.reply_text(
                "⚠️ Please start the bot in private by sending /start to me.",
                quote=True
            )
        return

    # Check for admin privileges if in a group or supergroup
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        is_admin: bool = await check_admin_privileges(client, message.chat.id)
        if not is_admin:
            await message.reply_text(
                "🔒 The bot needs to be an admin in this group to function properly.\n"
                "Please promote the bot to admin and try again.",
                quote=True
            )
            return

    # Proceed if the bot has admin privileges or if this is a private chat
    if not message.reply_to_message:
        await message.reply_text(
            "⚠️ Please use the /link command in reply to a file.",
            quote=True
        )
        return

    reply_msg: Message = message.reply_to_message
    if not reply_msg.media:
        await message.reply_text(
            "⚠️ The message you're replying to does not contain any file.",
            quote=True
        )
        return

    command_parts: List[str] = message.text.strip().split()
    num_files: int = 1
    if len(command_parts) > 1:
        try:
            num_files = int(command_parts[1])
            if num_files < 1 or num_files > 25:
                await message.reply_text(
                    "⚠️ **Please specify a number between 1 and 25.**",
                    quote=True
                )
                return
        except ValueError:
            await message.reply_text(
                "⚠️ **Invalid number specified.**",
                quote=True
            )
            return

    if num_files == 1:
        await process_media_message(client, message, reply_msg)
    else:
        await process_multiple_messages(client, message, reply_msg, num_files)


async def process_multiple_messages(
    client: Client,
    command_message: Message,
    reply_msg: Message,
    num_files: int
) -> None:
    """
    Processes multiple media messages based on the number specified by the user.

    Args:
        client (Client): The Pyrogram client instance.
        command_message (Message): The original command message from the user.
        reply_msg (Message): The message to which the command was replied.
        num_files (int): The number of files to process.
    """
    chat_id: int = command_message.chat.id
    start_message_id: int = reply_msg.id
    end_message_id: int = start_message_id + num_files - 1
    message_ids: List[int] = list(range(start_message_id, end_message_id + 1))

    try:
        messages: List[Optional[Message]] = await client.get_messages(
            chat_id=chat_id,
            message_ids=message_ids
        )
    except RPCError as e:
        await command_message.reply_text(
            f"❌ Failed to fetch messages: {e}",
            quote=True
        )
        logger.error(f"Failed to fetch messages: {e}", exc_info=True)
        return

    processed_count: int = 0
    download_links: List[str] = []
    for msg in messages:
        if msg and msg.media:
            download_link: Optional[str] = await process_media_message(
                client,
                command_message,
                msg
            )
            if download_link:
                download_links.append(download_link)
                processed_count += 1
        else:
            logger.info(
                f"Message {msg.id if msg else 'Unknown'} does not contain media or is inaccessible, skipping."
            )

    if download_links:
        links_text: str = "\n".join(download_links)
        message_text: str = (
            f"📥 **Here are your {processed_count} combined download links:**\n\n`{links_text}`"
        )
        await command_message.reply_text(
            message_text,
            quote=True,
            disable_web_page_preview=True
        )

    await command_message.reply_text(
        f"✅ **Processed {processed_count} files starting from the replied message.**",
        quote=True
    )


@StreamBot.on_message(
    filters.private & filters.incoming &
    (
        filters.document | filters.video | filters.photo | filters.audio |
        filters.voice | filters.animation | filters.video_note
    ),
    group=4
)
async def private_receive_handler(client: Client, message: Message) -> None:
    """
    Handles incoming media messages in private chats.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The incoming media message.
    """
    await process_media_message(client, message, message)


async def process_media_message(
    client: Client,
    command_message: Message,
    media_message: Message
) -> Optional[str]:
    """
    Processes a single media message by forwarding, generating links, caching,
    and sending links to the user.

    Args:
        client (Client): The Pyrogram client instance.
        command_message (Message): The original command or media message.
        media_message (Message): The media message to process.

    Returns:
        Optional[str]: The online download link if successful, else None.
    """
    retries: int = 0
    max_retries: int = 5
    while retries < max_retries:
        try:
            cache_key: Optional[str] = get_file_unique_id(media_message)
            if cache_key is None:
                await handle_user_error(
                    command_message, 
                    "⚠️ Could not extract file identifier from the media.", 
                    include_support=False
                )
                return None

            cached_data: Optional[Dict[str, Union[str, float]]] = CACHE.get(cache_key)
            if cached_data and (time.time() - cached_data['timestamp'] < CACHE_EXPIRY):
                await send_links_to_user(
                    client=client,
                    command_message=command_message,
                    media_name=cached_data['media_name'],
                    media_size=cached_data['media_size'],
                    stream_link=cached_data['stream_link'],
                    online_link=cached_data['online_link']
                )
                logger.info(
                    f"Served links from cache for user {command_message.from_user.id}"
                )
                return cached_data['online_link']

            log_msg: Message = await forward_media(media_message)
            stream_link, online_link, media_name, media_size = await generate_media_links(log_msg)

            CACHE[cache_key] = {
                'media_name': media_name,
                'media_size': media_size,
                'stream_link': stream_link,
                'online_link': online_link,
                'timestamp': time.time()
            }

            await send_links_to_user(
                client=client,
                command_message=command_message,
                media_name=media_name,
                media_size=media_size,
                stream_link=stream_link,
                online_link=online_link
            )
            await log_request(log_msg, command_message.from_user, stream_link, online_link)
            return online_link

        except FloodWait as e:
            await handle_flood_wait(e)
            retries += 1
            continue
        except Exception as e:
            error_text: str = f"Error processing media message: {e}"
            logger.error(error_text, exc_info=True)
            await handle_user_error(command_message, "An unexpected error occurred.")
            await notify_owner(client, f"⚠️ Critical error occurred:\n{e}")
            return None

    return None


@StreamBot.on_message(
    filters.channel & filters.incoming &
    (
        filters.document | filters.video | filters.photo | filters.audio |
        filters.voice | filters.animation | filters.video_note
    ) &
    ~filters.forwarded,
    group=-1
)
async def channel_receive_handler(client: Client, broadcast: Message) -> None:
    """
    Handles incoming media messages from channels, forwards them, generates links,
    and updates the message with link buttons.

    Args:
        client (Client): The Pyrogram client instance.
        broadcast (Message): The incoming media message from the channel.
    """
    retries: int = 0
    max_retries: int = 5
    while retries < max_retries:
        try:
            if int(broadcast.chat.id) in Var.BANNED_CHANNELS:
                await client.leave_chat(broadcast.chat.id)
                logger.info(f"Left banned channel: {broadcast.chat.id}")
                return

            log_msg: Message = await forward_media(broadcast)
            stream_link, online_link, media_name, media_size = await generate_media_links(log_msg)
            await log_request(log_msg, broadcast.chat, stream_link, online_link)

            can_edit: bool = False
            try:
                member = await client.get_chat_member(broadcast.chat.id, client.me.id)
                if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                    can_edit = True
                logger.info(
                    f"Bot can_edit_messages in chat {broadcast.chat.id}: {can_edit}"
                )
            except Exception as e:
                logger.error(
                    f"Error checking bot's admin status: {e}",
                    exc_info=True
                )

            if can_edit:
                await client.edit_message_reply_markup(
                    chat_id=broadcast.chat.id,
                    message_id=broadcast.id,
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("🖥️ Watch Now", url=stream_link),
                            InlineKeyboardButton("📥 Download", url=online_link)
                        ]
                    ])
                )
                logger.info(f"Edited broadcast message in channel {broadcast.chat.id}")
            else:
                await client.send_message(
                    chat_id=broadcast.chat.id,
                    text=(
                        "🔗 **Your Links are Ready!**\n\n"
                        f"📄 **File Name:** `{media_name}`\n"
                        f"📂 **File Size:** `{media_size}`\n\n"
                        f"📥 **Download Link:**\n`{online_link}`\n\n"
                        f"🖥️ **Watch Now:**\n`{stream_link}`\n\n"
                        "⏰ **Note:** Links are available as long as the bot is active."
                    ),
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("🖥️ Watch Now", url=stream_link),
                            InlineKeyboardButton("📥 Download", url=online_link)
                        ]
                    ]),
                )
                logger.info(
                    f"Sent new message with links in channel {broadcast.chat.id}"
                )
            break

        except FloodWait as e:
            await handle_flood_wait(e)
            retries += 1
            continue
        except Exception as e:
            error_text: str = f"Error handling channel message: {e}"
            logger.error(error_text, exc_info=True)
            await notify_owner(client, f"⚠️ Critical error occurred in channel handler:\n{e}")
            break

# ==============================
# Background Tasks
# ==============================

async def clean_cache_task() -> None:
    """
    Periodically cleans up expired entries from the cache.
    """
    while True:
        await asyncio.sleep(3600)  # Sleep for 1 hour
        current_time: float = time.time()
        keys_to_delete: List[str] = [
            key for key, value in CACHE.items()
            if current_time - value['timestamp'] > CACHE_EXPIRY
        ]
        for key in keys_to_delete:
            del CACHE[key]
        if keys_to_delete:
            logger.info(f"Cache cleaned up. Removed {len(keys_to_delete)} entries.")

# Start the cache cleaning task
StreamBot.loop.create_task(clean_cache_task())

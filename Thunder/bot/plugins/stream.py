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
from Thunder.utils import db, notify_channel, notify_owner, handle_user_error
from Thunder.bot_operations import send_links_to_user, generate_media_links, check_admin_privileges, log_new_user, log_request, forward_media
from Thunder.cache import cache_function
from Thunder.constraints import BANNED_CHANNELS

CACHE: Dict[str, Dict[str, Union[str, float]]] = {}
CACHE_EXPIRY: int = 86400  # 24 hours

@cache_function
def get_file_unique_id(media_message: Message) -> Optional[str]:
    """
    Retrieves the unique file identifier from a media message.

    Args:
        media_message (Message): The media message to extract the unique ID from.

    Returns:
        Optional[str]: The unique file identifier if found, else None.
    """
    media_types = [
        'document', 'video', 'audio', 'photo', 'animation',
        'voice', 'video_note', 'sticker'
    ]
    for media_type in media_types:
        media = getattr(media_message, media_type, None)
        if media:
            return media.file_unique_id
    return None

async def handle_flood_wait(e: FloodWait) -> None:
    """
    Handles FloodWait exceptions by logging a warning and sleeping for the required duration.

    Args:
        e (FloodWait): The FloodWait exception containing the wait duration.
    """
    logger.warning(f"FloodWait encountered. Sleeping for {e.value} seconds.")
    await asyncio.sleep(e.value + 1)

@StreamBot.on_message(filters.command("link") & ~filters.private)
async def link_handler(client: Client, message: Message) -> None:
    """
    Handles the /link command in groups and ensures the bot has admin privileges
    before proceeding with the command execution.
    """
    user_id: int = message.from_user.id

    if not await db.is_user_exist(user_id):
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
        return

    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        is_admin: bool = await check_admin_privileges(client, message.chat.id)
        if not is_admin:
            await message.reply_text(
                "🔒 The bot needs to be an admin in this group to function properly.\n"
                "Please promote the bot to admin and try again.",
                quote=True
            )
            return

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
        await command_message.reply_text(
            f"📥 **Here are your {processed_count} combined download links:**\n\n`{links_text}`",
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
    """
    if message.from_user:
        await log_new_user(
            bot=client,
            user_id=message.from_user.id,
            first_name=message.from_user.first_name
        )
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
    cache_key: Optional[str] = get_file_unique_id(media_message)
    if cache_key is None:
        await handle_user_error(command_message, "⚠️ Could not extract file identifier from the media.")
        return None

    cached_data: Optional[Dict[str, Union[str, float]]] = CACHE.get(cache_key)
    if cached_data and (time.time() - cached_data['timestamp'] < CACHE_EXPIRY):
        await send_links_to_user(
            client,
            command_message,
            cached_data['media_name'],
            cached_data['media_size'],
            cached_data['stream_link'],
            cached_data['online_link']
        )
        return cached_data['online_link']

    try:
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
            client,
            command_message,
            media_name,
            media_size,
            stream_link,
            online_link
        )
        await log_request(log_msg, command_message.from_user, stream_link, online_link)
        return online_link

    except FloodWait as e:
        await handle_flood_wait(e)
        return await process_media_message(client, command_message, media_message)
    except Exception as e:
       await handle_user_error(command_message, "An unexpected error occurred.")
       await notify_owner(client, f"⚠️ Critical error occurred:\n{e}")
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
    """
    if broadcast.chat.id in BANNED_CHANNELS:
        await leave_banned_channel(client, broadcast.chat.id)
        return

    try:
        log_msg: Message = await forward_media(broadcast)
        stream_link, online_link, media_name, media_size = await generate_media_links(log_msg)
        await log_request(log_msg, broadcast.chat, stream_link, online_link)

        can_edit: bool = False
        try:
            member = await client.get_chat_member(broadcast.chat.id, client.me.id)
            can_edit = member.status in ["administrator", "creator"]
        except Exception as e:
            logger.error(f"Error checking bot's admin status: {e}", exc_info=True)

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
    except FloodWait as e:
        await handle_flood_wait(e)
        await channel_receive_handler(client, broadcast)
    except Exception as e:
        await notify_owner(client, f"⚠️ Critical error occurred in channel handler:\n{e}")

# Start the cache cleaning task
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

StreamBot.loop.create_task(clean_cache_task())
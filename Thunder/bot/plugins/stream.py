# Thunder/bot/plugins/stream.py

import time
import asyncio
from urllib.parse import quote
from typing import Optional, Tuple, Dict, Union, List

from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid, RPCError
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
from Thunder.utils.time_format import get_readable_time
from Thunder.utils.logger import logger
from Thunder.vars import Var

from Thunder.utils.shared import (
    handle_flood_wait,
    notify_owner,
    handle_user_error,
    log_new_user,
    generate_media_links,
    send_links_to_user,
    log_request,
    check_admin_privileges,
    notify_channel,
    db,
    generate_links_ready_message,
    generate_links_keyboard
)
from Thunder.utils.constants import (
    INVALID_ARG_MSG,
    FAILED_USER_INFO_MSG,
    REPLY_DOES_NOT_CONTAIN_USER_MSG,
    LINKS_READY_MESSAGE_TEMPLATE,
    BROADCAST_MESSAGE_TEMPLATE
)
from Thunder.utils.decorators import command_handler
from Thunder.utils.cache import get_cached_data, set_cache, clean_cache

CACHE_EXPIRY: int = 86400  # 24 hours


def get_file_unique_id(media_message: Message) -> Optional[str]:
    """
    Extract the unique file ID from a media message.

    Args:
        media_message (Message): The message containing media.

    Returns:
        Optional[str]: The unique file ID if found, else None.
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


async def forward_media(media_message: Message) -> Optional[Message]:
    """
    Forward a media message to the BIN_CHANNEL.

    Args:
        media_message (Message): The media message to forward.

    Returns:
        Optional[Message]: The forwarded message in BIN_CHANNEL or None if failed.
    """
    try:
        return await media_message.forward(chat_id=Var.BIN_CHANNEL)
    except FloodWait as e:
        logger.warning(f"FloodWait error: sleeping for {e.value} seconds.")
        await handle_flood_wait(e)
        return await forward_media(media_message)
    except Exception as e:
        error_msg = f"Error forwarding media message: {e}"
        logger.error(error_msg, exc_info=True)
        return None


@StreamBot.on_message(filters.command("link") & ~filters.private)
async def link_handler(client: Client, message: Message) -> None:
    """
    Handler for the /link command. Generates download and streaming links for the replied media.
    """
    user_id: int = message.from_user.id

    if not await db.is_user_exist(user_id):
        try:
            invite_link: str = f"https://t.me/{client.me.username}?start=start"
            await message.reply_text(
                "⚠️ You need to start the bot in private first.\n"
                f"👉 [Click here]({invite_link}) to start.",
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📩 Start Chat", url=invite_link)]
                ]),
                quote=True
            )
            logger.info(f"User {user_id} prompted to start bot in private.")
        except Exception as e:
            logger.error(f"Error sending start prompt: {e}", exc_info=True)
            await message.reply_text("⚠️ Please start the bot in private by sending /start to me.", quote=True)
        return

    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        is_admin: bool = await check_admin_privileges(client, message.chat.id)
        if not is_admin:
            await message.reply_text(
                "🔒 The bot needs to be an admin to function.\nPlease promote the bot and try again.",
                quote=True
            )
            return

    if not message.reply_to_message:
        await message.reply_text("⚠️ Reply to a file with /link.", quote=True)
        return

    reply_msg: Message = message.reply_to_message
    if not reply_msg.media:
        await message.reply_text("⚠️ The replied message has no file.", quote=True)
        return

    # Process single or multiple files
    command_parts: List[str] = message.text.strip().split()
    num_files: int = 1
    if len(command_parts) > 1:
        try:
            num_files = int(command_parts[1])
            if num_files < 1 or num_files > 25:
                await message.reply_text("⚠️ **Specify a number between 1 and 25.**", quote=True)
                return
        except ValueError:
            await message.reply_text("⚠️ **Invalid number specified.**", quote=True)
            return

    if num_files == 1:
        await process_media_message(client, message, reply_msg)
    else:
        await process_multiple_messages(client, message, reply_msg, num_files)


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
    Handler for incoming media messages in private chats. Generates links.
    """
    await process_media_message(client, message, message)


async def process_multiple_messages(
    client: Client,
    command_message: Message,
    reply_msg: Message,
    num_files: int
) -> None:
    """
    Process multiple media messages and generate links for each.

    Args:
        client (Client): The Pyrogram client.
        command_message (Message): The command message invoking the handler.
        reply_msg (Message): The message being replied to.
        num_files (int): Number of files to process.
    """
    chat_id: int = command_message.chat.id
    start_message_id: int = reply_msg.id
    end_message_id: int = start_message_id + num_files - 1
    message_ids: List[int] = list(range(start_message_id, end_message_id + 1))

    try:
        messages: List[Optional[Message]] = await client.get_messages(chat_id=chat_id, message_ids=message_ids)
    except RPCError as e:
        await command_message.reply_text(f"❌ Failed to fetch messages: {e}", quote=True)
        logger.error(f"Failed to fetch messages: {e}", exc_info=True)
        return

    processed_count: int = 0
    download_links: List[str] = []
    for msg in messages:
        if msg and msg.media:
            download_link: Optional[str] = await process_media_message(client, command_message, msg)
            if download_link:
                download_links.append(download_link)
                processed_count += 1
        else:
            logger.info(f"Message {msg.id if msg else 'Unknown'} has no media, skipping.")

    if download_links:
        links_text: str = "\n".join(download_links)
        message_text: str = f"📥 **Your {processed_count} download links:**\n\n`{links_text}`"
        await command_message.reply_text(message_text, quote=True, disable_web_page_preview=True)

    await command_message.reply_text(
        f"✅ **Processed {processed_count} files starting from the replied message.**",
        quote=True
    )


async def process_media_message(
    client: Client,
    command_message: Message,
    media_message: Message
) -> Optional[str]:
    """
    Process a single media message and generate/send links.

    Args:
        client (Client): The Pyrogram client.
        command_message (Message): The command message invoking the handler.
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
                await command_message.reply_text("⚠️ Could not extract file identifier.", quote=True)
                return None

            cached_data = get_cached_data(cache_key)
            if cached_data:
                await send_links_to_user(
                    client,
                    command_message,
                    cached_data['media_name'],
                    cached_data['media_size'],
                    cached_data['stream_link'],
                    cached_data['online_link']
                )
                logger.info(f"Served links from cache for user {command_message.from_user.id}")
                return cached_data['online_link']

            log_msg: Optional[Message] = await forward_media(media_message)
            if log_msg is None:
                await handle_user_error(command_message, "❌ **Failed to forward the media for link generation.**")
                return None

            stream_link, online_link, media_name, media_size = await generate_media_links(log_msg)

            set_cache(cache_key, {
                'media_name': media_name,
                'media_size': media_size,
                'stream_link': stream_link,
                'online_link': online_link
            })

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
            retries += 1
            continue
        except Exception as e:
            error_text: str = f"Error processing media: {e}"
            logger.error(error_text, exc_info=True)
            await handle_user_error(command_message, "🚨 **An unexpected error occurred.**")
            await notify_owner(client, f"⚠️ Critical error:\n{e}")
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
    Handler for incoming media messages in channels. Generates and edits links.
    """
    retries: int = 0
    max_retries: int = 5
    while retries < max_retries:
        try:
            if int(broadcast.chat.id) in Var.BANNED_CHANNELS:
                await client.leave_chat(broadcast.chat.id)
                logger.info(f"Left banned channel: {broadcast.chat.id}")
                return

            log_msg: Optional[Message] = await forward_media(broadcast)
            if log_msg is None:
                logger.error("Failed to forward media message.")
                return

            stream_link, online_link, media_name, media_size = await generate_media_links(log_msg)
            await log_request(log_msg, broadcast.chat, stream_link, online_link)

            can_edit: bool = False
            try:
                member = await client.get_chat_member(broadcast.chat.id, client.me.id)
                can_edit = member.status in ["administrator", "creator"]
                logger.debug(f"Bot admin status in chat {broadcast.chat.id}: {can_edit}")
            except RPCError as e:
                logger.error(f"RPCError while checking admin status: {e}", exc_info=True)

            if can_edit:
                links_keyboard = generate_links_keyboard(stream_link, online_link)
                await client.edit_message_reply_markup(
                    chat_id=broadcast.chat.id,
                    message_id=broadcast.id,
                    reply_markup=links_keyboard
                )
                logger.info(f"Edited broadcast message in channel {broadcast.chat.id}")
            else:
                links_ready_message = await generate_links_ready_message(
                    media_name, media_size, online_link, stream_link
                )
                links_keyboard = generate_links_keyboard(stream_link, online_link)
                await client.send_message(
                    chat_id=broadcast.chat.id,
                    text=links_ready_message,
                    reply_markup=links_keyboard,
                    disable_web_page_preview=True
                )
                logger.info(f"Sent new message with links in channel {broadcast.chat.id}")
            break

        except FloodWait as e:
            await handle_flood_wait(e)
            retries += 1
            continue
        except Exception as e:
            error_text: str = f"Error handling channel message: {e}"
            logger.error(error_text, exc_info=True)
            await notify_owner(client, f"⚠️ Critical error in channel handler:\n{e}")
            break


async def clean_cache_task() -> None:
    """
    Periodic task to clean expired cache entries.
    """
    while True:
        await asyncio.sleep(3600)  # Sleep for 1 hour
        clean_cache()
        logger.info("Cache cleaned up.")


# Start the cache cleaning task
StreamBot.loop.create_task(clean_cache_task())

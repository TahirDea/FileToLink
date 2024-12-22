# Thunder/utils/bot_operations.py

import asyncio
import datetime
from typing import List, Dict, Union, Tuple
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, User, Chat
from Thunder.utils import db, notify_owner
from Thunder.utils.human_readable import humanbytes
from Thunder.utils.time_format import get_readable_time
from Thunder.messages import get_links_message, get_link_buttons, get_error_message, get_broadcast_complete_message, get_view_profile_button
from Thunder.vars import Var
from Thunder.utils.file_properties import get_hash, get_name, get_media_file_size
from Thunder.cache import cache_function
from Thunder.constraints import validate_file_count, MAX_FILES_PER_COMMAND

async def send_message_with_buttons(client: Client, message: Message, text: str, markup: InlineKeyboardMarkup):
    """Send message with inline buttons."""
    await message.reply_text(text=text, quote=True, disable_web_page_preview=True, reply_markup=markup)

async def send_links_to_user(client: Client, command_message: Message, media_name: str, media_size: str, stream_link: str, online_link: str):
    """Send media links to user."""
    text = get_links_message(media_name, media_size, stream_link, online_link)
    buttons = get_link_buttons(stream_link, online_link)
    await send_message_with_buttons(client, command_message, text, buttons)

@cache_function
async def handle_broadcast_completion(message: Message, output: Message, failures: int, successes: int, total_users: int, start_time: float):
    """Handle broadcast completion with caching to avoid repeated calculations."""
    elapsed_time = get_readable_time(time.time() - start_time)
    message_text = get_broadcast_complete_message(elapsed_time, total_users, successes, failures)
    await output.delete()
    await message.reply_text(message_text, parse_mode="Markdown", disable_web_page_preview=True)

async def log_request(log_msg: Message, user: Union[User, Chat], stream_link: str, online_link: str):
    """Log media request details."""
    try:
        await db.log_broadcast(
            broadcast_id=str(log_msg.id), 
            message=f"Requested by: {user.first_name} (ID: {user.id})\nDownload: {online_link}\nWatch: {stream_link}", 
            status="Completed"
        )
    except Exception as e:
        await notify_owner(log_msg._client, f"Error logging request: {e}")

@cache_function
async def generate_media_links(log_msg: Message) -> Tuple[str, str, str, str]:
    """Generate media links with caching for performance."""
    base_url = Var.URL.rstrip("/")
    file_id = log_msg.id
    media_name = get_name(log_msg).decode('utf-8', errors='replace') if isinstance(get_name(log_msg), bytes) else str(get_name(log_msg))
    media_size = humanbytes(get_media_file_size(log_msg))
    file_name_encoded = media_name.replace(' ', '_')
    hash_value = get_hash(log_msg)
    stream_link = f"{base_url}/watch/{file_id}/{file_name_encoded}?hash={hash_value}"
    online_link = f"{base_url}/{file_id}/{file_name_encoded}?hash={hash_value}"
    return stream_link, online_link, media_name, media_size

async def check_admin_privileges(client: Client, chat_id: int) -> bool:
    """Check if the bot has admin privileges in a chat."""
    try:
        chat = await client.get_chat(chat_id)
        if chat.type == 'private':
            return True
        member = await client.get_chat_member(chat_id, client.me.id)
        return member.status in ["administrator", "creator"]
    except Exception as e:
        await notify_owner(client, f"Error checking admin privileges in chat {chat_id}: {e}")
        return False

async def log_new_user(bot: Client, user_id: int, first_name: str):
    """Log new user."""
    try:
        if not await db.is_user_exist(user_id):
            await db.add_user(user_id)
            await notify_owner(bot, f"New User Alert! {first_name} (ID: {user_id}) has started the bot!")
    except Exception as e:
        await notify_owner(bot, f"Error logging new user {user_id}: {e}")

async def generate_dc_text(user: User) -> str:
    """Generate Data Center information text for a user."""
    dc_id = user.dc_id if user.dc_id is not None else "Unknown"
    return (
        f"🌐 **DC Info:**\n\n"
        f"👤 **User:** [{user.first_name}](tg://user?id={user.id})\n"
        f"🆔 **ID:** `{user.id}`\n"
        f"🌐 **Data Center:** `{dc_id}`"
    )

async def process_multiple_messages(
    client: Client, command_message: Message, reply_msg: Message, num_files: int
):
    """Process multiple media messages."""
    if not validate_file_count(num_files):
        await command_message.reply_text(f"⚠️ Please specify a number between {1} and {MAX_FILES_PER_COMMAND}.", quote=True)
        return

    chat_id = command_message.chat.id
    start_message_id = reply_msg.id
    end_message_id = start_message_id + num_files - 1
    message_ids = list(range(start_message_id, end_message_id + 1))

    try:
        messages = await client.get_messages(chat_id=chat_id, message_ids=message_ids)
        processed_count = 0
        download_links = []
        for msg in messages:
            if msg and msg.media:
                _, online_link, _, _ = await generate_media_links(msg)
                download_links.append(online_link)
                processed_count += 1
            else:
                await notify_owner(client, f"Skipped message {msg.id if msg else 'unknown'} in batch processing.")

        if download_links:
            links_text = "\n".join(download_links)
            await command_message.reply_text(
                f"📥 **Here are your {processed_count} combined download links:**\n\n`{links_text}`",
                quote=True,
                disable_web_page_preview=True
            )
        await command_message.reply_text(f"✅ **Processed {processed_count} files starting from the replied message.**", quote=True)

    except Exception as e:
        await notify_owner(client, f"Error in batch message processing: {e}")
        await command_message.reply_text("❌ An error occurred while processing multiple messages.", quote=True)
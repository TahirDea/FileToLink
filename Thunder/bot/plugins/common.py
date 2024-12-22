# Thunder/bot/plugins/common.py

import time
import asyncio
from typing import Tuple
from urllib.parse import quote_plus
from pyrogram import Client, filters
from pyrogram.errors import RPCError
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, User
from Thunder.bot import StreamBot
from Thunder.vars import Var
from Thunder.utils import db, notify_channel, handle_user_error, log_new_user
from Thunder.bot_operations import generate_dc_text
from Thunder.messages import get_help_message, get_about_message, get_welcome_message
from Thunder.constraints import BANNED_CHANNELS

@StreamBot.on_message(filters.command("start") & filters.private)
async def start_command(bot: Client, message: Message):
    """
    Handle the /start command in private chats.
    """
    try:
        if message.from_user:
            await log_new_user(bot, message.from_user.id, message.from_user.first_name)
        
        args = message.text.strip().split("_", 1)
        if len(args) == 1 or args[-1].lower() == "start":
            await message.reply_text(get_welcome_message())
        else:
            try:
                msg_id = int(args[-1])
                get_msg = await bot.get_messages(chat_id=Var.BIN_CHANNEL, message_ids=msg_id)
                if not get_msg:
                    raise ValueError("Message not found")
                file_name = get_name(get_msg)
                file_size = humanbytes(get_media_file_size(get_msg))
                stream_link, online_link, _, _ = await generate_media_links(get_msg)
                await send_links_to_user(bot, message, file_name, file_size, stream_link, online_link)
            except ValueError:
                await handle_user_error(message, "❌ **Invalid file identifier provided.**")
            except Exception as e:
                await handle_user_error(message, "❌ **Failed to retrieve file information.**")
                await notify_channel(bot, f"Error in start_command: {e}")
    except Exception as e:
        await handle_user_error(message, "🚨 **An unexpected error occurred.**")
        await notify_channel(bot, f"Error in start_command: {e}")

@StreamBot.on_message(filters.command("help") & filters.private)
async def help_command(bot: Client, message: Message):
    """
    Handle the /help command in private chats.
    """
    try:
        if message.from_user:
            await log_new_user(bot, message.from_user.id, message.from_user.first_name)
        await message.reply_text(get_help_message(), disable_web_page_preview=True)
    except Exception as e:
        await handle_user_error(message, "🚨 **An unexpected error occurred.**")
        await notify_channel(bot, f"Error in help_command: {e}")

@StreamBot.on_message(filters.command("about") & filters.private)
async def about_command(bot: Client, message: Message):
    """
    Handle the /about command in private chats.
    """
    try:
        if message.from_user:
            await log_new_user(bot, message.from_user.id, message.from_user.first_name)
        await message.reply_text(get_about_message(), disable_web_page_preview=True)
    except Exception as e:
        await handle_user_error(message, "🚨 **An unexpected error occurred.**")
        await notify_channel(bot, f"Error in about_command: {e}")

@StreamBot.on_message(filters.command("dc"))
async def dc_command(bot: Client, message: Message):
    """
    Handle the /dc command to provide Data Center information.
    """
    try:
        if message.from_user:
            await log_new_user(bot, message.from_user.id, message.from_user.first_name)

        args = message.text.strip().split(maxsplit=1)

        if len(args) > 1:
            query = args[1].strip()
            if query.startswith('@'):
                username = query
                try:
                    user = await bot.get_users(username)
                    dc_text = await generate_dc_text(user)
                    await message.reply_text(dc_text, disable_web_page_preview=True, reply_markup=get_view_profile_button(user.id), quote=True)
                except RPCError:
                    await handle_user_error(message, "❌ **Failed to retrieve user information.**")
                return

            elif query.isdigit():
                user_id_arg = int(query)
                try:
                    user = await bot.get_users(user_id_arg)
                    dc_text = await generate_dc_text(user)
                    await message.reply_text(dc_text, disable_web_page_preview=True, reply_markup=get_view_profile_button(user.id), quote=True)
                except RPCError:
                    await handle_user_error(message, "❌ **Failed to retrieve user information.**")
                return
            else:
                await handle_user_error(message, "❌ **Invalid argument.**")
                return

        # Check if the command is a reply to a message
        if message.reply_to_message and message.reply_to_message.from_user:
            user = message.reply_to_message.from_user
            dc_text = await generate_dc_text(user)
            await message.reply_text(dc_text, disable_web_page_preview=True, reply_markup=get_view_profile_button(user.id), quote=True)
            return

        # Default case: No arguments and not a reply, return the DC of the command issuer
        if message.from_user:
            user = message.from_user
            dc_text = await generate_dc_text(user)
            await message.reply_text(dc_text, disable_web_page_preview=True, reply_markup=get_view_profile_button(user.id), quote=True)
        else:
            await handle_user_error(message, "❌ **Unable to retrieve your information.**")
    except Exception as e:
        await handle_user_error(message, "🚨 **An unexpected error occurred.**")
        await notify_channel(bot, f"Error in dc_command: {e}")

@StreamBot.on_message(filters.command("ping") & filters.private)
async def ping_command(bot: Client, message: Message):
    """
    Handle the /ping command to check bot's response time.
    """
    try:
        start_time = time.time()
        response = await message.reply_text("🏓 Pong!")
        end_time = time.time()
        time_taken_ms = (end_time - start_time) * 1000
        await response.edit(f"🏓 **Pong!**\n⏱ **Response Time:** `{time_taken_ms:.3f} ms`")
    except Exception as e:
        await handle_user_error(message, "🚨 **An unexpected error occurred.**")
        await notify_channel(bot, f"Error in ping_command: {e}")
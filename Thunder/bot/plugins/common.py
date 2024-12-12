# Thunder/bot/plugins/common.py

import time
import asyncio
from urllib.parse import quote_plus

from pyrogram import Client, filters
from pyrogram.errors import RPCError
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User
)

from Thunder.bot import StreamBot
from Thunder.vars import Var
from Thunder.utils.database import Database
from Thunder.utils.human_readable import humanbytes
from Thunder.utils.file_properties import get_hash, get_media_file_size, get_name
from Thunder.utils.logger import logger

from Thunder.utils.shared import (
    notify_channel,
    handle_user_error,
    log_new_user,
    generate_media_links,
    send_links_to_user,
    log_request,
    check_admin_privileges,
    notify_owner,
    db,
    generate_links_ready_message,
    generate_links_keyboard
)
from Thunder.utils.constants import (
    INVALID_ARG_MSG,
    FAILED_USER_INFO_MSG,
    REPLY_DOES_NOT_CONTAIN_USER_MSG
)

async def generate_dc_text(user: User) -> str:
    dc_id = user.dc_id if user.dc_id is not None else "Unknown"
    return (
        f"🌐 **Data Center Information**\n\n"
        f"👤 **User:** [{user.first_name or 'User'}](tg://user?id={user.id})\n"
        f"🆔 **User ID:** `{user.id}`\n"
        f"🌐 **Data Center:** `{dc_id}`\n\n"
        "This is the data center where the specified user is hosted."
    )

@StreamBot.on_message(filters.command("start") & filters.private)
async def start_command(bot: Client, message: Message):
    try:
        if message.from_user:
            await log_new_user(bot, message.from_user.id, message.from_user.first_name)
        args = message.text.strip().split("_", 1)

        if len(args) == 1 or args[-1].lower() == "start":
            welcome_text = (
                "👋 **Welcome to the File to Link Bot!**\n\n"
                "I'm here to help you generate direct download and streaming links for your files.\n"
                "Simply send me any file, and I'll provide you with links.\n\n"
                "🔹 **Available Commands:**\n"
                "/help - How to use the bot\n"
                "/about - About the bot\n"
                "/ping - Check bot's response time\n\n"
                "Enjoy using the bot!"
            )
            await message.reply_text(text=welcome_text)
            logger.info(f"Sent welcome message to user {message.from_user.id}")
        else:
            try:
                msg_id = int(args[-1])
                get_msg = await bot.get_messages(chat_id=Var.BIN_CHANNEL, message_ids=msg_id)
                if not get_msg:
                    raise ValueError("Message not found")
                file_name = get_name(get_msg) or "Unknown File"
                file_size = humanbytes(get_media_file_size(get_msg))
                stream_link, online_link, media_name, media_size = await generate_media_links(get_msg)

                links_ready_message = await generate_links_ready_message(
                    media_name, media_size, online_link, stream_link
                )
                links_keyboard = generate_links_keyboard(stream_link, online_link)

                await message.reply_text(
                    text=links_ready_message,
                    disable_web_page_preview=True,
                    reply_markup=links_keyboard
                )
                logger.info(f"Provided links to user {message.from_user.id} for file_id {msg_id}")
            except ValueError:
                await handle_user_error(message, "❌ **Invalid file identifier provided.**")
                logger.warning(f"Invalid file ID by user {message.from_user.id}")
            except Exception as e:
                await handle_user_error(message, "❌ **Failed to retrieve file information.**")
                logger.error(f"Failed to retrieve file info: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error in start_command: {e}", exc_info=True)
        await handle_user_error(message, "🚨 **An unexpected error occurred.**")
        await notify_channel(bot, f"Error in start_command: {e}")

@StreamBot.on_message(filters.command("help") & filters.private)
async def help_command(bot: Client, message: Message):
    try:
        if message.from_user:
            await log_new_user(bot, message.from_user.id, message.from_user.first_name)
        help_text = (
            "ℹ️ **How to Use the File to Link Bot**\n\n"
            "🔹 **Generate Links:** Send me any file, I'll provide direct download and streaming links.\n"
            "🔹 **In Groups:** Use `/link` command by replying to a file.\n"
            "🔹 **In Channels:** Add me, I'll generate links for new posts.\n\n"
            "/about - Learn more\n"
            "/ping - Check response time\n"
        )
        await message.reply_text(text=help_text, disable_web_page_preview=True)
        logger.info(f"Sent help message to user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error in help_command: {e}", exc_info=True)
        await handle_user_error(message, "🚨 **An unexpected error occurred.**")
        await notify_channel(bot, f"Error in help_command: {e}")

@StreamBot.on_message(filters.command("about") & filters.private)
async def about_command(bot: Client, message: Message):
    try:
        if message.from_user:
            await log_new_user(bot, message.from_user.id, message.from_user.first_name)
        about_text = (
            "🤖 **About the File to Link Bot**\n\n"
            "This bot helps you generate direct download and streaming links for any file.\n\n"
            "🔹 **Features:**\n"
            "- Direct links for files\n"
            "- Supports all file types\n"
            "- Easy to use in private, groups, and channels\n"
        )
        await message.reply_text(text=about_text, disable_web_page_preview=True)
        logger.info(f"Sent about message to user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error in about_command: {e}", exc_info=True)
        await handle_user_error(message, "🚨 **An unexpected error occurred.**")
        await notify_channel(bot, f"Error in about_command: {e}")

@StreamBot.on_message(filters.command("dc"))
async def dc_command(bot: Client, message: Message):
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
                    dc_keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔍 View Profile", url=f"tg://user?id={user.id}")]
                    ])
                    await message.reply_text(dc_text, disable_web_page_preview=True, reply_markup=dc_keyboard, quote=True)
                    logger.info(f"Provided DC info for username {username}")
                except RPCError as e:
                    await handle_user_error(message, FAILED_USER_INFO_MSG)
                    logger.error(f"Failed for username {username}: {e}", exc_info=True)
                except Exception as e:
                    await handle_user_error(message, FAILED_USER_INFO_MSG)
                    logger.error(f"Failed for username {username}: {e}", exc_info=True)
                return

            elif query.isdigit():
                user_id_arg = int(query)
                try:
                    user = await bot.get_users(user_id_arg)
                    dc_text = await generate_dc_text(user)
                    dc_keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔍 View Profile", url=f"tg://user?id={user.id}")]
                    ])
                    await message.reply_text(dc_text, disable_web_page_preview=True, reply_markup=dc_keyboard, quote=True)
                    logger.info(f"Provided DC info for user ID {user_id_arg}")
                except RPCError as e:
                    await handle_user_error(message, FAILED_USER_INFO_MSG)
                    logger.error(f"Failed for user ID {user_id_arg}: {e}", exc_info=True)
                except Exception as e:
                    await handle_user_error(message, FAILED_USER_INFO_MSG)
                    logger.error(f"Failed for user ID {user_id_arg}: {e}", exc_info=True)
                return
            else:
                await handle_user_error(message, INVALID_ARG_MSG)
                logger.warning(f"Invalid argument in /dc: {query}")
                return

        if message.reply_to_message and message.reply_to_message.from_user:
            user = message.reply_to_message.from_user
            dc_text = await generate_dc_text(user)
            dc_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 View Profile", url=f"tg://user?id={user.id}")]
            ])
            await message.reply_text(dc_text, disable_web_page_preview=True, reply_markup=dc_keyboard, quote=True)
            logger.info(f"Provided DC info for replied user {user.id}")
            return

        if message.from_user:
            user = message.from_user
            dc_text = await generate_dc_text(user)
            dc_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 View Profile", url=f"tg://user?id={user.id}")]
            ])
            await message.reply_text(dc_text, disable_web_page_preview=True, reply_markup=dc_keyboard, quote=True)
            logger.info(f"Provided DC info for user {user.id}")
        else:
            await handle_user_error(message, "❌ **Unable to retrieve your information.**")
            logger.warning("Failed to retrieve info in /dc command.")
    except Exception as e:
        logger.error(f"Error in dc_command: {e}", exc_info=True)
        await handle_user_error(message, "🚨 **An unexpected error occurred.**")
        await notify_channel(bot, f"Error in dc_command: {e}")

@StreamBot.on_message(filters.command("ping") & filters.private)
async def ping_command(bot: Client, message: Message):
    try:
        start_time = time.time()
        response = await message.reply_text("🏓 Pong!")
        end_time = time.time()
        time_taken_ms = (end_time - start_time) * 1000
        await response.edit(f"🏓 **Pong!**\n⏱ **Response Time:** `{time_taken_ms:.3f} ms`")
        logger.info(f"Ping by user {message.from_user.id} in {time_taken_ms:.3f} ms")
    except Exception as e:
        logger.error(f"Error in ping_command: {e}", exc_info=True)
        await handle_user_error(message, "🚨 **An unexpected error occurred.**")
        await notify_channel(bot, f"Error in ping_command: {e}")

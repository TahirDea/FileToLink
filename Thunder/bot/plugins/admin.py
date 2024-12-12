# Thunder/bot/plugins/admin.py

import os
import sys
import time
import asyncio
import datetime
import shutil
import psutil
from typing import Tuple, List, Dict

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message
)

from Thunder.bot import StreamBot, multi_clients, work_loads
from Thunder.vars import Var
from Thunder import StartTime, __version__
from Thunder.utils.human_readable import humanbytes
from Thunder.utils.time_format import get_readable_time
from Thunder.utils.logger import logger, LOG_FILE
from Thunder.utils.shared import (
    notify_channel,
    notify_owner,
    handle_user_error,
    log_new_user,
    generate_media_links,
    send_links_to_user,
    log_request,
    check_admin_privileges,
    handle_flood_wait,
    generate_unique_id,
    db,
    generate_links_ready_message,
    generate_links_keyboard
)
from Thunder.utils.constants import (
    INVALID_ARG_MSG,
    FAILED_USER_INFO_MSG,
    REPLY_DOES_NOT_CONTAIN_USER_MSG
)
from Thunder.utils.decorators import command_handler

broadcast_ids: Dict[str, any] = {}

async def handle_broadcast_completion(
    message: Message,
    output: Message,
    failures: int,
    successes: int,
    total_users: int,
    start_time: float
):
    elapsed_time = get_readable_time(time.time() - start_time)
    await output.delete()
    message_text = (
        "✅ **Broadcast Completed** ✅\n\n"
        f"⏱️ **Duration:** {elapsed_time}\n\n"
        f"👥 **Total Users:** {total_users}\n\n"
        f"✅ **Success:** {successes}\n\n"
        f"❌ **Failed:** {failures}\n"
    )
    await message.reply_text(
        message_text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

@StreamBot.on_message(filters.command("users") & filters.private)
@command_handler(allowed_users=list(Var.OWNER_ID))
async def get_total_users(client: Client, message: Message):
    try:
        total_users = await db.total_users_count()
        await message.reply_text(
            f"👥 **Total Users in DB:** **{total_users}**",
            quote=True,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Error while fetching total users: {e}", exc_info=True)
        await message.reply_text(
            "🚨 **An error occurred while fetching the total users.**",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

@StreamBot.on_message(filters.command("broadcast") & filters.private)
@command_handler(allowed_users=list(Var.OWNER_ID))
async def broadcast_message(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("⚠️ **Please reply to a message to broadcast.**", quote=True)
        return

    try:
        output = await message.reply_text(
            "📢 **Broadcast Initiated**. Please wait until completion.",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

        all_users_cursor = db.get_all_users()
        all_users: List[Dict[str, int]] = []
        async for user in all_users_cursor:
            all_users.append(user)

        if not all_users:
            await output.edit("📢 **No Users Found**. Broadcast aborted.")
            return

        self_id = client.me.id
        start_time = time.time()
        successes, failures = 0, 0
        semaphore = asyncio.Semaphore(10)
        successes_lock = asyncio.Lock()
        failures_lock = asyncio.Lock()

        async def send_message_to_user(user_id: int):
            nonlocal successes, failures
            if not isinstance(user_id, int) or user_id == self_id:
                return

            async with semaphore:
                for attempt in range(3):
                    try:
                        if message.reply_to_message.text or message.reply_to_message.caption:
                            await client.send_message(
                                chat_id=user_id,
                                text=message.reply_to_message.text or message.reply_to_message.caption,
                                parse_mode=ParseMode.MARKDOWN,
                                disable_web_page_preview=True
                            )
                        elif message.reply_to_message.media:
                            await message.reply_to_message.copy(chat_id=user_id)

                        async with successes_lock:
                            successes += 1
                        break
                    except FloodWait as e:
                        await handle_flood_wait(e)
                        continue
                    except Exception as e:
                        logger.warning(f"Problem sending to {user_id}: {e}")
                        if "bot" in str(e).lower() or "self" in str(e).lower():
                            break
                        if "user" in str(e).lower() and "not found" in str(e).lower():
                            await db.delete_user(user_id)
                        async with failures_lock:
                            failures += 1
                        await asyncio.sleep(0.5)

        tasks = [send_message_to_user(int(user['id'])) for user in all_users]
        await asyncio.gather(*tasks)

        await handle_broadcast_completion(
            message,
            output,
            failures,
            successes,
            len(all_users),
            start_time
        )

    except Exception as e:
        error_text = f"Error during broadcast: {e}"
        logger.error(error_text, exc_info=True)
        await message.reply_text(
            "🚨 **An error occurred during the broadcast.**",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        await notify_channel(client, f"⚠️ Critical error during broadcast:\n{e}")

@StreamBot.on_message(filters.command("status") & filters.private)
@command_handler(allowed_users=list(Var.OWNER_ID))
async def show_status(client: Client, message: Message):
    try:
        uptime = get_readable_time(time.time() - StartTime)
        workloads_text = "📊 **Workloads per Bot:**\n\n"
        workloads = {
            f"🤖 Bot {c + 1}": load
            for c, (bot, load) in enumerate(
                sorted(work_loads.items(), key=lambda x: x[1], reverse=True)
            )
        }
        for bot_name, load in workloads.items():
            workloads_text += f"   {bot_name}: {load}\n"

        stats_text = (
            f"⚙️ **Server Status:** Running\n\n"
            f"🕒 **Uptime:** {uptime}\n\n"
            f"🤖 **Connected Bots:** {len(multi_clients)}\n\n"
            f"{workloads_text}\n"
            f"♻️ **Version:** {__version__}\n"
        )

        await message.reply_text(
            stats_text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Error displaying status: {e}", exc_info=True)
        await message.reply_text(
            "🚨 **An error occurred while retrieving the status.**",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

@StreamBot.on_message(filters.command("stats") & filters.private)
@command_handler(allowed_users=list(Var.OWNER_ID))
async def show_stats(client: Client, message: Message):
    try:
        current_time = get_readable_time(time.time() - StartTime)
        total, used, free = shutil.disk_usage('.')

        stats_text = (
            f"📊 **Bot Statistics** 📊\n\n"
            f"⏳ **Uptime:** {current_time}\n\n"
            f"💾 **Disk Space:**\n"
            f"   📀 **Total:** {humanbytes(total)}\n"
            f"   📝 **Used:** {humanbytes(used)}\n"
            f"   📭 **Free:** {humanbytes(free)}\n\n"
            f"📶 **Data Usage:**\n"
            f"   🔺 **Upload:** {humanbytes(psutil.net_io_counters().bytes_sent)}\n"
            f"   🔻 **Download:** {humanbytes(psutil.net_io_counters().bytes_recv)}\n\n"
            f"🖥️ **CPU Usage:** {psutil.cpu_percent(interval=0.5)}%\n"
            f"🧠 **RAM Usage:** {psutil.virtual_memory().percent}%\n"
            f"📦 **Disk Usage:** {psutil.disk_usage('/').percent}%\n"
        )
        await message.reply_text(
            stats_text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Error retrieving bot statistics: {e}", exc_info=True)
        await message.reply_text(
            "🚨 **Failed to retrieve the statistics.**",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

@StreamBot.on_message(filters.command("restart") & filters.private)
@command_handler(allowed_users=list(Var.OWNER_ID))
async def restart_bot(client: Client, message: Message):
    try:
        await message.reply_text(
            "🔄 **Restarting the bot...**",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        logger.info("Bot is restarting as per owner's request.")
        await asyncio.sleep(2)
        os.execv(sys.executable, [sys.executable, "-m", "Thunder"])
    except Exception as e:
        logger.error(f"Error during restart: {e}", exc_info=True)
        await message.reply_text(
            "🚨 **Failed to restart the bot.**",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

@StreamBot.on_message(filters.command("log") & filters.private)
@command_handler(allowed_users=list(Var.OWNER_ID))
async def send_logs(client: Client, message: Message):
    try:
        log_file_path = LOG_FILE
        if os.path.exists(log_file_path):
            if os.path.getsize(log_file_path) > 0:
                await message.reply_document(
                    document=log_file_path,
                    caption="📄 **Here are the latest logs:**",
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info("Sent log file to the owner.")
            else:
                await message.reply_text(
                    "⚠️ **The log file is empty.**",
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )
                logger.warning("Log file is empty; not sending.")
        else:
            await message.reply_text(
                "⚠️ **Log file not found.**",
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            logger.warning("Log file was requested but not found.")
    except Exception as e:
        logger.error(f"Error sending log file: {e}", exc_info=True)
        await message.reply_text(
            "🚨 **Failed to retrieve the log file.**",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

@StreamBot.on_message(filters.command("shell") & filters.private)
@command_handler(allowed_users=list(Var.OWNER_ID))
async def run_shell_command(client: Client, message: Message):
    try:
        if len(message.command) < 2:
            await message.reply_text(
                "⚠️ <b>Please provide a shell command to execute.</b>\n\n<b>Usage:</b> <code>/shell &lt;command&gt;</code>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            return

        shell_command = message.text.split(None, 1)[1]
        logger.info(f"Executing shell command: {shell_command}")

        process = await asyncio.create_subprocess_shell(
            shell_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()
        stdout, stderr = stdout.decode().strip(), stderr.decode().strip()

        stdout = html.escape(stdout)
        stderr = html.escape(stderr)

        response = ""
        if stdout:
            stdout = stdout[:4000]
            response += f"<b>STDOUT:</b>\n<pre>{stdout}</pre>"
        if stderr:
            stderr = stderr[:4000]
            if stdout:
                response += "\n\n"
            response += f"<b>STDERR:</b>\n<pre>{stderr}</pre>"
        if not stdout and not stderr:
            response = "⚠️ <b>No output returned from the command.</b>"

        await message.reply_text(
            response,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Error executing shell command: {e}", exc_info=True)
        await message.reply_text(
            "🚨 <b>Failed to execute the shell command.</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await notify_channel(client, f"Error in run_shell_command: {e}")

# Thunder/bot/plugins/admin.py

import time
import asyncio
from typing import Any, Dict, List
from pyrogram import Client, filters
from pyrogram.types import Message
from Thunder.bot import StreamBot
from Thunder.vars import Var
from Thunder.utils import db, notify_channel, notify_owner, handle_user_error, handle_critical_error
from Thunder.messages import get_broadcast_complete_message
from Thunder.bot_operations import handle_broadcast_completion
from Thunder.constraints import MAX_BROADCAST_USERS

@StreamBot.on_message(filters.command("users") & filters.private & filters.user(list(Var.OWNER_ID)))
async def get_total_users(client: Client, message: Message):
    """
    Retrieve and display the total number of users in the database for admin.
    """
    try:
        total_users = await db.total_users_count()
        await message.reply_text(f"👥 **Total Users in DB:** **{total_users}**", quote=True)
    except Exception as e:
        await handle_user_error(message, "🚨 **An error occurred while fetching the total users.**")
        await notify_owner(client, f"Error fetching total users: {e}")

@StreamBot.on_message(filters.command("broadcast") & filters.private & filters.user(list(Var.OWNER_ID)))
async def broadcast_message(client: Client, message: Message):
    """
    Broadcast a message to all users in the database for admin use only.
    """
    if not message.reply_to_message:
        await message.reply_text("⚠️ **Please reply to a message to broadcast.**", quote=True)
        return

    try:
        output = await message.reply_text(
            "📢 **Broadcast Initiated**. Please wait until completion.",
            parse_mode="Markdown"
        )

        all_users = await db.get_all_users()
        if not all_users:
            await output.edit("📢 **No Users Found**. Broadcast aborted.")
            return

        self_id = client.me.id
        start_time = time.time()
        successes, failures = 0, 0
        total_users = min(len(all_users), MAX_BROADCAST_USERS)  # Limit broadcasts to avoid overload

        semaphore = asyncio.Semaphore(10)
        successes_lock = asyncio.Lock()
        failures_lock = asyncio.Lock()

        async def send_message_to_user(user_id: int):
            nonlocal successes, failures
            if not isinstance(user_id, int) or user_id == self_id:
                return

            async with semaphore:
                try:
                    if message.reply_to_message.text or message.reply_to_message.caption:
                        await client.send_message(
                            chat_id=user_id,
                            text=message.reply_to_message.text or message.reply_to_message.caption,
                            parse_mode="Markdown"
                        )
                    elif message.reply_to_message.media:
                        await message.reply_to_message.copy(chat_id=user_id)
                    async with successes_lock:
                        successes += 1
                except Exception as e:
                    if "bot" in str(e).lower() or "self" in str(e).lower():
                        return
                    elif "user" in str(e).lower() and "not found" in str(e).lower():
                        await db.delete_user(user_id)
                    else:
                        async with failures_lock:
                            failures += 1

        tasks = [send_message_to_user(int(user['id'])) for user in all_users[:total_users]]
        await asyncio.gather(*tasks)

        await handle_broadcast_completion(message, output, failures, successes, total_users, start_time)

    except Exception as e:
        await message.reply_text("🚨 **An error occurred during the broadcast.**", parse_mode="Markdown")
        await notify_owner(client, f"Error during broadcast: {e}")

@StreamBot.on_message(filters.command("status") & filters.private & filters.user(list(Var.OWNER_ID)))
async def show_status(client: Client, message: Message):
    """
    Display the current status of the bot for admin use.
    """
    try:
        uptime = get_readable_time(time.time() - StartTime)
        bot_status = (
            f"⚙️ **Server Status:** Running\n\n"
            f"🕒 **Uptime:** {uptime}\n\n"
            f"🤖 **Connected Bots:** {len(multi_clients)}\n\n"
            f"♻️ **Version:** {__version__}\n"
        )
        await message.reply_text(bot_status, parse_mode="Markdown")
    except Exception as e:
        await handle_user_error(message, "🚨 **An error occurred while retrieving the status.**")
        await notify_owner(client, f"Error displaying status: {e}")

@StreamBot.on_message(filters.command("stats") & filters.private & filters.user(list(Var.OWNER_ID)))
async def show_stats(client: Client, message: Message):
    """
    Display detailed server statistics for admin use.
    """
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
        await message.reply_text(stats_text, parse_mode="Markdown")
    except Exception as e:
        await handle_user_error(message, "🚨 **Failed to retrieve the statistics.**")
        await notify_owner(client, f"Error retrieving bot statistics: {e}")

@StreamBot.on_message(filters.command("restart") & filters.private & filters.user(list(Var.OWNER_ID)))
async def restart_bot(client: Client, message: Message):
    """
    Restart the bot for admin use.
    """
    try:
        await message.reply_text("🔄 **Restarting the bot...**", parse_mode="Markdown")
        logger.info("Bot is restarting as per owner's request.")
        await asyncio.sleep(2)
        os.execv(sys.executable, [sys.executable, "-m", "Thunder"])
    except Exception as e:
        await handle_user_error(message, "🚨 **Failed to restart the bot.**")
        await notify_owner(client, f"Error during restart: {e}")

@StreamBot.on_message(filters.command("log") & filters.private & filters.user(list(Var.OWNER_ID)))
async def send_logs(client: Client, message: Message):
    """
    Send the latest log file to the bot owner.
    """
    try:
        log_file_path = LOG_FILE
        if os.path.exists(log_file_path):
            if os.path.getsize(log_file_path) > 0:
                await message.reply_document(
                    document=log_file_path,
                    caption="📄 **Here are the latest logs:**",
                    parse_mode="Markdown"
                )
            else:
                await message.reply_text("⚠️ **The log file is empty.**", parse_mode="Markdown")
        else:
            await message.reply_text("⚠️ **Log file not found.**", parse_mode="Markdown")
    except Exception as e:
        await handle_user_error(message, "🚨 **Failed to retrieve the log file.**")
        await notify_owner(client, f"Error sending log file: {e}")

@StreamBot.on_message(filters.command("shell") & filters.private & filters.user(list(Var.OWNER_ID)))
async def run_shell_command(client: Client, message: Message):
    """
    Execute a shell command on the server for admin use.
    """
    try:
        if len(message.command) < 2:
            await message.reply_text(
                "⚠️ **Please provide a shell command to execute.**\n\n**Usage:** `/shell <command>`",
                parse_mode="Markdown"
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

        response = ""
        if stdout:
            response += f"<b>STDOUT:</b>\n<pre>{stdout[:4000]}</pre>"
        if stderr:
            if response:
                response += "\n\n"
            response += f"<b>STDERR:</b>\n<pre>{stderr[:4000]}</pre>"
        if not stdout and not stderr:
            response = "⚠️ **No output returned from the command.**"

        await message.reply_text(response, parse_mode="HTML")
    except Exception as e:
        await handle_user_error(message, "🚨 **Failed to execute the shell command.**")
        await notify_owner(client, f"Error executing shell command: {e}")
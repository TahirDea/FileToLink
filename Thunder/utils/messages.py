# Thunder/utils/messages.py

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def get_welcome_message() -> str:
    """Return the welcome message for new users."""
    return (
        "👋 **Welcome to the File to Link Bot!**\n\n"
        "I'll generate links for your files. Send any file to get started.\n\n"
        "🔹 **Commands:**\n"
        "/help - Learn how to use me\n"
        "/about - Information about me\n"
        "/ping - Check my response time\n\n"
        "Let's share files easily!"
    )

def get_help_message() -> str:
    """Return the help message explaining bot usage."""
    return (
        "ℹ️ **How to Use:**\n\n"
        "🔹 Send files for link generation\n"
        "🔹 In groups, use `/link` command\n"
        "🔹 In channels, I auto-generate links\n\n"
        "🔸 **Commands:**\n"
        "/about - About this bot\n"
        "/ping - Test my responsiveness\n\n"
        "Need help? Contact support!"
    )

def get_about_message() -> str:
    """Return the about message for the bot."""
    return (
        "🤖 **About:**\n\n"
        "I'm here to help share files. Generate links for any type of file, usable in private chats, groups, or channels.\n\n"
        "🔹 **Features:**\n"
        "- Direct download links\n"
        "- Streaming links\n"
        "- Support for all file types\n\n"
        "Suggestions? Feel free to share!"
    )

def get_links_message(media_name: str, media_size: str, stream_link: str, online_link: str) -> str:
    """Format message for link sharing."""
    return (
        "🔗 **Here are your links!**\n\n"
        f"📄 **File:** `{media_name}`\n"
        f"📂 **Size:** `{media_size}`\n\n"
        f"📥 **Download:**\n`{online_link}`\n\n"
        f"🖥️ **Watch:**\n`{stream_link}`\n\n"
        "⏰ **Note:** These links work while the bot is active."
    )

def get_error_message(error: str) -> str:
    """Format error messages."""
    return f"❌ {error}\nPlease try again or contact support."

def get_broadcast_complete_message(duration: str, total_users: int, successes: int, failures: int) -> str:
    """Format broadcast completion message."""
    return (
        "✅ **Broadcast Complete** ✅\n\n"
        f"⏱️ **Time Taken:** {duration}\n\n"
        f"👥 **Total Users:** {total_users}\n\n"
        f"✅ **Successful:** {successes}\n\n"
        f"❌ **Failed:** {failures}\n"
    )

def get_link_buttons(stream_link: str, online_link: str) -> InlineKeyboardMarkup:
    """Create buttons for media links."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖥️ Watch", url=stream_link),
         InlineKeyboardButton("📥 Download", url=online_link)]
    ])

def get_view_profile_button(user_id: int) -> InlineKeyboardMarkup:
    """Create button to view user profile."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Profile", url=f"tg://user?id={user_id}")]
    ])
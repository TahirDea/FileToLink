from typing import List, Dict, Any

# Constants for constraints or limits within the bot
MAX_FILES_PER_COMMAND: int = 25
MIN_FILES_PER_COMMAND: int = 1
MAX_BROADCAST_USERS: int = 10000  # Example limit for broadcasting
MAX_MESSAGE_LENGTH: int = 4096  # Telegram's message length limit
MAX_FILE_SIZE: int = 2097152000  # 2GB file size limit for many platforms

# Banned channels list
BANNED_CHANNELS: List[int] = []  # Initially empty, can be populated from a config file or similar

# User roles or permissions dictionary
USER_ROLES: Dict[str, List[int]] = {
    'admin': [],  # List of admin user IDs
    'moderator': [],  # List of moderator user IDs
    'user': []  # All users by default, not explicitly defined here
}

def check_user_role(user_id: int, role: str) -> bool:
    """
    Check if a user has a specific role.

    Args:
        user_id (int): The ID of the user to check.
        role (str): The role to check against.

    Returns:
        bool: True if the user has the role, False otherwise.
    """
    if role not in USER_ROLES:
        return False
    return user_id in USER_ROLES[role]

def validate_file_count(count: int) -> bool:
    """
    Validate if the number of files is within acceptable limits.

    Args:
        count (int): Number of files to validate.

    Returns:
        bool: True if the count is valid, False otherwise.
    """
    return MIN_FILES_PER_COMMAND <= count <= MAX_FILES_PER_COMMAND

def validate_message_length(text: str) -> bool:
    """
    Check if the message length is within Telegram's limit.

    Args:
        text (str): The text of the message.

    Returns:
        bool: True if the message length is valid, False otherwise.
    """
    return len(text) <= MAX_MESSAGE_LENGTH

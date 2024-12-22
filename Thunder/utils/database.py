# Thunder/utils/database.py

import datetime
import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorCollection
from typing import Optional, List, Dict

class Database:
    """Database class for managing user and broadcast data."""

    def __init__(self, uri: str, database_name: str):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.users: AsyncIOMotorCollection = self.db.users
        self.broadcasts: AsyncIOMotorCollection = self.db.broadcasts

    @staticmethod
    def new_user(user_id: int) -> Dict:
        """Create a new user document."""
        return {'id': user_id, 'join_date': datetime.datetime.utcnow()}

    async def add_user(self, user_id: int):
        """Add a new user if they don't exist."""
        if not await self.is_user_exist(user_id):
            await self.users.insert_one(self.new_user(user_id))

    async def add_user_pass(self, user_id: int, ag_pass: str):
        """Add or update user's password."""
        await self.add_user(user_id)
        await self.users.update_one({'id': user_id}, {'$set': {'ag_p': ag_pass}})

    async def get_user_pass(self, user_id: int) -> Optional[str]:
        """Retrieve user's password."""
        user_pass = await self.users.find_one({'id': user_id}, {'ag_p': 1})
        return user_pass.get('ag_p') if user_pass else None

    async def is_user_exist(self, user_id: int) -> bool:
        """Check if user exists."""
        return bool(await self.users.find_one({'id': user_id}, {'_id': 1}))

    async def total_users_count(self) -> int:
        """Count total users."""
        return await self.users.count_documents({})

    async def get_all_users(self) -> List[Dict[str, int]]:
        """Retrieve all users."""
        return [{'id': user['id']} async for user in self.users.find({}, {'id': 1})]

    async def delete_user(self, user_id: int):
        """Delete a user."""
        await self.users.delete_one({'id': user_id})

    async def log_broadcast(self, broadcast_id: str, message: str, status: str):
        """Log broadcast details."""
        await self.broadcasts.insert_one({
            'id': broadcast_id, 'message': message, 'status': status,
            'timestamp': datetime.datetime.utcnow()
        })

    async def get_broadcast_history(self, limit: int = 10) -> List[Dict]:
        """Retrieve recent broadcast logs."""
        return await self.broadcasts.find().sort("timestamp", -1).limit(limit).to_list(length=limit)


# Initialize database instance
db = Database(Var.DATABASE_URL, Var.NAME)
from decouple import config
from motor.motor_asyncio import AsyncIOMotorClient
import os

# MongoDB Configuration
MONGODB_URL = config("MONGODB_URL", default="mongodb://localhost:27017")
DATABASE_NAME = config("DATABASE_NAME", default="vidyarthi_mitraa")

# JWT Configuration  
SECRET_KEY = config("SECRET_KEY", default="your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# File Upload Configuration
UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Create upload directories
os.makedirs(f"{UPLOAD_DIR}/images", exist_ok=True)
os.makedirs(f"{UPLOAD_DIR}/videos", exist_ok=True)
os.makedirs(f"{UPLOAD_DIR}/pdfs", exist_ok=True)
os.makedirs(f"{UPLOAD_DIR}/profiles", exist_ok=True)

# Database Connection
class Database:
    client: AsyncIOMotorClient = None
    database = None

db = Database()

async def get_database():
    return db.database

async def connect_to_mongo():
    db.client = AsyncIOMotorClient(MONGODB_URL)
    db.database = db.client[DATABASE_NAME]
    print("Connected to MongoDB")

async def close_mongo_connection():
    db.client.close()
    print("Disconnected from MongoDB")
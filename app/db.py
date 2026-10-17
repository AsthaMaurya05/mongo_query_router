# app/db.py
import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv()

MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://localhost:27017",
)

DEFAULT_DB_NAME = "shop_db"

client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000,
)


def get_db(db_name=DEFAULT_DB_NAME):
    """Return the requested database; defaults to shop_db."""
    return client[db_name]


def ping_mongodb():
    """Verify that MongoDB is reachable."""
    client.admin.command("ping")
    print("MongoDB ping successful!")


if __name__ == "__main__":
    try:
        ping_mongodb()
        print(f"Database ready: {get_db().name}")
    except PyMongoError as error:
        print(f"MongoDB connection failed: {error}")
        raise SystemExit(1)
    finally:
        client.close()

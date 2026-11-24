import os

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
FILENAME = os.getenv("FILENAME_LOG")
OTP_WEBHOOK_SECRET = os.getenv("OTP_WEBHOOK_SECRET")
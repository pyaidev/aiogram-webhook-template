from dotenv import load_dotenv
import os
import json

load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS = json.loads(os.getenv("ADMINS"))
IP = os.getenv("ip")
api_key = os.getenv("api_key")

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH")
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBAPP_HOST = os.getenv("WEBAPP_HOST")
WEBAPP_PORT = os.getenv("WEBAPP_PORT")

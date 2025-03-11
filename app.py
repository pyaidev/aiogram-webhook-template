from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from data.config import BOT_TOKEN, WEBHOOK_HOST, WEBHOOK_PATH, WEBHOOK_URL, WEBAPP_HOST, WEBAPP_PORT
import logging
import sys
from aiogram.fsm.storage.memory import MemoryStorage
from webhooks.message_webhook import setup_webhook_routes


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)


from handlers.users.start import router as start_router


bot = Bot(token=BOT_TOKEN)


WEBHOOK_HOST = WEBHOOK_HOST
WEBHOOK_PATH = WEBHOOK_PATH
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBAPP_HOST = WEBAPP_HOST
WEBAPP_PORT = int(WEBAPP_PORT)


async def on_startup(bot: Bot):
    logging.info(f"Setting webhook to {WEBHOOK_URL}")
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    logging.info("Webhook has been set")

    logging.info("Scheduler has been started")


async def on_shutdown(bot: Bot):
    logging.info("Removing webhook")
    await bot.delete_webhook()
    logging.info("Webhook has been removed")

def main():

    storage = MemoryStorage()

    dp = Dispatcher(storage=storage)

    logging.info("Registering routers")
    dp.include_router(start_router)
    

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    app = web.Application()
    
    logging.info("Setting up webhook handler")
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    

    webhook_handler.register(app, path=WEBHOOK_PATH)
    logging.info(f"Webhook handler registered at path {WEBHOOK_PATH}")
    
    # Set up our custom webhook routes
    setup_webhook_routes(app)
    

    setup_application(app, dp, bot=bot)
    

    logging.info(f"Starting web server at {WEBAPP_HOST}:{WEBAPP_PORT}")
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)

if __name__ == '__main__':
    logging.info("Starting bot application")
    main()
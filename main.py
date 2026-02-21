import asyncio
import logging

from aiogram import Bot, Dispatcher

import config
from bot.form_handlers import router as form_router
from bot.handlers import router
from services.form_service import FormService
from services.drive_service import DriveService


async def main():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()

    drive = DriveService(config.CREDENTIALS_PATH)

    form_service = FormService(drive, config.GOOGLE_DRIVE_FOLDER_ID)

    dp.include_router(form_router)
    dp.include_router(router)
    dp["drive"] = drive
    dp["root_folder_id"] = config.GOOGLE_DRIVE_FOLDER_ID
    dp["form_service"] = form_service

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

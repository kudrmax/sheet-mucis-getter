import asyncio
import logging

from aiogram import Bot, Dispatcher

import config
from bot.handlers import router
from services.drive_service import DriveService


async def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()

    drive = DriveService(config.CREDENTIALS_PATH)

    dp.include_router(router)
    dp["drive"] = drive
    dp["root_folder_id"] = config.GOOGLE_DRIVE_FOLDER_ID

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

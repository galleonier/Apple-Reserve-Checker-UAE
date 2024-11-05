import asyncio
import logging
import sys
import json

from aiohttp import ClientSession
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command
from aiogram.types import Message
from datetime import datetime, timedelta, timezone

with open("config.json") as config_file:
    config = json.load(config_file)

TOKEN = config["token"]
GROUP_ID_MAIN = config["group_id"]
PROXY = config["proxy"]
URL = config["url"]
MESSAGE_ID = config["message_id"]
START_TEXT = config["start_text"]
NOTIFY_TYPE = config["notify_type"]

with open("models.json") as models_file:
    models_data = json.load(models_file)
    pro_models = models_data["pro"]
    pro_max_models = models_data["pro_max"]

dp = Dispatcher()
stores_to_check = ["R597", "R596", "R595", "R706"]
store_names = {
    "R597": "Dubai - Dubai Mall",
    "R596": "Dubai - Mall of the Emirates",
    "R595": "Abu Dhabi - Yas Mall",
    "R706": "Abu Dhabi - Al Maryah Island"
}
availability_buffers = {store: {model_code: True for model_code in {**pro_models, **pro_max_models}} for store in stores_to_check}

async def fetch_data():
    async with ClientSession() as session:
        async with session.get(URL, proxy=PROXY) as response:
            if response.status == 200:
                return await response.json()
            return None

async def main_part(bot: Bot):
    dCode_buf = 0
    while True:
        try:
            data = await fetch_data()
            if data:
                dCode_now = data["updated"]
                if dCode_now != dCode_buf:
                    answer, updated = analyze_json(data)
                    if answer:
                        await send_telegram_message(bot, "\n".join(answer))
                    if updated:
                        await update_message_with_status(bot)
                    dCode_buf = dCode_now
            await asyncio.sleep(8)
        except Exception as e:
            print(f"Error {datetime.now()}: {e}")
            await asyncio.sleep(8)

async def update_message_with_status(bot: Bot) -> None:
    message_text = ""
    for model_code, model_name in {**pro_models, **pro_max_models}.items():
        for store in stores_to_check:
            icon = "🟢" if availability_buffers[store][model_code] else "🔴"
            message_text += icon
        abbrev_name = " ".join(word[0] for word in model_name.split(" - ")[1].split())
        message_text += f" -> {model_name.split(' - ')[0]} - {abbrev_name}\n"
    message_text += f"\nLast update time: {datetime.now(timezone(timedelta(hours=4))).strftime('%d.%m %H:%M')} (GMT+4)\n"
    await bot.edit_message_text(chat_id=GROUP_ID_MAIN, message_id=MESSAGE_ID, text=message_text)

def analyze_json(data):
    global availability_buffers
    changed_models = []
    have_update = False
    try:
        for store in stores_to_check:
            if store in data["stores"]:
                for model_code, model_name in {**pro_models, **pro_max_models}.items():
                    if model_code in data["stores"][store]:
                        availability = data["stores"][store][model_code]["availability"]["unlocked"]
                        if availability != availability_buffers[store][model_code]:
                            if availability and (model_code in pro_models if NOTIFY_TYPE == 0 else model_code in pro_max_models if NOTIFY_TYPE == 1 else True):
                                changed_models.append(f"{store_names.get(store, store)}: {model_name}")
                            availability_buffers[store][model_code] = availability
                            have_update = True
        return changed_models, have_update

    except Exception as e:
        logging.error(f"Error in analyze_json: {e}")
        return [], False

async def send_telegram_message(bot: Bot, message: str) -> None:
    await bot.send_message(chat_id=GROUP_ID_MAIN, text=message)

@dp.message(Command(commands=["start"]))
async def command_start_handler(message: Message) -> None:
    await message.answer(START_TEXT)

async def main() -> None:
    async with AiohttpSession() as session:
        bot = Bot(token=TOKEN, session=session)
        asyncio.create_task(main_part(bot))
        await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())

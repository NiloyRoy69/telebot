from fastapi import FastAPI
from dotenv import load_dotenv
import os
import datetime
import requests
from telegram import Bot
from telegram.constants import ParseMode
from dateutil import parser
import pytz
import time
import logging
from typing import List, Dict
import schedule
import threading
from calendar import month_name

# Load environment variables early
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
SHEET_URL = os.getenv("SHEET_URL")


class BirthdayBot:

    def __init__(self, bot_token: str, group_id: str, sheet_url: str):
        self.BOT_TOKEN = bot_token
        self.GROUP_ID = group_id
        self.SHEET_URL = sheet_url
        self.TIMEZONE = pytz.timezone("Asia/Dhaka")
        self.MESSAGE_DELAY = 1
        self.MAX_RETRIES = 3

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('birthday_bot.log'),
                logging.StreamHandler()
            ])
        self.logger = logging.getLogger(__name__)
        self.bot = Bot(token=self.BOT_TOKEN)

    def fetch_birthdays(self) -> List[Dict]:
        response = requests.get(self.SHEET_URL)
        return response.json()

    def get_monthly_birthdays(self) -> List[Dict]:
        current_month = datetime.datetime.now(self.TIMEZONE).month
        self.logger.info(f"📅 Checking birthdays for {month_name[current_month]}")
        birthdays = self.fetch_birthdays()
        monthly_birthdays = []

        for b in birthdays:
            name = b.get('name', '').strip()
            raw_birthday = b.get('birthday', '').strip()

            if not name or not raw_birthday:
                continue

            try:
                dt = parser.isoparse(raw_birthday).astimezone(self.TIMEZONE)
                if dt.month == current_month:
                    monthly_birthdays.append({'name': name, 'day': dt.day, 'month': dt.month})
            except Exception as e:
                self.logger.error(f"⚠️ Could not parse: {raw_birthday}, Error: {e}")

        monthly_birthdays.sort(key=lambda x: x['day'])
        return monthly_birthdays

    def send_monthly_birthday_list(self):
        monthly_birthdays = self.get_monthly_birthdays()
        current_month = datetime.datetime.now(self.TIMEZONE).month

        if not monthly_birthdays:
            message = "📅 There are no birthdays this month."
        else:
            message = f"🎉 <b>Birthdays in {month_name[current_month]}</b>:\n\n"
            for bday in monthly_birthdays:
                message += f"• {bday['name']} - <i>{bday['day']} {month_name[bday['month']]}</i>\n"
            message += "\nLet's celebrate together! 🎂🎉"

        try:
            self.bot.send_message(chat_id=self.GROUP_ID, text=message, parse_mode=ParseMode.HTML)
            self.logger.info("✅ Sent monthly birthday list")
        except Exception as e:
            self.logger.error(f"❌ Failed to send monthly birthday list: {e}")

    def check_daily_birthdays(self):
        today = datetime.datetime.now(self.TIMEZONE).strftime('%m-%d')
        self.logger.info(f"🔍 Checking birthdays for today (Asia/Dhaka): {today}")
        birthdays = self.fetch_birthdays()

        found = False
        for b in birthdays:
            name = b.get('name', '').strip()
            raw_birthday = b.get('birthday', '').strip()

            if not name or not raw_birthday:
                continue

            try:
                dt = parser.isoparse(raw_birthday).astimezone(self.TIMEZONE)
                bday = dt.strftime('%m-%d')
            except Exception as e:
                self.logger.error(f"⚠️ Could not parse: {raw_birthday}, Error: {e}")
                continue

            if bday == today:
                self.logger.info(f"🎂 It's {name}'s birthday today!")
                try:
                    self.bot.send_message(
                        chat_id=self.GROUP_ID,
                        text=f"🎂 <b>Happy Birthday, {name}!</b> 🎉\n\nWishing you a fantastic day! 🥳",
                        parse_mode=ParseMode.HTML)
                    time.sleep(self.MESSAGE_DELAY)
                    found = True
                except Exception as e:
                    self.logger.error(f"❌ Failed to send message for {name}: {e}")

        if not found:
            self.logger.info("❌ No birthdays today.")

    def run_scheduled_job(self):
        schedule.every().day.at("00:01").do(self.check_daily_birthdays)
        schedule.every().day.at("00:05").do(self.send_monthly_birthday_list).tag("monthly")
        self.logger.info("🎉 Birthday bot scheduler started.")

        while True:
            schedule.run_pending()
            time.sleep(60)

    def run_continuously(self):
        scheduler_thread = threading.Thread(target=self.run_scheduled_job)
        scheduler_thread.daemon = True
        scheduler_thread.start()

    def run_all(self):
        try:
            self.check_daily_birthdays()
            self.send_monthly_birthday_list()
            self.run_continuously()
        except Exception as e:
            self.logger.error(f"🔥 Critical error: {e}")


# Start FastAPI and scheduler
app = FastAPI()
birthday_bot = BirthdayBot(BOT_TOKEN, GROUP_ID, SHEET_URL)
has_started = False


@app.get("/date")
def get_date():
    birthday_bot.run_all()
    return {"msg": "Birthday bot is running."}


@app.on_event("startup")
def startup_event():
    global has_started
    if not has_started:
        birthday_bot.run_all()
        has_started = True

from fastapi import FastAPI

from dotenv import load_dotenv
import os
import datetime
import requests
from telegram import Bot, ParseMode
from dateutil import parser
import pytz
import time
import logging
from typing import List, Dict, Optional
import schedule
import threading
from calendar import month_name


class BirthdayBot:

  def __init__(self, bot_token: str, group_id: str, sheet_url: str):
    """Initialize the Birthday Bot with configuration"""
    self.BOT_TOKEN = bot_token
    self.GROUP_ID = group_id
    self.SHEET_URL = sheet_url
    self.TIMEZONE = pytz.timezone("Asia/Dhaka")
    self.MESSAGE_DELAY = 1  # seconds between messages
    self.MAX_RETRIES = 3

    # Set up logging
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[
                            logging.FileHandler('birthday_bot.log'),
                            logging.StreamHandler()
                        ])
    self.logger = logging.getLogger(__name__)

    # Initialize bot
    self.bot = Bot(token=self.BOT_TOKEN)

  def fetch_birthdays(self) -> List[Dict]:
    """Fetch birthdays from Google Sheets"""
    response = requests.get(self.SHEET_URL)
    return response.json()

  def get_monthly_birthdays(self) -> List[Dict]:
    """Get all birthdays occurring in the current month"""
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
          monthly_birthdays.append({
              'name': name,
              'day': dt.day,
              'month': dt.month
          })
      except Exception as e:
        self.logger.error(f"⚠️ Could not parse: {raw_birthday}, Error: {e}")
        continue

    # Sort birthdays by date (day of month)
    monthly_birthdays.sort(key=lambda x: x['day'])
    return monthly_birthdays

  def send_monthly_birthday_list(self):
    """Send formatted list of monthly birthdays to Telegram group"""
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
      self.bot.send_message(chat_id=self.GROUP_ID,
                            text=message,
                            parse_mode=ParseMode.HTML)
      self.logger.info("✅ Sent monthly birthday list")
    except Exception as e:
      self.logger.error(f"❌ Failed to send monthly birthday list: {e}")

  def check_daily_birthdays(self):
    """Check for birthdays matching today's date"""
    today = datetime.datetime.now(self.TIMEZONE).strftime('%m-%d')
    self.logger.info(f"🔍 Checking birthdays for today (Asia/Dhaka): {today}")

    birthdays = self.fetch_birthdays()
    self.logger.info("Fetched birthdays: %s", birthdays)

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
              text=
              f"🎂 <b>Happy Birthday, {name}!</b> 🎉\n\nWishing you a fantastic day! 🥳",
              parse_mode=ParseMode.HTML)
          time.sleep(self.MESSAGE_DELAY)
          found = True
        except Exception as e:
          self.logger.error(f"❌ Failed to send message for {name}: {e}")

    if not found:
      self.logger.info("❌ No birthdays today.")

  def run_scheduled_job(self):
    """Run the birthday check at scheduled time"""
    # Schedule to run every day at 12:01 AM Bangladesh time
    schedule.every().day.at("00:01").do(self.check_daily_birthdays)

    # Schedule to send monthly list on the 1st of each month at 00:05
    schedule.every().day.at("07:02").do(
        self.send_monthly_birthday_list).tag("monthly")

    self.logger.info(
        "🎉 Birthday bot scheduler started. Waiting for scheduled tasks...")

    # Keep the script running forever
    while True:
      schedule.run_pending()
      time.sleep(60)  # Check every minute if it's time to run

  def run_continuously(self):
    """Run the scheduler in a separate thread"""
    scheduler_thread = threading.Thread(target=self.run_scheduled_job)
    scheduler_thread.daemon = True  # Daemonize thread so it exits when main program exits
    scheduler_thread.start()

  def run_all(self):
    """Main method to run all birthday bot functionality"""
    try:
      # First run immediately
      self.check_daily_birthdays()
      self.send_monthly_birthday_list()  # Send monthly list on startup

      # Then start the scheduler for future runs
      self.run_continuously()

      # Keep the main thread alive
    except KeyboardInterrupt:
      self.logger.info("🛑 Bot stopped by user")
    except Exception as e:
      self.logger.error(f"🔥 Critical error: {e}")


# Load environment variables from .env file
load_dotenv()

# Access the variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
SHEET_URL = os.getenv("SHEET_URL")  # Create and run the birthday bot

app = FastAPI()
birthday_global = BirthdayBot(BOT_TOKEN, GROUP_ID, SHEET_URL)


@app.get("/")
def get_date():
  birthday_bot = birthday_global
  birthday_bot.run_all()

  return {"msg": "success"}

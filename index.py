import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import datetime
import time
import json
import os
from dotenv import load_dotenv
# Токен от BotFather

load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if ADMIN_ID:
    ADMIN_ID = int(ADMIN_ID)

bot = telebot.TeleBot(TOKEN)

DATA_FILE = "subscribers.json"
QUESTIONS_FILE = "questions.json"
CONFIRM_FILE = "confirmations.json"

# --- ЗАГРУЗКА ДАННЫХ ---
def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

subscribers = load_json(DATA_FILE, {})
questions = load_json(QUESTIONS_FILE, [])
confirmations = load_json(CONFIRM_FILE, [])

pending_name = set()
pending_question = set()

# Часовой пояс Алматы
tz = pytz.timezone("Asia/Almaty")

# --- КНОПКИ ---
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("📝 Сменить имя и фамилию"))
    markup.add(KeyboardButton("✅ Подтвердить заполнение часов"))
    markup.add(KeyboardButton("❓ Задать вопрос"))
    markup.add(KeyboardButton("/stop"))
    return markup

def start_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("/start"))
    return markup

# --- КОМАНДЫ ---
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = str(message.chat.id)
    # bot.send_message(chat_id, f"Твой chat_id: `{chat_id}`", parse_mode="Markdown")

    if chat_id in subscribers:
        bot.send_message(chat_id, f"С возвращением, {subscribers[chat_id]['name']} 👋", reply_markup=main_menu())
    else:
        bot.send_message(chat_id, "Привет 👋 Введи, пожалуйста, своё *Имя и Фамилию*:", parse_mode="Markdown",
                         reply_markup=ReplyKeyboardRemove())
        pending_name.add(chat_id)

@bot.message_handler(commands=['stop'])
def stop(message):
    chat_id = str(message.chat.id)
    if chat_id in subscribers:
        del subscribers[chat_id]
        save_json(DATA_FILE, subscribers)
        bot.send_message(chat_id, "Ты отписался от напоминаний ❌", reply_markup=start_menu())
    else:
        bot.send_message(chat_id, "Ты ещё не был подписан.", reply_markup=start_menu())

# --- ВВОД ИМЕНИ ---
@bot.message_handler(func=lambda m: str(m.chat.id) in pending_name)
def get_name(message):
    chat_id = str(message.chat.id)
    full_name = message.text.strip()
    if len(full_name.split()) < 2:
        bot.send_message(chat_id, "Пожалуйста, введи *Имя и Фамилию* через пробел ✍️", parse_mode="Markdown")
        return

    subscribers[chat_id] = {"name": full_name, "last_confirm": None}
    save_json(DATA_FILE, subscribers)
    pending_name.discard(chat_id)

    bot.send_message(chat_id, f"Спасибо, {full_name}! Теперь у тебя есть меню ⏰", reply_markup=main_menu())
    send_reminder(chat_id)

# --- ОБРАБОТКА КНОПОК ---
@bot.message_handler(func=lambda m: m.text == "📝 Сменить имя и фамилию")
def change_name(message):
    chat_id = str(message.chat.id)
    bot.send_message(chat_id, "Введи новые Имя и Фамилию ✍️", reply_markup=ReplyKeyboardRemove())
    pending_name.add(chat_id)

@bot.message_handler(func=lambda m: m.text == "✅ Подтвердить заполнение часов")
def confirm_from_menu(message):
    confirm_done_manual(message)

@bot.message_handler(func=lambda m: m.text == "❓ Задать вопрос")
def ask_question(message):
    chat_id = str(message.chat.id)
    bot.send_message(chat_id, "Напиши свой вопрос ✍️", reply_markup=ReplyKeyboardRemove())
    pending_question.add(chat_id)

# --- ОБРАБОТКА ВОПРОСОВ ---
@bot.message_handler(func=lambda m: str(m.chat.id) in pending_question)
def receive_question(message):
    chat_id = str(message.chat.id)
    user_name = subscribers.get(chat_id, {}).get("name", "Неизвестный")
    question_text = message.text.strip()

    entry = {"chat_id": chat_id, "name": user_name, "question": question_text}
    questions.append(entry)
    save_json(QUESTIONS_FILE, questions)

    pending_question.discard(chat_id)
    bot.send_message(chat_id, "Спасибо! Я передал твой вопрос администратору ✅", reply_markup=main_menu())

    if ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, f"❓ Вопрос от {user_name}:\n\n{question_text}")
        except Exception as e:
            print(f"Ошибка отправки админу: {e}")

# --- ПОДТВЕРЖДЕНИЕ ---
def send_reminder(chat_id):
    bot.send_message(chat_id, "⏰ Не забудь заполнить часы!", reply_markup=main_menu())

def confirm_done_manual(message):
    chat_id = str(message.chat.id)
    user_name = subscribers.get(chat_id, {}).get("name", "Неизвестный")
    username = message.from_user.username if message.from_user.username else "Без логина"

    today = datetime.datetime.now(tz)
    today_str = today.strftime("%d.%m.%Y")
    month_key = today.strftime("%m.%Y")

    entry = {
        "chat_id": chat_id,
        "name": user_name,
        "username": username,
        "date": today_str
    }
    confirmations.append(entry)
    save_json(CONFIRM_FILE, confirmations)

    if chat_id in subscribers:
        subscribers[chat_id]["last_confirm"] = month_key
        save_json(DATA_FILE, subscribers)

    bot.send_message(chat_id, "Отлично 👍 подтверждение принято.", reply_markup=main_menu())

    if ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, f"✅ {user_name} подтвердил заполнение часов.")
        except Exception as e:
            print(f"Ошибка при отправке админу: {e}")

# --- РАССЫЛКА ПО РАСПИСАНИЮ ---
def send_reminders():
    today = datetime.datetime.now(tz)
    month_key = today.strftime("%m.%Y")

    last_day = (today.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
    last_day_of_month = last_day.day

    if 27 <= today.day <= last_day_of_month:
        for chat_id, data in list(subscribers.items()):
            last_confirm = data.get("last_confirm")
            if last_confirm == month_key:  # уже подтвердил
                continue
            try:
                send_reminder(chat_id)
                time.sleep(0.5)
            except Exception as e:
                print(f"Ошибка отправки {chat_id}: {e}")

# --- ПЛАНИРОВЩИК ---
scheduler = BackgroundScheduler(timezone=tz)
scheduler.add_job(send_reminders, CronTrigger(hour=15, minute=0, timezone=tz))
scheduler.start()

print("Бот запущен...", flush=True)
bot.polling(none_stop=True)
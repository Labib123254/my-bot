import os
import threading
from flask import Flask
import telebot
from telebot import types

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running live 24/7!"

TOKEN = '8720565653:AAFltxQwffiTi5DmTwQKud-Wh1SkZlyVHm8'
bot = telebot.TeleBot(TOKEN, threaded=False)

ADMIN_ID = 6736272528
CHANNEL_USERNAME = "@incomex1954"
CHANNEL_URL = "https://t.me/incomex1954"
CHANNEL_ID = "-1004324671942"
ADMIN_SUPPORT_URL = "https://t.me/Xsupportadmin1"

users_db = {}
tasks_list = []

def get_user(uid):
    if uid not in users_db:
        users_db[uid] = {"balance": 0.0, "tasks": 0, "state": None, "method": None}
    return users_db[uid]

def main_kb():
    m = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    m.add('📖 কাজ ▸', '💵 ব্যালেন্স', 'টাকা উত্তোলন', 'My Referrals', '🧐 সাপোর্ট', '🧑‍💼 আমি নতুন')
    return m

def cancel_kb():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add('❌ বাতিল')
    return m

@bot.message_handler(commands=['start'])
def start_msg(message):
    bot.send_message(message.chat.id, "স্বাগতম! কাজ শুরু করতে নিচের অপশন ব্যবহার করুন:", reply_markup=main_kb())

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    uid = message.from_user.id
    text = message.text
    u = get_user(uid)

    if text == '❌ বাতিল':
        u['state'] = None
        bot.send_message(message.chat.id, "বাতিল করা হয়েছে।", reply_markup=main_kb())
        return

    if text == '💵 ব্যালেন্স':
        bot.reply_to(message, f"আপনার ব্যালেন্স: {u['balance']:.2f} BDT")

    elif text == '📖 কাজ ▸':
        bot.send_message(message.chat.id, "কাজের বিবরণ বা লিংক দিন:")

    elif text == 'টাকা উত্তোলন':
        u['state'] = 'WITHDRAW'
        bot.send_message(message.chat.id, "আপনার বিকাশ বা USDT নম্বর দিন:", reply_markup=cancel_kb())

    elif u['state'] == 'WITHDRAW':
        u['state'] = None
        bot.send_message(message.chat.id, "আপনার উইথড্র রিকোয়েস্ট সফলভাবে জমা হয়েছে!", reply_markup=main_kb())

    else:
        bot.send_message(message.chat.id, "দয়া করে নিচের মেনু থেকে অপশন সিলেক্ট করুন:", reply_markup=main_kb())

if __name__ == "__main__":
    def run_bot():
        try:
            bot.remove_webhook()
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print(e)

    t = threading.Thread(target=run_bot)
    t.daemon = True
    t.start()

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    

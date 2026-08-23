import os
import threading
import random
import string
from flask import Flask
import telebot
from telebot import types

# ১. Web Server
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running live 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ২. Bot setup
TOKEN = '8720565653:AAFltxQwffiTi5DmTwQKud-Wh1SkZlyVHm8'
bot = telebot.TeleBot(TOKEN)

users_db = {}

def get_user_data(user_id):
    if user_id not in users_db:
        users_db[user_id] = {"balance": 0.0, "referrals": 0, "state": None}
    return users_db[user_id]

def generate_random_username():
    name = "".join(random.choices(string.ascii_lowercase, k=8))
    num = "".join(random.choices(string.digits, k=5))
    return f"{name}{num}"

# মেনু কিবোর্ডসমূহ
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton('📖 কাজ ▸'),
        types.KeyboardButton('💵 ব্যালেন্স'),
        types.KeyboardButton('💰 টাকা উত্তোলন'),
        types.KeyboardButton('🎁 My Referrals'),
        types.KeyboardButton('🧐 সাপোর্ট'),
        types.KeyboardButton('🧑‍💼 আমি নতুন')
    )
    return markup

def category_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        types.KeyboardButton('📷 ইনস্টাগ্রাম কাজ >'),
        types.KeyboardButton('📧 Gmail কাজ'),
        types.KeyboardButton('📘 Facebook কাজ'),
        types.KeyboardButton('❌ বাতিল')
    )
    return markup

def instagram_sub_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        types.KeyboardButton('📷 ইনস্টাগ্রাম 2fa (৳2.70)'),
        types.KeyboardButton('⏮ ফিরে যান')
    )
    return markup

def task_action_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        types.KeyboardButton('🔑 2FA Set'),
        types.KeyboardButton('🤪 কিভাবে কাজ করব'),
        types.KeyboardButton('⏮ ফিরে যান')
    )
    return markup

def cancel_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(types.KeyboardButton('❌ বাতিল'))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    get_user_data(user_id)
    bot.send_message(
        message.chat.id, 
        f"হ্যালো {message.from_user.first_name}!\nনিচের মেনু থেকে একটি অপশন বেছে নিন:", 
        reply_markup=main_keyboard()
    )

@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    text = message.text

    # ১. প্রধান কাজের ক্যাটাগরি
    if text == '📖 কাজ ▸':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=category_keyboard(), parse_mode="Markdown")

    elif text == '📷 ইনস্টাগ্রাম কাজ >':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=instagram_sub_keyboard(), parse_mode="Markdown")

    # ২. ইনস্টাগ্রাম অ্যাকাউন্ট তৈরির টাস্ক জেনারেট
    elif text == '📷 ইনস্টাগ্রাম 2fa (৳2.70)':
        username = generate_random_username()
        msg_text = (
            f"👤 **Username:** `{username}`\n"
            f"🔐 **Password:** `vxebd@23`\n\n"
            f"📸 **উপরের ইউজারনেম এবং পাসওয়ার্ড দিয়ে অ্যাকাউন্ট খুলুন। তারপর নিচে 2FA Set বাটনে ক্লিক করুন 🤪**"
        )
        bot.send_message(message.chat.id, msg_text, reply_markup=task_action_keyboard(), parse_mode="Markdown")

    elif text == '🔑 2FA Set':
        user_data['state'] = 'WAITING_FOR_2FA'
        bot.send_message(message.chat.id, "📢 **2FA Key টি দিন:** 🎯", reply_markup=cancel_keyboard(), parse_mode="Markdown")

    # ৩. ২FA Key ইনপুট গ্রহণ
    elif user_data.get('state') == 'WAITING_FOR_2FA':
        if text == '❌ বাতিল':
            user_data['state'] = None
            bot.send_message(message.chat.id, "❌ **বাতিল করা হয়েছে।**", reply_markup=main_keyboard(), parse_mode="Markdown")
        else:
            user_data['state'] = None
            bot.send_message(message.chat.id, "✅ **আপনার ২FA সফলভাবে গৃহীত হয়েছে! তথ্য যাচাই করার পর ব্যালেন্স যোগ করা হবে।**", reply_markup=main_keyboard(), parse_mode="Markdown")

    # ৪. ফেরত এবং বাতিলের বাটনসমূহ
    elif text == '⏮ ফিরে যান':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=category_keyboard(), parse_mode="Markdown")

    elif text == '❌ বাতিল':
        bot.send_message(message.chat.id, "❌ **বাতিল করা হয়েছে।**", reply_markup=main_keyboard(), parse_mode="Markdown")

    # ৫. অন্যান্য মূল মেনু
    elif text == '💵 ব্যালেন্স':
        bal = user_data["balance"]
        bot.reply_to(message, f"👤 **আপনার প্রোফাইল:**\n\n💰 বর্তমান ব্যালেন্স: {bal} টাকা\n👥 মোট রেফারাল: {user_data['referrals']} জন", parse_mode="Markdown")

    elif text == '💰 টাকা উত্তোলন':
        bot.reply_to(message, "উত্তোলনের জন্য সর্বনিম্ন ব্যালেন্স ১০০ টাকা।")

    elif text == '🎁 My Referrals':
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        bot.reply_to(message, f"🔗 **আপনার রেফারাল লিংক:**\n{ref_link}\n\nপ্রতি সফল রেফারে পাবেন ১০ টাকা!", parse_mode="Markdown")

    elif text == '🧐 সাপোর্ট':
        bot.reply_to(message, "সাহায্যের জন্য অ্যাডমিন ইউজারনেমে যোগাযোগ করুন।")

    elif text == '🧑‍💼 আমি নতুন':
        bot.reply_to(message, "🔰 **নিয়ম:** প্রতিদিন কাজ করুন এবং বন্ধুদের রেফার করে আয় বাড়ান।", parse_mode="Markdown")

    elif text == '🤪 কিভাবে কাজ করব':
        bot.reply_to(message, "ইনস্টাগ্রামে অ্যাকাউন্ট তৈরি করে ২FA ব্যাকআপ কোড জমা দিন।")

# ৩. Execution
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    bot.infinity_polling()
    

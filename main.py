import os
import threading
from flask import Flask
import telebot
from telebot import types

# ১. Web Server (Render এর Port Active রাখার জন্য)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running live 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ২. Bot setup
TOKEN = '8720565653:AAFltxQwffiTi5DmT'
bot = telebot.TeleBot(TOKEN)

users_db = {}

def get_user_data(user_id):
    if user_id not in users_db:
        users_db[user_id] = {"balance": 0.0, "referrals": 0}
    return users_db[user_id]

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    get_user_data(user_id)
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_work = types.KeyboardButton('📖 কাজ ▸')
    btn_balance = types.KeyboardButton('💵 ব্যালেন্স')
    btn_withdraw = types.KeyboardButton('💰 টাকা উত্তোলন')
    btn_refer = types.KeyboardButton('🎁 My Referrals')
    btn_support = types.KeyboardButton('🧐 সাপোর্ট')
    btn_new = types.KeyboardButton('🧑‍💼 আমি নতুন')
    
    markup.add(btn_work, btn_balance, btn_withdraw, btn_refer, btn_support, btn_new)
    bot.send_message(message.chat.id, f"হ্যালো {message.from_user.first_name}!\nনিচের মেনু থেকে একটি অপশন বেছে নিন:", reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    text = message.text

    if text == '📖 কাজ ▸':
        bot.reply_to(message, "আপনার কাজ শীঘ্রই আসছে। সাথেই থাকুন!")
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

# ৩. Flask & Bot Execution
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    bot.infinity_polling()
    

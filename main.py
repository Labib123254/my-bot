import os
import io
import threading
import random
import string
from flask import Flask
import telebot
from telebot import types

# ১. Web Server setup
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

# আপনার চ্যানেল আইডি
CHANNEL_ID = -1004424525431

users_db = {}
tasks_list = []  # সব টাস্ক মেমোরিতে জমানোর জন্য

def get_user_data(user_id):
    if user_id not in users_db:
        users_db[user_id] = {
            "balance": 0.0, 
            "referrals": 0, 
            "state": None, 
            "withdraw_method": None, 
            "current_task": None,
            "generated_username": None,
            "generated_password": None,
            "task_type": None
        }
    return users_db[user_id]

def generate_random_username():
    names = ["Isabella Williams", "Sophia Brown", "Isabella Johnson", "Emma Davis", "Olivia Wilson"]
    selected_name = random.choice(names)
    num = "".join(random.choices(string.digits, k=4))
    return f"{selected_name}_{num}"

def generate_random_password():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

# --- কিবোর্ড বাটনসমূহ ---

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

def withdraw_methods_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton('Bkash'),
        types.KeyboardButton('Nagad'),
        types.KeyboardButton('Rocket'),
        types.KeyboardButton('❌ বাতিল')
    )
    return markup

# --- এডমিন কমান্ডসমূহ ---

@bot.message_handler(commands=['gettasks'])
def get_all_tasks_file(message):
    if not tasks_list:
        bot.reply_to(message, "⚠️ **এখনো কোনো টাস্ক জমা পড়েনি!**", parse_mode="Markdown")
        return
    
    file_content = "=== ALL SUBMITTED TASKS ===\n\n"
    for idx, item in enumerate(tasks_list, start=1):
        file_content += (
            f"[{idx}] User ID: {item['user_id']}\n"
            f"    Type: {item['type']}\n"
            f"    Name: {item['name']}\n"
            f"    Pass: {item['pass']}\n"
            f"    Submitted Data: {item['data']}\n"
            f"----------------------------------------\n"
        )
    
    file_data = io.BytesIO(file_content.encode('utf-8'))
    file_data.name = f"All_Tasks_Total_{len(tasks_list)}.txt"
    
    bot.send_document(message.chat.id, file_data, caption=f"📊 **মোট {len(tasks_list)} টি কাজের ফাইল একসাথে ডাউনলোড করা হয়েছে।**", parse_mode="Markdown")

@bot.message_handler(commands=['cleartasks'])
def clear_all_tasks(message):
    global tasks_list
    count = len(tasks_list)
    tasks_list = []
    bot.reply_to(message, f"🗑 **পূর্বের জমা হওয়া {count} টি টাস্ক ডাটা মুছে ফেলা হয়েছে।**", parse_mode="Markdown")

# --- মেসেজ হ্যান্ডলিং ---

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

    # ১. ২FA জমার পার্ট (ছবি অনুযায়ী ফরম্যাটে চ্যানেলে যাবে)
    if user_data.get('state') == 'WAITING_FOR_2FA':
        if text == '❌ বাতিল':
            user_data['state'] = None
            bot.send_message(message.chat.id, "❌ **টাস্ক বাতিল করা হয়েছে।**", reply_markup=main_keyboard(), parse_mode="Markdown")
        else:
            user_data['state'] = None
            
            acc_name = user_data.get('generated_username', 'Isabella Williams')
            acc_pass = user_data.get('generated_password', 'vxebd@23')
            task_type = user_data.get('task_type', '📷 ইনস্টাগ্রাম কাজ')
            
            # মেমোরিতে টাস্ক জমিয়ে রাখা
            tasks_list.append({
                "user_id": user_id,
                "type": task_type,
                "name": acc_name,
                "pass": acc_pass,
                "data": text
            })
            
            # ছবিতে দেখানো হুবহু ফরম্যাটে চ্যানেলে মেসেজ তৈরি
            channel_msg = (
                f"📥 **নতুন কাজ জমা পড়েছে!**\n\n"
                f"👤 **User ID:** `{user_id}`\n"
                f"📌 **Type:** {task_type}\n"
                f"🟢 **Name:** {acc_name}\n"
                f"🔐 **Pass:** {acc_pass}\n\n"
                f"📄 **Submitted Data:**\n{text}"
            )
            
            try:
                bot.send_message(CHANNEL_ID, channel_msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Channel Send Error: {e}")

            bot.send_message(message.chat.id, "✅ **আপনার ২FA কোডটি সফলভাবে জমা হয়েছে! এডমিন এটি যাচাই করে আপনার অ্যাকাউন্টে টাকা যোগ করে দেবে।**", reply_markup=main_keyboard(), parse_mode="Markdown")
        return

    # ২. উইথড্র পার্ট
    elif user_data.get('state') == 'WAITING_FOR_WITHDRAW_NUMBER':
        if text == '❌ বাতিল':
            user_data['state'] = None
            bot.send_message(message.chat.id, "❌ **উইথড্র বাতিল করা হয়েছে।**", reply_markup=main_keyboard(), parse_mode="Markdown")
        else:
            method = user_data.get('withdraw_method', 'N/A')
            amount = user_data['balance']
            user_data['state'] = None
            
            notify_msg = (
                f"💰 **নতুন উইথড্রয়াল রিকোয়েস্ট!**\n\n"
                f"👤 **ইউজার:** {message.from_user.first_name}\n"
                f"🆔 **আইডি:** `{user_id}`\n"
                f"💵 **পরিমাণ:** {amount} টাকা\n"
                f"🏦 **মেথড:** {method}\n"
                f"📱 **নম্বর:** `{text}`"
            )
            
            try:
                bot.send_message(CHANNEL_ID, notify_msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Channel Notification Error: {e}")

            bot.send_message(message.chat.id, f"✅ **আপনার {amount} টাকা উইথড্রয়াল রিকোয়েস্ট জমা হয়েছে!**", reply_markup=main_keyboard(), parse_mode="Markdown")
        return

    # --- মেনু অ্যাকশনসমূহ ---

    if text == '📖 কাজ ▸':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=category_keyboard(), parse_mode="Markdown")

    elif text == '📷 ইনস্টাগ্রাম কাজ >':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=instagram_sub_keyboard(), parse_mode="Markdown")

    elif text == '📷 ইনস্টাগ্রাম 2fa (৳2.70)':
        username = generate_random_username()
        password = generate_random_password()
        
        user_data['generated_username'] = username
        user_data['generated_password'] = password
        user_data['task_type'] = "📷 ইনস্টাগ্রাম কাজ"
        
        msg_text = (
            f"👤 **Name:** `{username}`\n"
            f"🔐 **Pass:** `{password}`\n\n"
            f"📸 **উপরের নেম এবং পাসওয়ার্ড দিয়ে অ্যাকাউন্ট খুলুন। তারপর নিচে 2FA Set বাটনে ক্লিক করুন 🤪**"
        )
        bot.send_message(message.chat.id, msg_text, reply_markup=task_action_keyboard(), parse_mode="Markdown")

    elif text == '🔑 2FA Set':
        user_data['state'] = 'WAITING_FOR_2FA'
        bot.send_message(message.chat.id, "📢 **2FA Key টি দিন:** 🎯", reply_markup=cancel_keyboard(), parse_mode="Markdown")

    elif text == '💰 টাকা উত্তোলন':
        if user_data['balance'] < 50:
            bot.reply_to(message, f"❌ **আপনার ব্যালেন্স পর্যাপ্ত নয়!**\nবর্তমান ব্যালেন্স: {user_data['balance']} টাকা।\nসর্বনিম্ন উইথড্র: ৫০ টাকা।")
        else:
            user_data['state'] = 'SELECT_WITHDRAW_METHOD'
            bot.send_message(message.chat.id, "🏦 **পেমেন্ট মেথড সিলেক্ট করুন:**", reply_markup=withdraw_methods_keyboard(), parse_mode="Markdown")

    elif text in ['Bkash', 'Nagad', 'Rocket']:
        user_data['withdraw_method'] = text
        user_data['state'] = 'WAITING_FOR_WITHDRAW_NUMBER'
        bot.send_message(message.chat.id, f"📱 **আপনার {text} নম্বরটি লিখে পাঠান:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")

    elif text == '⏮ ফিরে যান':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=category_keyboard(), parse_mode="Markdown")

    elif text == '❌ বাতিল':
        user_data['state'] = None
        bot.send_message(message.chat.id, "❌ **বাতিল করা হয়েছে।**", reply_markup=main_keyboard(), parse_mode="Markdown")

    elif text == '💵 ব্যালেন্স':
        bal = user_data["balance"]
        bot.reply_to(message, f"👤 **আপনার প্রোফাইল:**\n\n💰 বর্তমান ব্যালেন্স: {bal} টাকা\n👥 মোট রেফারাল: {user_data['referrals']} জন", parse_mode="Markdown")

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
    

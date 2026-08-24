import os
import io
import threading
import random
import string
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

def get_user_data(user_id):
    if user_id not in users_db:
        users_db[user_id] = {
            "balance": 0.0, 
            "total_income": 0.0,
            "completed_tasks": 0,
            "pending_tasks": 0,
            "referrals": 0, 
            "refer_income": 0.0,
            "referred_by": None,
            "state": None, 
            "withdraw_method": None, 
            "generated_username": None,
            "generated_password": None,
            "task_type": None
        }
    return users_db[user_id]

def check_user_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['member', 'creator', 'administrator']:
            return True
    except Exception as e:
        print(f"Sub Check Error: {e}")
    return False

def generate_random_username():
    names = ["Isabella Williams", "Sophia Brown", "Isabella Johnson", "Emma Davis", "Olivia Wilson"]
    selected_name = random.choice(names)
    num = "".join(random.choices(string.digits, k=4))
    return f"{selected_name}_{num}"

def generate_random_password():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

# --- Keyboards ---
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton('📖 কাজ ▸'),
        types.KeyboardButton('💵 ব্যালেন্স'),
        types.KeyboardButton('টাকা উত্তোলন'),
        types.KeyboardButton('My Referrals'),
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

def fb_task_action_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        types.KeyboardButton('🍪 Cookies দিন'),
        types.KeyboardButton('🤪 কিভাবে কাজ করব'),
        types.KeyboardButton('⏮ ফিরে যান')
    )
    return markup

def cancel_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(types.KeyboardButton('❌ বাতিল'))
    return markup

def withdraw_methods_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        types.KeyboardButton('USDT (BEP-20) -> সর্বনিম্ন: 0.3(-0.05)'),
        types.KeyboardButton('বিকাশ (Personal) -> সর্বনিম্ন: ৫০ টাকা'),
        types.KeyboardButton('মোবাইল রিচার্জ -> সর্বনিম্ন: ৩০ টাকা'),
        types.KeyboardButton('❌ বাতিল')
    )
    return markup

def sub_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Subscribe to channel", url=CHANNEL_URL))
    markup.add(types.InlineKeyboardButton("✅ Check subscription", callback_data="check_sub"))
    return markup

# --- Admin Commands ---
@bot.message_handler(commands=['gettasks'])
def get_all_tasks_file(message):
    if message.from_user.id != ADMIN_ID:
        return
    if not tasks_list:
        bot.reply_to(message, "⚠️ কোনো টাস্ক জমা পড়েনি!")
        return
    
    file_content = "=== ALL TASKS ===\n\n"
    for idx, item in enumerate(tasks_list, start=1):
        file_content += f"[{idx}] User ID: {item['user_id']}\nType: {item['type']}\nName: {item['name']}\nPass: {item['pass']}\nData: {item['data']}\n--------------------\n"
    
    file_data = io.BytesIO(file_content.encode('utf-8'))
    file_data.name = f"Tasks_{len(tasks_list)}.txt"
    bot.send_document(message.chat.id, file_data, caption=f"📊 মোট {len(tasks_list)} টি টাস্ক ফাইল।")

@bot.message_handler(commands=['cleartasks'])
def clear_all_tasks(message):
    if message.from_user.id != ADMIN_ID:
        return
    global tasks_list
    count = len(tasks_list)
    tasks_list = []
    bot.reply_to(message, f"🗑 {count} টি টাস্ক মুছে ফেলা হয়েছে।")

@bot.message_handler(commands=['addbalance'])
def add_user_balance(message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "⚠️ নিয়ম: `/addbalance <user_id> <amount>`", parse_mode="Markdown")
        return
    try:
        target_id = int(args[1])
        amount = float(args[2])
        target_user = get_user_data(target_id)
        target_user['balance'] += amount
        target_user['total_income'] += amount
        target_user['completed_tasks'] += 1
        
        bot.reply_to(message, f"✅ User ID: `{target_id}` এ {amount} BDT যোগ করা হয়েছে।", parse_mode="Markdown")
        try:
            bot.send_message(target_id, f"✅ আপনার টাস্ক এপ্রুভ হয়েছে!\n💰 যুক্ত হয়েছে: {amount:.2f} BDT")
        except:
            pass
    except ValueError:
        bot.reply_to(message, "⚠️ সঠিক আইডি বা পরিমাণ দিন।")

@bot.message_handler(commands=['sendmsg'])
def send_custom_message(message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        bot.reply_to(message, "⚠️ নিয়ম: `/sendmsg <user_id> <message>`")
        return
    try:
        bot.send_message(int(args[1]), f"📥 **অ্যাডমিনের মেসেজ:**\n\n{args[2]}", parse_mode="Markdown")
        bot.reply_to(message, "✅ মেসেজ পাঠানো হয়েছে।")
    except Exception as e:
        bot.reply_to(message, f"❌ ত্রুটি: {e}")

# --- Start & Subs ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    if not check_user_subscription(user_id):
        bot.send_message(message.chat.id, f"📢 বোট ব্যবহার করতে আমাদের চ্যানেলে জয়েন করুন: {CHANNEL_USERNAME}", reply_markup=sub_inline_keyboard())
    else:
        bot.send_message(message.chat.id, f"🥰 স্বাগতম, {first_name}!\nকাজ শুরু করতে নিচের অপশনগুলো ব্যবহার করুন 🔽", reply_markup=main_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def verify_subscription(call):
    user_id = call.from_user.id
    if check_user_subscription(user_id):
        bot.answer_callback_query(call.id, "✅ সাবস্ক্রিপশন নিশ্চিত করা হয়েছে!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, "🥰 স্বাগতম! অপশন সিলেক্ট করুন 🔽", reply_markup=main_keyboard())
    else:
        bot.answer_callback_query(call.id, "❌ আপনি এখনো চ্যানেলে জয়েন করেননি!", show_alert=True)

# --- Main Message Handler ---
@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    user_id = message.from_user.id
    text = message.text
    user_data = get_user_data(user_id)

    if text == '❌ বাতিল':
        user_data['state'] = None
        bot.send_message(message.chat.id, "❌ বাতিল করা হয়েছে।", reply_markup=main_keyboard())
        return

    current_state = user_data.get('state')

    if current_state in ['WAITING_FOR_2FA', 'WAITING_FOR_FB_COOKIES']:
        user_data['state'] = None
        acc_name = user_data.get('generated_username', 'User')
        acc_pass = user_data.get('generated_password', '123456')
        task_type = user_data.get('task_type', 'Task')
        
        user_data['pending_tasks'] += 1
        tasks_list.append({"user_id": user_id, "type": task_type, "name": acc_name, "pass": acc_pass, "data": text})
        
        try:
            bot.send_message(CHANNEL_ID, f"📥 নতুন কাজ জমা পড়েছে!\n👤 ID: `{user_id}`\n📌 Type: {task_type}\n🟢 Name: {acc_name}\n🔐 Pass: {acc_pass}\n📄 Data:\n{text}", parse_mode="Markdown")
        except:
            pass

        bot.send_message(message.chat.id, "✅ **Rcv**\n\nএটার টাকা খুব শীঘ্রই চেক করে আপনার ব্যালেন্সে এড করা হবে", reply_markup=main_keyboard(), parse_mode="Markdown")
        return

    if text == '📖 কাজ ▸':
        bot.send_message(message.chat.id, "🟣 সিলেক্ট করুন:", reply_markup=category_keyboard())
    elif text == '📷 ইনস্টাগ্রাম কাজ >':
        bot.send_message(message.chat.id, "🟣 সিলেক্ট করুন:", reply_markup=instagram_sub_keyboard())
    elif text == '📘 Facebook কাজ':
        u, p = generate_random_username(), generate_random_password()
        user_data.update({'generated_username': u, 'generated_password': p, 'task_type': "📘 Facebook কাজ"})
        bot.send_message(message.chat.id, f"👤 First name: {u.split('_')[0]}\n🔐 Password: `{p}`\n\n📘 অ্যাকাউন্ট খুলে নিচে Cookies দিন বাটনে চাপ দিন 🤪", reply_markup=fb_task_action_keyboard(), parse_mode="Markdown")
    elif text == '📷 ইনস্টাগ্রাম 2fa (৳2.70)':
        u, p = generate_random_username(), generate_random_password()
        user_data.update({'generated_username': u, 'generated_password': p, 'task_type': "📷 ইনস্টাগ্রাম কাজ"})
        bot.send_message(message.chat.id, f"👤 Name: `{u}`\n🔐 Pass: `{p}`\n\n📸 অ্যাকাউন্ট খুলে নিচে 2FA Set বাটনে ক্লিক করুন 🤪", reply_markup=task_action_keyboard(), parse_mode="Markdown")
    elif text == '🔑 2FA Set':
        user_data['state'] = 'WAITING_FOR_2FA'
        bot.send_message(message.chat.id, "📢 **2FA Key টি দিন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    elif text == '🍪 Cookies দিন':
        user_data['state'] = 'WAITING_FOR_FB_COOKIES'
        bot.send_message(message.chat.id, "🍪 **ফেসবুক কুকিজটি দিন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    elif text == 'টাকা উত্তোলন':
        bot.send_message(message.chat.id, "💰 টাকা তোলার মাধ্যম সিলেক্ট করুন:", reply_markup=withdraw_methods_keyboard())
    elif text in ['USDT (BEP-20) -> সর্বনিম্ন: 0.3(-0.05)', 'বিকাশ (Personal) -> সর্বনিম্ন: ৫০ টাকা', 'মোবাইল রিচার্জ -> সর্বনিম্ন: ৩০ টাকা']:
        user_data.update({'withdraw_method': text, 'state': 'WAITING_FOR_WITHDRAW_NUMBER'})
        bot.send_message(message.chat.id, "📱 আপনার সঠিক নম্বর বা অ্যাড্রেসটি লিখে পাঠান:", reply_markup=cancel_keyboard())
    elif current_state == 'WAITING_FOR_WITHDRAW_NUMBER':
        user_data['state'] = None
        try:
            bot.send_message(CHANNEL_ID, f"💰 নতুন উইথড্রয়াল রিকোয়েস্ট!\n👤 ID: `{user_id}`\n💵 Amount: {user_data['balance']} TK\n🏦 Method: {user_data['withdraw_method']}\n📱 Info: `{text}`", parse_mode="Markdown")
        except:
            pass
        bot.send_message(message.chat.id, "✅ আপনার উইথড্রয়াল রিকোয়েস্ট সফলভাবে জমা হয়েছে!", reply_markup=main_keyboard())
    elif text == '💵 ব্যালেন্স':
        bal = user_data["balance"]
        total_inc = user_data["total_income"]
        comp_tasks = user_data["completed_tasks"]
        pend_tasks = user_data["pending_tasks"]
        balance_msg = (
            f"💵 **আপনার ব্যালেন্স**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💸 **ব্যালেন্স:** {bal:.2f} BDT\n"
            f"⏳ **পেন্ডিং (উইথড্র):** 0.00 BDT\n"
            f"💰 **Total Income:** {total_inc:.2f} BDT\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✅ **সম্পন্ন কাজ:** {comp_tasks} টি\n"
            f"⏳ **রিভিউতে আছে:** {pend_tasks} টি"
        )
        bot.reply_to(message, balance_msg, parse_mode="Markdown")
    elif text == 'My Referrals':
        ref_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        bot.send_message(message.chat.id, f"🎁 **My Referrals**\n👤 Total Refer: {user_data['referrals']}\n🔗 Link:\n{ref_link}", parse_mode="Markdown")
    elif text == '🧐 সাপোর্ট':
        bot.send_message(message.chat.id, "সাপোর্টের জন্য নিচের লিঙ্কে যোগাযোগ করুন:", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🛠️ এডমিন সাপোর্ট", url=ADMIN_SUPPORT_URL)))
    elif text == '🧑‍💼 আমি নতুন':
        bot.reply_to(message, "🔰 প্রতিদিন কাজ করুন এবং বন্ধুদের রেফার করে আয় বাড়ান।")
    elif text == '⏮ ফিরে যান':
        bot.send_message(message.chat.id, "🟣 সিলেক্ট করুন:", reply_markup=category_keyboard())
    else:
        bot.send_message(message.chat.id, "দয়া করে নিচের মেনু থেকে অপশন ব্যবহার করুন:", reply_markup=main_keyboard())

if __name__ == "__main__":
    def run_bot():
        try:
            bot.remove_webhook()
            bot.infinity_polling(skip_pending=True, interval=1, timeout=20)
        except Exception as e:
            print(e)

    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
                         

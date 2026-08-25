import os
import io
import threading
import random
import string
import psycopg2
import psycopg2.extras
from flask import Flask, request
import telebot
from telebot import types

# ১. Web Server setup (Render-এর জন্য)
app = Flask(__name__)

# ২. Bot setup
TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN, threaded=False)

RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', '')

ADMIN_USERNAMES = ["Trillionaire_9"]

# Supabase Database Connection String
DATABASE_URL = "postgresql://postgres:Labib3305##@db.vcljsquskcyvkyavmuce.supabase.co:5432/postgres"

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
    return conn

# ডাটাবেজে টেবিল তৈরি (যদি না থাকে)
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # ইউজার টেবিল
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                balance REAL DEFAULT 0.0,
                total_income REAL DEFAULT 0.0,
                completed_tasks INT DEFAULT 0,
                pending_tasks INT DEFAULT 0,
                referrals INT DEFAULT 0,
                refer_income REAL DEFAULT 0.0,
                referred_by BIGINT DEFAULT NULL,
                state TEXT DEFAULT NULL,
                withdraw_method TEXT DEFAULT NULL,
                withdraw_address TEXT DEFAULT NULL,
                generated_username TEXT DEFAULT NULL,
                generated_password TEXT DEFAULT NULL,
                task_type TEXT DEFAULT NULL
            )
        ''')
        
        # সাবমিট করা টাস্ক সংরক্ষণের জন্য নতুন টেবিল
        cur.execute('''
            CREATE TABLE IF NOT EXISTS submitted_tasks (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                task_type TEXT,
                acc_name TEXT,
                acc_pass TEXT,
                task_data TEXT
            )
        ''')
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Database Initialization Error: {e}")

init_db()

def is_admin(message):
    username = message.from_user.username
    if username and username in ADMIN_USERNAMES:
        return True
    return False

# চ্যানেল কনফিগারেশন
CHANNEL_USERNAME = "@INCOMEXSUPPORT"  
CHANNEL_URL = "https://t.me/INCOMEXSUPPORT"
ADMIN_SUPPORT_URL = "https://t.me/Xsupportadmin1"

def get_user_data(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    
    if not row:
        cur.execute('''
            INSERT INTO users (user_id, balance, total_income, completed_tasks, pending_tasks, referrals, refer_income)
            VALUES (%s, 0.0, 0.0, 0, 0, 0, 0.0)
        ''', (user_id,))
        conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        
    cur.close()
    conn.close()
    return dict(row)

def update_user_data(user_id, kwargs):
    conn = get_db_connection()
    cur = conn.cursor()
    set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
    values = list(kwargs.values()) + [user_id]
    cur.execute(f"UPDATE users SET {set_clause} WHERE user_id = %s", values)
    conn.commit()
    cur.close()
    conn.close()

def check_user_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['member', 'creator', 'administrator']:
            return True
        else:
            return False
    except Exception as e:
        return False

def generate_random_username():
    names = ["Isabella Williams", "Sophia Brown", "Isabella Johnson", "Emma Davis", "Olivia Wilson"]
    selected_name = random.choice(names)
    num = "".join(random.choices(string.digits, k=4))
    return f"{selected_name}_{num}"

def generate_random_password():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

# --- কিবোর্ড বাটনসমূহ ---

def subscription_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 Subscribe to channel", url=CHANNEL_URL),
        types.InlineKeyboardButton("✅ Check subscription", callback_data="check_sub")
    )
    return markup

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

def fb_sub_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        types.KeyboardButton('0 fnd cookies | 4.00 ৳'),
        types.KeyboardButton('⏮ ফিরে যান')
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
        types.KeyboardButton('🍪 কুকিজ দিন'),
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
        types.KeyboardButton('মোবাইল রিচার্জ -> সর্বনিম্ন: ৩০(-৫)'),
        types.KeyboardButton('বিকাশ -> সর্বনিম্ন: ৫০ (-⁵)'),
        types.KeyboardButton('❌ বাতিল')
    )
    return markup

# --- ফ্লাস্ক রুট এবং ওয়েব হুক কনফিগারেশন ---

@app.route('/')
def home():
    return "Bot is running live via Webhook!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    else:
        return "Invalid Data", 403

# --- এডমিন কমান্ডসমূহ (ডাটাবেজ যুক্ত) ---

@bot.message_handler(commands=['gettasks'])
def get_all_tasks_file(message):
    if not is_admin(message):
        bot.reply_to(message, "❌ অনুমতি নেই।")
        return

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM submitted_tasks ORDER BY id ASC")
    tasks_rows = cur.fetchall()
    cur.close()
    conn.close()

    if not tasks_rows:
        bot.reply_to(message, "⚠️ কোনো টাস্ক জমা পড়েনি।")
        return
    
    file_content = "=== ALL SUBMITTED TASKS ===\n\n"
    for idx, item in enumerate(tasks_rows, start=1):
        file_content += (
            f"[{idx}] User ID: {item['user_id']}\n"
            f"    Type: {item['task_type']}\n"
            f"    Name: {item['acc_name']}\n"
            f"    Pass: {item['acc_pass']}\n"
            f"    Data: {item['task_data']}\n"
            f"----------------------------------------\n"
    )
    
    file_data = io.BytesIO(file_content.encode('utf-8'))
    file_data.name = f"All_Tasks_{len(tasks_rows)}.txt"
    bot.send_document(message.chat.id, file_data, caption=f"📊 মোট {len(tasks_rows)} টি টাস্ক ফাইল।")

@bot.message_handler(commands=['cleartasks'])
def clear_all_tasks(message):
    if not is_admin(message):
        return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM submitted_tasks")
    conn.commit()
    cur.close()
    conn.close()
    bot.reply_to(message, "🗑 সমস্ত টাস্ক মুছে ফেলা হয়েছে।")

@bot.message_handler(commands=['addbalance'])
def add_user_balance(message):
    if not is_admin(message):
        return
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "⚠️ নিয়ম: `/addbalance <user_id> <amount>`", parse_mode="Markdown")
        return
    try:
        target_user_id = int(args[1])
        amount = float(args[2])
        target_user = get_user_data(target_user_id)
        
        new_balance = target_user['balance'] + amount
        new_total_income = target_user['total_income'] + amount
        new_completed = target_user['completed_tasks'] + 1
        new_pending = max(0, target_user['pending_tasks'] - 1)
        
        update_user_data(target_user_id, {
            "balance": new_balance,
            "total_income": new_total_income,
            "completed_tasks": new_completed,
            "pending_tasks": new_pending
        })
        
        bot.reply_to(message, f"✅ User ID: `{target_user_id}` এ {amount} BDT যোগ করা হয়েছে।", parse_mode="Markdown")
        try:
            bot.send_message(target_user_id, f"✅ **টাস্ক এপ্রুভ হয়েছে!**\n💰 **যুক্ত হয়েছে: {amount:.2f} BDT**", parse_mode="Markdown")
        except:
            pass

        # ১০% রেফার কমিশন হিসাব
        referrer_id = target_user.get('referred_by')
        if referrer_id:
            commission = amount * 0.10
            referrer_user = get_user_data(referrer_id)
            ref_new_balance = referrer_user['balance'] + commission
            ref_new_income = referrer_user['refer_income'] + commission
            
            update_user_data(referrer_id, {
                "balance": ref_new_balance,
                "refer_income": ref_new_income
            })
            
            try:
                ref_msg = (
                    f"🎁 **রেফারেল কমিশন যোগ হয়েছে!**\n\n"
                    f"💰 আপনার এক রেফারেলের টাস্ক থেকে আপনি পেয়েছেন: **{commission:.2f} BDT** (১০% কমিশন)"
                )
                bot.send_message(referrer_id, ref_msg, parse_mode="Markdown")
            except:
                pass

    except ValueError:
        bot.reply_to(message, "⚠️ সঠিক সংখ্যা দিন।")

# --- স্টার্ট কমান্ড ও সাবস্ক্রিপশন চেক হ্যান্ডলার ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    user_data = get_user_data(user_id)
    
    args = message.text.split()
    if len(args) > 1 and user_data['referred_by'] is None:
        try:
            referrer_id = int(args[1])
            if referrer_id != user_id:
                referrer_data = get_user_data(referrer_id)
                if referrer_data:
                    update_user_data(user_id, {"referred_by": referrer_id})
                    update_user_data(referrer_id, {"referrals": referrer_data['referrals'] + 1})
                    
                    ref_notify_msg = (
                        f"🎉 **সফল রেফারেল বোনাস!**\n\n"
                        f"👤 **{first_name}** আপনার রেফারেলে জয়েন করেছে!\n"
                        f"💰 তার কাজের 10% কমিশন আপনার ব্যালেন্সে এড হতে থাকবে।"
                    )
                    try:
                        bot.send_message(referrer_id, ref_notify_msg, parse_mode="Markdown")
                    except:
                        pass
        except ValueError:
            pass

    if not check_user_subscription(user_id):
        sub_msg = (
            f"📢 To use this bot you must subscribe to our channel: {CHANNEL_USERNAME}\n\n"
            f"👇 Use the buttons below."
        )
        bot.send_message(message.chat.id, sub_msg, reply_markup=subscription_markup())
        return

    welcome_msg = f"🥰 স্বাগতম, {first_name}!\n💎 কাজ শুরু করতে নিচের অপশনগুলো ব্যবহার করুন 🔽"
    bot.send_message(message.chat.id, welcome_msg, reply_markup=main_keyboard(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check_sub(call):
    user_id = call.from_user.id
    first_name = call.from_user.first_name
    if check_user_subscription(user_id):
        bot.answer_callback_query(call.id, "✅ ধন্যবাদ! আপনার সাবস্ক্রিপশন ভেরিফাই হয়েছে।")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        welcome_msg = f"🥰 স্বাগতম, {first_name}!\n💎 কাজ শুরু করতে নিচের অপশনগুলো ব্যবহার করুন 🔽"
        bot.send_message(call.message.chat.id, welcome_msg, reply_markup=main_keyboard(), parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "❌ আপনি এখনো চ্যানেলে জয়েন করেননি! দয়া করে আগে জয়েন করুন।", show_alert=True)

# --- সাধারণ মেসেজ হ্যান্ডলার ---

@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    user_id = message.from_user.id
    text = message.text
    user_data = get_user_data(user_id)

    if not check_user_subscription(user_id):
        sub_msg = (
            f"📢 To use this bot you must subscribe to our channel: {CHANNEL_USERNAME}\n\n"
            f"👇 Use the buttons below."
        )
        bot.send_message(message.chat.id, sub_msg, reply_markup=subscription_markup())
        return

    if text == '❌ বাতিল':
        update_user_data(user_id, {"state": None})
        bot.send_message(message.chat.id, "❌ **বাতিল করা হয়েছে।**", reply_markup=main_keyboard(), parse_mode="Markdown")
        return

    current_state = user_data.get('state')
    
    if current_state in ['WAITING_FOR_2FA', 'WAITING_FOR_FB_COOKIES']:
        update_user_data(user_id, {"state": None})
        acc_name = user_data.get('generated_username', 'Account User')
        acc_pass = user_data.get('generated_password', '12345678')
        task_type = user_data.get('task_type', 'টাস্ক')
        
        update_user_data(user_id, {"pending_tasks": user_data['pending_tasks'] + 1})
        
        # টাস্কটি সরাসরি ডাটাবেজে সেভ করা হলো (RAM-এর পরিবর্তে)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO submitted_tasks (user_id, task_type, acc_name, acc_pass, task_data)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user_id, task_type, acc_name, acc_pass, text))
        conn.commit()
        cur.close()
        conn.close()
        
        channel_msg = (
            f"📥 **নতুন কাজ জমা পড়েছে!**\n\n"
            f"👤 **User ID:** `{user_id}`\n"
            f"📌 **Type:** {task_type}\n"
            f"🟢 **Name:** {acc_name}\n"
            f"🔐 **Pass:** {acc_pass}\n\n"
            f"📄 **Data:**\n{text}"
        )
        try:
            bot.send_message(CHANNEL_USERNAME, channel_msg, parse_mode="Markdown")
        except:
            pass

        bot.send_message(message.chat.id, "✅ **Rcv**\n\nএটার টাকা খুব শীঘ্রই চেক করে আপনার ব্যালেন্সে এড করা হবে", reply_markup=main_keyboard(), parse_mode="Markdown")
        return

    elif current_state == 'WAITING_FOR_WITHDRAW_NUMBER':
        update_user_data(user_id, {
            "withdraw_address": text,
            "state": 'WAITING_FOR_WITHDRAW_AMOUNT'
        })
        bot.send_message(message.chat.id, "টাকার পরিমাণ লিখুন", reply_markup=cancel_keyboard(), parse_mode="Markdown")
        return

    elif current_state == 'WAITING_FOR_WITHDRAW_AMOUNT':
        method = user_data.get('withdraw_method', 'N/A')
        address = user_data.get('withdraw_address', 'N/A')
        try:
            amount_to_log = float(text)
        except ValueError:
            bot.send_message(message.chat.id, "⚠️ সঠিক সংখ্যায় টাকার পরিমাণ লিখুন।", reply_markup=cancel_keyboard(), parse_mode="Markdown")
            return

        min_limit = 0.3 if "USDT" in method else (30.0 if "মোবাইল" in method else 50.0)
        if user_data['balance'] < amount_to_log or amount_to_log < min_limit:
            update_user_data(user_id, {"state": None})
            bot.send_message(message.chat.id, f"❌ পর্যাপ্ত ব্যালেন্স নেই। আপনার ব্যালেন্স: {user_data['balance']:.2f} BDT", reply_markup=main_keyboard(), parse_mode="Markdown")
            return

        update_user_data(user_id, {
            "balance": user_data['balance'] - amount_to_log,
            "state": None
        })
        
        channel_withdraw_msg = (
            f"💰 **নতুন উইথড্রয়াল রিকোয়েস্ট!**\n\n"
            f"👤 **ইউজার:** {message.from_user.first_name}\n"
            f"🆔 **আইডি:** `{user_id}`\n"
            f"💵 **পরিমাণ:** {amount_to_log} টাকা\n"
            f"🏦 **মেথড:** {method}\n"
            f"📱 **অ্যাকাউন্ট:** `{address}`"
        )
        try:
            bot.send_message(CHANNEL_USERNAME, channel_withdraw_msg, parse_mode="Markdown")
        except:
            pass

        bot.send_message(message.chat.id, f"✅ **আপনার উইথড্রয়াল রিকোয়েস্ট সফলভাবে জমা হয়েছে!**", reply_markup=main_keyboard(), parse_mode="Markdown")
        return

    # মেনু নেভিগেশন
    if text == '📖 কাজ ▸':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=category_keyboard(), parse_mode="Markdown")
    elif text == '📷 ইনস্টাগ্রাম কাজ >':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=instagram_sub_keyboard(), parse_mode="Markdown")
    elif text == '📘 Facebook কাজ':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=fb_sub_keyboard(), parse_mode="Markdown")
    elif text == '0 fnd cookies | 4.00 ৳':
        first_name = generate_random_username().split('_')[0]
        last_name = generate_random_username().split('_')[0]
        password = generate_random_password()
        update_user_data(user_id, {
            "generated_username": f"{first_name} {last_name}",
            "generated_password": password,
            "task_type": "📘 Facebook কাজ (4.00 ৳)"
        })
        
        msg_text = (
            f"👤 **First name:** {first_name}\n"
            f"👤 **Last name:** {last_name}\n"
            f"🔐 **Password:** {password}\n\n"
            f"📘 উপরের তথ্য দিয়ে অ্যাকাউন্ট খুলে নিচে **কুকিজ দিন** বাটনে চাপ দিন 🤪"
        )
        bot.send_message(message.chat.id, msg_text, reply_markup=fb_task_action_keyboard(), parse_mode="Markdown")
    elif text == '📷 ইনস্টাগ্রাম 2fa (৳2.70)':
        username = generate_random_username()
        password = generate_random_password()
        update_user_data(user_id, {
            "generated_username": username,
            "generated_password": password,
            "task_type": "📷 ইনস্টাগ্রাম কাজ"
        })
        msg_text = f"👤 **Name:** `{username}`\n🔐 **Pass:** `{password}`\n\n📸 **অ্যাকাউন্ট খুলে নিচে 2FA Set বাটনে ক্লিক করুন 🤪**"
        bot.send_message(message.chat.id, msg_text, reply_markup=task_action_keyboard(), parse_mode="Markdown")
    elif text == '🔑 2FA Set':
        update_user_data(user_id, {"state": 'WAITING_FOR_2FA'})
        bot.send_message(message.chat.id, "📢 **2FA Key টি দিন:** 🎯", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    elif text == '🍪 কুকিজ দিন':
        update_user_data(user_id, {"state": 'WAITING_FOR_FB_COOKIES'})
        bot.send_message(message.chat.id, "📝 **আপনার ফেসবুক অ্যাকাউন্টের কুকিজটি দিন:** 🎯", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    elif text == 'টাকা উত্তোলন':
        update_user_data(user_id, {"state": 'SELECT_WITHDRAW_METHOD'})
        bot.send_message(messag

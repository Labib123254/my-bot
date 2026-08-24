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

# আপনার চ্যানেল আইডি বা ইউজারনেম
CHANNEL_USERNAME = "@INCOMEXSUPPORT"
CHANNEL_URL = "https://t.me/INCOMEXSUPPORT"
CHANNEL_ID = "@hi54854" # কাজের নোটিফিকেশন পাঠানোর চ্যানেল

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

# ইউজার চ্যানেলে জয়েন আছে কি না তা চেক করার ফাংশন
def check_user_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['member', 'creator', 'administrator']:
            return True
    except Exception as e:
        print(f"Subscription Check Error: {e}")
    return False

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
        types.KeyboardButton('উইথড্র'),
        types.KeyboardButton('মাই রেফারেল'),
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
        types.KeyboardButton('মোবাইল রিচার্জ -> সর্বনিম্ন: ৩০(-৫)'),
        types.KeyboardButton('বিকাশ -> সর্বনিম্ন: ৫০ (-৫)'),
        types.KeyboardButton('❌ বাতিল')
    )
    return markup

# সাবস্ক্রাইব করার ইনলাইন কিবোর্ড
def sub_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Subscribe to channel", url=CHANNEL_URL))
    markup.add(types.InlineKeyboardButton("✅ Check subscription", callback_data="check_sub"))
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

@bot.message_handler(commands=['addbalance'])
def add_user_balance(message):
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "⚠️ **সঠিক নিয়ম:** `/addbalance <user_id> <amount>`", parse_mode="Markdown")
        return
    
    try:
        target_user_id = int(args[1])
        amount = float(args[2])
        
        target_user = get_user_data(target_user_id)
        target_user['balance'] += amount
        target_user['total_income'] += amount
        target_user['completed_tasks'] += 1  
        
        if target_user['pending_tasks'] > 0:
            target_user['pending_tasks'] -= 1
        
        # --- রেফারের ১০% কমিশন হিসাব ও অ্যাড করার লজিক ---
        referrer_id = target_user.get('referred_by')
        if referrer_id and referrer_id in users_db:
            commission = amount * 0.10  # ১০% কমিশন
            ref_user = users_db[referrer_id]
            ref_user['balance'] += commission
            ref_user['refer_income'] += commission
            
            try:
                ref_notification = (
                    f"💰 **রেফারেল কমিশন যুক্ত হয়েছে!**\n"
                    f"আপনার রেফারেলে থাকা ইউজারের কাজ এপ্রুভ হওয়ার কারণে আপনি পেয়েছেন: `{commission:.2f} BDT` কমিশন।"
                )
                bot.send_message(referrer_id, ref_notification, parse_mode="Markdown")
            except Exception as e:
                print(f"Referrer Notification Error: {e}")
        # -----------------------------------------------

        bot.reply_to(message, f"✅ সফলভাবে User ID: `{target_user_id}` এর ব্যালেন্সে `{amount} BDT` যোগ করা হয়েছে।", parse_mode="Markdown")
        
        try:
            notification_msg = (
                f"✅ **টাস্ক এপ্রুভ হয়েছে!**\n"
                f"পরিমাণ: ১ টি\n"
                f"💰 **যুক্ত হয়েছে: {amount:.2f} BDT**"
            )
            bot.send_message(target_user_id, notification_msg, parse_mode="Markdown")
        except Exception as e:
            print(f"User Notification Error: {e}")
            
    except ValueError:
        bot.reply_to(message, "⚠️ ইউজার আইডি বা টাকার পরিমাণ সঠিক সংখ্যায় দিন।")

@bot.message_handler(commands=['sendmsg'])
def send_custom_message_to_user(message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        bot.reply_to(message, "⚠️ **সঠিক নিয়ম:** `/sendmsg <user_id> <আপনার মেসেজ>`", parse_mode="Markdown")
        return
    
    try:
        target_user_id = int(args[1])
        custom_message = args[2]
        bot.send_message(target_user_id, f"📥 **অ্যাডমিনের মেসেজ:**\n\n{custom_message}", parse_mode="Markdown")
        bot.reply_to(message, f"✅ সফলভাবে User ID: `{target_user_id}` এর কাছে মেসেজ পাঠানো হয়েছে।", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ মেসেজ পাঠানো সম্ভব হয়নি। কারণ: {e}")

# --- স্টার্ট কমান্ড ও রেফারেল হ্যান্ডলিং ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    user_data = get_user_data(user_id)
    
    # রেফারেল চেক (যদি নতুন ইউজার অন্য কারো লিংকে জয়েন করে)
    args = message.text.split()
    if len(args) > 1 and user_data['referred_by'] is None:
        try:
            referrer_id = int(args[1])
            if referrer_id != user_id and referrer_id in users_db:
                user_data['referred_by'] = referrer_id
                users_db[referrer_id]['referrals'] += 1
                
                # রেফারারকে নোটিফিকেশন পাঠানো
                ref_notify_msg = (
                    f"🎉 সফল রেফারেল বোনাস!\n\n"
                    f"👤 {first_name} আপনার রেফারেলে জয়েন করেছে!\n"
                    f"💰 তার কাজের 10% কমিশন আপনার ব্যালেন্সে এড হতে থাকবে।"
                )
                bot.send_message(referrer_id, ref_notify_msg, parse_mode="Markdown")
        except ValueError:
            pass

    # ইউজার চ্যানেলে জয়েন আছে কি না চেক করা
    if not check_user_subscription(user_id):
        text = f"📢 To use this bot you must subscribe to our channel: {CHANNEL_USERNAME}\n\n👇 Use the buttons below."
        bot.send_message(message.chat.id, text, reply_markup=sub_inline_keyboard(), parse_mode="Markdown")
    else:
        welcome_msg = (
            f"🥰 স্বাগতম, {first_name}!\n"
            f"💎কাজ শুরু করতে নিচের অপশনগুলো ব্যবহার করুন 🔽"
        )
        bot.send_message(message.chat.id, welcome_msg, reply_markup=main_keyboard(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def verify_subscription(call):
    user_id = call.from_user.id
    first_name = call.from_user.first_name
    
    if check_user_subscription(user_id):
        bot.answer_callback_query(call.id, "✅ ধন্যবাদ! আপনার সাবস্ক্রিপশন নিশ্চিত করা হয়েছে।")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        welcome_msg = (
            f"🥰 স্বাগতম, {first_name}!\n"
            f"💎কাজ শুরু করতে নিচের অপশনগুলো ব্যবহার করুন 🔽"
        )
        bot.send_message(call.message.chat.id, welcome_msg, reply_markup=main_keyboard(), parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "❌ আপনি এখনো আমাদের চ্যানেলে জয়েন করেননি! দয়া করে আগে জয়েন করুন।", show_alert=True)

# --- মেসেজ হ্যান্ডলিং ---

@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    user_id = message.from_user.id
    
    if not check_user_subscription(user_id):
        text = f"📢 To use this bot you must subscribe to our channel: {CHANNEL_USERNAME}\n\n👇 Use the buttons below."
        bot.send_message(message.chat.id, text, reply_markup=sub_inline_keyboard(), parse_mode="Markdown")
        return

    user_data = get_user_data(user_id)
    text = message.text

    if text == '❌ বাতিল':
        user_data['state'] = None
        bot.send_message(message.chat.id, "❌ **বাতিল করা হয়েছে।**", reply_markup=main_keyboard(), parse_mode="Markdown")
        return

    if user_data.get('state') in ['WAITING_FOR_2FA', 'WAITING_FOR_FB_COOKIES']:
        current_state = user_data.get('state')
        user_data['state'] = None
        
        acc_name = user_data.get('generated_username', 'Account User')
        acc_pass = user_data.get('generated_password', '12345678')
        task_type = user_data.get('task_type', 'টাস্ক')
        
        user_data['pending_tasks'] += 1
        
        tasks_list.append({
            "user_id": user_id,
            "type": task_type,
            "name": acc_name,
            "pass": acc_pass,
            "data": text
        })
        
        data_label = "Submitted Data (Cookies)" if current_state == 'WAITING_FOR_FB_COOKIES' else "Submitted Data (2FA)"
        channel_msg = (
            f"📥 **নতুন কাজ জমা পড়েছে!**\n\n"
            f"👤 **User ID:** `{user_id}`\n"
            f"📌 **Type:** {task_type}\n"
            f"🟢 **Name:** {acc_name}\n"
            f"🔐 **Pass:** {acc_pass}\n\n"
            f"📄 **{data_label}:**\n{text}"
        )
        
        try:
            bot.send_message(CHANNEL_ID, channel_msg, parse_mode="Markdown")
        except Exception as e:
            print(f"Channel Send Error: {e}")

        success_reply = "✅ **Rcv**\n\nএটার টাকা খুব শীঘ্রই চেক করে আপনার ব্যালেন্সে এড করা হবে"
        bot.send_message(message.chat.id, success_reply, reply_markup=main_keyboard(), parse_mode="Markdown")
        return

    elif user_data.get('state') == 'WAITING_FOR_WITHDRAW_NUMBER':
        method = user_data.get('withdraw_method', 'N/A')
        amount = user_data['balance']
        user_data['state'] = None
        
        notify_msg = (
            f"💰 **নতুন উইথড্রয়াল রিকোয়েস্ট!**\n\n"
            f"👤 **ইউজার:** {message.from_user.first_name}\n"
            f"🆔 **আইডি:** `{user_id}`\n"
            f"💵 **পরিমাণ:** {amount} টাকা\n"
            f"🏦 **মেথড:** {method}\n"
            f"📱 **নম্বর/অ্যাকাউন্ট:** `{text}`"
        )
        
        try:
            bot.send_message(CHANNEL_ID, notify_msg, parse_mode="Markdown")
        except Exception as e:
            print(f"Channel Notification Error: {e}")

        bot.send_message(message.chat.id, f"✅ **আপনার উইথড্রয়াল রিকোয়েস্ট সফলভাবে জমা হয়েছে!**", reply_markup=main_keyboard(), parse_mode="Markdown")
        return

    # --- মেনু অ্যাকশনসমূহ ---

    if text == '📖 কাজ ▸':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=category_keyboard(), parse_mode="Markdown")

    elif text == '📷 ইনস্টাগ্রাম কাজ >':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=instagram_sub_keyboard(), parse_mode="Markdown")

    elif text == '📘 Facebook কাজ':
        username = generate_random_username()
        password = generate_random_password()
        user_data['generated_username'] = username
        user_data['generated_password'] = password
        user_data['task_type'] = "📘 Facebook কাজ"
        
        msg_text = (
            f"👤 **First name:** {username.split('_')[0].split(' ')[0]}\n"
            f"👤 **Last name:** {username.split('_')[0].split(' ')[-1]}\n"
            f"🔐 **Password:** `{password}`\n\n"
            f"📘 **উপরের তথ্য দিয়ে অ্যাকাউন্ট খুলে নিচে Cookies দিন বাটনে চাপ দিন 🤪**"
        )
        bot.send_message(message.chat.id, msg_text, reply_markup=fb_task_action_keyboard(), parse_mode="Markdown")

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

    elif text == '🍪 Cookies দিন':
        user_data['state'] = 'WAITING_FOR_FB_COOKIES'
        bot.send_message(message.chat.id, "🍪 **আপনার ফেসবুক অ্যাকাউন্টের কুকিজটি দিন:** 🎯", reply_markup=cancel_keyboard(), parse_mode="Markdown")

    elif text == 'উইথড্র':
        user_data['state'] = 'SELECT_WITHDRAW_METHOD'
        bot.send_message(message.chat.id, "💰 **টাকা তোলার মাধ্যম সিলেক্ট করুন:**", reply_markup=withdraw_methods_keyboard(), parse_mode="Markdown")

    elif text in ['USDT (BEP-20) -> সর্বনিম্ন: 0.3(-0.05)', 'মোবাইল রিচার্জ -> সর্বনিম্ন: ৩০(-৫)', 'বিকাশ -> সর্বনিম্ন: ৫০ (-৫)']:
        user_data['withdraw_method'] = text
        user_data['state'] = 'WAITING_FOR_WITHDRAW_NUMBER'
        bot.send_message(message.chat.id, f"📱 **আপনার {text} অ্যাকাউন্ট/নম্বরটি লিখে পাঠান:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")

    elif text == '⏮ ফিরে যান':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=category_keyboard(), parse_mode="Markdown")

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

    elif text == 'মাই রেফারেল':
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        total_ref = user_data["referrals"]
        ref_inc = user_data["refer_income"]
        
        referral_msg = (
            f"🎁 **My Referrals**\n"
            f"👤 **Total Refer:** {total_ref}\n"
            f"💲 **Total Refer Income:** {ref_inc:.2f} BDT\n"
            f"🔗 **আপনার রেফার লিংক:**\n{ref_link}\n\n"
            f"ℹ️ **আপনি আপনার প্রতিটি রেফারেলের সম্পূর্ণ করা কাজ থেকে আয়ের 10% কমিশন পাবেন।**"
        )
        
        share_markup = types.InlineKeyboardMarkup()
        share_url = f"https://t.me/share/url?url={ref_link}&text=घर বসে অনলাইন থেকে প্রতিদিন ইনকাম করুন! এখনই বোটটিতে জয়েন করুন:"
        share_markup.add(types.InlineKeyboardButton("🔄 শেয়ার করুন", url=share_url))
        
        bot.send_message(message.chat.id, referral_msg, reply_markup=share_markup, parse_mode="Markdown")

    elif text == '🧐 সাপোর্ট':
        bot.reply_to(message, "সাহায্যের জন্য অ্যাডমিন ইউজারনেমে যোগাযোগ করুন।")

    elif text == '🧑‍💼 আমি নতুন':
        bot.reply_to(message, "🔰 **নিয়ম:** প্রতিদিন কাজ করুন এবং বন্ধুদের রেফার করে আয় বাড়ান।")

    elif text == '🤪 কিভাবে কাজ করব':
        bot.reply_to(message, "অ্যাকাউন্ট তৈরি করে প্রয়োজনীয় তথ্য (2FA বা Cookies) জমা দিন।")

# ৩. Execution
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    bot.infinity_polling()
        

import os
import io
import re
import threading
import random
import string
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from flask import Flask, request
import telebot
from telebot import types

# ১. Web Server setup (Render-এর জন্য)
app = Flask(__name__)

# ২. Bot setup
TOKEN = os.environ.get('BOT_TOKEN')
# num_threads বাড়ানো হলো - ডিফল্ট মাত্র ২টা থ্রেড দিয়ে চলত,
# যার ফলে একসাথে বেশি ইউজার মেসেজ পাঠালে বট স্লো/হ্যাং হয়ে যেত।
# এখন ৫০টা থ্রেড একসাথে অনেক ইউজারের মেসেজ প্যারালালি প্রসেস করতে পারবে।
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=50)

# সাবস্ক্রিপশন চেকের ফলাফল কিছুক্ষণ মনে রাখা হবে (ক্যাশ),
# যাতে প্রতিটা মেসেজে বারবার Telegram-কে জিজ্ঞেস করতে না হয় - বট দ্রুত হবে
import time
subscription_cache = {}
SUBSCRIPTION_CACHE_SECONDS = 300  # ৫ মিনিট

# ---------------------------------------------------------------------------
# স্প্যাম প্রোটেকশন (Per-user In-flight Lock)
#
# সমস্যা: কোনো ইউজার যদি খুব দ্রুত বারবার বাটনে (যেমন "উইথড্র") ক্লিক করে,
# প্রতিটা ক্লিকেই handle_menu() কল হয় - যেটা একাধিকবার DB কানেকশন নেয়
# (get_user_data, update_user_data), Telegram API কল করে (send_message,
# মাঝে মাঝে get_chat_member)। একজন ইউজার একসাথে অনেকগুলো ক্লিক পাঠালে
# সেগুলো একাধিক থ্রেডে (num_threads=50) একসাথে প্রসেস হতে শুরু করে এবং
# DB কানেকশন পুল (max 30) ও Telegram-এর rate limit এর উপর চাপ বাড়িয়ে দেয় -
# ফলে অন্য ইউজারদের রিকোয়েস্ট পুল/থ্রেড খালি হওয়ার জন্য আটকে থাকে এবং
# পুরো বটটাই স্লো/হ্যাং মনে হয়।
#
# সমাধান: ফিক্সড টাইম কুলডাউনের বদলে (যেটা রিয়েল ইউজারদেরও আটকে দিতে পারে),
# প্রতি ইউজারের জন্য একটা "in-flight" লক রাখা হলো। একজন ইউজারের একটা
# মেসেজ প্রসেস হওয়া শুরু হলে তাকে "busy" মার্ক করা হয়; সেই প্রসেসিং শেষ
# না হওয়া পর্যন্ত (সাধারণত এক সেকেন্ডেরও কম সময়) ওই একই ইউজারের নতুন কোনো
# মেসেজ এলে সেটা বাদ দেওয়া হবে। প্রসেসিং শেষ হলেই লক খুলে যায়।
#
# এতে স্বাভাবিক গতিতে ব্যবহারকারীদের কোনো সমস্যা হয় না (মানুষ যতটুকু গ্যাপ
# দিয়ে বাটনে চাপে সেটা প্রসেসিং টাইমের চেয়ে অনেক বেশি) - শুধু সত্যিকারের
# স্প্যাম/একসাথে অনেক ক্লিক ঠেকানো যায়।
processing_users = set()
processing_lock = threading.Lock()

def try_start_processing(user_id):
    with processing_lock:
        if user_id in processing_users:
            return False
        processing_users.add(user_id)
        return True

def end_processing(user_id):
    with processing_lock:
        processing_users.discard(user_id)
# ---------------------------------------------------------------------------

RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', '')

ADMIN_USERNAMES = ["Trillionaire_9", "vx_7e"]

# Supabase Database Connection String
DATABASE_URL = "postgresql://postgres.vcljsquskcyvkyavmuce:Labib3305%23%23@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"

# একবার কয়েকটা কানেকশন খুলে রাখা হচ্ছে (Connection Pool) -
# এতে বারবার নতুন কানেকশন খুলতে হবে না, বট অনেক দ্রুত হবে
#
# আগে SimpleConnectionPool ব্যবহার হতো, যেটা মাল্টি-থ্রেডেড অ্যাপের জন্য
# thread-safe না (একসাথে অনেক ইউজার থাকলে কানেকশন কনফ্লিক্ট/করাপশন হতে পারত)।
# ThreadedConnectionPool ব্যবহার করা হলো যেটা থ্রেড-সেফ, আর pool size বাড়িয়ে
# ৩০ করা হলো যাতে বেশি ইউজার একসাথে থাকলেও কানেকশনের অভাব না হয়।
db_pool = psycopg2.pool.ThreadedConnectionPool(
    2, 30,
    dsn=DATABASE_URL,
    cursor_factory=psycopg2.extras.DictCursor
)

def get_db_connection():
    return db_pool.getconn()

def release_db_connection(conn):
    db_pool.putconn(conn)

# /gettasks এ "শেষ কতদূর পাঠানো হয়েছে" ট্র্যাক করার হেল্পার ফাংশন
def get_last_sent_task_id():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM bot_settings WHERE key = 'last_sent_task_id'")
    row = cur.fetchone()
    cur.close()
    release_db_connection(conn)
    return int(row['value']) if row else 0

def set_last_sent_task_id(task_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO bot_settings (key, value) VALUES ('last_sent_task_id', %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    ''', (str(task_id),))
    conn.commit()
    cur.close()
    release_db_connection(conn)


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

        # পুরনো ডাটাবেজে banned column না থাকলে যোগ করা হচ্ছে
        # (ব্যান/আনব্যান ফিচারের জন্য)
        cur.execute('''
            ALTER TABLE users ADD COLUMN IF NOT EXISTS banned BOOLEAN DEFAULT FALSE
        ''')

        # সাবমিট করা টাস্ক সংরক্ষণের জন্য নতুন টেবিল
        cur.execute('''
            CREATE TABLE IF NOT EXISTS submitted_tasks (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                task_type TEXT,
                acc_name TEXT,
                acc_pass TEXT,
                task_data TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        # পুরনো ডাটাবেজে created_at column না থাকলে যোগ করা হচ্ছে
        cur.execute('''
            ALTER TABLE submitted_tasks ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()
        ''')

        # টাস্কের স্ট্যাটাস (pending/approved/rejected) ট্র্যাক করার জন্য কলাম -
        # /history কমান্ডে প্রতিটা কাজের অবস্থা দেখানোর জন্য দরকার
        cur.execute('''
            ALTER TABLE submitted_tasks ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending'
        ''')

        # উইথড্র হিস্টরি সংরক্ষণের জন্য নতুন টেবিল
        # (/history কমান্ডে user এর উইথড্র হিস্টরি দেখানোর জন্য দরকার)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount REAL,
                method TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        # /gettasks কমান্ডে "শেষ কতদূর পাঠানো হয়েছে" মনে রাখার জন্য ছোট একটা key-value টেবিল
        cur.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # status কলাম যোগ হওয়ার আগে যেসব টাস্ক আসলে এপ্রুভ/রিজেক্ট হয়ে গিয়েছিল,
        # সেগুলো ডিফল্টভাবে 'pending' রয়ে গেছে। এখানে একবারের জন্য ঠিক করা হচ্ছে -
        # প্রতিটা ইউজারের বর্তমান pending_tasks সংখ্যার চেয়ে বেশি 'pending' থাকলে,
        # সবচেয়ে পুরনো এক্সট্রা গুলোকে 'approved' মার্ক করে দেওয়া হচ্ছে।
        # (একবার ঠিক হয়ে গেলে সংখ্যা মিলে যাবে, তাই পরের বার আর কিছু বদলাবে না)
        cur.execute("SELECT user_id, pending_tasks FROM users")
        all_users = cur.fetchall()
        for u in all_users:
            uid = u['user_id']
            target_pending = u['pending_tasks']
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM submitted_tasks WHERE user_id = %s AND status = 'pending'",
                (uid,)
            )
            current_pending_count = cur.fetchone()['cnt']
            excess = current_pending_count - target_pending
            if excess > 0:
                cur.execute('''
                    UPDATE submitted_tasks SET status = 'approved'
                    WHERE id IN (
                        SELECT id FROM submitted_tasks
                        WHERE user_id = %s AND status = 'pending'
                        ORDER BY id ASC LIMIT %s
                    )
                ''', (uid, excess))

        conn.commit()
        cur.close()
        release_db_connection(conn)
    except Exception as e:
        print(f"Database Initialization Error: {e}")

init_db()

# /addbalance, /approvetask, /rejecttask - এই কমান্ডগুলো নির্দিষ্ট কোন
# submitted_tasks রো এর সাথে সম্পর্কিত তা জানে না (শুধু user_id + amount/reason
# পাঠানো হয়)। তাই approve/reject হলে ওই ইউজারের সবচেয়ে পুরনো 'pending'
# টাস্কটাকেই (সম্ভব হলে টাইপ মিলিয়ে) approved/rejected হিসেবে মার্ক করা হয় -
# এতে /history তে প্রতিটা টাস্কের সঠিক অবস্থা দেখানো যায়।
def mark_oldest_pending_task(user_id, new_status, type_keyword=None):
    conn = get_db_connection()
    cur = conn.cursor()
    if type_keyword:
        cur.execute('''
            SELECT id FROM submitted_tasks
            WHERE user_id = %s AND status = 'pending' AND task_type ILIKE %s
            ORDER BY id ASC LIMIT 1
        ''', (user_id, f"%{type_keyword}%"))
        row = cur.fetchone()
        if not row:
            # ওই টাইপের pending টাস্ক না পেলে, যেকোনো টাইপের সবচেয়ে পুরনো pending টাস্ক ধরা হচ্ছে
            cur.execute('''
                SELECT id FROM submitted_tasks
                WHERE user_id = %s AND status = 'pending'
                ORDER BY id ASC LIMIT 1
            ''', (user_id,))
            row = cur.fetchone()
    else:
        cur.execute('''
            SELECT id FROM submitted_tasks
            WHERE user_id = %s AND status = 'pending'
            ORDER BY id ASC LIMIT 1
        ''', (user_id,))
        row = cur.fetchone()

    if row:
        cur.execute("UPDATE submitted_tasks SET status = %s WHERE id = %s", (new_status, row['id']))
        conn.commit()

    cur.close()
    release_db_connection(conn)


def is_admin(message):
    username = message.from_user.username
    if username and username in ADMIN_USERNAMES:
        return True
    return False

# চ্যানেল কনফিগারেশন
CHANNEL_USERNAME = "@INCOMEXSUPPORT"
CHANNEL_URL = "https://t.me/INCOMEXSUPPORT"
ADMIN_SUPPORT_URL = "https://t.me/Xsupportadmin1"

# টাস্ক জমা ও উইথড্র রিকোয়েস্টের নোটিফিকেশন এই Private চ্যানেলে পাঠানো হবে
NOTIFY_CHANNEL_ID = -1003916527223

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
    release_db_connection(conn)
    return dict(row)

def update_user_data(user_id, kwargs):
    conn = get_db_connection()
    cur = conn.cursor()
    set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
    values = list(kwargs.values()) + [user_id]
    cur.execute(f"UPDATE users SET {set_clause} WHERE user_id = %s", values)
    conn.commit()
    cur.close()
    release_db_connection(conn)

def check_user_subscription(user_id):
    now = time.time()
    cached = subscription_cache.get(user_id)
    # শুধু আগে "subscribed" (True) পাওয়া রেজাল্টটাই ক্যাশ থেকে ব্যবহার হবে।
    # "subscribed না" (False) রেজাল্ট কখনো ক্যাশ থেকে রিটার্ন করা হবে না -
    # যাতে জয়েন করার সাথে সাথেই পরের চেকে সঠিকভাবে ধরা পড়ে।
    if cached and cached[0] and (now - cached[1] < SUBSCRIPTION_CACHE_SECONDS):
        return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        result = member.status in ['member', 'creator', 'administrator']
    except Exception as e:
        # Telegram API কল ব্যর্থ হলে (network/timeout/rate-limit ইত্যাদি) এটা
        # আসল "subscribed না" নয় - এটা আমাদের সিস্টেমের সমস্যা।
        # তাই এই ক্ষেত্রে ইউজারকে ভুলভাবে ব্লক না করে ঢুকতে দেওয়া হচ্ছে (fail-open),
        # আর error টা log ও admin চ্যানেলে পাঠানো হচ্ছে যাতে দ্রুত ধরা পড়ে।
        import traceback
        error_detail = traceback.format_exc()
        print(f"[SUBSCRIPTION CHECK ERROR] user_id={user_id} channel={CHANNEL_USERNAME}\n{error_detail}")
        try:
            bot.send_message(
                NOTIFY_CHANNEL_ID,
                f"⚠️ **Subscription check ব্যর্থ হয়েছে!**\n\n"
                f"👤 User ID: `{user_id}`\n"
                f"📢 Channel: {CHANNEL_USERNAME}\n"
                f"❗ Error: `{str(e)}`\n\n"
                f"সম্ভাব্য কারণ: বট ওই চ্যানেলে admin/member নেই, অথবা username ভুল, অথবা Telegram API সাময়িক সমস্যা।",
                parse_mode="Markdown"
            )
        except:
            pass
        return True  # error হলে ইউজারকে block না করে ঢুকতে দাও

    if result:
        subscription_cache[user_id] = (True, now)
    else:
        subscription_cache.pop(user_id, None)
    return result

def generate_random_username():
    names = ["Isabella Williams", "Sophia Brown", "Isabella Johnson", "Emma Davis", "Olivia Wilson"]
    selected_name = random.choice(names)
    num = "".join(random.choices(string.digits, k=4))
    return f"{selected_name}_{num}"

# ফার্স্ট নেম ও লাস্ট নেম আলাদা লিস্টে রাখা হয়েছে, যাতে দুইটা স্বাধীনভাবে
# random ভাবে বাছাই হয় - এতে নাম বারবার রিপিট না হয়ে অনেক বেশি ভ্যারাইড হবে
# ৭৫ x ৭৫ = ৫৬২৫ টা সম্ভাব্য কম্বিনেশন
FIRST_NAMES = [
    "Isabella", "Sophia", "Emma", "Olivia", "Ava", "Mia", "Grace", "Chloe",
    "Lily", "Zoe", "Hannah", "Amelia", "Ella", "Layla", "Nora", "Riley",
    "Aria", "Scarlett", "Victoria", "Madison", "Luna", "Camila", "Aubrey", "Zoey",
    "Charlotte", "Abigail", "Emily", "Harper", "Evelyn", "Ellie", "Avery",
    "Sofia", "Aubree", "Willow", "Bella", "Claire", "Skylar",
    "Lucy", "Paisley", "Everly", "Anna", "Caroline", "Nova", "Genesis",
    "Emilia", "Kennedy", "Samantha", "Maya", "Sarah", "Natalie", "Hazel",
    "Autumn", "Kinsley", "Ariana", "Peyton", "Rylee", "Brooklyn", "Aaliyah",
    "Savannah", "Alexa", "Ariel", "Alice", "Eliana", "Adeline", "Mila",
    "Julia", "Ivy", "Alaina", "Vivian", "Reagan", "Piper", "Quinn",
    "Melanie", "Cora", "Josephine"
]
LAST_NAMES = [
    "Williams", "Brown", "Johnson", "Davis", "Wilson", "Smith", "Taylor",
    "Anderson", "Thomas", "Clark", "Miller", "Moore", "Jackson", "Martin",
    "Lee", "Walker", "Hall", "Allen", "Young", "King", "Wright", "Scott", "Green", "Baker",
    "Adams", "Nelson", "Carter", "Mitchell", "Perez", "Roberts", "Turner",
    "Phillips", "Campbell", "Parker", "Evans", "Edwards", "Collins", "Stewart",
    "Sanchez", "Morris", "Rogers", "Reed", "Cook", "Morgan", "Bell",
    "Murphy", "Bailey", "Rivera", "Cooper", "Richardson", "Cox", "Howard",
    "Ward", "Peterson", "Gray", "James", "Watson", "Brooks", "Kelly",
    "Sanders", "Price", "Bennett", "Wood", "Barnes", "Ross", "Henderson",
    "Coleman", "Jenkins", "Perry", "Powell", "Long", "Patterson", "Hughes",
    "Flores", "Washington"
]

def generate_random_full_name():
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    return first, last

def generate_random_password():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

# --- ভ্যালিডেশন ফাংশনসমূহ ---

def has_bangla(text):
    return bool(re.search(r'[\u0980-\u09FF]', text))

def is_valid_fb_cookie(text):
    # কমপক্ষে ১৪ ক্যারেক্টার, বাংলা থাকা যাবে না
    if has_bangla(text):
        return False
    if len(text.strip()) < 14:
        return False
    return True

def is_valid_usdt_address(text):
    # কমপক্ষে ২০ ক্যারেক্টার, শুধু ইংরেজি অক্ষর ও সংখ্যা
    text = text.strip()
    if len(text) < 20:
        return False
    if not re.fullmatch(r'[A-Za-z0-9]+', text):
        return False
    return True

def is_valid_phone_number(text):
    # ঠিক ১১ সংখ্যা, শুধু ডিজিট
    text = text.strip()
    return bool(re.fullmatch(r'\d{11}', text))

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
        types.KeyboardButton('উইথড্র'),
        types.KeyboardButton('রেফার'),
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
        types.KeyboardButton('4.00৳'),
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

    # /gettasks       -> আগেরবার পাঠানোর পর যেসব নতুন কাজ জমা পড়েছে শুধু সেগুলো দেখাবে
    # /gettasks all   -> শুরু থেকে এখন পর্যন্ত সব কাজ দেখাবে (পুরনো পয়েন্টার বদলাবে না)
    args = message.text.split()
    show_all = len(args) > 1 and args[1].lower() == 'all'

    conn = get_db_connection()
    cur = conn.cursor()
    if show_all:
        cur.execute("SELECT * FROM submitted_tasks ORDER BY id ASC")
    else:
        last_id = get_last_sent_task_id()
        cur.execute("SELECT * FROM submitted_tasks WHERE id > %s ORDER BY id ASC", (last_id,))
    tasks_rows = cur.fetchall()
    cur.close()
    release_db_connection(conn)

    if not tasks_rows:
        bot.reply_to(message, "⚠️ নতুন কোনো টাস্ক জমা পড়েনি।" if not show_all else "⚠️ কোনো টাস্ক জমা পড়েনি।")
        return

    file_content = "=== SUBMITTED TASKS ===\n\n"
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
    file_data.name = f"Tasks_{len(tasks_rows)}.txt"
    bot.send_document(message.chat.id, file_data, caption=f"📊 মোট {len(tasks_rows)} টি টাস্ক ফাইল।")

    # শুধু "নতুন" মোডে পাঠালেই পয়েন্টার আপডেট হবে, 'all' মোডে হবে না
    if not show_all:
        newest_id = max(item['id'] for item in tasks_rows)
        set_last_sent_task_id(newest_id)

@bot.message_handler(commands=['cleartasks'])
def clear_all_tasks(message):
    if not is_admin(message):
        return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM submitted_tasks")
    conn.commit()
    cur.close()
    release_db_connection(conn)
    # সব টাস্ক মুছে ফেলা হলো, তাই /gettasks এর "নতুন কাজ" পয়েন্টারও রিসেট করা হলো
    set_last_sent_task_id(0)
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

        # কোন নির্দিষ্ট টাস্কের জন্য এপ্রুভ করা হচ্ছে তা এখানে জানা নেই
        # (শুধু user_id + amount দেওয়া হয়), তাই সবচেয়ে পুরনো pending
        # টাস্কটাকেই approved মার্ক করা হচ্ছে
        mark_oldest_pending_task(target_user_id, 'approved')

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

@bot.message_handler(commands=['approvetask'])
def approve_tasks_bulk(message):
    if not is_admin(message):
        return

    # ফরম্যাট: /approvetask <facebook/instagram/gmail> <amount> <user_id1,user_id2,...>
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        bot.reply_to(
            message,
            "⚠️ নিয়ম: `/approvetask <facebook/instagram/gmail> <amount> <user_id1,user_id2,...>`\n\n"
            "উদাহরণ: `/approvetask facebook 4.00 7236432836,8757506241,8714247505`",
            parse_mode="Markdown"
        )
        return

    task_type_key = parts[1].strip().lower()
    task_type_names = {
        "facebook": "ফেসবুকের",
        "instagram": "ইনস্টাগ্রামের",
        "gmail": "জিমেইলের",
    }
    if task_type_key not in task_type_names:
        bot.reply_to(message, "⚠️ কাজের ধরন ভুল। এই তিনটার একটা দিন: `facebook`, `instagram`, `gmail`", parse_mode="Markdown")
        return

    try:
        amount = float(parts[2])
    except ValueError:
        bot.reply_to(message, "⚠️ সঠিক amount দিন।")
        return

    user_ids = []
    for piece in parts[3].split(','):
        piece = piece.strip()
        if piece.isdigit():
            user_ids.append(int(piece))

    if not user_ids:
        bot.reply_to(message, "⚠️ কোনো সঠিক User ID পাওয়া যায়নি। কমা (,) দিয়ে আলাদা করে ID দিন।")
        return

    bot.reply_to(message, f"⏳ {len(user_ids)} জনের টাস্ক এপ্রুভ করা হচ্ছে, একটু সময় লাগতে পারে...")

    threading.Thread(
        target=_do_approve_tasks_bulk,
        args=(message.chat.id, user_ids, amount, task_type_names[task_type_key], task_type_key),
        daemon=True
    ).start()

def _do_approve_tasks_bulk(admin_chat_id, user_ids, amount, task_type_display, task_type_key=None):
    approved = []
    not_found = []

    for uid in user_ids:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
        row = cur.fetchone()
        cur.close()
        release_db_connection(conn)

        if not row:
            not_found.append(uid)
            continue

        target_user = dict(row)
        new_balance = target_user['balance'] + amount
        new_total_income = target_user['total_income'] + amount
        new_completed = target_user['completed_tasks'] + 1
        new_pending = max(0, target_user['pending_tasks'] - 1)

        update_user_data(uid, {
            "balance": new_balance,
            "total_income": new_total_income,
            "completed_tasks": new_completed,
            "pending_tasks": new_pending
        })

        # নির্দিষ্ট টাইপ মিলিয়ে সবচেয়ে পুরনো pending টাস্কটাকে approved মার্ক করা হচ্ছে
        mark_oldest_pending_task(uid, 'approved', type_keyword=task_type_key)

        # ১০% রেফার কমিশন হিসাব (আগের /addbalance এর মতোই)
        referrer_id = target_user.get('referred_by')
        if referrer_id:
            commission = amount * 0.10
            referrer_user = get_user_data(referrer_id)
            update_user_data(referrer_id, {
                "balance": referrer_user['balance'] + commission,
                "refer_income": referrer_user['refer_income'] + commission
            })
            try:
                bot.send_message(
                    referrer_id,
                    f"🎁 **রেফারেল কমিশন যোগ হয়েছে!**\n\n"
                    f"💰 আপনার এক রেফারেলের টাস্ক থেকে আপনি পেয়েছেন: **{commission:.2f} BDT** (১০% কমিশন)",
                    parse_mode="Markdown"
                )
            except:
                pass

        approved.append(uid)

    # প্রতিটা approve হওয়া user কে নোটিফিকেশন পাঠানো হচ্ছে
    sent = 0
    failed_send = 0
    for uid in approved:
        try:
            bot.send_message(
                uid,
                f"✅ **{task_type_display} টাস্ক এপ্রুভ হয়েছে!**\n"
                f"পরিমাণ: ১ টি\n"
                f"💰 যুক্ত হয়েছে: {amount:.2f} BDT",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed_send += 1
        time.sleep(0.05)

    summary = (
        f"✅ টাস্ক এপ্রুভ সম্পন্ন হয়েছে!\n"
        f"পরিমাণ: {len(approved)} টি\n"
        f"📨 মেসেজ পাঠানো হয়েছে: {sent} জনকে\n"
    )
    if failed_send:
        summary += f"⚠️ মেসেজ পাঠানো যায়নি: {failed_send} জনকে\n"
    if not_found:
        summary += f"❓ খুঁজে পাওয়া যায়নি: {', '.join(map(str, not_found))}\n"

    try:
        bot.send_message(admin_chat_id, summary, parse_mode="Markdown")
    except:
        pass

@bot.message_handler(commands=['sendmsg'])
def send_message_to_user(message):
    if not is_admin(message):
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ নিয়ম: `/sendmsg <user_id> <বার্তা>`", parse_mode="Markdown")
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        bot.reply_to(message, "⚠️ সঠিক user_id দিন (সংখ্যা হতে হবে)।")
        return

    text_to_send = parts[2]

    try:
        bot.send_message(target_user_id, text_to_send, parse_mode="Markdown")
        bot.reply_to(message, f"✅ User ID: `{target_user_id}` কে মেসেজ পাঠানো হয়েছে।", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ মেসেজ পাঠানো যায়নি।\nError: `{e}`", parse_mode="Markdown")

@bot.message_handler(commands=['sendall'])
def send_message_to_all(message):
    if not is_admin(message):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ নিয়ম: `/sendall <বার্তা>`\n\nবার্তাটি সকল ইউজারকে পাঠানো হবে।", parse_mode="Markdown")
        return

    broadcast_text = parts[1]
    bot.reply_to(message, "📤 সবাইকে পাঠানো শুরু হয়েছে, ইউজার সংখ্যা বেশি হলে কিছুটা সময় লাগতে পারে...")

    # Broadcast আলাদা থ্রেডে চালানো হচ্ছে, যাতে অনেক ইউজার থাকলেও
    # বটের বাকি অংশ (webhook handler) ব্লক না হয়ে যায়।
    threading.Thread(target=_do_broadcast, args=(message.chat.id, broadcast_text), daemon=True).start()

def _do_broadcast(admin_chat_id, text):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    rows = cur.fetchall()
    cur.close()
    release_db_connection(conn)

    success = 0
    failed = 0
    for row in rows:
        uid = row['user_id']
        try:
            bot.send_message(uid, text, parse_mode="Markdown")
            success += 1
        except Exception:
            failed += 1
        # Telegram-এর rate limit এড়াতে প্রতি মেসেজের মাঝে সামান্য গ্যাপ
        time.sleep(0.05)

    try:
        bot.send_message(
            admin_chat_id,
            f"✅ **সবাইকে পাঠানো সম্পন্ন হয়েছে!**\n\n"
            f"📨 সফলভাবে পাঠানো হয়েছে: {success} জনকে\n"
            f"❌ ব্যর্থ হয়েছে: {failed} জনকে",
            parse_mode="Markdown"
        )
    except:
        pass

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if not is_admin(message):
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ নিয়ম: `/ban <user_id>`", parse_mode="Markdown")
        return
    try:
        target_user_id = int(args[1])
    except ValueError:
        bot.reply_to(message, "⚠️ সঠিক user_id দিন (সংখ্যা হতে হবে)।")
        return

    # ইউজারকে কোনো নোটিফিকেশন পাঠানো হচ্ছে না - শুধু চুপচাপ ব্যান করা হচ্ছে
    update_user_data(target_user_id, {"banned": True})
    bot.reply_to(message, f"🚫 User ID: `{target_user_id}` কে ব্যান করা হয়েছে।", parse_mode="Markdown")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if not is_admin(message):
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ নিয়ম: `/unban <user_id>`", parse_mode="Markdown")
        return
    try:
        target_user_id = int(args[1])
    except ValueError:
        bot.reply_to(message, "⚠️ সঠিক user_id দিন (সংখ্যা হতে হবে)।")
        return

    # ইউজারকে কোনো নোটিফিকেশন পাঠানো হচ্ছে না - শুধু চুপচাপ আনব্যান করা হচ্ছে
    update_user_data(target_user_id, {"banned": False})
    bot.reply_to(message, f"✅ User ID: `{target_user_id}` কে আনব্যান করা হয়েছে।", parse_mode="Markdown")

@bot.message_handler(commands=['cutbalance'])
def cut_user_balance(message):
    if not is_admin(message):
        return
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "⚠️ নিয়ম: `/cutbalance <user_id> <amount>`", parse_mode="Markdown")
        return
    try:
        target_user_id = int(args[1])
        amount = float(args[2])
    except ValueError:
        bot.reply_to(message, "⚠️ সঠিক সংখ্যা দিন।")
        return

    target_user = get_user_data(target_user_id)
    new_balance = target_user['balance'] - amount

    # ইউজারকে কোনো নোটিফিকেশন পাঠানো হচ্ছে না - শুধু চুপচাপ ব্যালেন্স কাটা হচ্ছে
    update_user_data(target_user_id, {"balance": new_balance})
    bot.reply_to(
        message,
        f"✅ User ID: `{target_user_id}` এর ব্যালেন্স থেকে {amount} BDT কাটা হয়েছে।\n"
        f"বর্তমান ব্যালেন্স: {new_balance:.2f} BDT",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['cutallbalance'])
def cut_all_balance(message):
    if not is_admin(message):
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ নিয়ম: `/cutallbalance <amount>`", parse_mode="Markdown")
        return
    try:
        amount = float(args[1])
    except ValueError:
        bot.reply_to(message, "⚠️ সঠিক সংখ্যা দিন।")
        return

    conn = get_db_connection()
    cur = conn.cursor()
    # ব্যালেন্স ০ এর নিচে যাবে না
    cur.execute("UPDATE users SET balance = GREATEST(balance - %s, 0)", (amount,))
    affected = cur.rowcount
    conn.commit()
    cur.close()
    release_db_connection(conn)

    # কাউকে কোনো নোটিফিকেশন পাঠানো হচ্ছে না
    bot.reply_to(message, f"✅ মোট {affected} জন ইউজারের ব্যালেন্স থেকে {amount} BDT করে কাটা হয়েছে।", parse_mode="Markdown")

@bot.message_handler(commands=['history'])
def user_history(message):
    if not is_admin(message):
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ নিয়ম: `/history <user_id>`", parse_mode="Markdown")
        return
    try:
        target_user_id = int(args[1])
    except ValueError:
        bot.reply_to(message, "⚠️ সঠিক user_id দিন (সংখ্যা হতে হবে)।")
        return

    target_user = get_user_data(target_user_id)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM submitted_tasks WHERE user_id = %s ORDER BY id ASC",
        (target_user_id,)
    )
    tasks_rows = cur.fetchall()
    cur.execute(
        "SELECT * FROM withdrawals WHERE user_id = %s ORDER BY id ASC",
        (target_user_id,)
    )
    withdraw_rows = cur.fetchall()
    cur.close()
    release_db_connection(conn)

    summary = (
        f"📊 **ইউজার হিস্টরি: `{target_user_id}`**\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💸 ব্যালেন্স: {target_user['balance']:.2f} BDT\n"
        f"💰 Total Income: {target_user['total_income']:.2f} BDT\n"
        f"✅ সম্পন্ন কাজ: {target_user['completed_tasks']} টি\n"
        f"⏳ রিভিউতে আছে: {target_user['pending_tasks']} টি\n"
        f"📥 মোট জমা দেওয়া কাজ: {len(tasks_rows)} টি\n"
        f"🚫 ব্যান স্ট্যাটাস: {'হ্যাঁ' if target_user.get('banned') else 'না'}\n"
    )
    bot.send_message(message.chat.id, summary, parse_mode="Markdown")

    if not tasks_rows:
        bot.send_message(message.chat.id, "📌 জমা দেওয়া কাজের তালিকা: কোনো কাজ পাওয়া যায়নি।")
    else:
        task_text = f"📌 জমা দেওয়া কাজের তালিকা ({len(tasks_rows)} টি):\n\n"
        status_labels = {
            "approved": "✅ এপ্রুভড",
            "rejected": "❌ রিজেক্টেড",
            "pending": "⏳ রিভিউতে আছে",
        }
        for idx, item in enumerate(tasks_rows, start=1):
            status_display = status_labels.get(item.get('status') or 'pending', "⏳ রিভিউতে আছে")
            task_text += (
                f"[{idx}] 📥 নতুন কাজ জমা পড়েছে!\n"
                f"📊 স্ট্যাটাস: {status_display}\n"
                f"👤 User ID: {item['user_id']}\n"
                f"📌 Type: {item['task_type']}\n"
                f"🟢 Name: {item['acc_name']}\n"
                f"🔐 Pass: {item['acc_pass']}\n"
                f"📄 Data: {item['task_data']}\n"
                f"🕒 সময়: {item['created_at']}\n"
                f"----------------------------------------\n"
            )
        # টেলিগ্রামের ৪০৯৬ ক্যারেক্টার লিমিটের কারণে বড় হলে ভাগ করে পাঠানো হচ্ছে
        #
        # parse_mode="Markdown" ব্যবহার করা হচ্ছে না এখানে, কারণ Data/Pass
        # ফিল্ডে ইউজারের দেওয়া raw কুকিজ/2FA টেক্সট থাকে যাতে *, _, ` এর
        # মতো ক্যারেক্টার থাকতে পারে - Markdown parse_mode দিয়ে পাঠালে
        # Telegram সেগুলোকে ফরম্যাটিং হিসেবে ধরার চেষ্টা করে, আর আনম্যাচড
        # হলে পুরো send_message কল এরর দিয়ে ফেইল করে। এতে try/except না
        # থাকলে পুরো ফাংশনই থেমে যায় (নিচের উইথড্র হিস্টরিও আর পাঠানো হয় না)।
        for i in range(0, len(task_text), 3500):
            try:
                bot.send_message(message.chat.id, task_text[i:i+3500])
            except Exception as e:
                bot.send_message(message.chat.id, f"⚠️ একটি অংশ পাঠাতে সমস্যা হয়েছে: {e}")

    if not withdraw_rows:
        bot.send_message(message.chat.id, "💰 উইথড্র হিস্টরি: কোনো উইথড্র পাওয়া যায়নি।")
    else:
        withdraw_text = f"💰 উইথড্র হিস্টরি ({len(withdraw_rows)} টি):\n\n"
        for idx, item in enumerate(withdraw_rows, start=1):
            withdraw_text += (
                f"[{idx}] {item['amount']} BDT - {item['method']}\n"
                f"    Address: {item['address']}\n"
                f"    সময়: {item['created_at']}\n"
                f"----------------------------------------\n"
            )
        for i in range(0, len(withdraw_text), 3500):
            try:
                bot.send_message(message.chat.id, withdraw_text[i:i+3500])
            except Exception as e:
                bot.send_message(message.chat.id, f"⚠️ একটি অংশ পাঠাতে সমস্যা হয়েছে: {e}")

@bot.message_handler(commands=['rejecttask'])
def reject_tasks(message):
    if not is_admin(message):
        return

    # ফরম্যাট: /rejecttask <facebook/instagram/gmail> <user_id1,user_id2,...> <কারণ>
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        bot.reply_to(
            message,
            "⚠️ নিয়ম: `/rejecttask <facebook/instagram/gmail> <user_id1,user_id2,...> <কারণ>`\n\n"
            "উদাহরণ: `/rejecttask facebook 7236432836,8757506241 আপনার কুকিজ সঠিক ছিল না`",
            parse_mode="Markdown"
        )
        return

    task_type_key = parts[1].strip().lower()
    task_type_names = {
        "facebook": "ফেসবুকের",
        "instagram": "ইনস্টাগ্রামের",
        "gmail": "জিমেইলের",
    }
    if task_type_key not in task_type_names:
        bot.reply_to(message, "⚠️ কাজের ধরন ভুল। এই তিনটার একটা দিন: `facebook`, `instagram`, `gmail`", parse_mode="Markdown")
        return

    raw_ids = parts[2]
    reason = parts[3]

    user_ids = []
    for piece in raw_ids.split(','):
        piece = piece.strip()
        if piece.isdigit():
            user_ids.append(int(piece))

    if not user_ids:
        bot.reply_to(message, "⚠️ কোনো সঠিক User ID পাওয়া যায়নি। কমা (,) দিয়ে আলাদা করে ID দিন।")
        return

    bot.reply_to(message, f"⏳ {len(user_ids)} জনের টাস্ক রিজেক্ট করা হচ্ছে, একটু সময় লাগতে পারে...")

    threading.Thread(
        target=_do_reject_tasks,
        args=(message.chat.id, user_ids, reason, task_type_names[task_type_key], task_type_key),
        daemon=True
    ).start()

def _do_reject_tasks(admin_chat_id, user_ids, reason, task_type_display, task_type_key=None):
    rejected = []
    not_found = []

    for uid in user_ids:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
        row = cur.fetchone()

        if not row:
            not_found.append(uid)
            cur.close()
            release_db_connection(conn)
            continue

        # ওই ইউজারের pending_tasks থেকে ১টা কমানো হলো (০ এর নিচে যাবে না)
        cur.execute(
            "UPDATE users SET pending_tasks = GREATEST(pending_tasks - 1, 0) WHERE user_id = %s",
            (uid,)
        )
        conn.commit()
        cur.close()
        release_db_connection(conn)

        # নির্দিষ্ট টাইপ মিলিয়ে সবচেয়ে পুরনো pending টাস্কটাকে rejected মার্ক করা হচ্ছে
        mark_oldest_pending_task(uid, 'rejected', type_keyword=task_type_key)

        rejected.append(uid)

    # প্রতিটা affected ইউজারকে রিজেকশন মেসেজ পাঠানো হচ্ছে
    sent = 0
    failed_send = 0
    for uid in rejected:
        try:
            bot.send_message(
                uid,
                f"❌ **আপনার {task_type_display} একটি কাজ বাতিল করা হয়েছে!**\n\n"
                f"📝 **কারণ:** {reason}\n\n"
                f"পরবর্তীতে নিয়ম মেনে কাজ করার চেষ্টা করুন। কোনো প্রশ্ন থাকলে সাপোর্টে যোগাযোগ করুন।",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed_send += 1
        time.sleep(0.05)

    summary = (
        f"❌ {task_type_display} টাস্ক রিজেক্ট হয়েছে!\n"
        f"পরিমাণ: {len(rejected)} টি\n"
        f"📨 মেসেজ পাঠানো হয়েছে: {sent} জনকে\n"
    )
    if failed_send:
        summary += f"⚠️ মেসেজ পাঠানো যায়নি: {failed_send} জনকে\n"
    if not_found:
        summary += f"❓ খুঁজে পাওয়া যায়নি: {', '.join(map(str, not_found))}\n"

    try:
        bot.send_message(admin_chat_id, summary, parse_mode="Markdown")
    except:
        pass

# --- স্টার্ট কমান্ড ও সাবস্ক্রিপশন চেক হ্যান্ডলার ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    user_data = get_user_data(user_id)

    # ব্যান করা ইউজারকে কোনো রেসপন্স না দিয়ে চুপচাপ ইগনোর করা হচ্ছে
    if user_data.get('banned'):
        return

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

    # স্প্যাম প্রোটেকশন - আগের রিকোয়েস্ট প্রসেস হতে থাকলে নতুনটা বাদ যাবে
    if not try_start_processing(user_id):
        try:
            bot.answer_callback_query(call.id)
        except:
            pass
        return
    try:
        _callback_check_sub_inner(call, user_id)
    finally:
        end_processing(user_id)

def _callback_check_sub_inner(call, user_id):
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

    # স্প্যাম/বারবার-ক্লিক প্রোটেকশন - আগের রিকোয়েস্ট প্রসেস হতে থাকলে নতুনটা বাদ যাবে
    if not try_start_processing(user_id):
        return
    try:
        _handle_menu_inner(message, user_id)
    finally:
        end_processing(user_id)

def _handle_menu_inner(message, user_id):
    text = message.text
    user_data = get_user_data(user_id)

    # ব্যান করা ইউজারের কোনো মেসেজেই বট রেসপন্স করবে না (চুপচাপ ইগনোর)
    if user_data.get('banned'):
        return

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

    if current_state == 'WAITING_FOR_FB_COOKIES':
        if not is_valid_fb_cookie(text):
            bot.send_message(message.chat.id, "😔 দুঃখিত, এটি সঠিক কুকিজ নয়! অনুগ্রহ করে সঠিক কুকিজটি দিন।", reply_markup=cancel_keyboard(), parse_mode="Markdown")
            return

        update_user_data(user_id, {"state": None})
        acc_name = user_data.get('generated_username', 'Account User')
        acc_pass = user_data.get('generated_password', '12345678')
        task_type = user_data.get('task_type', 'টাস্ক')

        update_user_data(user_id, {"pending_tasks": user_data['pending_tasks'] + 1})

        # টাস্কটি সরাসরি ডাটাবেজে সেভ করা হলো
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO submitted_tasks (user_id, task_type, acc_name, acc_pass, task_data)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user_id, task_type, acc_name, acc_pass, text))
        conn.commit()
        cur.close()
        release_db_connection(conn)

        channel_msg = (
            f"📥 **নতুন কাজ জমা পড়েছে!**\n\n"
            f"👤 **User ID:** `{user_id}`\n"
            f"📌 **Type:** {task_type}\n"
            f"🟢 **Name:** {acc_name}\n"
            f"🔐 **Pass:** {acc_pass}\n\n"
            f"📄 **Data:**\n{text}"
        )
        try:
            bot.send_message(NOTIFY_CHANNEL_ID, channel_msg, parse_mode="Markdown")
        except:
            pass

        bot.send_message(message.chat.id, "✅ **Rcv**\n\nএটার টাকা খুব শীঘ্রই চেক করে আপনার ব্যালেন্সে এড করা হবে", reply_markup=main_keyboard(), parse_mode="Markdown")
        return

    elif current_state == 'WAITING_FOR_2FA':
        update_user_data(user_id, {"state": None})
        acc_name = user_data.get('generated_username', 'Account User')
        acc_pass = user_data.get('generated_password', '12345678')
        task_type = user_data.get('task_type', 'টাস্ক')

        update_user_data(user_id, {"pending_tasks": user_data['pending_tasks'] + 1})

        # টাস্কটি সরাসরি ডাটাবেজে সেভ করা হলো
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO submitted_tasks (user_id, task_type, acc_name, acc_pass, task_data)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user_id, task_type, acc_name, acc_pass, text))
        conn.commit()
        cur.close()
        release_db_connection(conn)

        channel_msg = (
            f"📥 **নতুন কাজ জমা পড়েছে!**\n\n"
            f"👤 **User ID:** `{user_id}`\n"
            f"📌 **Type:** {task_type}\n"
            f"🟢 **Name:** {acc_name}\n"
            f"🔐 **Pass:** {acc_pass}\n\n"
            f"📄 **Data:**\n{text}"
        )
        try:
            bot.send_message(NOTIFY_CHANNEL_ID, channel_msg, parse_mode="Markdown")
        except:
            pass

        bot.send_message(message.chat.id, "✅ **Rcv**\n\nএটার টাকা খুব শীঘ্রই চেক করে আপনার ব্যালেন্সে এড করা হবে", reply_markup=main_keyboard(), parse_mode="Markdown")
        return

    elif current_state == 'WAITING_FOR_WITHDRAW_NUMBER':
        method = user_data.get('withdraw_method', 'N/A')

        if "USDT" in method:
            if not is_valid_usdt_address(text):
                bot.send_message(message.chat.id, "😔 দুঃখিত, আপনার USDT (BEP-20) অ্যাড্রেসটি সঠিক নয়", reply_markup=cancel_keyboard(), parse_mode="Markdown")
                return
        else:
            if not is_valid_phone_number(text):
                bot.send_message(message.chat.id, "😔 দুঃখিত, আপনার নাম্বারটি সঠিক নয়। অনুগ্রহ করে সঠিক নাম্বারটি দিন।", reply_markup=cancel_keyboard(), parse_mode="Markdown")
                return

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

        # উইথড্র রিকোয়েস্টটি ডাটাবেজে সেভ করা হলো, যাতে /history কমান্ডে দেখা যায়
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO withdrawals (user_id, amount, method, address)
            VALUES (%s, %s, %s, %s)
        ''', (user_id, amount_to_log, method, address))
        conn.commit()
        cur.close()
        release_db_connection(conn)

        channel_withdraw_msg = (
            f"💰 **নতুন উইথড্রয়াল রিকোয়েস্ট!**\n\n"
            f"👤 **ইউজার:** {message.from_user.first_name}\n"
            f"🆔 **আইডি:** `{user_id}`\n"
            f"💵 **পরিমাণ:** {amount_to_log} টাকা\n"
            f"🏦 **মেথড:** {method}\n"
            f"📱 **অ্যাকাউন্ট:** `{address}`"
        )
        try:
            bot.send_message(NOTIFY_CHANNEL_ID, channel_withdraw_msg, parse_mode="Markdown")
        except:
            pass

        bot.send_message(message.chat.id, f"✅ **আপনার উইথড্রয়াল রিকোয়েস্ট সফলভাবে জমা হয়েছে!**", reply_markup=main_keyboard(), parse_mode="Markdown")
        return

    # মেনু নেভিগেশন
    if text == '📖 কাজ ▸':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=category_keyboard(), parse_mode="Markdown")

    elif text == '📷 ইনস্টাগ্রাম কাজ >':
        bot.send_message(message.chat.id, "⚠️ **ইনস্টাগ্রামের কাজ এখন বন্ধ আছে, ফেসবুকের কাজ করতে পারেন।**", reply_markup=category_keyboard(), parse_mode="Markdown")

    elif text == '📧 Gmail কাজ':
        bot.send_message(message.chat.id, "⚠️ **জিমেইলের কাজ এখন বন্ধ আছে, ফেসবুকের কাজ করতে পারেন।**", reply_markup=category_keyboard(), parse_mode="Markdown")

    elif text == '📘 Facebook কাজ':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=fb_sub_keyboard(), parse_mode="Markdown")

    elif text == '4.00৳':
        first_name, last_name = generate_random_full_name()
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

    elif text == '🤪 কিভাবে কাজ করব':
        bot.send_message(message.chat.id, "🤪 **কাজ সম্পর্কিত বিস্তারিত জানতে সাপোর্টে যোগাযোগ করুন।**", parse_mode="Markdown")

    elif text == '⏮ ফিরে যান':
        bot.send_message(message.chat.id, "🟣 **সিলেক্ট করুন:**", reply_markup=category_keyboard(), parse_mode="Markdown")

    elif text == 'উইথড্র':
        update_user_data(user_id, {"state": 'SELECT_WITHDRAW_METHOD'})
        bot.send_message(message.chat.id, "💰 **মাধ্যম সিলেক্ট করুন:**", reply_markup=withdraw_methods_keyboard(), parse_mode="Markdown")

    elif text in ['USDT (BEP-20) -> সর্বনিম্ন: 0.3(-0.05)', 'মোবাইল রিচার্জ -> সর্বনিম্ন: ৩০(-৫)', 'বিকাশ -> সর্বনিম্ন: ৫০ (-⁵)']:
        update_user_data(user_id, {
            "withdraw_method": text,
            "state": 'WAITING_FOR_WITHDRAW_NUMBER'
        })
        bot.send_message(message.chat.id, "আপনার নম্বর বা অ্যাড্রেসটি দিন", reply_markup=cancel_keyboard(), parse_mode="Markdown")

    elif text == '💵 ব্যালেন্স':
        bal = user_data["balance"]
        total_inc = user_data["total_income"]
        comp_tasks = user_data["completed_tasks"]
        pend_tasks = user_data["pending_tasks"]
        balance_msg = (
            f"💵 আপনার ব্যালেন্স\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"💸 ব্যালেন্স: {bal:.2f} BDT\n"
            f"💰 Total Income: {total_inc:.2f} BDT\n"
            f"━━━━━━━━━━━━━━━━━\n\n"
            f"✅ সম্পন্ন কাজ: {comp_tasks} টি\n"
            f"⏳ রিভিউতে আছে: {pend_tasks} টি"
        )
        bot.send_message(message.chat.id, balance_msg, reply_markup=main_keyboard(), parse_mode="Markdown")

    elif text == 'রেফার':
        ref_count = user_data["referrals"]
        ref_income = user_data["refer_income"]
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        ref_msg = (
            f"👥 **আপনার রেফারেল তথ্য**\n\n"
            f"🔗 **আপনার রেফারেল লিংক:**\n`{ref_link}`\n\n"
            f"👤 **মোট রেফারেল:** {ref_count} জন\n"
            f"💰 **রেফারেল থেকে ইনকাম:** {ref_income:.2f} BDT\n\n"
            f"প্রতিটি রেফারেলের কাজের ইনকাম থেকে আপনি ১০% কমিশন পাবেন।"
        )
        bot.send_message(message.chat.id, ref_msg, reply_markup=main_keyboard(), parse_mode="Markdown")

    elif text == '🧐 সাপোর্ট':
        support_msg = (
            "📞 সাপোর্ট সেন্টার\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "প্রিয় সদস্য,\n\n"
            "যেকোনো সমস্যা, প্রশ্ন বা সহায়তার প্রয়োজনে আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করুন। আমরা যত দ্রুত সম্ভব আপনাকে সহযোগিতা করার চেষ্টা করব।\n\n"
            "দ্রষ্টব্য: প্রয়োজনীয় বিষয়েই যোগাযোগ করুন এবং অপ্রয়োজনীয় বার্তা পাঠানো থেকে বিরত থাকুন।\n\n"
            "ধন্যবাদ।"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📩 সাপোর্টে যোগাযোগ করুন", url=ADMIN_SUPPORT_URL),
            types.InlineKeyboardButton("📢 চ্যানেলে যোগ দিন", url=CHANNEL_URL)
        )
        bot.send_message(message.chat.id, support_msg, reply_markup=markup, parse_mode="Markdown")

    elif text == '🧑\u200d💼 আমি নতুন':
        new_user_msg = (
            "🧑\u200d💼 **নতুনদের জন্য সহায়িকা**\n\n"
            "১️⃣ '📖 কাজ ▸' বাটনে চাপ দিয়ে একটি কাজ বেছে নিন\n"
            "২️⃣ নির্দেশনা অনুযায়ী অ্যাকাউন্ট তৈরি করুন\n"
            "৩️⃣ চাওয়া তথ্য জমা দিন\n"
            "8️⃣ কাজ যাচাই হলে ব্যালেন্সে টাকা যোগ হবে\n\n"
            "কোনো সমস্যা হলে '🧐 সাপোর্ট' বাটনে যোগাযোগ করুন।"
        )
        bot.send_message(message.chat.id, new_user_msg, reply_markup=main_keyboard(), parse_mode="Markdown")

# --- সার্ভার চালু করা ---

# আগে app.run() (Flask-এর built-in dev server) দিয়ে চালানো হতো, যেটা
# single-threaded এবং প্রোডাকশনের জন্য উপযুক্ত না - একসাথে বেশি রিকোয়েস্ট
# আসলে একটার পর একটা লাইনে দাঁড়িয়ে থাকত, তাই বট স্লো/বন্ধ মনে হতো।
#
# এখন Render-এ gunicorn ব্যবহার করে চালাতে হবে (multi-worker/thread সাপোর্ট করে)।
# Render Dashboard -> Settings -> Start Command এ বসাও:
#
#     gunicorn main-4:app --workers 2 --threads 8 --timeout 120
#
# (ফাইলের নাম main-4.py হলে "main-4:app", অথবা main.py রাখলে "main:app")
#
# gunicorn দিয়ে চালালে webhook সেট করার কোডটা module load হওয়ার সময়েই
# রান করতে হবে (নিচে), কারণ gunicorn `if __name__ == "__main__"` ব্লক
# চালায় না - সরাসরি app অবজেক্ট ইমপোর্ট করে ব্যবহার করে।

if RENDER_EXTERNAL_URL:
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{TOKEN}")

if __name__ == "__main__":
    if RENDER_EXTERNAL_URL:
        # সেফটি-নেট: gunicorn ছাড়া (ভুলবশত) সরাসরি রান হলেও threaded=True
        # দেওয়া থাকায় Flask-এর dev server একসাথে একাধিক রিকোয়েস্ট নিতে পারবে।
        # তবে প্রোডাকশনে অবশ্যই উপরের gunicorn কমান্ড Start Command-এ বসাতে হবে,
        # কারণ dev server-এর concurrency সীমিত ও প্রোডাকশনের জন্য যথেষ্ট স্থিতিশীল না।
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), threaded=True)
    else:
        bot.remove_webhook()
        bot.infinity_polling()

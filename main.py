import telebot
from telebot import types

TOKEN = '8720565653:AAFltxQwffiTi5DmTwQKud-Wh1SkZlyVHm8'
bot = telebot.TeleBot(TOKEN)

def main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('📖 কাজ ▸', '💵 ব্যালেন্স', '💰 টাকা উত্তোলন', '🎁 My Referrals', '🧐 সাপোর্ট', '👨‍💼 আমি নতুন')
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, f"হ্যালো {message.from_user.first_name}!\nবটে আপনাকে স্বাগতম।", reply_markup=main_menu())

@bot.message_handler(func=lambda message: True)
def handle_buttons(message):
    text = message.text
    if text == '📖 কাজ ▸':
        bot.reply_to(message, "আপনার কাজ শীঘ্রই আসছে।")
    elif text == '💵 ব্যালেন্স':
        bot.reply_to(message, "আপনার বর্তমান ব্যালেন্স: ০ টাকা")
    elif text == '💰 টাকা উত্তোলন':
        bot.reply_to(message, "উত্তোলনের জন্য সর্বনিম্ন ব্যালেন্স ১০০ টাকা।")
    elif text == '🎁 My Referrals':
        bot.reply_to(message, "আপনার রেফারেল লিংক তৈরির কাজ চলছে।")
    elif text == '🧐 সাপোর্ট':
        bot.reply_to(message, "যেকোনো সহায়তার জন্য অ্যাডমিনকে মেসেজ দিন।")
    elif text == '👨‍💼 আমি নতুন':
        bot.reply_to(message, "বটে কিভাবে কাজ করবেন তার নিয়মাবলী এখানে দেখতে পাবেন।")

bot.infinity_polling()


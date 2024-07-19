from collections import defaultdict
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, Poll, PollAnswer
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    ConversationHandler,
    PollAnswerHandler,   
    Defaults,
    JobQueue,
    CallbackQueryHandler
)
import re
from random import randint
import logging
import io
import os
from datetime import datetime, timedelta, time
import sqlite3
import httpx

# Application builder setup
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
admin_bot_username = os.getenv("admin_bot_username")
admin_bot_username2 = os.getenv("admin_bot_username2")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
ADMIN = os.getenv("ADMIN").split(',') 
previous_opinions = []
# ایجاد اپلیکیشن تلگرام
application = ApplicationBuilder().token(TOKEN).build()

# متغیرهای جهانی برای ذخیره اطلاعات کاربران
user_registration = {}
user_language = {}
user_referrals = {}
verification_codes = {}

# مراحل مختلف مکالمه
LANGUAGE, EMAIL, MAIN_MENU, VERIFY = range(4)

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

async def send_registration_summary(context: CallbackContext):
    total_registrations = len(user_registration)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"تعداد کل افراد ثبت‌نامی تا {current_time}:\n{total_registrations} نفر"
    
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
    except Exception as e:
        logging.error(f"Error sending registration summary: {e}")

 
# تابع شروع
async def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    
    if chat_id == ADMIN_CHAT_ID:    
     await context.bot.send_message(chat_id=chat_id, text="تعداد ثبت‌ نامی هر ۱۲ ساعت.")
    if str(chat_id) in ADMIN:
        await context.bot.send_message(chat_id=chat_id, text="Welcome back, Admin.")
        return ConversationHandler.END
    
    referral_id = context.args[0] if context.args else None
    
    if referral_id and referral_id.isdigit():
        referral_id = int(referral_id)
        if referral_id != chat_id and referral_id in user_registration:
            user_referrals[referral_id] = user_referrals.get(referral_id, 0) + 1
    
    if chat_id in user_registration:
        await context.bot.send_message(chat_id=chat_id, text="You are already registered.")
        return ConversationHandler.END
    else:
        keyboard_buttons = [
            [KeyboardButton('فارسی'), KeyboardButton('English')]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard_buttons, one_time_keyboard=True, resize_keyboard=True)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="Please select your language: \n \n Benefiting the global community even in small amounts! \n\n لطفاً زبان خود را انتخاب کنید: \n\n  نفع رساندن به جامعه جهانی حتی به مقدار کم!",
            reply_markup=reply_markup
        )
        return LANGUAGE

# تابع انتخاب زبان
async def select_language(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    language = update.message.text
    
    if language == 'فارسی':
        user_language[chat_id] = 'fa'
        await context.bot.send_message(chat_id=chat_id, text="لطفاً ایمیل خود را وارد کنید.")
    elif language == 'English':
        user_language[chat_id] = 'en'
        await context.bot.send_message(chat_id=chat_id, text="Please enter your email.")
    else:
        await context.bot.send_message(chat_id=chat_id, text="Invalid selection. Please choose a valid language.")
        return LANGUAGE
    
    return EMAIL

# تابع ثبت ایمیل کاربر
async def email(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    email = update.message.text
    lang = user_language.get(chat_id, 'fa')
    
    # بررسی صحت ایمیل
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@([a-zA-Z0-9.-]+\.)+com$')
    if not email_pattern.match(email):
        if lang == 'fa':
            await context.bot.send_message(chat_id=chat_id, text="ایمیل نامعتبر است. لطفاً یک ایمیل معتبر وارد کنید.")
        else:
            await context.bot.send_message(chat_id=chat_id, text="Invalid email. Please enter a valid email.")
        return EMAIL
    
    if chat_id in user_registration:
        await context.bot.send_message(chat_id=chat_id, text="You are already registered.")
        return ConversationHandler.END
    
    # بررسی اینکه ایمیل قبلاً ثبت شده یا نه
    for stored_chat_id, data in user_registration.items():
        if data.get('email') == email:
            if lang == 'fa':
                await context.bot.send_message(chat_id=chat_id, text="این ایمیل قبلاً ثبت‌ نام شده است.")
            else:
                await context.bot.send_message(chat_id=chat_id, text="This email is already registered.")
            return ConversationHandler.END
    
    # ذخیره اطلاعات ثبت‌نام کاربر
    user_registration[chat_id] = {'email': email}
    
    # ارسال پیام تأیید ثبت موفقیت‌آمیز ایمیل
    if lang == 'fa':
        await context.bot.send_message(chat_id=chat_id, text="ایمیل شما با موفقیت ثبت شد.")
    else:
        await context.bot.send_message(chat_id=chat_id, text="Your email has been successfully registered.")
    
    # ایجاد و ارسال کد تأیید دو مرحله‌ای
    verification_code = randint(100000, 999999)
    verification_codes[chat_id] = verification_code
    if lang == 'fa':
        await context.bot.send_message(chat_id=chat_id, text=f"کد تأیید شما: {verification_code}\nلطفاً این کد را وارد کنید.")
    else:
        await context.bot.send_message(chat_id=chat_id, text=f"Your verification code: {verification_code}\nPlease enter this code.")
    
    return VERIFY

# تابع تأیید دو مرحله‌ای
async def verify(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    code = update.message.text
    lang = user_language.get(chat_id, 'fa')
    
    if chat_id not in verification_codes or verification_codes[chat_id] != int(code):
        if lang == 'fa':
            await context.bot.send_message(chat_id=chat_id, text="کد تأیید نامعتبر است. لطفاً دوباره تلاش کنید.")
            await context.bot.send_message(chat_id=chat_id, text="لطفاً کد تأیید را دوباره وارد کنید.")
        else:
            await context.bot.send_message(chat_id=chat_id, text="Invalid verification code. Please try again.")
            await context.bot.send_message(chat_id=chat_id, text="Please enter the verification code again.")
        return VERIFY
    
    del verification_codes[chat_id]
    # ذخیره اطلاعات ثبت‌نام کاربر (اطمینان از اینکه ایمیل ذخیره شده است)
    if chat_id in user_registration and 'email' in user_registration[chat_id]:
        email = user_registration[chat_id]['email']
    else:
        email = None
    
    if email:
        if lang == 'fa':
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"درود \n \nنام کاربری: @{update.message.from_user.username} \n \nآیدی: {chat_id} \n \nایمیل: {email} \n \nخوش آمدید"
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Hello \n \nUsername: @{update.message.from_user.username} \n \nID: {chat_id} \n \nEmail: {email} \n \nWelcome"
            )
    
        # Send registration info to admin bot
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"New registration:\n\nUsername: @{update.message.from_user.username}\nID: {chat_id}\nEmail: {email}"
        )
    
    # Show main menu if registration is successful
    if chat_id == ADMIN_CHAT_ID:
        main_menu_keyboard = [
            [KeyboardButton('تعداد اعضا')],
            [KeyboardButton('بازگشت')]
        ]
        reply_markup = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="لطفاً یک گزینه را انتخاب کنید:",
            reply_markup=reply_markup
        )
    else:
        referral_link = f"https://t.me/{context.bot.username}?start={chat_id}"
        user_referrals[chat_id] = 0

    if lang == 'fa':
        main_menu_keyboard = [[KeyboardButton('⚖️ قوانین ⚖️')],
            [KeyboardButton('اخبار 📣')],
            [KeyboardButton('عضوگیری 👨‍👩‍👧‍👦')]

        ]
        reply_markup = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"لینک عضویت شما: {referral_link}"
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text="لطفاً یک گزینه را انتخاب کنید:",
            reply_markup=reply_markup
        )

    else:
        main_menu_keyboard = [[KeyboardButton('⚖️ Rules ⚖️')],
            [KeyboardButton('News 📣')],
            [KeyboardButton('Membership 👨‍👩‍👧‍👦')]
    
        ]
        reply_markup = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Referral link: {referral_link}"
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text="Please select an option:",
            reply_markup=reply_markup
        )
    
    return MAIN_MENU

# Handle main menu options
async def main_menu(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    text = update.message.text
    lang = user_language.get(chat_id, 'fa')

    # مدیریت دیگر گزینه‌های منو
    if text == '⚖️ قوانین ⚖️' or text == '⚖️ Rules ⚖️':
        if lang == 'fa':
            await context.bot.send_message(chat_id=chat_id, text="به قسمت قوانین خوش آمدید: \n\n اینجا قوانین به شرح زیر میباشد: \n\n 1:ثبت نام با هر ایدی تلگرام یک بار و با یک ایمیل باید انجام شود درصورت خلاف آیدی متخلف بلاک میشود. \n\n 2:شما میتوانید هر مقدار که میخواهید عضو گیری انجام دهید. \n\n 3:هر ماه شما زمان دارید که هزینه مورد نظر را ارسال نمایید. \n\n 4:شما باید هر دو هفته یک بار هزینه اشتراک به مبلغی که در قسمت خرید نمایش داده میشود پرداخت نمایید.درصورت عدم پرداخت آید شخص تا دو ماه حق فعالیت ندارد. \n\n 5:شما میتوانید درصورت اعلام با کلید ارتباط با ما اعلام نمایید که مثال:من تا تاریخ ... نمیتوانم حق عضویت پرداخت کنم در اینصورت آیدی شخص میتواند به فعالیت خود ادامه دهد. \n\n 6:این قوانین سخت گیرانه به نفع همه میباشد و امید داریم کسی را ناراحت نکرده باشیم.با احترام تیم Smart_cash 😉 \n\n 7:این قوانین ادامه دارد!")
        else:
            await context.bot.send_message(chat_id=chat_id, text="Welcome to the rules section: \n\n Here are the rules as follows: \n\n 1: Registration must be done once with each Telegram ID and with one email, otherwise the offending ID will be blocked. \n\n 2: You can subscribe as much as you want. 3: Every month you have time to send the desired fee. 4: You have to pay the subscription fee every two weeks It will be displayed in the purchase section, please pay. In case of non-payment, the person will not have the right to work for two months. 5: You can inform us with the contact key that, for example, I will not be able to become a member until the date... In this case, the person's ID can continue to operate. \n\n 6: These strict rules are for the benefit of everyone and we hope that we have not upset anyone. With respect to the Smart_cash team 😉 \n\n 7: These rules continue has it!")

        return MAIN_MENU
    
    if text == 'اخبار 📣' or text == 'News 📣':
        if lang == 'fa':
            await context.bot.send_message(chat_id=chat_id, text="به قسمت اخبار خوش آمدید:\n\nشاید با خودتون فکر کنید که چرا من اینجا هستم؟! علت این هست که شما میتونید برنده باشید!این یک تحول بسیار بزرگ است!ما در کنار شما هستیم.اینها شعار نیست ما آمده ایم که شعارها را حذف کنیم و به دنیای واقعی زندگی ببخشیم با کمک خدا.پس بیایید یک خانواده بزرگی را تشکیل دهیم و پایبند به حقوق و قوانین آن باشیم.ما میتوانیم بالا برویم بدون این که به دیگران آسیب بزنیم یا ناراحتی بوجود بیاوریم!ما حامی طبیعت و محیط زیست هستیم این میتواند تاثیر مستقیم بر زندگی ما و آیندگان داشته باشد!پس بیاید از خودمان شروع کنیم.زندگی حق ما هست.خبرهای خوبی در راه است!منتظر باشید.")
        else:
            await context.bot.send_message(chat_id=chat_id, text="Welcome to the news section:\n\nMaybe you are thinking to yourself, why am I here? The reason is that you can win! This is a huge change! We are with you. These are not slogans. We have come to remove the slogans and give life to the real world with God's help. So let's be a family. form a greatness and adhere to its rights and laws. We can climb without hurting or causing discomfort to others! We support nature and the environment. This can directly affect our lives and future generations! Let's start with ourselves. Life is ours. Good news is coming! Be patient.")

        return MAIN_MENU
    
    elif text == 'آموزش 📝' or text == 'Education 📝':
        if lang == 'fa':
            await context.bot.send_message(chat_id=chat_id, text="به قسمت آموزش خوش آمدید:دراینجا قصد داریم با هم بپردازیم به نحوه کار با ربات دوستان بعد از ثبت ایمیل شما میتونید فعالیت خودتون در ربات رو شروع کنید فقط دقت داشته باشید که ایمیل واقعی ثبت کنید!!! بعد میتونید به خرید ها برید در اون قسمت میتونید مبلغی که نوشته شده رو ببینید و اگر دوست داشتید میتونید برای خودتون سرمایه گذاری کنید❗️بعد ارزی که باید بفرستید مشخص شده و در قسمت بعدی آدرس کیف پول دیجیتال ودر آخر شبکه این ارز نوشته شده که باید دقت کنید که شبکه رو برای ارسال درست انتخاب کرده باشید❗️بعد از ارسال مبلغ منتظر اعلام نتایج باشید همچنین در گزینه اخبار فعال باشید خبر های خوبی در راه است❗️برای آموزش های بیشتر به این قسمت سر بزنید چون همیشه گزینه ها آپدیت میشه ")
        else:
            await context.bot.send_message(chat_id=chat_id, text="Welcome to the training section: here we are going to discuss how to work with the robot, friends, after registering your email, you can start your activity in the robot, just be careful to register a real email!!! Then you can go to purchases, in that part you can see the amount written and if you like, you can invest for yourself❗️ Then the currency you need to send is specified and in the next part the address of the digital wallet and at the end of the network of this currency is written that You must make sure that you have selected the correct network for sending ❗️ After sending the amount, wait for the announcement of the results. Also, be active in the news option, good news is coming. ❗️ For more training, visit this section because the options are always updated.")

        contact_button = InlineKeyboardButton(text="آموزش 📝", url=f"https://www.google.com") if lang == 'fa' else InlineKeyboardButton(text="Education 📝", url=f"https://www.google.com")
        reply_markup = InlineKeyboardMarkup([[contact_button]])

        await context.bot.send_message(
            chat_id=chat_id,
            text="برای دیدن آموزش عملیات خرید روی دکمه زیر کلیک کنید." if lang == 'fa' else "Click on the button below to see the purchase operation tutorial.",
            reply_markup=reply_markup
        )

        return MAIN_MENU

    elif text == 'خرید 🛒' or text == 'Purchase 🛒':
        if lang == 'fa':
            await context.bot.send_message(chat_id=chat_id, text="به قسمت خرید خوش آمدید:\n قیمت 10000 تومان: \n \n ارز پرداختی: tether \n \n ادرس پرداخت:\n\n TUsStz7DSwWuWiZtQCT2pZGztWiJa5WS6x \n \n شبکه پرداختی:Trc20")

            await context.bot.send_message(
            chat_id=chat_id, 
            text="TUsStz7DSwWuWiZtQCT2pZGztWiJa5WS6x"
        )
        else:
            await context.bot.send_message(chat_id=chat_id, text="Welcome to the purchase section: \n The price is $0.25 \n \n Payment currency: tether \n \n Payment address:\n\n TUsStz7DSwWuWiZtQCT2pZGztWiJa5WS6x \n \n Payment network: Trc20")
            
            await context.bot.send_message(
            chat_id=chat_id, 
            text="TUsStz7DSwWuWiZtQCT2pZGztWiJa5WS6x"
        )
            
        return MAIN_MENU

    elif text == 'ارسال عکس تراکنش 🎆' or text == 'Send Photo Transaction 🎆':
        if lang == 'fa':
            await context.bot.send_message(chat_id=chat_id, text="اسکرین شات هاتون رو با گزینه ارتباط با ما برای ما بفرستید.")
        else:
            await context.bot.send_message(chat_id=chat_id, text="Send us your screenshots with the contact us option.")

            return MAIN_MENU
        
    elif text == 'تراکنش برندگان 🎁' or text == 'Transaction Winners 🎁':
        if lang == 'fa':
            await context.bot.send_message(chat_id=chat_id, text="در این قسمت لیست هر دوره از کسانی که برنده شدند قرار داده میشه همراه با ای دی تلگرام اونها میتونید به راحتی بااونها در ارتباط باشید این میتونه خوب باشه!")
        else:
            await context.bot.send_message(chat_id=chat_id, text="In this section, the list of those who won each course is placed along with their Telegram ID, you can easily contact them, this can be good!")

        return MAIN_MENU
        
    elif text == 'عضوگیری 👨‍👩‍👧‍👦' or text == 'Membership 👨‍👩‍👧‍👦':
        if lang == 'fa':
            referral_link = f"https://t.me/{context.bot.username}?start={chat_id}"
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"لینک عضویت شما: {referral_link}\nتعداد کاربرانی که با لینک شما عضو شده‌اند: {user_referrals.get(chat_id, 0)}"
            )
        else:
            referral_link = f"https://t.me/{context.bot.username}?start={chat_id}"
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Your referral link: {referral_link}\nNumber of users who have joined using your link: {user_referrals.get(chat_id, 0)}"
            )

        return MAIN_MENU
    
    elif text == 'ارتباط با ما 📞' or text == 'Contact Us 📞':
        if lang == 'fa':
            contact_button = InlineKeyboardButton(text="ارتباط با ادمین", url=f"https://t.me/{admin_bot_username}")
        else:
            contact_button = InlineKeyboardButton(text="Contact Admin", url=f"https://t.me/{admin_bot_username2}")

        reply_markup = InlineKeyboardMarkup([[contact_button]])

        await context.bot.send_message(
            chat_id=chat_id,
            text="برای ارتباط با ادمین روی دکمه زیر کلیک کنید." if lang == 'fa' else "Click the button below to contact the admin.",
            reply_markup=reply_markup
        )

        return MAIN_MENU

    elif text ==  'یوتیوب 💎' or text == 'YOUTUBE 💎':
        if lang == 'fa':
            contact_button = InlineKeyboardButton(text="یوتیوب 💎", url=f"https://www.youtube.com/channel/YOUR_CHANNEL_ID")
        else:
            contact_button = InlineKeyboardButton(text="YOUTUBE 💎", url=f"https://www.youtube.com/channel/YOUR_CHANNEL_ID")
        reply_markup = InlineKeyboardMarkup([[contact_button]]) 
        await context.bot.send_message(
            chat_id=chat_id,
            text="برای ورود به سایت روی دکمه زیر کلیک کنید." if lang == 'fa' else "Click the button below to enter the site.",
            reply_markup=reply_markup
        )
        return MAIN_MENU
    
# تابع برای بررسی وضعیت ثبت‌نام
def check_registration_status(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # بررسی وجود کاربر در پایگاه داده
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY,name TEXT,email TEXT UNIQUE,registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,is_active BOOLEAN DEFAULT TRUE)")
    cursor.execute("SELECT registered FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()

    conn.close()

    # اگر کاربر در پایگاه داده وجود دارد و ثبت‌نام کرده است، مقدار True برمی‌گرداند
    if result:
        return result[0]
    else:
        return False

# تابع برای بررسی وضعیت ثبت‌نام
async def check_and_start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    lang = user_language.get(chat_id, 'fa')

    if check_registration_status(user_id):
        # ارسال منوی اصلی به کاربر
        await context.bot.send_message(
            chat_id=chat_id,
            text="Welcome to the main menu!\n\nبه منوی اصلی خوش آمدید!"
        )
    else:
        # ارسال پیام ثبت‌نام
        await context.bot.send_message(
            chat_id=chat_id,
            text="You are not registered. Please register first.\n\nشما ثبت‌نام نکرده‌اید. لطفاً ابتدا ثبت‌نام کنید."
        )

# دیتابیس ساده برای ذخیره ارجاعات و اطلاعات کاربران
user_registration = defaultdict(dict)
user_referrals = defaultdict(int)
referral_details = defaultdict(list)
previous_opinions = []

# تابع برای ارسال فایل جزئیات ثبت‌نام به ادمین
async def send_registration_file(context: CallbackContext):
    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"registration_details_{current_time}.txt"
    
    with io.StringIO() as output:
        for chat_id, data in user_registration.items():
            username = data.get('username', 'N/A')
            email = data.get('email', 'N/A')
            referrals = user_referrals.get(chat_id, 0)
            output.write(f"User ID: {chat_id}\nUsername: {username}\nEmail: {email}\nReferrals: {referrals}\n\n")
        
        output.seek(0)
        file_content = output.read()
    
    if not file_content.strip():  # Check if the file is empty
        logging.warning("The registration details file is empty. No file will be sent.")
        return
    
    file_bytes = io.BytesIO(file_content.encode('utf-8'))
    file_bytes.name = filename
    
    await context.bot.send_document(chat_id=ADMIN_CHAT_ID, document=file_bytes, filename=filename)

# تابع برای ارسال گزارش ماهانه به ادمین
async def send_monthly_report(context: CallbackContext) -> None:
    high_referrals = {user_id: count for user_id, count in user_referrals.items() if count > 20}
    if high_referrals:
        report_text = "گزارش کاربران با بیش از 20 ارجاع:\n\n"
        for user_id, count in high_referrals.items():
            # اضافه کردن اطلاعات کاربر اصلی
            report_text += f"کاربر {user_id} با {count} ارجاع:\n"
            for referral_id, referral_email in referral_details[user_id]:
                report_text += f"  - ارجاع {referral_id} (ایمیل: {referral_email})\n"
            report_text += "\n"
        
        try:
            # ارسال گزارش به صورت متن به ادمین
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=report_text
            )
        except Exception as e:
            logging.error(f"Error sending monthly report: {e}")

# برنامه‌ریزی اجرای تابع ارسال گزارش ماهانه
def schedule_monthly_report(job_queue):
    now = datetime.now()
    # محاسبه اولین روز ماه آینده
    first_day_next_month = (now.replace(day=1) + timedelta(days=31)).replace(day=1)
    job_time = datetime.combine(first_day_next_month, time.min)  # زمان اجرای گزارش (مثلاً ساعت 00:00:00)
    
    # اجرای تابع در زمان مشخص شده
    job_queue.run_once(
        send_monthly_report,
        when=(job_time - datetime.now()).total_seconds()
    )

    # برنامه‌ریزی اجرای تابع در هر ماه
    job_queue.run_repeating(
        send_monthly_report,
        interval=30 * 24 * 3600,  # یک ماه به ثانیه
        first=job_time
    )

    
# Conversation handler for user registration
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_language)],
        EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, email)],
        VERIFY: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify)],
        MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)]
    },
    fallbacks=[CommandHandler('start', start)],
)

callback_query_handler = CallbackQueryHandler(schedule_monthly_report)
callback_query_handler = CallbackQueryHandler(check_registration_status)
# Add handlers to application
application.add_handler(conv_handler)
application.add_handler(CallbackQueryHandler(check_registration_status))
application.add_handler(callback_query_handler)

# Job queue for sending registration details file every hour
job_queue = application.job_queue
schedule_monthly_report(job_queue)
job_queue.run_repeating(send_registration_file, interval=24 * 3600, first=0)
job_queue.run_repeating(send_monthly_report, interval=86400, first=0)  
job_queue.run_repeating(send_registration_summary, interval=24 * 3600, first=0) 
# Start the application
if __name__ == '__main__':
    application.run_polling()

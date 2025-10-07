import logging
import os
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# 🔑 Налаштування бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN не задан')
ADMIN_ID = 869393770  # твій ID
COOLDOWN_MINUTES = 5

# 📦 Пам'ять у процесі
user_last_message = {}        # {user_id: datetime} — для колдауна
blocked_users = set()         # {"@username"} — завжди з @ і в lowercase
admins = {ADMIN_ID}
cooldown_bypass_once = set()  # {user_id} — одноразовий пропуск після "Створити анкету"

# 📝 Логування
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# 🧩 Приклад анкети
EXAMPLE_ANKETA = """Приклад правильної анкети:
Ім'я:
Вік:
Місто:
Інтереси:
Про себе:
Телеграм: @свійЮзернейм"""

# ====== ХЕНДЛЕРИ КОМАНД ТА ПОВІДОМЛЕНЬ ======

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [KeyboardButton("Створити анкету")],
        [KeyboardButton("Чому мою анкету не виклали?")],
        [KeyboardButton("Зв'язатися з адміністрацією")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_html(
        rf"Привіт, {user.first_name or 'друже'}! ❤️ Ласкаво просимо до бота каналу "
        "«Шукаю інтернет друга/подругу». Тут ти швидко створиш анкету й опинишся в нашій дружній спільноті! ✨\n\n"
        "Натискай «Створити анкету», заповнюй приклад і відправляй мені. Я все акуратно передам адміну.😊",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    text = (update.message.text or "").strip()

    # 🔒 Перевірка блокування
    if user.username:
        uname = f"@{user.username.lower()}"
        if uname in blocked_users:
            await update.message.reply_text("На жаль, доступ обмежено. Якщо це помилка — напиши адміністрації. 🙏")
            return

    # 🟡 Кнопки — без колдауна і без оновлення часу
    if text == "Створити анкету":
        await update.message.reply_text(EXAMPLE_ANKETA)
        await update.message.reply_text(
            "Можеш скопіювати приклад вище, заповни своїми даними та надішли мені - я одразу передам адміну."
        )
        cooldown_bypass_once.add(user_id)
        return

    if text == "Чому мою анкету не виклали?":
        await update.message.reply_text(
            "Усі причини та поради описані тут: https://uafriends.netlify.app/ 📚\n"
            "Якщо щось не ясно — натисни «Зв'язатися з адміністрацією» 💬"
        )
        return

    if text == "Зв'язатися з адміністрацією":
        await update.message.reply_text(
            "Є питання або ідеї? Пиши сюди 👉 @Pidtrimkaanket_bot 💌\n"
            "Ми на зв'язку і завжди раді допомогти! ✨"
        )
        return

    # ⏱ Колдаун застосовується тільки до «звичайних» повідомлень (анкет)
    now = datetime.now()
    if user_id not in cooldown_bypass_once:
        last = user_last_message.get(user_id)
        if last:
            elapsed = now - last
            if elapsed < timedelta(minutes=COOLDOWN_MINUTES):
                remaining = timedelta(minutes=COOLDOWN_MINUTES) - elapsed
                minutes = max(1, int(remaining.total_seconds() // 60))  # показати щонайменше 1 хв
                await update.message.reply_text(
                    f"Трішки перепочинемо, щоб не було спаму 😇 "
                    f"Можеш написати знову через {minutes} хвилин."
                )
                return
    else:
        # одноразовий пропуск використано
        cooldown_bypass_once.discard(user_id)

    # 📤 Надсилаємо анкету адміну
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"Нова анкета від @{user.username or 'без_юзернейму'} (ID: {user_id}):\n\n{text}"
        )
    )
    await update.message.reply_text(
        "Дякуємо! 🌟 Анкету отримано і передано на модерацію. "
        "Слідкуй за каналом — скоро побачиш себе у каналі! 💙"
    )
    # оновлюємо час останнього «значущого» повідомлення
    user_last_message[user_id] = now

# ====== АДМІН-КОМАНДИ ======

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Ця команда лише для власника бота.")
        return
    if not context.args:
        await update.message.reply_text("Використання: /addadmin <user_id>")
        return
    try:
        new_admin_id = int(context.args[0])
        admins.add(new_admin_id)
        await update.message.reply_text(f"Адміна з ID {new_admin_id} додано. ✅")
    except ValueError:
        await update.message.reply_text("ID має бути числом.")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Ця команда лише для власника бота.")
        return
    if not context.args:
        admin_list = "\n".join([f"- {admin_id}" for admin_id in admins])
        await update.message.reply_text(
            f"Поточні адміни:\n{admin_list}\n\nВикористання: /removeadmin <user_id>"
        )
        return
    try:
        admin_to_remove = int(context.args[0])
        if admin_to_remove == ADMIN_ID:
            await update.message.reply_text("Неможливо видалити власника бота.")
        elif admin_to_remove in admins:
            admins.remove(admin_to_remove)
            await update.message.reply_text(f"Адміна з ID {admin_to_remove} видалено. 🗑️")
        else:
            await update.message.reply_text("Цей ID не знайдено серед адмінів.")
    except ValueError:
        await update.message.reply_text("ID має бути числом.")

async def block_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Ця команда лише для власника бота.")
        return
    if not context.args:
        await update.message.reply_text("Використання: /block @юзернейм")
        return
    username = context.args[0].lower()
    if not username.startswith('@'):
        username = f"@{username}"
    blocked_users.add(username)
    await update.message.reply_text(f"Користувача {username} додано до чорного списку. 🚫")

async def unblock_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Ця команда лише для власника бота.")
        return
    if not context.args:
        if blocked_users:
            blocked_list = "\n".join([f"- {u}" for u in blocked_users])
            await update.message.reply_text(
                f"Заблоковані користувачі:\n{blocked_list}\n\nВикористання: /unblock @юзернейм"
            )
        else:
            await update.message.reply_text("Чорний список порожній. ✅")
        return
    username = context.args[0].lower()
    if not username.startswith('@'):
        username = f"@{username}"
    if username in blocked_users:
        blocked_users.remove(username)
        await update.message.reply_text(f"Користувача {username} розблоковано. ✅")
    else:
        await update.message.reply_text("Цього користувача немає у чорному списку.")

# ====== ЗАПУСК ======

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Команди
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addadmin", add_admin))
    application.add_handler(CommandHandler("removeadmin", remove_admin))
    application.add_handler(CommandHandler("block", block_user_cmd))
    application.add_handler(CommandHandler("unblock", unblock_user_cmd))

    # Текстові повідомлення та кнопки
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == "__main__":
    main()

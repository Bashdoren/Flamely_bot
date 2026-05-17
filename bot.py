import logging
import firebase_admin
from firebase_admin import credentials, firestore
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8610496403:AAHLyRtghzD9A4QGsHNoS1CxNYa0q7FMYVE"
ADMIN_ID = 0  # Запусти бота, напиши /start — он покажет твой ID, вставь сюда
SERVICE_ACCOUNT_FILE = "serviceAccount.json"
# ================================

logging.basicConfig(level=logging.INFO)

cred = credentials.Certificate(SERVICE_ACCOUNT_FILE)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Состояния ConversationHandler
(
    WAIT_UID_PRIME, WAIT_UID_ELO, WAIT_ELO_VALUE,
    WAIT_UID_VERIFY, WAIT_VERIFY_TYPE,
    WAIT_SUPPORT_MSG, WAIT_SUPPORT_REPLY,
    WAIT_VERIFY_GAME_ID, WAIT_VERIFY_SOCIALS, WAIT_VERIFY_PHOTO
) = range(10)


# ========== УТИЛИТЫ ==========

def is_admin(user_id):
    return user_id == ADMIN_ID

def admin_required(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Нет доступа.")
            return ConversationHandler.END
        return await func(update, context)
    return wrapper


# ========== /start ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if ADMIN_ID == 0:
        await update.message.reply_text(f"Твой Telegram ID: {uid}\nВставь его в ADMIN_ID в коде.")
        return

    if is_admin(uid):
        kb = [
            [InlineKeyboardButton("💎 Prime", callback_data="admin_prime"),
             InlineKeyboardButton("📊 ELO", callback_data="admin_elo")],
            [InlineKeyboardButton("✅ Верификация", callback_data="admin_verify"),
             InlineKeyboardButton("💬 Тикеты", callback_data="admin_tickets")],
        ]
        await update.message.reply_text(
            "👑 Админ-панель:", reply_markup=InlineKeyboardMarkup(kb)
        )
    else:
        kb = [
            [InlineKeyboardButton("💎 Купить Prime", callback_data="buy_prime")],
            [InlineKeyboardButton("✅ Верификация", callback_data="start_verify")],
            [InlineKeyboardButton("💬 Поддержка", callback_data="support")],
        ]
        await update.message.reply_text(
            "👋 Добро пожаловать в Flamely!\nЧто хочешь сделать?",
            reply_markup=InlineKeyboardMarkup(kb)
        )


# ========== АДМИН: PRIME ==========

async def admin_prime_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    kb = [
        [InlineKeyboardButton("✅ Выдать", callback_data="prime_give"),
         InlineKeyboardButton("❌ Снять", callback_data="prime_remove")]
    ]
    await query.edit_message_text("💎 Prime — выберите действие:", reply_markup=InlineKeyboardMarkup(kb))

async def prime_give_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["prime_action"] = "give"
    await query.edit_message_text("Введите UID игрока для выдачи Prime:")
    return WAIT_UID_PRIME

async def prime_remove_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["prime_action"] = "remove"
    await query.edit_message_text("Введите UID игрока для снятия Prime:")
    return WAIT_UID_PRIME

async def prime_uid_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    uid = update.message.text.strip()
    action = context.user_data.get("prime_action")
    value = action == "give"
    db.collection("users").document(uid).set({"prime": value}, merge=True)
    status = "выдан ✅" if value else "снят ❌"
    await update.message.reply_text(f"💎 Prime {status} игроку {uid}")
    return ConversationHandler.END


# ========== АДМИН: ELO ==========

async def admin_elo_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    await query.edit_message_text("📊 Введите UID игрока для изменения ELO:")
    return WAIT_UID_ELO

async def elo_uid_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data["elo_uid"] = update.message.text.strip()
    await update.message.reply_text("Введите новое значение ELO:")
    return WAIT_ELO_VALUE

async def elo_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        elo = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ ELO должно быть числом.")
        return WAIT_ELO_VALUE
    uid = context.user_data["elo_uid"]
    db.collection("users").document(uid).set({"elo": elo}, merge=True)
    await update.message.reply_text(f"📊 ELO установлено {elo} для {uid}")
    return ConversationHandler.END


# ========== АДМИН: ВЕРИФИКАЦИЯ ==========

async def admin_verify_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    await query.edit_message_text("✅ Введите UID игрока для верификации:")
    return WAIT_UID_VERIFY

async def verify_uid_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data["verify_uid"] = update.message.text.strip()
    kb = [
        [InlineKeyboardButton("🔵 Синяя", callback_data="verify_blue"),
         InlineKeyboardButton("🟡 Золотая", callback_data="verify_gold")],
        [InlineKeyboardButton("❌ Снять", callback_data="verify_remove")]
    ]
    await update.message.reply_text("Выберите тип верификации:", reply_markup=InlineKeyboardMarkup(kb))
    return WAIT_VERIFY_TYPE

async def verify_type_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = context.user_data.get("verify_uid")
    action = query.data

    if action == "verify_blue":
        db.collection("users").document(uid).set({"verification": "blue"}, merge=True)
        await query.edit_message_text(f"🔵 Синяя верификация выдана {uid}")
    elif action == "verify_gold":
        db.collection("users").document(uid).set({"verification": "gold"}, merge=True)
        await query.edit_message_text(f"🟡 Золотая верификация выдана {uid}")
    elif action == "verify_remove":
        db.collection("users").document(uid).set({"verification": None}, merge=True)
        await query.edit_message_text(f"❌ Верификация снята с {uid}")
    return ConversationHandler.END


# ========== АДМИН: ТИКЕТЫ ==========

async def admin_tickets_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    tickets = db.collection("support_tickets").where("status", "==", "open").stream()
    ticket_list = list(tickets)
    if not ticket_list:
        await query.edit_message_text("💬 Открытых тикетов нет.")
        return

    text = "💬 Открытые тикеты:\n\n"
    kb = []
    for t in ticket_list:
        data = t.to_dict()
        text += f"#{t.id[:6]} от {data.get('username','?')}: {data.get('message','')[:50]}\n"
        kb.append([InlineKeyboardButton(f"Ответить #{t.id[:6]}", callback_data=f"reply_{t.id}")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def reply_ticket_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticket_id = query.data.replace("reply_", "")
    context.user_data["reply_ticket_id"] = ticket_id
    await query.edit_message_text(f"Введите ответ на тикет #{ticket_id[:6]}:")
    return WAIT_SUPPORT_REPLY

async def support_reply_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    ticket_id = context.user_data["reply_ticket_id"]
    reply_text = update.message.text

    ticket = db.collection("support_tickets").document(ticket_id).get()
    if ticket.exists:
        user_tg_id = ticket.to_dict().get("telegram_id")
        db.collection("support_tickets").document(ticket_id).update({"status": "closed"})
        if user_tg_id:
            await context.bot.send_message(
                chat_id=user_tg_id,
                text=f"💬 Ответ поддержки:\n{reply_text}"
            )
    await update.message.reply_text("✅ Ответ отправлен, тикет закрыт.")
    return ConversationHandler.END


# ========== ИГРОК: ПОДДЕРЖКА ==========

async def support_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💬 Опишите вашу проблему:")
    return WAIT_SUPPORT_MSG

async def support_msg_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message.text
    ticket_ref = db.collection("support_tickets").add({
        "telegram_id": user.id,
        "username": user.username or user.first_name,
        "message": msg,
        "status": "open"
    })
    await update.message.reply_text("✅ Тикет создан! Ожидайте ответа от администратора.")
    if ADMIN_ID:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📩 Новый тикет от @{user.username or user.first_name}:\n{msg}"
        )
    return ConversationHandler.END


# ========== ИГРОК: ВЕРИФИКАЦИЯ ==========

async def start_verify_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✅ Верификация\n\nШаг 1: Введите ваш игровой ID (UID в игре):"
    )
    return WAIT_VERIFY_GAME_ID

async def verify_game_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["verify_game_id"] = update.message.text.strip()
    await update.message.reply_text(
        "Шаг 2: Отправьте ссылки на ваши соц. сети через запятую:\n"
        "Telegram, TikTok, YouTube, Like"
    )
    return WAIT_VERIFY_SOCIALS

async def verify_socials_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["verify_socials"] = update.message.text.strip()
    await update.message.reply_text(
        "Шаг 3: Отправьте фото/скриншот, подтверждающий что эти соц. сети ваши:"
    )
    return WAIT_VERIFY_PHOTO

async def verify_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    game_id = context.user_data.get("verify_game_id")
    socials = context.user_data.get("verify_socials")

    # Сохраняем заявку в Firebase
    db.collection("verification_requests").add({
        "telegram_id": user.id,
        "username": user.username or user.first_name,
        "game_id": game_id,
        "socials": socials,
        "status": "pending"
    })

    await update.message.reply_text(
        "📨 Заявка на верификацию отправлена! Ожидайте ответа."
    )

    # Уведомляем админа
    if ADMIN_ID:
        photo = update.message.photo[-1].file_id if update.message.photo else None
        caption = (
            f"🔔 Новая заявка на верификацию!\n"
            f"👤 @{user.username or user.first_name} (ID: {user.id})\n"
            f"🎮 Игровой ID: {game_id}\n"
            f"🔗 Соц. сети: {socials}\n\n"
            f"Одобрить: /verify_approve {user.id}\n"
            f"Отклонить: /verify_reject {user.id}"
        )
        if photo:
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo, caption=caption)
        else:
            await context.bot.send_message(chat_id=ADMIN_ID, text=caption)

    return ConversationHandler.END


# ========== КОМАНДЫ ОДОБРЕНИЯ/ОТКЛОНЕНИЯ ВЕРИФИКАЦИИ ==========

async def verify_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        target_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /verify_approve <telegram_id>")
        return
    kb = [
        [InlineKeyboardButton("🔵 Синяя", callback_data=f"vapprove_blue_{target_id}"),
         InlineKeyboardButton("🟡 Золотая", callback_data=f"vapprove_gold_{target_id}")]
    ]
    await update.message.reply_text("Какую верификацию выдать?", reply_markup=InlineKeyboardMarkup(kb))

async def verify_approve_type_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    vtype = parts[1]
    target_id = int(parts[2])

    db.collection("users").document(str(target_id)).set(
        {"verification": vtype}, merge=True
    )
    await context.bot.send_message(
        chat_id=target_id,
        text=f"✅ Вы прошли верификацию! Тип: {'🔵 Синяя' if vtype == 'blue' else '🟡 Золотая'}"
    )
    await query.edit_message_text(f"✅ Верификация ({vtype}) выдана {target_id}")

async def verify_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        target_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /verify_reject <telegram_id>")
        return
    await context.bot.send_message(
        chat_id=target_id,
        text="❌ Вы не прошли верификацию. Не расстраивайтесь — вы можете набрать актив и написать снова."
    )
    await update.message.reply_text(f"❌ Верификация отклонена для {target_id}")


# ========== CANCEL ==========

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# ========== MAIN ==========

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(prime_give_cb, pattern="^prime_give$"),
            CallbackQueryHandler(prime_remove_cb, pattern="^prime_remove$"),
            CallbackQueryHandler(admin_elo_cb, pattern="^admin_elo$"),
            CallbackQueryHandler(admin_verify_cb, pattern="^admin_verify$"),
            CallbackQueryHandler(reply_ticket_cb, pattern="^reply_"),
            CallbackQueryHandler(support_cb, pattern="^support$"),
            CallbackQueryHandler(start_verify_cb, pattern="^start_verify$"),
        ],
        states={
            WAIT_UID_PRIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, prime_uid_received)],
            WAIT_UID_ELO: [MessageHandler(filters.TEXT & ~filters.COMMAND, elo_uid_received)],
            WAIT_ELO_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, elo_value_received)],
            WAIT_UID_VERIFY: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_uid_received)],
            WAIT_VERIFY_TYPE: [CallbackQueryHandler(verify_type_cb, pattern="^verify_")],
            WAIT_SUPPORT_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, support_msg_received)],
            WAIT_SUPPORT_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, support_reply_received)],
            WAIT_VERIFY_GAME_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_game_id_received)],
            WAIT_VERIFY_SOCIALS: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_socials_received)],
            WAIT_VERIFY_PHOTO: [MessageHandler(filters.PHOTO | filters.TEXT, verify_photo_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("verify_approve", verify_approve))
    app.add_handler(CommandHandler("verify_reject", verify_reject))
    app.add_handler(CallbackQueryHandler(admin_prime_cb, pattern="^admin_prime$"))
    app.add_handler(CallbackQueryHandler(admin_tickets_cb, pattern="^admin_tickets$"))
    app.add_handler(CallbackQueryHandler(verify_approve_type_cb, pattern="^vapprove_"))
    app.add_handler(conv)

    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()

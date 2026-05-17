import logging
import firebase_admin
from firebase_admin import credentials, firestore
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    CallbackQueryHandler, ConversationHandler, CallbackContext
)

BOT_TOKEN = "8610496403:AAHLyRtghzD9A4QGsHNoS1CxNYa0q7FMYVE"
ADMIN_ID = 8842178466
SERVICE_ACCOUNT_FILE = "serviceAccount.json"

logging.basicConfig(level=logging.INFO)
cred = credentials.Certificate(SERVICE_ACCOUNT_FILE)
firebase_admin.initialize_app(cred)
db = firestore.client()

(WAIT_UID_PRIME, WAIT_UID_ELO, WAIT_ELO_VALUE,
 WAIT_UID_VERIFY, WAIT_VERIFY_TYPE, WAIT_SUPPORT_MSG,
 WAIT_SUPPORT_REPLY, WAIT_VERIFY_GAME_ID,
 WAIT_VERIFY_SOCIALS, WAIT_VERIFY_PHOTO) = range(10)

def is_admin(uid): return uid == ADMIN_ID

def start(update, context):
    uid = update.effective_user.id
    if ADMIN_ID == 0:
        update.message.reply_text(f"Твой Telegram ID: {uid}")
        return
    if is_admin(uid):
        kb = [[InlineKeyboardButton("💎 Prime", callback_data="admin_prime"),
               InlineKeyboardButton("📊 ELO", callback_data="admin_elo")],
              [InlineKeyboardButton("✅ Верификация", callback_data="admin_verify"),
               InlineKeyboardButton("💬 Тикеты", callback_data="admin_tickets")]]
        update.message.reply_text("👑 Админ-панель:", reply_markup=InlineKeyboardMarkup(kb))
    else:
        kb = [[InlineKeyboardButton("💎 Купить Prime", callback_data="buy_prime")],
              [InlineKeyboardButton("✅ Верификация", callback_data="start_verify")],
              [InlineKeyboardButton("💬 Поддержка", callback_data="support")]]
        update.message.reply_text("👋 Добро пожаловать в Flamely!", reply_markup=InlineKeyboardMarkup(kb))

def admin_prime_cb(update, context):
    q = update.callback_query; q.answer()
    if not is_admin(q.from_user.id): return
    kb = [[InlineKeyboardButton("✅ Выдать", callback_data="prime_give"),
           InlineKeyboardButton("❌ Снять", callback_data="prime_remove")]]
    q.edit_message_text("💎 Prime:", reply_markup=InlineKeyboardMarkup(kb))

def prime_give_cb(update, context):
    q = update.callback_query; q.answer()
    context.user_data["prime_action"] = "give"
    q.edit_message_text("Введите UID для выдачи Prime:")
    return WAIT_UID_PRIME

def prime_remove_cb(update, context):
    q = update.callback_query; q.answer()
    context.user_data["prime_action"] = "remove"
    q.edit_message_text("Введите UID для снятия Prime:")
    return WAIT_UID_PRIME

def prime_uid_received(update, context):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    uid = update.message.text.strip()
    value = context.user_data.get("prime_action") == "give"
    db.collection("users").document(uid).set({"prime": value}, merge=True)
    update.message.reply_text(f"💎 Prime {'выдан ✅' if value else 'снят ❌'} для {uid}")
    return ConversationHandler.END

def admin_elo_cb(update, context):
    q = update.callback_query; q.answer()
    if not is_admin(q.from_user.id): return
    q.edit_message_text("📊 Введите UID игрока:")
    return WAIT_UID_ELO

def elo_uid_received(update, context):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    context.user_data["elo_uid"] = update.message.text.strip()
    update.message.reply_text("Введите новое значение ELO:")
    return WAIT_ELO_VALUE

def elo_value_received(update, context):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    try: elo = int(update.message.text.strip())
    except:
        update.message.reply_text("❌ Введите число.")
        return WAIT_ELO_VALUE
    uid = context.user_data["elo_uid"]
    db.collection("users").document(uid).set({"elo": elo}, merge=True)
    update.message.reply_text(f"📊 ELO = {elo} для {uid}")
    return ConversationHandler.END

def admin_verify_cb(update, context):
    q = update.callback_query; q.answer()
    if not is_admin(q.from_user.id): return
    q.edit_message_text("✅ Введите UID игрока:")
    return WAIT_UID_VERIFY

def verify_uid_received(update, context):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    context.user_data["verify_uid"] = update.message.text.strip()
    kb = [[InlineKeyboardButton("🔵 Синяя", callback_data="verify_blue"),
           InlineKeyboardButton("🟡 Золотая", callback_data="verify_gold")],
          [InlineKeyboardButton("❌ Снять", callback_data="verify_remove")]]
    update.message.reply_text("Тип верификации:", reply_markup=InlineKeyboardMarkup(kb))
    return WAIT_VERIFY_TYPE

def verify_type_cb(update, context):
    q = update.callback_query; q.answer()
    uid = context.user_data.get("verify_uid")
    vmap = {"verify_blue": "blue", "verify_gold": "gold", "verify_remove": None}
    labels = {"verify_blue": "🔵 Синяя выдана", "verify_gold": "🟡 Золотая выдана", "verify_remove": "❌ Снята"}
    db.collection("users").document(uid).set({"verification": vmap[q.data]}, merge=True)
    q.edit_message_text(f"{labels[q.data]} для {uid}")
    return ConversationHandler.END

def admin_tickets_cb(update, context):
    q = update.callback_query; q.answer()
    if not is_admin(q.from_user.id): return
    tickets = list(db.collection("support_tickets").where("status", "==", "open").stream())
    if not tickets:
        q.edit_message_text("💬 Открытых тикетов нет."); return
    text = "💬 Открытые тикеты:\n\n"
    kb = []
    for t in tickets:
        d = t.to_dict()
        text += f"#{t.id[:6]} от {d.get('username','?')}: {d.get('message','')[:50]}\n"
        kb.append([InlineKeyboardButton(f"Ответить #{t.id[:6]}", callback_data=f"reply_{t.id}")])
    q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

def reply_ticket_cb(update, context):
    q = update.callback_query; q.answer()
    context.user_data["reply_ticket_id"] = q.data.replace("reply_", "")
    q.edit_message_text("Введите ответ:")
    return WAIT_SUPPORT_REPLY

def support_reply_received(update, context):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    tid = context.user_data["reply_ticket_id"]
    t = db.collection("support_tickets").document(tid).get()
    if t.exists:
        uid = t.to_dict().get("telegram_id")
        db.collection("support_tickets").document(tid).update({"status": "closed"})
        if uid:
            context.bot.send_message(chat_id=uid, text=f"💬 Ответ поддержки:\n{update.message.text}")
    update.message.reply_text("✅ Ответ отправлен.")
    return ConversationHandler.END

def support_cb(update, context):
    q = update.callback_query; q.answer()
    q.edit_message_text("💬 Опишите проблему:")
    return WAIT_SUPPORT_MSG

def support_msg_received(update, context):
    user = update.effective_user
    db.collection("support_tickets").add({
        "telegram_id": user.id,
        "username": user.username or user.first_name,
        "message": update.message.text,
        "status": "open"
    })
    update.message.reply_text("✅ Тикет создан!")
    if ADMIN_ID:
        context.bot.send_message(chat_id=ADMIN_ID,
            text=f"📩 Тикет от @{user.username or user.first_name}:\n{update.message.text}")
    return ConversationHandler.END

def start_verify_cb(update, context):
    q = update.callback_query; q.answer()
    q.edit_message_text("✅ Шаг 1: Введите ваш игровой ID:")
    return WAIT_VERIFY_GAME_ID

def verify_game_id_received(update, context):
    context.user_data["verify_game_id"] = update.message.text.strip()
    update.message.reply_text("Шаг 2: Ссылки на соц. сети (Telegram, TikTok, YouTube, Like):")
    return WAIT_VERIFY_SOCIALS

def verify_socials_received(update, context):
    context.user_data["verify_socials"] = update.message.text.strip()
    update.message.reply_text("Шаг 3: Отправьте фото что соц. сети ваши:")
    return WAIT_VERIFY_PHOTO

def verify_photo_received(update, context):
    user = update.effective_user
    game_id = context.user_data.get("verify_game_id")
    socials = context.user_data.get("verify_socials")
    db.collection("verification_requests").add({
        "telegram_id": user.id,
        "username": user.username or user.first_name,
        "game_id": game_id, "socials": socials, "status": "pending"
    })
    update.message.reply_text("📨 Заявка отправлена! Ожидайте.")
    if ADMIN_ID:
        caption = (f"🔔 Верификация!\n👤 @{user.username or user.first_name} (ID: {user.id})\n"
                   f"🎮 ID: {game_id}\n🔗 Соц. сети: {socials}\n\n"
                   f"Одобрить: /verify_approve {user.id}\nОтклонить: /verify_reject {user.id}")
        try:
            if update.message.photo:
                context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id, caption=caption)
            else:
                context.bot.send_message(chat_id=ADMIN_ID, text=caption)
        except: pass
    return ConversationHandler.END

def verify_approve(update, context):
    if not is_admin(update.effective_user.id): return
    try: target_id = int(context.args[0])
    except: update.message.reply_text("Использование: /verify_approve <id>"); return
    kb = [[InlineKeyboardButton("🔵 Синяя", callback_data=f"vapprove_blue_{target_id}"),
           InlineKeyboardButton("🟡 Золотая", callback_data=f"vapprove_gold_{target_id}")]]
    update.message.reply_text("Какую верификацию выдать?", reply_markup=InlineKeyboardMarkup(kb))

def verify_approve_type_cb(update, context):
    q = update.callback_query; q.answer()
    parts = q.data.split("_")
    vtype, target_id = parts[1], int(parts[2])
    db.collection("users").document(str(target_id)).set({"verification": vtype}, merge=True)
    context.bot.send_message(chat_id=target_id,
        text=f"✅ Вы прошли верификацию! {'🔵 Синяя' if vtype == 'blue' else '🟡 Золотая'}")
    q.edit_message_text(f"✅ Выдано {target_id}")

def verify_reject(update, context):
    if not is_admin(update.effective_user.id): return
    try: target_id = int(context.args[0])
    except: update.message.reply_text("Использование: /verify_reject <id>"); return
    context.bot.send_message(chat_id=target_id,
        text="❌ Вы не прошли верификацию. Наберите актив и напишите снова.")
    update.message.reply_text(f"❌ Отклонено для {target_id}")

def buy_prime_cb(update, context):
    q = update.callback_query; q.answer()
    q.edit_message_text("💎 Напишите администратору для покупки Prime.")

def cancel(update, context):
    update.message.reply_text("Отменено.")
    return ConversationHandler.END

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

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
            WAIT_UID_PRIME: [MessageHandler(Filters.text & ~Filters.command, prime_uid_received)],
            WAIT_UID_ELO: [MessageHandler(Filters.text & ~Filters.command, elo_uid_received)],
            WAIT_ELO_VALUE: [MessageHandler(Filters.text & ~Filters.command, elo_value_received)],
            WAIT_UID_VERIFY: [MessageHandler(Filters.text & ~Filters.command, verify_uid_received)],
            WAIT_VERIFY_TYPE: [CallbackQueryHandler(verify_type_cb, pattern="^verify_")],
            WAIT_SUPPORT_MSG: [MessageHandler(Filters.text & ~Filters.command, support_msg_received)],
            WAIT_SUPPORT_REPLY: [MessageHandler(Filters.text & ~Filters.command, support_reply_received)],
            WAIT_VERIFY_GAME_ID: [MessageHandler(Filters.text & ~Filters.command, verify_game_id_received)],
            WAIT_VERIFY_SOCIALS: [MessageHandler(Filters.text & ~Filters.command, verify_socials_received)],
            WAIT_VERIFY_PHOTO: [MessageHandler(Filters.photo | Filters.text, verify_photo_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("verify_approve", verify_approve))
    dp.add_handler(CommandHandler("verify_reject", verify_reject))
    dp.add_handler(CallbackQueryHandler(admin_prime_cb, pattern="^admin_prime$"))
    dp.add_handler(CallbackQueryHandler(admin_tickets_cb, pattern="^admin_tickets$"))
    dp.add_handler(CallbackQueryHandler(verify_approve_type_cb, pattern="^vapprove_"))
    dp.add_handler(CallbackQueryHandler(buy_prime_cb, pattern="^buy_prime$"))
    dp.add_handler(conv)

    print("Бот запущен!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()

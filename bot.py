import asyncio
import json
import os
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery, ContentType
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ══════════════════════════════════════════════
#  КОНФИГ — заполни перед запуском
# ══════════════════════════════════════════════
BOT_TOKEN   = "ВАШ_BOT_TOKEN"          # от @BotFather
ADMIN_IDS   = [123456789]               # твой Telegram ID
PRIME_PRICE = 50                        # цена в звёздах

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ══════════════════════════════════════════════
#  БАЗА ДАННЫХ (JSON)
# ══════════════════════════════════════════════
DB_FILE = "data.json"

def load_db() -> dict:
    if not os.path.exists(DB_FILE):
        return {"users": {}, "verif_requests": {}, "prime_requests": {}}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data: dict):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(uid: int) -> dict:
    db = load_db()
    return db["users"].get(str(uid), {})

def set_user(uid: int, data: dict):
    db = load_db()
    db["users"][str(uid)] = data
    save_db(db)

# ══════════════════════════════════════════════
#  FSM СОСТОЯНИЯ
# ══════════════════════════════════════════════
class PrimeFlow(StatesGroup):
    enter_nickname  = State()
    confirm         = State()

class VerifFlow(StatesGroup):
    enter_nickname  = State()
    confirm_nick    = State()
    send_result     = State()
    confirm_result  = State()
    send_socials    = State()
    send_screenshot = State()

# ══════════════════════════════════════════════
#  ХЕЛПЕРЫ — клавиатуры
# ══════════════════════════════════════════════
def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Купить Prime",        callback_data="menu_prime")],
        [InlineKeyboardButton(text="✅ Верификация аккаунта", callback_data="menu_verif")],
        [InlineKeyboardButton(text="💬 Техподдержка",         callback_data="menu_support")],
    ])

def kb_yes_no(yes_cb: str, no_cb: str):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да",  callback_data=yes_cb),
        InlineKeyboardButton(text="❌ Нет", callback_data=no_cb),
    ]])

def kb_back():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")]
    ])

def kb_admin_prime(uid: int, nickname: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выдать Prime", callback_data=f"adm_prime_yes_{uid}"),
            InlineKeyboardButton(text="❌ Отклонить",    callback_data=f"adm_prime_no_{uid}"),
        ]
    ])

def kb_admin_verif(uid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Верифицировать", callback_data=f"adm_verif_yes_{uid}"),
            InlineKeyboardButton(text="❌ Отклонить",      callback_data=f"adm_verif_no_{uid}"),
        ]
    ])

# ══════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════
@dp.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(
        "👋 Привет! Я <b>Элла</b> — помощник Flamely.\n\n"
        "Выбери что тебя интересует:",
        reply_markup=kb_main(),
        parse_mode="HTML"
    )

# ══════════════════════════════════════════════
#  НАЗАД В МЕНЮ
# ══════════════════════════════════════════════
@dp.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "👋 Привет! Я <b>Элла</b> — помощник Flamely.\n\n"
        "Выбери что тебя интересует:",
        reply_markup=kb_main(),
        parse_mode="HTML"
    )

# ══════════════════════════════════════════════
#  ТЕХПОДДЕРЖКА
# ══════════════════════════════════════════════
@dp.callback_query(F.data == "menu_support")
async def menu_support(cb: CallbackQuery):
    await cb.message.edit_text(
        "💬 <b>Техподдержка</b>\n\n"
        "Напиши свой вопрос прямо в чате на сайте Flamely:\n"
        "🔗 Раздел <b>ПОДДЕРЖКА</b> → кнопка темы → опиши проблему.\n\n"
        "Администратор ответит в течение 24 часов.",
        reply_markup=kb_back(),
        parse_mode="HTML"
    )

# ══════════════════════════════════════════════════════════════
#  ██████  PRIME FLOW
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_prime")
async def prime_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(PrimeFlow.enter_nickname)
    await cb.message.edit_text(
        "💎 <b>Покупка Prime</b>\n\n"
        "Введи свой <b>никнейм на сайте Flamely</b> точно как он написан:",
        parse_mode="HTML"
    )

@dp.message(PrimeFlow.enter_nickname)
async def prime_nickname(msg: Message, state: FSMContext):
    nick = msg.text.strip()
    await state.update_data(nickname=nick)
    await state.set_state(PrimeFlow.confirm)
    await msg.answer(
        f"Твой ник на сайте: <b>{nick}</b>\n\nВсё верно?",
        reply_markup=kb_yes_no("prime_confirm_yes", "prime_confirm_no"),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "prime_confirm_no")
async def prime_confirm_no(cb: CallbackQuery, state: FSMContext):
    await state.set_state(PrimeFlow.enter_nickname)
    await cb.message.edit_text(
        "Введи никнейм заново:",
    )

@dp.callback_query(F.data == "prime_confirm_yes")
async def prime_confirm_yes(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    nick = data["nickname"]
    uid  = cb.from_user.id

    # Сохраняем pending-заявку
    db = load_db()
    db["prime_requests"][str(uid)] = {
        "nickname": nick,
        "tg_user": cb.from_user.username or str(uid),
        "status": "pending_payment",
        "date": datetime.now().isoformat()
    }
    save_db(db)

    # Отправляем инвойс со звёздами
    await cb.message.delete()
    await bot.send_invoice(
        chat_id=uid,
        title="💎 Flamely Prime",
        description=f"Prime-статус для игрока {nick} на сайте Flamely",
        payload=f"prime_{uid}_{nick}",
        currency="XTR",               # Telegram Stars
        prices=[LabeledPrice(label="Prime", amount=PRIME_PRICE)],
    )
    await state.clear()

# ── Подтверждение платежа ──
@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def payment_success(msg: Message):
    uid      = msg.from_user.id
    db       = load_db()
    req      = db["prime_requests"].get(str(uid), {})
    nick     = req.get("nickname", "?")
    tg_user  = msg.from_user.username or str(uid)

    db["prime_requests"][str(uid)]["status"] = "paid"
    save_db(db)

    # Уведомляем пользователя
    await msg.answer(
        "✅ <b>Оплата прошла!</b>\n\n"
        f"💎 Prime для <b>{nick}</b> будет выдан в течение нескольких минут.\n"
        "Ожидай уведомления.",
        parse_mode="HTML",
        reply_markup=kb_back()
    )

    # Уведомляем всех админов
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💎 <b>НОВАЯ ОПЛАТА PRIME</b>\n\n"
                f"👤 Ник на сайте: <code>{nick}</code>\n"
                f"📱 Telegram: @{tg_user} (<code>{uid}</code>)\n"
                f"💰 Оплачено: {PRIME_PRICE} ⭐\n"
                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                reply_markup=kb_admin_prime(uid, nick),
                parse_mode="HTML"
            )
        except Exception:
            pass

# ── Админ выдаёт Prime ──
@dp.callback_query(F.data.startswith("adm_prime_yes_"))
async def adm_prime_yes(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Нет доступа")

    uid = int(cb.data.split("_")[-1])
    db  = load_db()
    req = db["prime_requests"].get(str(uid), {})
    nick = req.get("nickname", "?")

    db["prime_requests"][str(uid)]["status"] = "issued"
    save_db(db)

    await bot.send_message(
        uid,
        "🎉 <b>Prime выдан!</b>\n\n"
        f"Зайди на сайт — у тебя уже активен <b>💎 Prime</b> для ника <code>{nick}</code>.\n\n"
        "Приятной игры!",
        parse_mode="HTML",
        reply_markup=kb_back()
    )
    await cb.message.edit_text(
        cb.message.text + "\n\n✅ <b>Prime выдан</b>",
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("adm_prime_no_"))
async def adm_prime_no(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Нет доступа")

    uid = int(cb.data.split("_")[-1])
    db  = load_db()
    db["prime_requests"][str(uid)]["status"] = "rejected"
    save_db(db)

    await bot.send_message(
        uid,
        "❌ <b>Заявка на Prime отклонена.</b>\n\n"
        "Если считаешь это ошибкой — напиши в поддержку на сайте.",
        parse_mode="HTML",
        reply_markup=kb_back()
    )
    await cb.message.edit_text(
        cb.message.text + "\n\n❌ <b>Отклонено</b>",
        parse_mode="HTML"
    )

# ══════════════════════════════════════════════════════════════
#  ████  ВЕРИФИКАЦИЯ FLOW
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_verif")
async def verif_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(VerifFlow.enter_nickname)
    await cb.message.edit_text(
        "✅ <b>Верификация аккаунта</b>\n\n"
        "Введи свой <b>никнейм на сайте Flamely</b> точно как он написан:",
        parse_mode="HTML"
    )

@dp.message(VerifFlow.enter_nickname)
async def verif_nickname(msg: Message, state: FSMContext):
    nick = msg.text.strip()
    await state.update_data(nickname=nick)
    await state.set_state(VerifFlow.confirm_nick)
    await msg.answer(
        f"Твой ник на сайте: <b>{nick}</b>\n\nВсё верно?",
        reply_markup=kb_yes_no("verif_nick_yes", "verif_nick_no"),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "verif_nick_no")
async def verif_nick_no(cb: CallbackQuery, state: FSMContext):
    await state.set_state(VerifFlow.enter_nickname)
    await cb.message.edit_text("Введи никнейм заново:")

@dp.callback_query(F.data == "verif_nick_yes")
async def verif_nick_yes(cb: CallbackQuery, state: FSMContext):
    await state.set_state(VerifFlow.send_result)
    await cb.message.edit_text(
        "📊 <b>Шаг 1 из 3 — Результат матча</b>\n\n"
        "Отправь <b>скриншот результата своего матча</b> на Flamely.\n"
        "(фото или файл)",
        parse_mode="HTML"
    )

@dp.message(VerifFlow.send_result, F.photo | F.document)
async def verif_result_received(msg: Message, state: FSMContext):
    # Сохраняем file_id
    if msg.photo:
        file_id = msg.photo[-1].file_id
    else:
        file_id = msg.document.file_id
    await state.update_data(result_file=file_id, result_type="photo" if msg.photo else "document")
    await state.set_state(VerifFlow.confirm_result)
    await msg.answer(
        "Это скриншот результата твоего матча?",
        reply_markup=kb_yes_no("verif_result_yes", "verif_result_no")
    )

@dp.message(VerifFlow.send_result)
async def verif_result_wrong(msg: Message):
    await msg.answer("📸 Отправь <b>фото или файл</b> скриншота.", parse_mode="HTML")

@dp.callback_query(F.data == "verif_result_no")
async def verif_result_no(cb: CallbackQuery, state: FSMContext):
    await state.set_state(VerifFlow.send_result)
    await cb.message.edit_text(
        "Отправь скриншот результата матча заново:"
    )

@dp.callback_query(F.data == "verif_result_yes")
async def verif_result_yes(cb: CallbackQuery, state: FSMContext):
    await state.set_state(VerifFlow.send_socials)
    await cb.message.edit_text(
        "🔗 <b>Шаг 2 из 3 — Соцсети</b>\n\n"
        "Отправь ссылки на свои аккаунты (через запятую или каждый с новой строки):\n\n"
        "• TikTok\n• YouTube\n• Telegram\n• Лайк (если есть)\n\n"
        "Можешь пропустить те, которых нет — но хотя бы одна нужна.",
        parse_mode="HTML"
    )

@dp.message(VerifFlow.send_socials)
async def verif_socials(msg: Message, state: FSMContext):
    await state.update_data(socials=msg.text.strip())
    await state.set_state(VerifFlow.send_screenshot)
    await msg.answer(
        "📸 <b>Шаг 3 из 3 — Скриншот владения</b>\n\n"
        "Отправь скриншот, что <b>эти аккаунты принадлежат тебе</b>.\n\n"
        "Например: скриншот настроек профиля, страницы с твоим именем, или что-то что однозначно докажет что это твой аккаунт.",
        parse_mode="HTML"
    )

@dp.message(VerifFlow.send_screenshot, F.photo | F.document)
async def verif_screenshot(msg: Message, state: FSMContext):
    if msg.photo:
        file_id = msg.photo[-1].file_id
    else:
        file_id = msg.document.file_id

    data     = await state.get_data()
    uid      = msg.from_user.id
    tg_user  = msg.from_user.username or str(uid)
    nick     = data["nickname"]
    socials  = data.get("socials", "—")

    # Сохраняем заявку
    db = load_db()
    db["verif_requests"][str(uid)] = {
        "nickname":    nick,
        "tg_user":     tg_user,
        "socials":     socials,
        "result_file": data.get("result_file"),
        "proof_file":  file_id,
        "status":      "pending",
        "date":        datetime.now().isoformat()
    }
    save_db(db)
    await state.clear()

    await msg.answer(
        "⏳ <b>Заявка на верификацию отправлена!</b>\n\n"
        "Администратор проверит данные и ответит в ближайшее время.\n"
        "Ожидай уведомления здесь.",
        parse_mode="HTML",
        reply_markup=kb_back()
    )

    # Уведомляем всех админов
    for admin_id in ADMIN_IDS:
        try:
            caption = (
                f"✅ <b>ЗАЯВКА НА ВЕРИФИКАЦИЮ</b>\n\n"
                f"👤 Ник: <code>{nick}</code>\n"
                f"📱 Telegram: @{tg_user} (<code>{uid}</code>)\n"
                f"🔗 Соцсети:\n{socials}\n"
                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            # Отправляем скриншот владения с описанием
            await bot.send_photo(
                admin_id,
                photo=file_id,
                caption=caption,
                reply_markup=kb_admin_verif(uid),
                parse_mode="HTML"
            )
            # Отдельно скриншот матча
            result_file = data.get("result_file")
            if result_file:
                await bot.send_photo(
                    admin_id,
                    photo=result_file,
                    caption=f"📊 Скриншот матча от @{tg_user}"
                )
        except Exception:
            pass

@dp.message(VerifFlow.send_screenshot)
async def verif_screenshot_wrong(msg: Message):
    await msg.answer("📸 Отправь <b>фото или файл</b> скриншота.", parse_mode="HTML")

# ── Админ верифицирует ──
@dp.callback_query(F.data.startswith("adm_verif_yes_"))
async def adm_verif_yes(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Нет доступа")

    uid = int(cb.data.split("_")[-1])
    db  = load_db()
    req = db["verif_requests"].get(str(uid), {})
    nick = req.get("nickname", "?")

    db["verif_requests"][str(uid)]["status"] = "approved"
    save_db(db)

    await bot.send_message(
        uid,
        "🎉 <b>Верификация одобрена!</b>\n\n"
        f"Аккаунт <code>{nick}</code> теперь верифицирован на Flamely ✅\n\n"
        "Значок появится рядом с ником на сайте.",
        parse_mode="HTML",
        reply_markup=kb_back()
    )
    await cb.message.edit_caption(
        cb.message.caption + "\n\n✅ <b>Верификация одобрена</b>",
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("adm_verif_no_"))
async def adm_verif_no(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Нет доступа")

    uid = int(cb.data.split("_")[-1])
    db  = load_db()
    db["verif_requests"][str(uid)]["status"] = "rejected"
    save_db(db)

    await bot.send_message(
        uid,
        "❌ <b>Верификация отклонена.</b>\n\n"
        "Причина могла быть:\n"
        "• Соцсети не принадлежат тебе\n"
        "• Недостаточно подписчиков\n"
        "• Некорректные скриншоты\n\n"
        "Можешь подать заявку повторно с корректными данными.",
        parse_mode="HTML",
        reply_markup=kb_back()
    )
    await cb.message.edit_caption(
        cb.message.caption + "\n\n❌ <b>Отклонено</b>",
        parse_mode="HTML"
    )

# ══════════════════════════════════════════════
#  АДМИН-КОМАНДЫ
# ══════════════════════════════════════════════
@dp.message(Command("admin"))
async def cmd_admin(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    db = load_db()
    prime_total  = len(db.get("prime_requests", {}))
    prime_paid   = sum(1 for v in db.get("prime_requests", {}).values() if v.get("status") == "paid")
    verif_total  = len(db.get("verif_requests", {}))
    verif_pend   = sum(1 for v in db.get("verif_requests", {}).values() if v.get("status") == "pending")

    await msg.answer(
        "⚙️ <b>ADMIN PANEL — Ella Bot</b>\n\n"
        f"💎 Prime заявок: <b>{prime_total}</b> (ожидают выдачи: <b>{prime_paid}</b>)\n"
        f"✅ Верификаций: <b>{verif_total}</b> (на рассмотрении: <b>{verif_pend}</b>)\n\n"
        "<b>Команды:</b>\n"
        "/pending_prime — список ожидающих Prime\n"
        "/pending_verif — список ожидающих верификации\n"
        "/notify &lt;id&gt; &lt;текст&gt; — написать пользователю",
        parse_mode="HTML"
    )

@dp.message(Command("pending_prime"))
async def cmd_pending_prime(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    db   = load_db()
    reqs = {k: v for k, v in db.get("prime_requests", {}).items() if v.get("status") == "paid"}
    if not reqs:
        return await msg.answer("Нет ожидающих выдачи Prime.")
    for uid, r in reqs.items():
        await msg.answer(
            f"💎 <b>Prime — ожидает выдачи</b>\n"
            f"👤 Ник: <code>{r['nickname']}</code>\n"
            f"📱 @{r.get('tg_user', uid)} (<code>{uid}</code>)\n"
            f"🕐 {r.get('date','?')[:16]}",
            reply_markup=kb_admin_prime(int(uid), r['nickname']),
            parse_mode="HTML"
        )

@dp.message(Command("pending_verif"))
async def cmd_pending_verif(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    db   = load_db()
    reqs = {k: v for k, v in db.get("verif_requests", {}).items() if v.get("status") == "pending"}
    if not reqs:
        return await msg.answer("Нет ожидающих верификации.")
    for uid, r in reqs.items():
        text = (
            f"✅ <b>Верификация — ожидает</b>\n"
            f"👤 Ник: <code>{r['nickname']}</code>\n"
            f"📱 @{r.get('tg_user', uid)} (<code>{uid}</code>)\n"
            f"🔗 Соцсети: {r.get('socials','—')}\n"
            f"🕐 {r.get('date','?')[:16]}"
        )
        proof = r.get("proof_file")
        if proof:
            await bot.send_photo(msg.chat.id, photo=proof, caption=text,
                                 reply_markup=kb_admin_verif(int(uid)), parse_mode="HTML")
        else:
            await msg.answer(text, reply_markup=kb_admin_verif(int(uid)), parse_mode="HTML")

@dp.message(Command("notify"))
async def cmd_notify(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    parts = msg.text.split(maxsplit=2)
    if len(parts) < 3:
        return await msg.answer("Формат: /notify <user_id> <текст>")
    try:
        target_id = int(parts[1])
        text      = parts[2]
        await bot.send_message(target_id,
            f"📢 <b>Сообщение от администрации Flamely:</b>\n\n{text}",
            parse_mode="HTML", reply_markup=kb_back())
        await msg.answer("✅ Отправлено")
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")

# ══════════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════════
async def main():
    print("🤖 Ella Bot запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

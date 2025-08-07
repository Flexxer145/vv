import logging
import json
import sqlite3
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler
)

# Конфигурация
TELEGRAM_TOKEN = "8324877709:AAE_M6zfE6hj5G_ZpmJuAY4PuSSXBAiMYdo"
USDA_API_KEY = "Okpv8RdqZ0PZyOgtfhHMMcUnkWAPmC1f3kluHyVg"
ADMIN_ID = 8158576899

# === ИНИЦИАЛИЗАЦИЯ БД ===
def init_db():
    with sqlite3.connect("food.db") as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            calories REAL,
            protein REAL,
            fat REAL,
            carbs REAL
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            food_id INTEGER,
            FOREIGN KEY(food_id) REFERENCES foods(id)
        )""")
        conn.commit()

# === ПОИСК ПРОДУКТА В БД ===
def search_local_food(name):
    with sqlite3.connect("food.db") as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM foods WHERE LOWER(name) LIKE ?", ('%' + name.lower() + '%',))
        return c.fetchone()

# === ДОБАВЛЕНИЕ ПРОДУКТА В БД ===
def add_food(name, calories, protein, fat, carbs):
    with sqlite3.connect("food.db") as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO foods (name, calories, protein, fat, carbs) VALUES (?, ?, ?, ?, ?)",
                  (name, calories, protein, fat, carbs))
        conn.commit()

# === ДОБАВЛЕНИЕ ПРИЁМА ПИЩИ ===
def add_meal(user_id, food_id):
    with sqlite3.connect("food.db") as conn:
        c = conn.cursor()
        date = datetime.now().strftime("%Y-%m-%d")
        c.execute("INSERT INTO meals (user_id, date, food_id) VALUES (?, ?, ?)", (user_id, date, food_id))
        conn.commit()

# === ПОЛУЧЕНИЕ СУММЫ ЗА ДЕНЬ ===
def get_today_summary(user_id):
    date = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect("food.db") as conn:
        c = conn.cursor()
        c.execute("""
        SELECT f.name, f.calories, f.protein, f.fat, f.carbs
        FROM meals m
        JOIN foods f ON m.food_id = f.id
        WHERE m.user_id = ? AND m.date = ?
        """, (user_id, date))
        rows = c.fetchall()

    if not rows:
        return "📭 Сегодня вы ничего не ели."

    total_cals = sum(row[1] for row in rows)
    total_prot = sum(row[2] for row in rows)
    total_fat = sum(row[3] for row in rows)
    total_carbs = sum(row[4] for row in rows)

    items = "\n".join([f"🍽 {row[0]} — {row[1]} ккал" for row in rows])
    summary = f"\n\n🔥 Всего: {total_cals:.0f} ккал\n🥩 Белки: {total_prot:.1f} г\n🥑 Жиры: {total_fat:.1f} г\n🍞 Углеводы: {total_carbs:.1f} г"
    return items + summary

# === ОБРАБОТЧИКИ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Я — твой персональный диетолог! Напиши мне, что ты ел, и я скажу тебе БЖУ и калории.")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    summary = get_today_summary(user_id)
    await update.message.reply_text(summary)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.message.text
    food = search_local_food(query)
    if food:
        id, name, cal, prot, fat, carb = food
        text = f"🍽 {name}\n🔥 {cal} ккал\n🥩 {prot} г белка\n🥑 {fat} г жира\n🍞 {carb} г углеводов"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Добавить в дневник", callback_data=f"add:{id}")]
        ])
        await update.message.reply_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text("❌ Продукт не найден в базе. Используй /add для добавления.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("add:"):
        food_id = int(data.split(":")[1])
        user_id = query.from_user.id
        add_meal(user_id, food_id)
        await query.edit_message_text("✅ Добавлено в дневник!")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только админ может добавлять продукты.")
        return

    try:
        name = context.args[0]
        cal = float(context.args[1])
        prot = float(context.args[2])
        fat = float(context.args[3])
        carb = float(context.args[4])
        add_food(name, cal, prot, fat, carb)
        await update.message.reply_text(f"✅ Продукт '{name}' добавлен!")
    except:
        await update.message.reply_text("❗ Используй формат:
/add Яблоко 52 0.3 0.2 14")

# === ГЛАВНЫЙ ЗАПУСК ===
def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()

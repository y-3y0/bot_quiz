from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
import sqlite3
import os
import logging

TOKEN = "7490335964:AAFn3ifkQKpVfFHf20mCaPgjC6nykozO-lo"

ASK_QUESTION, ASK_OPTIONS, ASK_CORRECT, ASK_EXPLANATION, ASK_IMAGE, ASK_DELETE = range(6)

logging.basicConfig(level=logging.INFO)

def get_db_connection():
    conn = sqlite3.connect("questions.db")
    conn.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        options TEXT NOT NULL,
        correct INTEGER NOT NULL,
        explanation TEXT,
        image TEXT
    )''')
    return conn

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Начать викторину", "Добавить вопрос"], ["Удалить вопрос"]]
    await update.message.reply_text("Привет! Я бот-викторина 🎉", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions ORDER BY RANDOM() LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if row:
        q_id, question, options_str, correct, explanation, image = row
        options = options_str.split(";")

        context.user_data["current_question"] = {
            "id": q_id,
            "question": question,
            "options": options,
            "correct": correct,
            "explanation": explanation
        }

        keyboard = ReplyKeyboardMarkup([[opt] for opt in options], one_time_keyboard=True, resize_keyboard=True)

        try:
            if image and os.path.exists(image):
                await update.message.reply_photo(photo=InputFile(image), caption=f"❓ {question}", reply_markup=keyboard)
            else:
                await update.message.reply_text(f"❓ {question}", reply_markup=keyboard)
        except Exception as e:
            logging.error(f"Ошибка при отправке изображения: {e}")
            await update.message.reply_text(f"❓ {question}\n⚠️ (изображение не удалось загрузить)", reply_markup=keyboard)
    else:
        await update.message.reply_text("❌ Нет вопросов.")

async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data.get("current_question")
    if not data:
        await update.message.reply_text("Нажмите 'Начать викторину', чтобы начать.")
        return

    user_answer = update.message.text
    correct_answer = data["options"][data["correct"]]

    if user_answer == correct_answer:
        text = "✅ Правильно!"
    else:
        text = f"❌ Неправильно. Правильный ответ: {correct_answer}"

    text += f"\n📘 Объяснение: {data['explanation']}"

    keyboard = ReplyKeyboardMarkup([["Следующий вопрос"], ["Главное меню"]], resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=keyboard)

    context.user_data.pop("current_question", None)

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Начать викторину", "Добавить вопрос"], ["Удалить вопрос"]]
    await update.message.reply_text("Главное меню.", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите вопрос:")
    return ASK_QUESTION

async def ask_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"] = {"question": update.message.text}
    await update.message.reply_text("Введите варианты через `;` (пример: A;B;C;D):")
    return ASK_OPTIONS

async def ask_correct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    options = update.message.text.split(";")
    context.user_data["new_question"]["options"] = options
    await update.message.reply_text("Введите номер правильного ответа (с 1):")
    return ASK_CORRECT

async def ask_explanation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        correct_index = int(update.message.text) - 1
        context.user_data["new_question"]["correct"] = correct_index
        await update.message.reply_text("Введите объяснение:")
        return ASK_EXPLANATION
    except:
        await update.message.reply_text("Номер должен быть числом.")
        return ASK_CORRECT

async def ask_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        context.user_data["new_question"]["explanation"] = update.message.text
        await update.message.reply_text("Прикрепите изображение или напишите 'нет':")
        return ASK_IMAGE
    else:
        await update.message.reply_text("❌ Пожалуйста, введите объяснение текстом.")
        return ASK_EXPLANATION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = context.user_data["new_question"]

    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        image_path = f"images/{file.file_unique_id}.jpg"
        os.makedirs("images", exist_ok=True)
        await file.download_to_drive(image_path)
        q["image"] = image_path
    elif update.message.text and update.message.text.lower() == "нет":
        q["image"] = None
    else:
        await update.message.reply_text("❌ Прикрепите фото или напишите 'нет'.")
        return ASK_IMAGE

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO questions (question, options, correct, explanation, image) VALUES (?, ?, ?, ?, ?)",
                   (q["question"], ";".join(q["options"]), q["correct"], q["explanation"], q["image"]))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Вопрос добавлен!", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите ID вопроса для удаления:")
    return ASK_DELETE

async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qid = int(update.message.text)
    except:
        await update.message.reply_text("ID должен быть числом.")
        return ASK_DELETE

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM questions WHERE id = ?", (qid,))
    if cur.fetchone():
        cur.execute("DELETE FROM questions WHERE id = ?", (qid,))
        conn.commit()
        await update.message.reply_text(f"✅ Вопрос {qid} удалён.")
    else:
        await update.message.reply_text("❌ Вопрос не найден.")
    conn.close()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("add", add),
            MessageHandler(filters.Regex("^Добавить вопрос$"), add),
            CommandHandler("delete", delete),
            MessageHandler(filters.Regex("^Удалить вопрос$"), delete)
        ],
        states={
            ASK_QUESTION: [MessageHandler(filters.TEXT, ask_options)],
            ASK_OPTIONS: [MessageHandler(filters.TEXT, ask_correct)],
            ASK_CORRECT: [MessageHandler(filters.TEXT, ask_explanation)],
            ASK_EXPLANATION: [MessageHandler(filters.TEXT, ask_image)],
            ASK_IMAGE: [MessageHandler(filters.TEXT | filters.PHOTO, save_question)],
            ASK_DELETE: [MessageHandler(filters.TEXT, confirm_delete)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^Начать викторину$"), quiz))
    app.add_handler(MessageHandler(filters.Regex("^Следующий вопрос$"), quiz))
    app.add_handler(MessageHandler(filters.Regex("^Главное меню$"), back_to_main_menu))
    app.add_handler(MessageHandler(filters.TEXT, answer))

    print("✅ Бот запущен.")
    app.run_polling()

if __name__ == "__main__":
    main()

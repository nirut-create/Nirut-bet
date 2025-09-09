import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    JobQueue,
)

# -------- CONFIG --------
TOKEN = "8088409074:AAHqWWjIbN_jAsnY0qcxov6-C9vDJuSD1wE"
CHECK_INTERVAL = 60  # segundos entre chequeos
# -----------------------

# Diccionario para guardar cuotas que estamos vigilando
watched_cuotas = {}

# Función para revisar cuotas
async def check_cuotas(context: ContextTypes.DEFAULT_TYPE):
    for chat_id, data in watched_cuotas.items():
        url = data["url"]
        selector = data["selector"]
        last_value = data["last_value"]

        try:
            r = requests.get(url)
            soup = BeautifulSoup(r.text, "html.parser")
            element = soup.select_one(selector)
            if element:
                new_value = element.get_text(strip=True)
                if new_value != last_value:
                    await context.bot.send_message(chat_id=chat_id, text=f"¡Cambio detectado!\n{new_value}")
                    watched_cuotas[chat_id]["last_value"] = new_value
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=f"Error revisando cuota: {e}")

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Bot activo! Usa /seguir <URL> para vigilar cuotas.")

# Comando /seguir
async def seguir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usa: /seguir <URL>")
        return

    url = context.args[0]
    chat_id = update.message.chat_id

    # Por simplicidad pedimos que el selector lo escribas aquí manualmente:
    await update.message.reply_text("Escribe el selector CSS de la cuota que quieres vigilar:")

    # Guardamos temporalmente la URL para el chat
    context.user_data["url"] = url

# Comando para registrar selector
async def selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    selector = " ".join(context.args)
    url = context.user_data.get("url")

    if not url:
        await update.message.reply_text("Primero usa /seguir <URL>.")
        return

    # Guardamos la cuota a vigilar
    watched_cuotas[chat_id] = {"url": url, "selector": selector, "last_value": None}
    await update.message.reply_text(f"Cuota registrada. Te avisaré de cambios cada {CHECK_INTERVAL} segundos.")

# -----------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("seguir", seguir))
    app.add_handler(CommandHandler("selector", selector))

    # JobQueue
    job_queue: JobQueue = app.job_queue
    job_queue.run_repeating(check_cuotas, interval=CHECK_INTERVAL, first=10)

    # Ejecutar bot
    app.run_polling()

if __name__ == "__main__":
    main()

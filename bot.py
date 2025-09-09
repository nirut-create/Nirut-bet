import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler

# ---------------- CONFIG ----------------
TOKEN = "8088409074:AAHqWWjIbN_jAsnY0qcxov6-C9vDJuSD1wE"  # reemplaza con tu token de BotFather
CHECK_INTERVAL = 60  # segundos entre revisiones
# ----------------------------------------

vigias = {}  # Guarda las cuotas que estás siguiendo: {chat_id: {"url": ..., "selector": ..., "valor": ...}}

# Etapas de conversación
ESPERANDO_SELECCION = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hola! Usa /seguir <URL> para empezar a vigilar cuotas."
    )

async def seguir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    if len(context.args) != 1:
        await update.message.reply_text("Debes enviar una URL, ejemplo:\n/seguir https://ejemplo.com/partido123")
        return ConversationHandler.END

    url = context.args[0]
    try:
        r = requests.get(url)
        r.raise_for_status()
    except:
        await update.message.reply_text("No pude acceder a la página. Revisa la URL.")
        return ConversationHandler.END

    soup = BeautifulSoup(r.text, "html.parser")
    spans = soup.find_all("span")
    opciones = []
    for i, span in enumerate(spans):
        text = span.get_text(strip=True)
        if text.replace(".", "").isdigit():  # solo números, posibles cuotas
            opciones.append(f"[{i+1}] {text} → selector: {span.name}[data-id='{span.get('data-id','')}']")

    if not opciones:
        await update.message.reply_text("No encontré cuotas en esa página.")
        return ConversationHandler.END

    msg = "Encontré estas cuotas:\n" + "\n".join(opciones[:20]) + "\n\nResponde con el número de la cuota que quieres vigilar."
    await update.message.reply_text(msg)

    # Guardamos temporalmente la URL y opciones
    context.user_data["opciones"] = opciones
    context.user_data["url"] = url
    return ESPERANDO_SELECCION

async def elegir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    try:
        eleccion = int(update.message.text.strip()) - 1
    except:
        await update.message.reply_text("Por favor, envía un número válido.")
        return ESPERANDO_SELECCION

    opciones = context.user_data.get("opciones", [])
    url = context.user_data.get("url")
    if eleccion < 0 or eleccion >= len(opciones):
        await update.message.reply_text("Número fuera de rango, intenta de nuevo.")
        return ESPERANDO_SELECCION

    opcion = opciones[eleccion]
    # Extraemos selector simple (data-id)
    start_idx = opcion.find("data-id='") + len("data-id='")
    end_idx = opcion.find("'", start_idx)
    selector_id = opcion[start_idx:end_idx]

    # Guardamos vigilancia
    vigias[chat_id] = {"url": url, "selector": selector_id, "valor": None}

    await update.message.reply_text(f"Comenzaré a vigilar la cuota seleccionada: {opcion}")

    return ConversationHandler.END

async def check_cuotas(context: ContextTypes.DEFAULT_TYPE):
    for chat_id, info in vigias.items():
        try:
            r = requests.get(info["url"])
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            span = soup.find("span", {"data-id": info["selector"]})
            if span:
                valor = span.get_text(strip=True)
                if info["valor"] != valor:
                    # actualiza y notifica
                    old_val = info["valor"] if info["valor"] else "desconocido"
                    info["valor"] = valor
                    await context.bot.send_message(chat_id, f"⚡ Cambio detectado:\nAntes: {old_val}\nAhora: {valor}\n{info['url']}")
        except Exception as e:
            print("Error al revisar cuota:", e)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('seguir', seguir)],
        states={
            ESPERANDO_SELECCION: [CommandHandler('elegir', elegir), CommandHandler('text', elegir)]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    # Job de revisión periódica
    app.job_queue.run_repeating(check_cuotas, interval=CHECK_INTERVAL, first=10)

    print("Bot corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()

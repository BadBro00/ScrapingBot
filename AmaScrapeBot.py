import os
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import (ApplicationBuilder, CommandHandler, ContextTypes, JobQueue)

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36'
HEADERS = {'User-Agent': USER_AGENT}
DEALS_PAGES = [
    'https://www.amazon.it/gp/goldbox',
    'https://www.amazon.it/gp/bestsellers',
    'https://www.amazon.it/deals?ref_=nav_cs_gb',
    'https://www.amazon.it/ref=nav_logo'
]

INTERVAL = int(os.getenv('DEFAULT_INTERVAL', 3600))
current_job = None

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Estrai le offerte Amazon
def fetch_deals(url):
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    items = []
    for card in soup.select('.DealGridItem-module__dealItem'):
        nome = card.select_one('.DealContent-module__truncate')
        prezzo_element = card.select_one('.a-price-whole')
        sconto_element = card.select_one('.a-color-price') or card.select_one('.a-size-mini.a-color-base')
        timer_element = card.select_one('.a-declarative')
        link_elem = card.select_one('a.a-link-normal')
        rel_url = link_elem['href'] if link_elem and 'href' in link_elem.attrs else None
        link = f"https://www.amazon.it{relative_url}" if relative_url else "Link non disponibile"
        nome_text = nome.get_text(strip=True) if nome else 'N/D'
        prezzo = prezzo_element.get_text(strip=True) if prezzo_element else 'N/D'
        sconto = sconto_element.get_text(strip=True) if sconto_element else '0%'
        durata = timer_element.get('data-deal-duration') if timer_element else 'sconosciuta'
        items.append({
            'Prodotto': nome_text,
            'Prezzo': prezzo,
            'Sconto': sconto,
            'Durata': durata,
            'Link' : link
        })
    return items

# Invia le offerte al chat
async def send_deals(context):
    job = context.job
    chat_id = job.chat_id
    try:
        all_deals = []
        for page in DEALS_PAGES:
            all_deals.extend(fetch_deals(page))

        if not all_deals:
            await context.bot.send_message(chat_id=chat_id, text="Nessuna offerta trovata in questo momento.")
            return

        for deal in all_deals:
            text = (
                f"[ {deal['nome']} ]\n"
                f"€ {deal['prezzo']}\n"
                f"Offerta del {deal['sconto']}\n"
                f"Durata: {deal['durata']}"
            )
            await context.bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        logger.error(f"Errore: {e}")
        await context.bot.send_message(chat_id=chat_id, text="Errore durante il controllo delle offerte.")

# Comandi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot attivo! Usa /setinterval <secondi> per cambiare l'intervallo, /run per avviare e /stop per fermare.")

async def setinterval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global INTERVAL
    try:
        INTERVAL = int(context.args[0])
        await update.message.reply_text(f"Intervallo impostato a {INTERVAL} secondi.")
    except (IndexError, ValueError):
        await update.message.reply_text("Uso corretto: /setinterval <secondi>")

async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_job
    chat_id = update.effective_chat.id
    if current_job:
        current_job.schedule_removal()
    current_job = context.job_queue.run_repeating(send_deals, interval=INTERVAL, first=0, chat_id=chat_id)
    await update.message.reply_text(f"Polling avviato ogni {INTERVAL} secondi.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_job
    if current_job:
        current_job.schedule_removal()
        current_job = None
        await update.message.reply_text("Polling fermato.")
    else:
        await update.message.reply_text("Nessun polling attivo.")

# MAIN COMPATIBILE CON EVENT LOOP GIÀ ATTIVO (Jupyter, IDLE, WSL/GUI)
def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("Errore: TELEGRAM_TOKEN non impostato.")
        return

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setinterval", setinterval))
    app.add_handler(CommandHandler("run", run))
    app.add_handler(CommandHandler("stop", stop))

    print("Bot avviato...")
    app.run_polling()

if __name__ == '__main__':
    main()

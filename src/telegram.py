import os
import asyncio
from telegram import Bot

async def enviar_mensagem_telegram(texto):
    """Envia uma mensagem de texto para o canal/chat configurado."""
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("Credenciais do Telegram não configuradas.")
        return

    bot = Bot(token=token)
    async with bot:
        await bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
        print("Mensagem enviada para o Telegram com sucesso!")
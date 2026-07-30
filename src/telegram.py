import os
import asyncio
from telegram import Bot

async def enviar_mensagem_telegram(texto, caminho_foto=None):
    """Envia uma mensagem de texto ou uma foto com legenda para o canal/chat configurado."""
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("Credenciais do Telegram não configuradas.")
        return

    bot = Bot(token=token)
    async with bot:
        if caminho_foto and os.path.exists(caminho_foto):
            with open(caminho_foto, 'rb') as photo_file:
                await bot.send_photo(chat_id=chat_id, photo=photo_file, caption=texto, parse_mode="Markdown")
            print("Foto com legenda enviada para o Telegram com sucesso!")
        else:
            await bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
            print("Mensagem de texto enviada para o Telegram com sucesso!")
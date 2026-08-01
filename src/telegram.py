import os
import asyncio
from telegram import Bot
from telegram.request import HTTPXRequest

async def enviar_mensagem_telegram(texto, caminho_foto=None):
    """Envia uma mensagem de texto ou uma foto com legenda para o canal/chat."""
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("Credenciais do Telegram não configuradas.")
        return

    request_config = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    bot = Bot(token=token, request=request_config)
    
    async with bot:
        if caminho_foto and os.path.exists(caminho_foto):
            with open(caminho_foto, 'rb') as photo_file:
                await bot.send_photo(chat_id=chat_id, photo=photo_file, caption=texto, parse_mode="Markdown")
            print("Foto/Banner enviado com sucesso!")
        else:
            await bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")

async def enviar_video_telegram(texto, caminho_video):
    """Envia um vídeo MP4 gerado para o Telegram."""
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_MY_CHAT_ID")
    
    if not token or not chat_id:
        print("Credenciais do Telegram não configuradas.")
        return

    request_config = HTTPXRequest(connect_timeout=60.0, read_timeout=60.0)
    bot = Bot(token=token, request=request_config)
    
    async with bot:
        if os.path.exists(caminho_video):
            with open(caminho_video, 'rb') as video_file:
                await bot.send_video(chat_id=chat_id, video=video_file, caption=texto, parse_mode="Markdown")
            print("🎬 Vídeo do TikTok enviado com sucesso para o Telegram!")
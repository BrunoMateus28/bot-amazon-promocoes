import os
import re
import csv
import json
import asyncio
import numpy as np
import textwrap
import time
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

from dotenv import load_dotenv
load_dotenv()

# Motor de Falsificação de Assinatura (Burla o TLS Fingerprint da Amazon)
from curl_cffi import requests 

from google import genai
from google.genai import types

from src.telegram import enviar_mensagem_telegram, enviar_video_telegram

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from moviepy.editor import ImageSequenceClip

# ==========================================================
# CONFIGURAÇÕES E UTILITÁRIOS
# ==========================================================
HISTORICO_FILE = "historico_precos.json"
ASSETS_DIR = "assets"

os.makedirs(ASSETS_DIR, exist_ok=True)

def carregar_json(caminho, default):
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)

def limpar_historico_antigo(valores):
    limite_30_dias = datetime.now() - timedelta(days=30)
    return [
        v for v in valores 
        if datetime.strptime(v["data"], "%Y-%m-%d") >= limite_30_dias
    ]

def formatar_real(valor):
    return f"{valor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

def remover_emojis(texto):
    if not texto:
        return ""
    return re.sub(r'[^\x00-\x7F\x80-\xFF\u0100-\u017F\u0180-\u024F\u1E00-\u1EFF]', '', texto).strip()

# ==========================================================
# CÉREBRO DE RASPAGEM NATIVA
# ==========================================================
def obter_asin_do_link(url_curta):
    try:
        res = requests.get(url_curta, impersonate="chrome", timeout=15, allow_redirects=True)
        url_final = res.url
        
        match = re.search(r'/(?:dp|product|ASIN)/([A-Z0-9]{10})', url_final, re.IGNORECASE)
        if not match:
            match = re.search(r'/([A-Z0-9]{10})(?:[/?]|$)', url_final, re.IGNORECASE)
            
        if match:
            return match.group(1).upper()
            
    except Exception as e:
        print(f"  ❌ Erro ao decodificar link: {e}")
        
    return None

def raspar_preco_amazon_direto(url_original):
    asin = obter_asin_do_link(url_original)
    if not asin:
        print("  ❌ ASIN não encontrado na URL final.")
        return None
        
    url_busca = f"https://www.amazon.com.br/s?k={asin}&rh=p_6%3AA1ZZFT5FULY4LN"

    for tentativa in range(3):
        try:
            res = requests.get(url_busca, impersonate="chrome", timeout=15)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "html.parser")
                preco_elemento = soup.select_one(f'div[data-asin="{asin}"] .a-price .a-offscreen')
                if not preco_elemento:
                    preco_elemento = soup.select_one('.s-result-item .a-price .a-offscreen')
                
                if preco_elemento:
                    texto_preco = preco_elemento.get_text().strip()
                    texto_limpo = texto_preco.replace("R$", "").replace("\xa0", "").replace(" ", "").replace(".", "").replace(",", ".").strip()
                    match_preco = re.search(r"(\d+\.\d{2})", texto_limpo)
                    if match_preco:
                        return float(match_preco.group(1))
                else:
                    print(f"  ⚠️ [Tentativa {tentativa+1}/3] Fora de estoque ou layout dinâmico.")
            else:
                print(f"  ⚠️ [Tentativa {tentativa+1}/3] Erro HTTP: {res.status_code}")
                
        except Exception as e:
            print(f"  ❌ Erro de conexão: {e}")
            
        time.sleep(random.uniform(2.0, 5.0))
    return None

# ==========================================================
# INTEGRAÇÃO GEMINI: CONTEÚDO DO TELEGRAM + TIKTOK
# ==========================================================
def gerar_legenda_ia(titulo, preco_atual, media_preco):
    api_key = os.getenv("GEMINI_API_KEY")

    # Fallbacks para o caso da API do Gemini estar indisponível.
    resultado_padrao = {
        "gancho": "VOCÊ NÃO VAI ACREDITAR...",
        "legenda": (
            f"📖 {titulo}\n\n"
            "Uma fantasia cheia de personagens marcantes, conflitos de poder "
            "e escolhas que podem mudar completamente o rumo da história. "
            "Se você gosta de histórias que prendem do começo ao fim, "
            "essa pode ser uma ótima leitura. #BookTokBrasil #LivrosDeFantasia"
        ),
        "descricao_telegram": (
            f"{titulo} é uma história de fantasia cheia de conflitos, "
            "personagens marcantes e reviravoltas. Uma ótima pedida para "
            "quem gosta de mundos envolventes e histórias difíceis de largar."
        ),
        "comentario_estrategico": (
            "Qual o seu personagem favorito dessa história? 👇"
        )
    }

    if not api_key:
        return resultado_padrao

    try:
        client = genai.Client(api_key=api_key)

        prompt = f"""
        Você é um especialista em literatura de fantasia. Seu objetivo é criar 
        conteúdo para a comunidade leitora (BookTok) e para um canal do Telegram.

        Livro: "{titulo}"
        Preço atual: R$ {preco_atual}
        Média de preço: R$ {media_preco}

        Gere conteúdo para DOIS canais diferentes: Telegram e TikTok.

        REGRAS DA DESCRIÇÃO DO TELEGRAM:
        - Escreva uma descrição curta e envolvente do livro.
        - Entre 60 e 100 palavras.
        - NÃO revele spoilers.
        - Não conte o final, mortes, grandes reviravoltas ou revelações.
        - Apresente a premissa, o tipo de mundo/conflito e o que torna a leitura interessante.
        - O texto deve provocar vontade de ler.
        - Não mencione preço, promoção, Amazon ou link (isso é adicionado depois).
        - Não use hashtags.
        - Escreva em português brasileiro natural.

        REGRAS DO TIKTOK (ATENÇÃO MÁXIMA - RISCO DE BANIMENTO):
        - Gere um gancho curto, com no máximo 7 palavras.
        - Gere uma legenda otimizada para descoberta de livros (BookTok).
        - A legenda DEVE focar APENAS na história, universo, romance, dragões ou conflitos.
        - É ESTRITAMENTE PROIBIDO usar as palavras: preço, desconto, promoção, comprar, garanta, estoque, corra, link, bio, comentário fixado, oferta.
        - É ESTRITAMENTE PROIBIDO criar senso de urgência ou tentar vender o livro.
        - Gere um comentário estratégico focado APENAS em puxar assunto com a comunidade (Ex: "Quem aqui já leu essa obra?", "Qual sua parte favorita?"). NUNCA direcione para links ou vendas no comentário.
        - Inclua hashtags focadas na história (ex: #booktokbrasil #livrosdefantasia).

        Retorne EXATAMENTE UM JSON válido com estas chaves:
        {{
            "gancho": "gancho do TikTok",
            "legenda": "legenda do TikTok",
            "descricao_telegram": "descrição do livro para o canal do Telegram",
            "comentario_estrategico": "comentário para fixar no TikTok"
        }}

        Não coloque markdown, ``` ou qualquer texto fora do JSON.
        """

        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt
        )

        if response.text:
            texto_limpo = (
                response.text
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )
            dados = json.loads(texto_limpo)

            return {
                "gancho": dados.get("gancho", resultado_padrao["gancho"]),
                "legenda": dados.get("legenda", resultado_padrao["legenda"]),
                "descricao_telegram": dados.get(
                    "descricao_telegram",
                    resultado_padrao["descricao_telegram"]
                ),
                "comentario_estrategico": dados.get(
                    "comentario_estrategico",
                    resultado_padrao["comentario_estrategico"]
                )
            }

        return resultado_padrao

    except Exception as e:
        print(f"❌ Erro na IA: {e}")
        return resultado_padrao

def montar_mensagem_telegram(
    titulo,
    preco_atual,
    media_preco,
    menor_historico,
    url,
    descricao_ia
):
    """
    Monta exclusivamente a mensagem da promoção do Telegram.

    A IA fornece apenas a descrição literária.
    A estrutura comercial é controlada pelo código para garantir
    que preço, média e link sempre apareçam corretamente.
    """

    if preco_atual < menor_historico:
        header = "🔥 MENOR PREÇO HISTÓRICO!"
    else:
        header = "📉 ABAIXO DA MÉDIA!"

    return (
        f"{header}\n\n"
        f"📖 *{titulo}*\n\n"
        f"{descricao_ia.strip()}\n\n"
        f"💰 *Agora:* R$ {formatar_real(preco_atual)}\n"
        f"📊 *Média:* R$ {formatar_real(media_preco)}\n\n"
        f"🛒 *Comprar:*\n"
        f"{url}"
    )


# ==========================================================
# DESIGNER DE VÍDEO (LOOPING E RETENÇÃO)
# ==========================================================
def obter_fonte(tamanho):
    caminho_fonte = os.path.join(ASSETS_DIR, "Montserrat-Bold.ttf")
    if not os.path.exists(caminho_fonte):
        url = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf"
        try:
            res = requests.get(url, impersonate="chrome", timeout=15)
            with open(caminho_fonte, 'wb') as f:
                f.write(res.content)
        except Exception:
            return ImageFont.load_default()
    try:
        return ImageFont.truetype(caminho_fonte, tamanho)
    except IOError:
        return ImageFont.load_default()

def criar_gradiente_vertical(largura, altura, cor_topo, cor_base):
    base = Image.new('RGBA', (largura, altura), cor_base)
    topo = Image.new('RGBA', (largura, altura), cor_topo)
    mask = Image.new('L', (largura, altura))
    for y in range(altura):
        val = int(255 * (y / altura))
        ImageDraw.Draw(mask).line([(0, y), (largura, y)], fill=val)
    return Image.composite(base, topo, mask)

def gerar_video_tiktok(item, media_preco, caminho_capa, caminho_grafico, caminho_saida_video, gancho_ia=""):
    largura, altura = 1080, 1920
    fps = 24
    duracao = 5.5
    total_frames = int(fps * duracao)

    fonte_h = obter_fonte(45)
    fonte_gancho = obter_fonte(65)
    fonte_t = obter_fonte(50) 
    fonte_p = obter_fonte(145)
    fonte_m = obter_fonte(40)
    fonte_c = obter_fonte(35)

    capa = Image.open(caminho_capa).convert("RGBA") if caminho_capa and os.path.exists(caminho_capa) else None
    grafico = Image.open(caminho_grafico).convert("RGBA") if caminho_grafico and os.path.exists(caminho_grafico) else None

    if capa:
        nova_alt = 500
        capa = capa.resize((int(nova_alt * (capa.width/capa.height)), nova_alt), Image.Resampling.LANCZOS)
    if grafico:
        nova_larg = 960
        grafico = grafico.resize((nova_larg, int(nova_larg / (grafico.width/grafico.height))), Image.Resampling.LANCZOS)

    fundo_escuro = criar_gradiente_vertical(largura, altura, (20, 15, 40, 255), (10, 5, 20, 255))
    fundo_contraste = criar_gradiente_vertical(largura, altura, (40, 15, 55, 255), (15, 5, 25, 255))
    fundo_alerta = criar_gradiente_vertical(largura, altura, (25, 20, 30, 255), (5, 5, 10, 255))

    gancho_tela = remover_emojis(gancho_ia).upper() if gancho_ia else "ALERTA DE DESCONTO!"
    frames = []
    pos_y_card = 840 if capa else 600
    altura_card = 380 if capa else 500

    for f_idx in range(total_frames):
        t = f_idx / fps
        
        if t < 1.5:
            img = fundo_escuro.copy()
            draw = ImageDraw.Draw(img)
            linhas_gancho = textwrap.wrap(gancho_tela, width=20)
            y_g = 800
            cor_gancho = (255, 179, 0, 255) if f_idx % 6 < 3 else (255, 255, 255, 255)
            for lg in linhas_gancho[:3]:
                draw.text((540, y_g), lg, font=fonte_gancho, fill=cor_gancho, anchor="mm")
                y_g += 80
                
        elif 1.5 <= t < 3.5:
            img = fundo_contraste.copy()
            draw = ImageDraw.Draw(img)
            if capa:
                img.paste(capa, ((largura - capa.width)//2, 280), capa)
            draw.rounded_rectangle([70, pos_y_card, 1010, pos_y_card + altura_card], radius=30, fill=(25, 25, 35, 240), outline=(255, 179, 0, 255), width=4)
            draw.text((540, pos_y_card + 50), "MENOR PREÇO DO MÊS!", font=fonte_h, fill=(255, 179, 0, 255), anchor="mm")
            linhas_titulo = textwrap.wrap(item["titulo"], width=28)
            y_titulo = pos_y_card + 130
            for linha in linhas_titulo[:2]: 
                draw.text((540, y_titulo), linha, font=fonte_t, fill=(255, 255, 255, 255), anchor="mm")
                y_titulo += 60
            draw.text((540, pos_y_card + 280), f"R$ {formatar_real(item['preco_atual'])}", font=fonte_p, fill=(16, 185, 129, 255), anchor="mm")
            
        elif 3.5 <= t < 4.8:
            img = fundo_alerta.copy()
            draw = ImageDraw.Draw(img)
            draw.text((540, 200), "PROVA DO DESCONTO", font=fonte_h, fill=(255, 179, 0, 255), anchor="mm")
            linhas_titulo = textwrap.wrap(item["titulo"], width=35)
            draw.text((540, 270), linhas_titulo[0], font=fonte_m, fill=(220, 220, 230, 255), anchor="mm")
            if grafico:
                img.paste(grafico, ((largura - grafico.width)//2, 450), grafico)
                
        else:
            img = fundo_escuro.copy()
            draw = ImageDraw.Draw(img)
            draw.text((540, 800), "VERIFIQUE AGORA", font=fonte_gancho, fill=(255, 255, 255, 255), anchor="mm")
            draw.text((540, 900), "OS COMENTÁRIOS!", font=fonte_gancho, fill=(255, 179, 0, 255), anchor="mm")
            draw.rounded_rectangle([150, 1350, 930, 1450], radius=40, fill=(255, 179, 0, 255))
            draw.text((540, 1400), "ANTES QUE ZERE", font=fonte_c, fill=(15, 15, 20, 255), anchor="mm")

        if 1.5 <= t < 4.8:
            draw.rounded_rectangle([140, 50, 940, 130], radius=25, fill=(74, 20, 140, 220), outline=(255, 179, 0, 255), width=3)
            draw.text((540, 90), "BARDO DAS PROMOÇÕES", font=fonte_h, fill=(255, 255, 255, 255), anchor="mm")

        draw.rectangle([0, 0, int((f_idx/total_frames)*largura), 15], fill=(255, 179, 0, 255))
        frames.append(np.array(img.convert("RGB")))

    clip = ImageSequenceClip(frames, fps=fps)
    clip.write_videofile(caminho_saida_video, codec="libx264", audio=False, logger=None)

# ==========================================================
# GOOGLE SHEETS E PORTAL COM HOVER SWAP
# ==========================================================
def buscar_ofertas_csv():
    url_csv = os.getenv("GOOGLE_SHEETS_CSV_URL")
    if not url_csv:
        return []
    try:
        res = requests.get(url_csv, impersonate="chrome", timeout=15)
        res.encoding = 'utf-8'
        res.raise_for_status()
        linhas_csv = [linha for inline in res.text.splitlines() if (linha := inline.strip())]
        if not linhas_csv:
            return []
        primeira_linha = linhas_csv[0]
        delimitador = ';' if ';' in primeira_linha else ','
        leitor = csv.DictReader(linhas_csv, delimiter=delimitador)
        ofertas = []
        for linha in leitor:
            linha_limpa = {k.strip(): v.strip() for k, v in linha.items() if k and v}
            id_item = linha_limpa.get("id", "").strip()
            titulo = linha_limpa.get("titulo", "").strip()
            preco_raw = linha_limpa.get("preco_atual", "")
            preco_str = preco_raw.replace("R$", "").replace(" ", "").replace(",", ".").strip() if preco_raw else "0"
            url = linha_limpa.get("url", "").strip()
            imagem_url = linha_limpa.get("imagem_url", "").strip()
            if id_item and titulo and url:
                try:
                    ofertas.append({
                        "id": id_item, "titulo": titulo,
                        "preco_atual": float(preco_str), "url": url, "imagem_url": imagem_url
                    })
                except ValueError:
                    pass
        return ofertas
    except Exception as e:
        print(f"-> Erro ao sincronizar CSV: {e}")
        return []

def gerar_sitemap():
    url_base = "https://brunomateus28.github.io/bot-amazon-promocoes/"
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
   <url><loc>{url_base}</loc><lastmod>{data_hoje}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>
</urlset>"""
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write(xml_content)

def _gerar_card_produto(item, preco_atual, media, menor):
    item_id = item["id"]
    titulo = item["titulo"]
    badge_html = ""
    if preco_atual < menor:
        badge_html = '<div class="absolute top-3 left-3 z-10"><span class="px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-full backdrop-blur-md shadow-lg">Recorde Histórico</span></div>'
    elif preco_atual < media:
        badge_html = '<div class="absolute top-3 left-3 z-10"><span class="px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-full backdrop-blur-md shadow-lg">Abaixo da Média</span></div>'
    
    # Busca a imagem da Capa e do Gráfico salvos localmente
    caminho_capa = f"assets/capa_{item_id}.jpg"
    caminho_grafico = f"assets/grafico_{item_id}.png"
    
    # Define as imagens do hover (Usa URL do item caso a capa local não exista ainda)
    img_capa = caminho_capa if os.path.exists(caminho_capa) else (item.get("imagem_url") or "bau.png")
    # Se o gráfico não existir (ainda não foi gerado), exibe a capa nas duas fases do hover
    img_grafico = caminho_grafico if os.path.exists(caminho_grafico) else img_capa
    
    return f"""
    <article class="relative flex flex-col bg-surface rounded-2xl border border-white/5 overflow-hidden hover:border-bardo-gold/40 transition-all duration-300 group shadow-lg">
        {badge_html}
        <!-- Vitrine com Efeito Hover Swap -->
        <div class="relative h-64 w-full bg-gradient-to-b from-white/[0.03] to-transparent border-b border-white/5 overflow-hidden">
            <!-- Imagem 1: Capa (Soma ao Hover) -->
            <img src="{img_capa}" alt="Capa de {titulo}" loading="lazy" class="absolute inset-0 w-full h-full p-6 object-contain drop-shadow-[0_15px_25px_rgba(0,0,0,0.6)] transition-opacity duration-500 opacity-100 group-hover:opacity-0" />
            <!-- Imagem 2: Gráfico (Aparece no Hover) -->
            <img src="{img_grafico}" alt="Gráfico de {titulo}" loading="lazy" class="absolute inset-0 w-full h-full p-4 object-contain drop-shadow-[0_15px_25px_rgba(0,0,0,0.6)] transition-opacity duration-500 opacity-0 group-hover:opacity-100" />
        </div>
        <div class="p-5 flex flex-col flex-grow">
            <h3 class="text-base font-semibold text-gray-100 leading-snug line-clamp-2 mb-4 group-hover:text-bardo-gold transition-colors">{titulo}</h3>
            <div class="flex flex-col mt-auto mb-5">
                <div class="flex items-baseline gap-2">
                    <span class="text-2xl font-bold text-white tracking-tight">R$ {formatar_real(preco_atual)}</span>
                    <span class="text-sm text-gray-500 line-through">R$ {formatar_real(media)}</span>
                </div>
            </div>
            <a href="{item['url']}" target="_blank" rel="nofollow noopener" class="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-white/5 hover:bg-bardo-gold hover:text-bardo-dark text-sm font-bold text-gray-200 transition-all">Comprar na Amazon</a>
        </div>
    </article>"""

def gerar_site_estatico(ofertas, historico):
    cards_html_list = []
    for item in ofertas:
        item_id = item["id"]
        preco_atual = item["preco_atual"]
        if item_id in historico and historico[item_id]["valores_30_dias"]:
            precos = [v["preco"] for v in historico[item_id]["valores_30_dias"]]
            media = sum(precos)/len(precos)
            menor = historico[item_id]["menor_preco_historico"]
        else:
            media, menor = preco_atual, preco_atual
        cards_html_list.append(_gerar_card_produto(item, preco_atual, media, menor))

    html_template = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bardo das Promoções | Ofertas de Fantasia e Sci-Fi</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    colors: {{
                        background: '#09090b',
                        surface: '#121214',
                        'bardo-gold': '#FFB300',
                        'bardo-dark': '#202024'
                    }}
                }}
            }}
        }}
    </script>
</head>
<body class="bg-background text-gray-300 min-h-screen p-4 md:p-8">
    <header class="max-w-7xl mx-auto mb-12 text-center">
        <h1 class="text-3xl md:text-5xl font-bold text-white mb-3">Bardo das Promoções</h1>
        <p class="text-bardo-gold font-semibold tracking-wide uppercase text-sm md:text-base mb-6">Monitoramento 24h de Fantasia & Sci-Fi</p>
        
        <!-- BOTÃO DO TELEGRAM AQUI -->
        <a href="https://t.me/bardodaspromos" target="_blank" rel="noopener noreferrer" class="inline-flex items-center justify-center gap-2 px-8 py-3.5 text-sm md:text-base font-bold text-bardo-dark bg-bardo-gold rounded-full hover:bg-yellow-400 hover:-translate-y-1 transition-all duration-300 shadow-[0_0_20px_rgba(255,179,0,0.3)] hover:shadow-[0_0_30px_rgba(255,179,0,0.6)]">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.295-.6.295-.002 0-.003 0-.005 0l.213-3.054 5.56-5.022c.24-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.832.941z"/></svg>
            Entrar no Canal do Telegram
        </a>
    </header>
    
    <main class="max-w-7xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {''.join(cards_html_list)}
    </main>
</body>
</html>"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_template)
    gerar_sitemap()

# ==========================================================
# LÓGICA PRINCIPAL DO BOT
# ==========================================================
async def processar_ofertas():
    ofertas = buscar_ofertas_csv()
    if not ofertas:
        print("Nenhuma oferta para processar.")
        return

    historico = carregar_json(HISTORICO_FILE, {})
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    houve_mudanca_no_historico = False

    for item in ofertas:
        item_id = item["id"]
        print(f"\n🔍 Raspando a Amazon nativamente: {item['titulo'][:30]}...")
        
        preco_raspado = raspar_preco_amazon_direto(item["url"])
        
        if preco_raspado:
            preco_atual = preco_raspado
            item["preco_atual"] = preco_atual 
            print(f"   ✅ Preço capturado com sucesso: R$ {preco_atual:.2f}")
        else:
            if item_id in historico and len(historico[item_id].get("valores_30_dias", [])) > 0:
                preco_atual = historico[item_id]["valores_30_dias"][-1]["preco"]
                item["preco_atual"] = preco_atual
                print(f"   ⚠️ Falha na raspagem. Usando último preço do histórico: R$ {preco_atual:.2f}")
            else:
                print(f"   ⏭️ Pulando: Sem preço na Amazon e sem histórico local.")
                continue

        time.sleep(random.uniform(2.0, 4.0))

        livro_novo = False
        if item_id not in historico:
            historico[item_id] = {"menor_preco_historico": preco_atual, "ultimo_preco_divulgado": preco_atual, "valores_30_dias": []}
            livro_novo = True
        
        dados_item = historico[item_id]
        dados_item["valores_30_dias"].append({"data": data_hoje, "preco": preco_atual})
        dados_item["valores_30_dias"] = limpar_historico_antigo(dados_item["valores_30_dias"])
        houve_mudanca_no_historico = True
        
        precos_30 = [v["preco"] for v in dados_item["valores_30_dias"]]
        media_preco = sum(precos_30) / len(precos_30) if precos_30 else preco_atual
        menor_historico = dados_item["menor_preco_historico"]
        ultimo_divulgado = dados_item["ultimo_preco_divulgado"]
        
        condicao_1 = preco_atual < menor_historico
        condicao_2 = (preco_atual < media_preco) and (preco_atual < ultimo_divulgado) if ultimo_divulgado is not None else False
        condicao_forcada = ultimo_divulgado is None

        if livro_novo:
            print(f"   🆕 Primeira vez rastreando. Preço base salvo no histórico, não será postado hoje.")
        elif condicao_1 or condicao_2 or condicao_forcada:
            print(f"🔥 Aprovado para postagem: {item['titulo']}")
            mensagem = f"🚨 PROMOÇÃO!\n\n📚 *{item['titulo']}*\n💰 R$ {formatar_real(preco_atual)}\n\n🔗 {item['url']}"
            
            caminho_grafico = os.path.join(ASSETS_DIR, f"grafico_{item_id}.png")
            caminho_capa = os.path.join(ASSETS_DIR, f"capa_{item_id}.jpg")
            caminho_video = os.path.join(ASSETS_DIR, f"tiktok_{item_id}.mp4")
            
            if item.get("imagem_url"):
                try:
                    res_capa = requests.get(item["imagem_url"], impersonate="chrome", timeout=10)
                    if res_capa.status_code == 200:
                        with open(caminho_capa, 'wb') as f:
                            f.write(res_capa.content)
                except Exception:
                    pass

            try:
                valores_ordenados = sorted(dados_item["valores_30_dias"], key=lambda x: x["data"])
                plt.style.use('dark_background')
                fig, ax = plt.subplots(figsize=(9, 4.5))
                fig.patch.set_facecolor('#1d1d1d')
                ax.set_facecolor('#1d1d1d')
                ax.plot([v["data"] for v in valores_ordenados], [v["preco"] for v in valores_ordenados], color='#FFB300', marker='o', linewidth=2)
                plt.savefig(caminho_grafico, facecolor=fig.get_facecolor(), dpi=120)
                plt.close()
            except Exception:
                plt.close()
                caminho_grafico = None

            conteudo_ia = gerar_legenda_ia(
                item['titulo'],
                preco_atual,
                media_preco
            )

            # Mensagem específica do canal:
            # header dinâmico + descrição sem spoiler + preço + média + link.
            mensagem = montar_mensagem_telegram(
                titulo=item['titulo'],
                preco_atual=preco_atual,
                media_preco=media_preco,
                menor_historico=menor_historico,
                url=item['url'],
                descricao_ia=conteudo_ia["descricao_telegram"]
            )
            
            try:
                gerar_video_tiktok(item, media_preco, caminho_capa if os.path.exists(caminho_capa) else None, caminho_grafico, caminho_video, gancho_ia=conteudo_ia["gancho"])
            except Exception:
                caminho_video = None

            # CRIANDO O BANNER FUNDIDO PARA O TELEGRAM (CAPA + GRÁFICO LADO A LADO)
            caminho_combo = None
            if caminho_grafico and os.path.exists(caminho_grafico) and caminho_capa and os.path.exists(caminho_capa):
                caminho_combo = os.path.join(ASSETS_DIR, f"combo_{item_id}.png")
                try:
                    img_grafico = Image.open(caminho_grafico)
                    img_capa = Image.open(caminho_capa)
                    altura_alvo = img_grafico.height
                    largura_capa = int(altura_alvo * (img_capa.width / img_capa.height))
                    img_capa_resized = img_capa.resize((largura_capa, altura_alvo), Image.Resampling.LANCZOS)
                    
                    largura_total = img_grafico.width + largura_capa
                    img_combo = Image.new('RGB', (largura_total, altura_alvo), (29, 29, 29))
                    img_combo.paste(img_capa_resized, (0, 0))
                    img_combo.paste(img_grafico, (largura_capa, 0))
                    img_combo.save(caminho_combo)
                except Exception as e:
                    print(f"Erro ao combinar imagens: {e}")
                    caminho_combo = caminho_grafico 
            else:
                caminho_combo = caminho_grafico

            try:
                # 1. Envia Imagem Combinada + Promoção (O seu telegram.py já sabe que vai pro Canal)
                await enviar_mensagem_telegram(mensagem, caminho_foto=caminho_combo)
                
                # 2. Envia Vídeo + Estratégia SEO (O seu telegram.py já sabe que vai pro Privado)
                if caminho_video and os.path.exists(caminho_video):
                    legenda_privada = (
                        f"📱 *VÍDEO PRONTO PARA POSTAR*\n\n"
                        f"📝 *LEGENDA (Focada em reter e sem 'link na bio'):*\n{conteudo_ia['legenda']}\n\n"
                        f"💬 *COMENTÁRIO PARA FIXAR (Link + Polêmica):*\n{conteudo_ia['comentario_estrategico']}"
                    )
                    await enviar_video_telegram(legenda_privada, caminho_video)
                    os.remove(caminho_video)
                
                dados_item["ultimo_preco_divulgado"] = preco_atual
            except Exception as e:
                print(f"Erro ao enviar: {e}")

        if preco_atual < menor_historico:
            historico[item_id]["menor_preco_historico"] = preco_atual

    gerar_site_estatico(ofertas, historico)
    if houve_mudanca_no_historico:
        salvar_json(HISTORICO_FILE, historico)

if __name__ == "__main__":
    asyncio.run(processar_ofertas())
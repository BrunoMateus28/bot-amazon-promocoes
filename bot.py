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

# Motor de Falsificação de Assinatura (Burla o TLS Fingerprint da Amazon)
from curl_cffi import requests 

from apify_client import ApifyClient

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
    """Remove caracteres emoji para evitar blocos brancos em fontes ttf comuns."""
    if not texto:
        return ""
    return re.sub(r'[^\x00-\x7F\x80-\xFF\u0100-\u017F\u0180-\u024F\u1E00-\u1EFF]', '', texto).strip()

# ==========================================================
# CÉREBRO DE RASPAGEM NATIVA (ZERO CUSTO E ANTI-BLOQUEIO)
# ==========================================================
def obter_asin_do_link(url_curta):
    """Segue o redirecionamento disfarçado de Chrome para capturar o ASIN oficial."""
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

def raspar_preco_amazon(url):
    """Busca o preço usando a infraestrutura do Apify (Proxy Residencial)."""
    api_token = os.getenv("APIFY_TOKEN")
    if not api_token:
        print("❌ APIFY_TOKEN não configurada.")
        return None

    client = ApifyClient(api_token)
    
    # Prepara a entrada para o Actor da Amazon (apify/amazon-scraper)
    run_input = {
        "queries": [url],
        "maxItemsPerQuery": 1,
        "categoryDetails": False,
        "reviewsDetails": False,
    }

    try:
        # Chama o Actor oficial do Apify para Amazon
        run = client.actor("apify/amazon-scraper").call(run_input=run_input)
        
        # Pega o resultado direto do dataset
        dataset = client.dataset(run["defaultDatasetId"]).iterate_items()
        
        for item in dataset:
            # O Apify retorna o preço formatado e limpo
            preco_str = item.get("price") # Ex: "R$ 78,99"
            if preco_str:
                preco_limpo = preco_str.replace("R$", "").replace(".", "").replace(",", ".").strip()
                return float(preco_limpo)
                
    except Exception as e:
        print(f"❌ Erro ao buscar preço via Apify: {e}")
        
    return None
# ==========================================================
# INTEGRAÇÃO GEMINI: GERAÇÃO DE LEGENDA PARA TIKTOK
# ==========================================================
def gerar_legenda_ia(titulo, preco_atual, media_preco):
    """Usa a SDK do Gemini para gerar um gancho dinâmico para o vídeo e uma legenda completa."""
    api_key = os.getenv("GEMINI_API_KEY")
    
    legenda_padrao = (
        f"🔥 *QUEDA DE PREÇO!* {titulo}\n\n"
        f"💰 *Preço Atual:* R$ {formatar_real(preco_atual)}\n"
        f"📊 *Média de 30 dias:* R$ {formatar_real(media_preco)}\n\n"
        f"🔗 *Link de compra com desconto no nosso canal do Telegram (link na bio)!*\n\n"
        f"#booktokbrasil #booktok #livros #promocaodelivros"
    )
    
    resultado_padrao = {
        "gancho": "Você já conhecia essa história?",
        "legenda": legenda_padrao
    }

    if not api_key:
        print("⚠️ GEMINI_API_KEY não configurada. Usando legenda e gancho padrão.")
        return resultado_padrao

    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        Aja como um criador de conteúdo do BookTok/Cultura Geek no TikTok. 
        O livro '{titulo}' entrou em promoção na Amazon: de R$ {formatar_real(media_preco)} por R$ {formatar_real(preco_atual)}.

        Forneça a resposta estritamente no seguinte formato JSON (sem formatação markdown ```json, apenas o JSON puro):
        {{
            "gancho": "Uma frase de impacto curta e intrigante de até 10 palavras sobre o lore/autor do livro para colocar DENTRO do vídeo (ex: 'A melhor fantasia que você não leu ainda!')",
            "legenda": "A legenda completa do TikTok seguindo as regras..."
        }}

        Regras para a legenda:
        1. Comece com um gancho desafiador ou curiosidade.
        2. NÃO pareça um vendedor. Seja fã recomendando para fã.
        3. Não mencione o preço na legenda.
        4. No final, adicione exatamente: "🔗 Link de compra com desconto no nosso canal do Telegram (link na bio)!"
        5. Adicione 5 hashtags relacionadas a #BookTokBrasil.
        6. Sem spoilers, max 150 caracteres no corpo principal.
        """
        
        print(f"🧠 Gerando legenda e gancho com IA para '{titulo[:20]}...'")
        
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt,
        )
        
        if response.text:
            texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
            dados = json.loads(texto_limpo)
            return {
                "gancho": dados.get("gancho", "Sua próxima grande leitura!"),
                "legenda": dados.get("legenda", legenda_padrao)
            }
        return resultado_padrao
        
    except Exception as e:
        print(f"❌ Erro ao gerar legenda/gancho com Gemini: {e}")
        return resultado_padrao

# ==========================================================
# DESIGNER DE VÍDEO (TIKTOK V3 PREMIUM - ALTA RETENÇÃO)
# ==========================================================
def obter_fonte(tamanho):
    caminho_fonte = os.path.join(ASSETS_DIR, "Montserrat-Bold.ttf")
    if not os.path.exists(caminho_fonte):
        url = "[https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf](https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf)"
        try:
            # Usando curl_cffi para downloads também
            res = requests.get(url, impersonate="chrome", timeout=15)
            res.raise_for_status()
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
    print(f"🎬 Criando vídeo dinâmico de alta retenção: {item['titulo'][:30]}...")
    largura, altura = 1080, 1920
    fps = 24
    duracao = 6
    total_frames = fps * duracao

    fonte_h = obter_fonte(45)
    fonte_gancho = obter_fonte(55) 
    fonte_t = obter_fonte(50) 
    fonte_p = obter_fonte(140)
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

    gancho_tela = remover_emojis(gancho_ia) if gancho_ia else "Você já leu essa história?"

    frames = []

    pos_y_card = 840 if capa else 600
    altura_card = 380 if capa else 500

    for f_idx in range(total_frames):
        t = f_idx / fps
        
        if t < 1.5:
            img = fundo_escuro.copy()
            draw = ImageDraw.Draw(img)
            
            linhas_gancho = textwrap.wrap(gancho_tela, width=25)
            y_g = 850
            for lg in linhas_gancho[:3]:
                draw.text((540, y_g), lg.upper(), font=fonte_gancho, fill=(255, 179, 0, 255), anchor="mm")
                y_g += 70

        elif 1.5 <= t < 3.0:
            img = fundo_contraste.copy()
            draw = ImageDraw.Draw(img)
            
            if capa:
                y_capa = 280
                img.paste(capa, ((largura - capa.width)//2, y_capa), capa)
            
            draw.rounded_rectangle([70, pos_y_card, 1010, pos_y_card + altura_card], radius=30, fill=(25, 25, 35, 240), outline=(255, 179, 0, 255), width=4)
            draw.text((540, pos_y_card + 50), "DESCONTO DETECTADO!", font=fonte_h, fill=(255, 179, 0, 255), anchor="mm")

            linhas_titulo = textwrap.wrap(item["titulo"], width=28)
            y_titulo = pos_y_card + 130
            for linha in linhas_titulo[:2]: 
                draw.text((540, y_titulo), linha, font=fonte_t, fill=(255, 255, 255, 255), anchor="mm")
                y_titulo += 60

            draw.text((540, pos_y_card + 280), f"R$ {formatar_real(item['preco_atual'])}", font=fonte_p, fill=(16, 185, 129, 255), anchor="mm")
            draw.text((540, pos_y_card + 370), f"Média 30 dias: R$ {formatar_real(media_preco)}", font=fonte_m, fill=(160, 160, 180, 255), anchor="mm")

        elif 3.0 <= t < 4.8:
            img = fundo_alerta.copy()
            draw = ImageDraw.Draw(img)
            
            draw.text((540, 200), "HISTÓRICO DE PREÇOS", font=fonte_h, fill=(255, 179, 0, 255), anchor="mm")
            linhas_titulo = textwrap.wrap(item["titulo"], width=35)
            draw.text((540, 270), linhas_titulo[0], font=fonte_m, fill=(220, 220, 230, 255), anchor="mm")
            
            if grafico:
                img.paste(grafico, ((largura - grafico.width)//2, 450), grafico)

        else:
            img = fundo_escuro.copy()
            draw = ImageDraw.Draw(img)
            
            draw.text((540, 800), "O LINK COPIÁVEL ESTÁ", font=fonte_gancho, fill=(255, 255, 255, 255), anchor="mm")
            draw.text((540, 900), "NO CANAL DA BIO!", font=fonte_gancho, fill=(255, 179, 0, 255), anchor="mm")
            
            draw.rounded_rectangle([150, 1350, 930, 1450], radius=40, fill=(255, 179, 0, 255))
            draw.text((540, 1400), "CORRA PARA APROVEITAR", font=fonte_c, fill=(15, 15, 20, 255), anchor="mm")

        if 1.5 <= t < 4.8:
            draw.rounded_rectangle([140, 50, 940, 130], radius=25, fill=(74, 20, 140, 220), outline=(255, 179, 0, 255), width=3)
            draw.text((540, 90), "BARDO DAS PROMOÇÕES", font=fonte_h, fill=(255, 255, 255, 255), anchor="mm")

        draw.rectangle([0, 0, int((f_idx/total_frames)*largura), 15], fill=(255, 179, 0, 255))

        frames.append(np.array(img.convert("RGB")))

    clip = ImageSequenceClip(frames, fps=fps)
    clip.write_videofile(caminho_saida_video, codec="libx264", audio=False, logger=None)

# ==========================================================
# INTEGRAÇÃO COM GOOGLE SHEETS VIA CSV
# ==========================================================
def buscar_ofertas_csv():
    url_csv = os.getenv("GOOGLE_SHEETS_CSV_URL")
    if not url_csv:
        print("-> ERRO: GOOGLE_SHEETS_CSV_URL não configurada.")
        return []

    print("-> Sincronizando lista de produtos via CSV do Google Sheets...")
    try:
        response = requests.get(url_csv, impersonate="chrome", timeout=15)
        response.encoding = 'utf-8'
        response.raise_for_status()

        linhas_csv = [linha for inline in response.text.splitlines() if (linha := inline.strip())]
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
                    preco_atual = float(preco_str)
                    ofertas.append({
                        "id": id_item,
                        "titulo": titulo,
                        "preco_atual": preco_atual,
                        "url": url,
                        "imagem_url": imagem_url
                    })
                except ValueError:
                    pass

        print(f"-> Sincronização concluída! {len(ofertas)} produtos carregados.")
        return ofertas
    except Exception as e:
        print(f"-> Erro ao sincronizar produtos do CSV: {e}")
        return []

# ==========================================================
# GERADOR DO PORTAL WEB ESTÁTICO E SITEMAP
# ==========================================================
def gerar_sitemap():
    url_base = "[https://brunomateus28.github.io/bot-amazon-promocoes/](https://brunomateus28.github.io/bot-amazon-promocoes/)"
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="[http://www.sitemaps.org/schemas/sitemap/0.9](http://www.sitemaps.org/schemas/sitemap/0.9)">
   <url>
      <loc>{url_base}</loc>
      <lastmod>{data_hoje}</lastmod>
      <changefreq>daily</changefreq>
      <priority>1.0</priority>
   </url>
</urlset>"""
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write(xml_content)

def _gerar_card_produto(item, preco_atual, media, menor):
    item_id = item["id"]
    titulo = item["titulo"]
    
    badge_html = ""
    if preco_atual < menor:
        badge_html = """
        <div class="absolute top-3 left-3 z-10">
            <span class="px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-full backdrop-blur-md flex items-center gap-1 shadow-lg">
                <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path></svg>
                Recorde Histórico
            </span>
        </div>"""
    elif preco_atual < media:
        badge_html = """
        <div class="absolute top-3 left-3 z-10">
            <span class="px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-full backdrop-blur-md shadow-lg">
                Abaixo da Média
            </span>
        </div>"""

    path_banner_local = os.path.join(ASSETS_DIR, f"banner_{item_id}.png")
    if os.path.exists(path_banner_local):
        src_imagem = f"assets/banner_{item_id}.png"
    else:
        src_imagem = item.get("imagem_url") if item.get("imagem_url") else "bau.png"

    return f"""
    <article class="relative flex flex-col bg-surface rounded-2xl border border-white/5 overflow-hidden hover:border-bardo-gold/40 hover:shadow-2xl hover:shadow-bardo-gold/5 transition-all duration-300 group">
        {badge_html}
        
        <div class="relative h-64 w-full p-8 flex items-center justify-center bg-gradient-to-b from-white/[0.03] to-transparent border-b border-white/5">
            <img src="{src_imagem}" alt="Capa de {titulo}" loading="lazy" 
                 class="h-full w-auto object-contain drop-shadow-[0_15px_25px_rgba(0,0,0,0.6)] group-hover:-translate-y-1.5 group-hover:scale-[1.03] transition-all duration-500 ease-out" />
        </div>

        <div class="p-5 flex flex-col flex-grow">
            <h3 class="text-base font-semibold text-gray-100 leading-snug line-clamp-2 mb-4 group-hover:text-bardo-gold transition-colors duration-300" title="{titulo}">
                {titulo}
            </h3>

            <div class="flex flex-col mt-auto mb-5">
                <div class="flex items-baseline gap-2">
                    <span class="text-2xl font-bold text-white tracking-tight">R$ {formatar_real(preco_atual)}</span>
                    <span class="text-sm text-gray-500 line-through mb-0.5" title="Preço Médio 30 dias">R$ {formatar_real(media)}</span>
                </div>
                <div class="mt-1 flex items-center gap-1.5">
                    <span class="text-[11px] font-medium text-gray-400 bg-white/5 px-2 py-0.5 rounded">
                        Mínimo visto: R$ {formatar_real(menor)}
                    </span>
                </div>
            </div>

            <a href="{item['url']}" target="_blank" rel="nofollow noopener" 
               class="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-white/5 hover:bg-bardo-gold hover:text-bardo-dark text-sm font-bold text-gray-200 transition-all duration-300 active:scale-[0.98]">
                Comprar na Amazon
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
            </a>
        </div>
    </article>"""

def gerar_site_estatico(ofertas, historico):
    print("-> Gerando portal estático e-commerce para SEO...")
    
    produtos_schema = []
    cards_html_list = []

    for i, item in enumerate(ofertas):
        item_id = item["id"]
        preco_atual = item["preco_atual"]
        
        dados_item = historico.get(item_id, {})
        precos_30 = [v["preco"] for v in dados_item.get("valores_30_dias", [])]
        media = sum(precos_30) / len(precos_30) if precos_30 else preco_atual
        menor = dados_item.get("menor_preco_historico", preco_atual)
        
        produtos_schema.append({
            "@type": "ListItem",
            "position": i + 1,
            "item": {
                "@type": "Product",
                "name": item["titulo"],
                "url": item["url"],
                "offers": {
                    "@type": "Offer",
                    "priceCurrency": "BRL",
                    "price": preco_atual,
                    "availability": "[https://schema.org/InStock](https://schema.org/InStock)"
                }
            }
        })

        cards_html_list.append(_gerar_card_produto(item, preco_atual, media, menor))

    json_ld = json.dumps({
        "@context": "[https://schema.org](https://schema.org)",
        "@type": "ItemList",
        "name": "Promoções Ativas de Fantasia",
        "itemListElement": produtos_schema
    }, ensure_ascii=False)

    html_template = f"""<!DOCTYPE html>
<html lang="pt-BR" class="scroll-smooth bg-background">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bardo das Promoções | Curadoria de Livros</title>
    <meta name="description" content="Rastreamento matemático de preços de livros de fantasia e sci-fi na Amazon.">
    <script type="application/ld+json">{json_ld}</script>
    <link rel="preconnect" href="[https://fonts.googleapis.com](https://fonts.googleapis.com)">
    <link rel="preconnect" href="[https://fonts.gstatic.com](https://fonts.gstatic.com)" crossorigin>
    <link href="[https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,700;1,700&display=swap](https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,700;1,700&display=swap)" rel="stylesheet">
    <script src="[https://cdn.tailwindcss.com](https://cdn.tailwindcss.com)"></script>
    <script>
        tailwind.config = {{
            theme: {{ 
                extend: {{ 
                    fontFamily: {{
                        sans: ['Inter', 'sans-serif'],
                        serif: ['Playfair Display', 'serif'],
                    }},
                    colors: {{ 
                        background: '#0a0a0c',
                        surface: '#121217',
                        bardo: {{ dark: '#0a0a0c', accent: '#4A148C', gold: '#FFB300', success: '#10B981' }} 
                    }} 
                }} 
            }}
        }}
    </script>
    <style>
        .text-gradient {{ 
            background-clip: text; 
            -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent; 
            background-image: linear-gradient(90deg, #FFB300, #F59E0B); 
        }}
    </style>
</head>
<body class="antialiased min-h-screen flex flex-col relative overflow-x-hidden text-gray-300">
    <header class="container mx-auto px-6 pt-16 pb-14 text-center relative z-10">
        <h1 class="text-4xl md:text-5xl lg:text-6xl font-serif font-bold text-white mb-4 tracking-tight">
            Bardo das <span class="text-gradient">Promoções</span>
        </h1>
        <p class="max-w-2xl mx-auto text-base md:text-lg text-gray-400 mb-10 font-sans">
            Curadoria automática e rastreamento de preços de livros de Fantasia e Sci-Fi.
        </p>
        <a href="[https://t.me/bardodaspromos](https://t.me/bardodaspromos)" target="_blank" rel="noopener noreferrer" 
           class="inline-flex items-center px-8 py-3.5 font-bold text-background bg-bardo-gold hover:bg-yellow-400 hover:scale-105 rounded-xl shadow-[0_0_20px_rgba(255,179,0,0.3)] transition-all duration-300 gap-3">
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.295-.6.295-.002 0-.003 0-.005 0l.213-3.054 5.56-5.022c.24-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.832.94z"/></svg>
            Acessar Canal Gratuito
        </a>
    </header>

    <main class="container mx-auto px-4 md:px-6 py-8 flex-grow z-10 max-w-7xl">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 md:gap-8">
            {''.join(cards_html_list)}
        </div>
    </main>
    
    <footer class="mt-auto border-t border-white/5 py-8 text-center text-sm text-gray-500">
        <p>Atualizado automaticamente. Os preços podem variar na Amazon.</p>
    </footer>
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
        
        print(f"\n🔍 Consultando Amazon via Apify: {item['titulo'][:30]}...")
        preco_atual = raspar_preco_amazon(item["url"])
        
        if preco_atual:
            item["preco_atual"] = preco_atual
            print(f"   ✅ Preço obtido: R$ {preco_atual:.2f}")
        else:
            # Fallback mantido caso o Apify não retorne preço (ou esteja sem estoque)
            preco_atual = item.get("preco_atual", 0)
            if preco_atual <= 0:
                print(f"   ⏭️ Pulando: Bloqueado pela Amazon e sem preço de backup na planilha.")
                continue
            else:
                print(f"   ⚠️ Usando preço de backup da planilha: R$ {preco_atual:.2f}")

        if item_id not in historico:
            historico[item_id] = {
                "menor_preco_historico": preco_atual,
                "ultimo_preco_divulgado": None,
                "valores_30_dias": []
            }
        
        dados_item = historico[item_id]
        dados_item["valores_30_dias"].append({"data": data_hoje, "preco": preco_atual})
        dados_item["valores_30_dias"] = limpar_historico_antigo(dados_item["valores_30_dias"])
        houve_mudanca_no_historico = True
        
        precos_30_dias = [v["preco"] for v in dados_item["valores_30_dias"]]
        media_preco = sum(precos_30_dias) / len(precos_30_dias) if precos_30_dias else preco_atual
        
        menor_historico = dados_item["menor_preco_historico"]
        ultimo_divulgado = dados_item["ultimo_preco_divulgado"]
        
        condicao_1 = preco_atual < menor_historico
        condicao_2 = False
        if ultimo_divulgado is not None:
            condicao_2 = (preco_atual < media_preco) and (preco_atual < ultimo_divulgado)
        condicao_forcada = ultimo_divulgado is None

        if condicao_1 or condicao_2 or condicao_forcada:
            print(f"🔥 Aprovado para postagem: {item['titulo']} (R$ {preco_atual:.2f})")
            
            detalhe_gatilho = "🚨 MENOR PREÇO HISTÓRICO!" if condicao_1 else ("📉 ABAIXO DA MÉDIA MÓVEL!" if condicao_2 else "✨ OFERTA DO DIA!")
            
            mensagem = (
                f"{detalhe_gatilho}\n\n"
                f"📚 *{item['titulo']}*\n"
                f"💰 Por apenas: *R$ {formatar_real(preco_atual)}*\n"
                f"📊 Média de 30 dias: R$ {formatar_real(media_preco)}\n\n"
                f"🛒 Compre pelo link:\n{item['url']}"
            )
            
            caminho_grafico = os.path.join(ASSETS_DIR, f"grafico_{item_id}.png")
            caminho_banner = os.path.join(ASSETS_DIR, f"banner_{item_id}.png")
            caminho_capa = os.path.join(ASSETS_DIR, f"capa_{item_id}.jpg")
            caminho_video = os.path.join(ASSETS_DIR, f"tiktok_{item_id}.mp4")
            imagem_envio = None
            
            if item.get("imagem_url"):
                try:
                    # Também usamos a falsificação TLS aqui para burlar bloqueios de imagens da Amazon
                    res_capa = requests.get(item["imagem_url"], impersonate="chrome", timeout=10)
                    if res_capa.status_code == 200:
                        with open(caminho_capa, 'wb') as f:
                            f.write(res_capa.content)
                except Exception as e:
                    print(f"Erro ao baixar capa: {e}")
            
            try:
                valores_ordenados = sorted(dados_item["valores_30_dias"], key=lambda x: x["data"])
                datas_grafico = [v["data"] for v in valores_ordenados]
                precos_grafico = [v["preco"] for v in valores_ordenados]
                
                medias_grafico = []
                soma_acumulada = 0
                for idx, val in enumerate(precos_grafico):
                    soma_acumulada += val
                    medias_grafico.append(soma_acumulada / (idx + 1))
                
                plt.style.use('dark_background')
                fig, ax = plt.subplots(figsize=(9, 4.5))
                fig.patch.set_facecolor('#1d1d1d')
                ax.set_facecolor('#1d1d1d')
                
                ax.plot(datas_grafico, precos_grafico, color='#FFB300', marker='o', linewidth=2, label='Preço Amazon')
                ax.plot(datas_grafico, medias_grafico, color='#4A148C', linestyle='--', linewidth=2, label='Média Móvel (30d)')
                ax.set_title(f"Evolução: {item['titulo'][:35]}...", color='#FFB300', fontsize=12, pad=12)
                ax.set_ylabel("Valor (R$)", color='#ffffff')
                ax.grid(True, color='#333333', linestyle=':', alpha=0.5)
                ax.legend(facecolor='#1d1d1d', edgecolor='#4A148C')
                plt.xticks(rotation=35, ha='right')
                plt.tight_layout()
                plt.savefig(caminho_grafico, facecolor=fig.get_facecolor(), edgecolor='none', dpi=120)
                plt.close()
                
                imagem_envio = caminho_grafico
                
                if os.path.exists(caminho_capa):
                    try:
                        capa_livro = Image.open(caminho_capa)
                        grafico_img = Image.open(caminho_grafico)
                        
                        altura_alvo = grafico_img.height
                        largura_nova_capa = int(altura_alvo * (capa_livro.width / capa_livro.height))
                        
                        capa_livro = capa_livro.resize((largura_nova_capa, altura_alvo), Image.Resampling.LANCZOS)
                        banner = Image.new('RGB', (largura_nova_capa + grafico_img.width, altura_alvo), color='#1d1d1d')
                        banner.paste(capa_livro, (0, 0))
                        banner.paste(grafico_img, (largura_nova_capa, 0))
                        banner.save(caminho_banner)
                        imagem_envio = caminho_banner
                    except Exception as e_img:
                        print(f"Erro na montagem do banner: {e_img}")

            except Exception as ge:
                print(f"Erro ao gerar gráfico: {ge}")
                plt.close()
            
            conteudo_ia = gerar_legenda_ia(item['titulo'], preco_atual, media_preco)
            gancho_video = conteudo_ia["gancho"]
            legenda_tiktok = conteudo_ia["legenda"]

            try:
                gerar_video_tiktok(
                    item, 
                    media_preco, 
                    caminho_capa if os.path.exists(caminho_capa) else None, 
                    caminho_grafico, 
                    caminho_video,
                    gancho_ia=gancho_video
                )
            except Exception as ve:
                print(f"Erro ao gerar vídeo TikTok: {ve}")
                caminho_video = None

            try:
                await enviar_mensagem_telegram(mensagem, caminho_foto=imagem_envio)
                
                if caminho_video and os.path.exists(caminho_video):
                    await enviar_video_telegram(legenda_tiktok, caminho_video)
                    os.remove(caminho_video)
                    
                if os.path.exists(caminho_capa): os.remove(caminho_capa)
                if imagem_envio == caminho_banner and os.path.exists(caminho_grafico):
                    os.remove(caminho_grafico)
                    
                dados_item["ultimo_preco_divulgado"] = preco_atual
            except Exception as e:
                print(f"Erro ao enviar postagem: {e}")
        else:
            print(f"❌ Retido: {item['titulo']} (R$ {formatar_real(preco_atual)} | Recorde: R$ {formatar_real(menor_historico)})")

        if preco_atual < menor_historico:
            historico[item_id]["menor_preco_historico"] = preco_atual

    gerar_site_estatico(ofertas, historico)
    if houve_mudanca_no_historico:
        salvar_json(HISTORICO_FILE, historico)

if __name__ == "__main__":
    asyncio.run(processar_ofertas())
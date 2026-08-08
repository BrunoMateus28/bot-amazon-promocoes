import os
import re
import csv
import json
import asyncio
import requests
import numpy as np
import textwrap
from datetime import datetime, timedelta
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
            res = requests.get(url, timeout=15)
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

    gancho_tela = remover_emojis(gancho_ia) if gancho_ia else "Voce ja leu essa historia?"

    frames = []

    # Ajuste dinâmico se houver capa
    pos_y_card = 840 if capa else 600
    altura_card = 380 if capa else 500

    for f_idx in range(total_frames):
        t = f_idx / fps
        
        # CENA 1: O GANCHO MATADOR (0.0s a 1.5s)
        if t < 1.5:
            img = fundo_escuro.copy()
            draw = ImageDraw.Draw(img)
            
            linhas_gancho = textwrap.wrap(gancho_tela, width=25)
            y_g = 850
            for lg in linhas_gancho[:3]:
                draw.text((540, y_g), lg.upper(), font=fonte_gancho, fill=(255, 179, 0, 255), anchor="mm")
                y_g += 70

        # CENA 2: A PROVOCAÇÃO / REVELAÇÃO (1.5s a 3.0s)
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

        # CENA 3: O GRÁFICO / PROVA MATEMÁTICA (3.0s a 4.8s)
        elif 3.0 <= t < 4.8:
            img = fundo_alerta.copy()
            draw = ImageDraw.Draw(img)
            
            draw.text((540, 200), "HISTÓRICO DE PREÇOS", font=fonte_h, fill=(255, 179, 0, 255), anchor="mm")
            linhas_titulo = textwrap.wrap(item["titulo"], width=35)
            draw.text((540, 270), linhas_titulo[0], font=fonte_m, fill=(220, 220, 230, 255), anchor="mm")
            
            if grafico:
                img.paste(grafico, ((largura - grafico.width)//2, 450), grafico)

        # CENA 4: CTA FINAL DE RETENÇÃO (4.8s a 6.0s)
        else:
            img = fundo_escuro.copy()
            draw = ImageDraw.Draw(img)
            
            draw.text((540, 800), "O LINK COPIÁVEL ESTÁ", font=fonte_gancho, fill=(255, 255, 255, 255), anchor="mm")
            draw.text((540, 900), "NO CANAL DA BIO!", font=fonte_gancho, fill=(255, 179, 0, 255), anchor="mm")
            
            draw.rounded_rectangle([150, 1350, 930, 1450], radius=40, fill=(255, 179, 0, 255))
            draw.text((540, 1400), "CORRA PARA APROVEITAR", font=fonte_c, fill=(15, 15, 20, 255), anchor="mm")

        # Top Header fixo apenas nas Cenas do meio para limpar o visual
        if 1.5 <= t < 4.8:
            draw.rounded_rectangle([140, 50, 940, 130], radius=25, fill=(74, 20, 140, 220), outline=(255, 179, 0, 255), width=3)
            draw.text((540, 90), "BARDO DAS PROMOÇÕES", font=fonte_h, fill=(255, 255, 255, 255), anchor="mm")

        # Barra de progresso do vídeo rodando no topo
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
        response = requests.get(url_csv, timeout=15)
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
            preco_raw = linha_limpa.get("preco_atual", "0")
            preco_str = preco_raw.replace("R$", "").replace(" ", "").replace(",", ".").strip()
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

def gerar_site_estatico(ofertas, historico):
    print("-> Gerando portal estático para SEO...")
    produtos_schema = []
    for item in ofertas:
        produtos_schema.append({
            "@type": "Product",
            "name": item["titulo"],
            "url": item["url"],
            "offers": {
                "@type": "Offer",
                "priceCurrency": "BRL",
                "price": item["preco_atual"],
                "availability": "[https://schema.org/InStock](https://schema.org/InStock)"
            }
        })
    json_ld = json.dumps({
        "@context": "[https://schema.org](https://schema.org)",
        "@type": "ItemList",
        "name": "Promoções Ativas de Fantasia",
        "itemListElement": [{"@type": "ListItem", "position": i+1, "item": p} for i, p in enumerate(produtos_schema)]
    }, ensure_ascii=False)

    html_template = f"""<!DOCTYPE html>
<html lang="pt-BR" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bardo das Promoções | Curadoria de Livros</title>
    <meta name="description" content="Rastreamento matemático de preços de livros de fantasia e sci-fi na Amazon.">
    <script type="application/ld+json">{json_ld}</script>
    <link href="[https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Playfair+Display:ital,wght@0,700;1,700&display=swap](https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Playfair+Display:ital,wght@0,700;1,700&display=swap)" rel="stylesheet">
    <script src="[https://cdn.tailwindcss.com](https://cdn.tailwindcss.com)"></script>
    <script>
        tailwind.config = {{
            theme: {{ extend: {{ colors: {{ bardo: {{ dark: '#0f0f13', card: '#1a1a20', accent: '#4A148C', gold: '#FFB300', success: '#10B981' }} }} }} }}
        }}
    </script>
    <style>
        body {{ background-color: #0f0f13; color: #e2e8f0; font-family: 'Inter', sans-serif; }}
        h1, h2, h3 {{ font-family: 'Playfair Display', serif; }}
        .glass-card {{ background: rgba(26, 26, 32, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(74, 20, 140, 0.3); transition: all 0.3s; }}
        .glass-card:hover {{ transform: translateY(-8px); border-color: rgba(255, 179, 0, 0.6); box-shadow: 0 10px 30px -10px rgba(74, 20, 140, 0.5); }}
        .text-gradient {{ background-clip: text; -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-image: linear-gradient(90deg, #FFB300, #F59E0B); }}
    </style>
</head>
<body class="antialiased min-h-screen flex flex-col relative overflow-x-hidden">
    <header class="container mx-auto px-6 pt-16 pb-12 text-center relative z-10">
        <h1 class="text-5xl md:text-6xl font-bold text-white mb-6">Bardo das <span class="text-gradient">Promoções</span></h1>
        <p class="max-w-2xl mx-auto text-lg text-gray-400 mb-10">Rastreamento matemático de preços de livros de Fantasia e Sci-Fi.</p>
        <a href="[https://t.me/bardodaspromos](https://t.me/bardodaspromos)" target="_blank" class="inline-flex items-center px-8 py-4 font-bold text-bardo-dark bg-bardo-gold hover:bg-yellow-400 rounded-lg shadow-lg gap-3">
            Entrar no Canal do Telegram
        </a>
    </header>
    <main class="container mx-auto px-6 py-8 flex-grow z-10">
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">"""

    for item in ofertas:
        item_id = item["id"]
        titulo = item["titulo"]
        preco_atual = item["preco_atual"]
        
        dados_item = historico.get(item_id, {})
        precos_30 = [v["preco"] for v in dados_item.get("valores_30_dias", [])]
        media = sum(precos_30) / len(precos_30) if precos_30 else preco_atual
        menor = dados_item.get("menor_preco_historico", preco_atual)
        
        status_badge = ""
        if preco_atual < menor:
            status_badge = '<span class="px-2 py-1 text-xs font-bold text-red-100 bg-red-900/60 border border-red-700 rounded absolute top-3 right-3 rotate-3 shadow-sm z-20">Recorde!</span>'
        elif preco_atual < media:
            status_badge = '<span class="px-2 py-1 text-xs font-bold text-green-100 bg-green-900/60 border border-green-700 rounded absolute top-3 right-3 shadow-sm z-20">Abaixo da Média</span>'

        path_banner_local = os.path.join(ASSETS_DIR, f"banner_{item_id}.png")
        if os.path.exists(path_banner_local):
            src_imagem = f"assets/banner_{item_id}.png"
        else:
            src_imagem = item.get("imagem_url") if item.get("imagem_url") else "bau.png"

        card_html = f"""
            <article class="glass-card rounded-xl overflow-hidden relative flex flex-col h-full group">
                {status_badge}
                <div class="w-full h-48 bg-black/40 flex items-center justify-center overflow-hidden border-b border-gray-800">
                    <img src="{src_imagem}" alt="{titulo}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300">
                </div>
                <div class="p-6 flex-grow flex flex-col justify-between">
                    <div>
                        <h3 class="text-lg font-bold text-gray-100 leading-snug mb-5">{titulo[:47]}...</h3>
                        <div class="space-y-3 mb-6">
                            <div class="flex justify-between border-b border-gray-700/50 pb-3">
                                <span class="text-sm text-gray-400">Preço Agora</span>
                                <span class="text-xl font-bold text-bardo-success">R$ {formatar_real(preco_atual)}</span>
                            </div>
                            <div class="flex justify-between text-sm">
                                <span class="text-gray-500">Média (30 dias)</span><span class="text-gray-300">R$ {formatar_real(media)}</span>
                            </div>
                            <div class="flex justify-between text-sm">
                                <span class="text-gray-500">Menor Histórico</span><span class="text-gray-300">R$ {formatar_real(menor)}</span>
                            </div>
                        </div>
                    </div>
                    <a href="{item['url']}" target="_blank" rel="nofollow" class="w-full block text-center py-3 bg-gray-800 hover:bg-bardo-accent text-white font-medium rounded-lg transition-colors border border-gray-700">Ver na Loja &rarr;</a>
                </div>
            </article>"""
        html_template += card_html

    html_template += """
        </div>
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
        preco_atual = item["preco_atual"]
        
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
            
            # --- 1. BAIXA A CAPA SE EXISTIR ---
            if item.get("imagem_url"):
                try:
                    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
                    res_capa = requests.get(item["imagem_url"], headers=headers, timeout=10)
                    if res_capa.status_code == 200:
                        with open(caminho_capa, 'wb') as f:
                            f.write(res_capa.content)
                except Exception as e:
                    print(f"Erro ao baixar capa: {e}")
            
            # --- 2. GERA O GRÁFICO ---
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
                
                # --- 3. MONTA BANNER SE HOUVER CAPA BAIXADA ---
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
            
            # --- 4. GERA CONTEÚDO VIA IA (GANCHO + LEGENDA) ---
            conteudo_ia = gerar_legenda_ia(item['titulo'], preco_atual, media_preco)
            gancho_video = conteudo_ia["gancho"]
            legenda_tiktok = conteudo_ia["legenda"]

            # --- 5. GERA O VÍDEO DO TIKTOK COM O GANCHO DA IA ---
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

            # --- 6. ENVIA DADOS PARA O TELEGRAM ---
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
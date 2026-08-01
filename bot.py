import os
import csv
import json
import asyncio
import requests
import numpy as np
import textwrap # <--- NOVO: Biblioteca para quebrar os textos
from datetime import datetime, timedelta
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

# ==========================================================
# DESIGNER DE VÍDEO (TIKTOK V3 PREMIUM)
# ==========================================================
def obter_fonte(tamanho):
    """Baixa a fonte profissional Montserrat para o vídeo."""
    caminho_fonte = os.path.join(ASSETS_DIR, "Montserrat-Bold.ttf")
    if not os.path.exists(caminho_fonte):
        url = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf"
        try:
            print("⬇️ Baixando fonte premium...")
            res = requests.get(url, timeout=15)
            res.raise_for_status()
            with open(caminho_fonte, 'wb') as f:
                f.write(res.content)
            print("✅ Fonte baixada com sucesso.")
        except Exception as e:
            print(f"⚠️ Erro ao baixar fonte: {e}. Usando padrão.")
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

def gerar_video_tiktok(item, media_preco, caminho_capa, caminho_grafico, caminho_saida_video):
    """Renderiza o vídeo vertical 9:16 com animações responsivas."""
    print(f"🎬 Criando vídeo premium responsivo: {item['titulo'][:30]}...")
    largura, altura = 1080, 1920
    fps, duracao = 24, 6
    total_frames = fps * duracao

    fonte_h = obter_fonte(45)
    fonte_t = obter_fonte(55) # Diminuí um pouco para caber melhor
    fonte_p = obter_fonte(140)
    fonte_m = obter_fonte(40)
    fonte_c = obter_fonte(35)

    capa = Image.open(caminho_capa).convert("RGBA") if caminho_capa and os.path.exists(caminho_capa) else None
    grafico = Image.open(caminho_grafico).convert("RGBA") if caminho_grafico and os.path.exists(caminho_grafico) else None

    if capa:
        nova_alt = 550
        capa = capa.resize((int(nova_alt * (capa.width/capa.height)), nova_alt), Image.Resampling.LANCZOS)
    if grafico:
        nova_larg = 960
        grafico = grafico.resize((nova_larg, int(nova_larg / (grafico.width/grafico.height))), Image.Resampling.LANCZOS)

    fundo_base = criar_gradiente_vertical(largura, altura, (20, 15, 40, 255), (10, 5, 20, 255))
    frames = []

    # Se não houver capa, ele sobe todo o layout para não deixar buraco
    offset_sem_capa = -300 if not capa else 0

    for f_idx in range(total_frames):
        t = f_idx / fps
        img = fundo_base.copy()
        draw = ImageDraw.Draw(img)

        # Barra progresso
        draw.rectangle([0, 0, int((f_idx/total_frames)*largura), 15], fill=(255, 179, 0, 255))
        
        # Header (Sem Emojis para evitar os quadrados)
        draw.rounded_rectangle([140, 70, 940, 160], radius=25, fill=(74, 20, 140, 220), outline=(255, 179, 0, 255), width=3)
        draw.text((540, 115), "BARDO DAS PROMOÇÕES", font=fonte_h, fill=(255, 255, 255, 255), anchor="mm")

        # Animação Capa
        if capa:
            y_capa = 220 + int((1.0 - (min(1.0, t/0.5))) * 100)
            img.paste(capa, ((largura - capa.width)//2, y_capa), capa)

        # Card Preço
        if t >= 0.6:
            pulse = 1.0 + 0.05 * np.sin(t * 10)
            top_card = 840 + offset_sem_capa
            draw.rounded_rectangle([70, top_card, 1010, top_card + 380], radius=30, fill=(25, 25, 35, 240), outline=(255, 179, 0, 255), width=4)
            
            # Badge
            draw.text((540, top_card + 40), "DESCONTO DETECTADO!", font=fonte_h, fill=(255, 179, 0, 255), anchor="mm")

            # Quebra automática de texto para não vazar a tela
            linhas_titulo = textwrap.wrap(item["titulo"], width=30)
            y_titulo = top_card + 110
            for linha in linhas_titulo[:2]: # Pega no máximo 2 linhas para não amassar o preço
                draw.text((540, y_titulo), linha, font=fonte_t, fill=(220, 220, 230, 255), anchor="mm")
                y_titulo += 65

            draw.text((540, top_card + 260), f"R$ {formatar_real(item['preco_atual'])}", font=fonte_p, fill=(16, 185, 129, 255), anchor="mm")
            draw.text((540, top_card + 340), f"Média 30 dias: R$ {formatar_real(media_preco)}", font=fonte_m, fill=(160, 160, 180, 255), anchor="mm")

        # Gráfico
        if grafico and t >= 1.5:
            img.paste(grafico, ((largura - grafico.width)//2, 1270 + (offset_sem_capa // 2)), grafico)

        # CTA (Sem Emojis)
        if t >= 2.0:
            draw.rounded_rectangle([150, 1780, 930, 1860], radius=40, fill=(255, 179, 0, 255))
            draw.text((540, 1820), "LINK DE COMPRA NO CANAL! (LINK NA BIO)", font=fonte_c, fill=(15, 15, 20, 255), anchor="mm")

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
    url_base = "https://brunomateus28.github.io/bot-amazon-promocoes/"
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
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
                "availability": "https://schema.org/InStock"
            }
        })
    json_ld = json.dumps({
        "@context": "https://schema.org",
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
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Playfair+Display:ital,wght@0,700;1,700&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
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
        <a href="https://t.me/bardodaspromos" target="_blank" class="inline-flex items-center px-8 py-4 font-bold text-bardo-dark bg-bardo-gold hover:bg-yellow-400 rounded-lg shadow-lg gap-3">
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
            
            # --- 4. GERA O VÍDEO DO TIKTOK (.MP4) ---
            try:
                gerar_video_tiktok(item, media_preco, caminho_capa if os.path.exists(caminho_capa) else None, caminho_grafico, caminho_video)
            except Exception as ve:
                print(f"Erro ao gerar vídeo TikTok: {ve}")
                caminho_video = None

            # --- 5. ENVIA DADOS PARA O TELEGRAM ---
            try:
                # Envia mensagem normal com Foto/Banner
                await enviar_mensagem_telegram(mensagem, caminho_foto=imagem_envio)
                
                # Envia o arquivo .MP4 do TikTok
                if caminho_video and os.path.exists(caminho_video):
                    legenda_tiktok = (
                        f"🔥 *QUEDA DE PREÇO!* {item['titulo']}\n\n"
                        f"💰 *Preço Atual:* R$ {formatar_real(preco_atual)}\n"
                        f"📊 *Média de 30 dias:* R$ {formatar_real(media_preco)}\n"
                        f"🚨 {detalhe_gatilho}\n\n"
                        f"🔗 *Link de compra com desconto no nosso canal do Telegram (link na bio)!*\n\n"
                        f"#booktokbrasil #booktok #livros #promocaodelivros #livrosdefantasia #lendo #leitores"
                    )
                    await enviar_video_telegram(legenda_tiktok, caminho_video)
                    os.remove(caminho_video)
                    
                # Limpeza final dos assets intermediários
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
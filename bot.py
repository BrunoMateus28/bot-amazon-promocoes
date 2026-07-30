import os
import csv
import json
import asyncio
import requests
from datetime import datetime, timedelta
from src.telegram import enviar_mensagem_telegram

# Configura o matplotlib para rodar em modo 'headless' (sem interface gráfica/servidor X)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ==========================================================
# CONFIGURAÇÕES E UTILITÁRIOS
# ==========================================================
HISTORICO_FILE = "historico_precos.json"

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

# ==========================================================
# INTEGRAÇÃO COM GOOGLE SHEETS VIA CSV PÚBLICO
# ==========================================================
def buscar_ofertas_csv():
    """Baixa o CSV público do Google Sheets e retorna a lista de ofertas."""
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
            print("-> AVISO: O CSV baixado está vazio.")
            return []

        primeira_linha = linhas_csv[0]
        delimitador = ';' if ';' in primeira_linha else ','

        leitor = csv.DictReader(linhas_csv, delimiter=delimitador)

        ofertas = []
        for linha in leitor:
            linha_limpa = {k.strip(): v.strip() for k, v in linha.items() if k}

            id_item = linha_limpa.get("id", "")
            titulo = linha_limpa.get("titulo", "")
            preco_raw = linha_limpa.get("preco_atual", "0")
            preco_str = preco_raw.replace("R$", "").replace(" ", "").replace(",", ".").strip()
            url = linha_limpa.get("url", "")

            if id_item and titulo and url:
                try:
                    preco_atual = float(preco_str)
                    ofertas.append({
                        "id": id_item,
                        "titulo": titulo,
                        "preco_atual": preco_atual,
                        "url": url
                    })
                except ValueError:
                    print(f"-> AVISO: Preço inválido no item '{id_item}' ({preco_raw}). Pulando...")

        print(f"-> Sincronização concluída! {len(ofertas)} produtos carregados do Sheets.")
        return ofertas

    except Exception as e:
        print(f"-> Erro ao sincronizar produtos do CSV: {e}")
        return []

# ==========================================================
# GERADOR DO PORTAL WEB ESTÁTICO (SEO GOOGLE)
# ==========================================================
def gerar_site_estatico(ofertas, historico):
    """Gera um arquivo HTML moderno e responsivo com a listagem atual de promoções."""
    print("-> Gerando portal estático index.html para SEO do Google...")
    
    html_template = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bardo das Promoções - Livros de Fantasia & Geek</title>
    <style>
        body { background-color: #1d1d1d; color: #ffffff; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        h1 { color: #FFB300; text-shadow: 2px 2px #4A148C; margin-bottom: 5px; }
        p.subtitle { color: #aaaaaa; margin-bottom: 30px; font-size: 1.1em; text-align: center; }
        .container { width: 100%; max-width: 1000px; display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .card { background-color: #2b2b2b; border: 1px solid #4A148C; border-radius: 8px; padding: 20px; display: flex; flex-direction: column; justify-content: space-between; transition: transform 0.2s; box-shadow: 0 4px 8px rgba(0,0,0,0.3); }
        .card:hover { transform: translateY(-5px); border-color: #FFB300; }
        .title { color: #FFB300; font-size: 1.15em; font-weight: bold; margin-bottom: 10px; min-height: 45px; }
        .price-info { margin: 15px 0; font-size: 0.95em; color: #dddddd; line-height: 1.6; }
        .current-price { font-size: 1.3em; color: #00FF41; font-weight: bold; }
        .btn-buy { display: block; background-color: #4A148C; color: #ffffff; text-align: center; padding: 12px; text-decoration: none; border-radius: 5px; font-weight: bold; transition: background 0.2s; margin-top: 10px; }
        .btn-buy:hover { background-color: #FFB300; color: #1d1d1d; }
        footer { margin-top: 50px; color: #777777; font-size: 0.85em; text-align: center; border-top: 1px solid #333; padding-top: 20px; width: 100%; max-width: 1000px; }
        a { color: #FFB300; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>🧙‍♂️ Bardo das Promoções</h1>
    <p class="subtitle">Desmascarando a "metade do dobro". Rastreamento matemático de livros de fantasia.</p>
    <div class="container">"""

    for item in ofertas:
        item_id = item["id"]
        titulo = item["titulo"]
        preco_atual = item["preco_atual"]
        url = item["url"]
        
        dados_item = historico.get(item_id, {})
        precos_30 = [v["preco"] for v in dados_item.get("valores_30_dias", [])]
        media = sum(precos_30) / len(precos_30) if precos_30 else preco_atual
        menor = dados_item.get("menor_preco_historico", preco_atual)
        
        card_html = f"""
        <div class="card">
            <div>
                <div class="title">{titulo}</div>
                <div class="price-info">
                    Preço Atual: <span class="current-price">R$ {preco_atual:.2f}</span><br>
                    Média de 30 dias: R$ {media:.2f}<br>
                    Menor Histórico: R$ {menor:.2f}
                </div>
            </div>
            <a href="{url}" target="_blank" class="btn-buy">🛒 Garantir Loot</a>
        </div>"""
        html_template += card_html

    html_template += f"""
    </div>
    <footer>
        <p>Atualizado automaticamente via GitHub Actions em: {datetime.now().strftime('%d/%m/%Y %H:%M')} (Horário de Brasília)</p>
        <p>Participe do nosso canal principal no Telegram: <a href="https://t.me/bardodaspromos" target="_blank">@bardodaspromos</a></p>
    </footer>
</body>
</html>"""
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_template)
    print("✅ index.html gerado com sucesso!")

# ==========================================================
# LÓGICA PRINCIPAL DO BOT
# ==========================================================
async def processar_ofertas():
    postar = True  
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

        if (condicao_1 or condicao_2 or condicao_forcada) and postar:
            print(f"🔥 Aprovado para postagem: {item['titulo']} (R$ {preco_atual:.2f})")
            
            if condicao_1:
                detalhe_gatilho = "🚨 MENOR PREÇO HISTÓRICO!"
            elif condicao_2:
                detalhe_gatilho = "📉 ABAIXO DA MÉDIA MÓVEL!"
            else:
                detalhe_gatilho = "✨ OFERTA DO DIA!"
            
            mensagem = (
                f"{detalhe_gatilho}\n\n"
                f"📚 *{item['titulo']}*\n"
                f"💰 Por apenas: *R$ {preco_atual:.2f}*\n"
                f"📊 Média de 30 dias: R$ {media_preco:.2f}\n\n"
                f"🛒 Compre pelo link:\n{item['url']}"
            )
            
            # --- GERAÇÃO DO GRÁFICO DE ANÁLISE ---
            caminho_grafico = f"grafico_{item_id}.png"
            try:
                valores_ordenados = sorted(dados_item["valores_30_dias"], key=lambda x: x["data"])
                datas_grafico = [v["data"] for v in valores_ordenados]
                precos_grafico = [v["preco"] for v in valores_ordenados]
                
                # Monta a evolução das médias para desenhar no gráfico
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
                
                ax.set_title(f"Evolução de Preço: {item['titulo'][:35]}...", color='#FFB300', fontsize=12, pad=12)
                ax.set_ylabel("Valor (R$)", color='#ffffff')
                ax.grid(True, color='#333333', linestyle=':', alpha=0.5)
                ax.legend(facecolor='#1d1d1d', edgecolor='#4A148C')
                plt.xticks(rotation=35, ha='right')
                plt.tight_layout()
                plt.savefig(caminho_grafico, facecolor=fig.get_facecolor(), edgecolor='none', dpi=120)
                plt.close()
            except Exception as ge:
                print(f"Erro ao gerar gráfico para {item_id}: {ge}")
                caminho_grafico = None
            
            try:
                # Envia o gráfico gerado com a mensagem estruturada na legenda
                await enviar_mensagem_telegram(mensagem, caminho_foto=caminho_grafico)
                
                # Limpa a imagem temporária para não poluir o repositório
                if caminho_grafico and os.path.exists(caminho_grafico):
                    os.remove(caminho_grafico)
                    
                dados_item["ultimo_preco_divulgado"] = preco_atual
                if preco_atual < menor_historico:
                    dados_item["menor_preco_historico"] = preco_atual
                postar = False
            except Exception as e:
                print(f"Erro ao enviar postagem: {e}")
        else:
            print(f"❌ Retido pelas regras de preço: {item['titulo']} (Atual: R$ {preco_atual:.2f} | Recorde: R$ {menor_historico:.2f})")

        if preco_atual < menor_historico:
            dados_item["menor_preco_historico"] = preco_atual

    # Reconstrói e atualiza o portal de ofertas index.html
    gerar_site_estatico(ofertas, historico)

    if houve_mudanca_no_historico:
        salvar_json(HISTORICO_FILE, historico)

if __name__ == "__main__":
    asyncio.run(processar_ofertas())
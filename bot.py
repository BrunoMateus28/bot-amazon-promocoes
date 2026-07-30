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
# GERADOR DO PORTAL WEB ESTÁTICO
# ==========================================================
def gerar_site_estatico(ofertas, historico):
    """Gera um arquivo HTML moderno e responsivo com a listagem atual de promoções."""
    print("-> Gerando portal estático index.html de alto padrão para SEO do Google...")
    
    html_template = """<!DOCTYPE html>
<html lang="pt-BR" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bardo das Promoções | Curadoria de Livros de Fantasia</title>
    <meta name="description" content="Rastreamento matemático de preços de livros de fantasia na Amazon. Fugimos da 'metade do dobro' usando dados reais e média de 30 dias.">
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Playfair+Display:ital,wght@0,700;1,700&display=swap" rel="stylesheet">
    
    <script src="https://cdn.tailwindcss.com"></script>
    
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['Inter', 'sans-serif'],
                        serif: ['Playfair Display', 'serif'],
                    },
                    colors: {
                        bardo: {
                            dark: '#0f0f13',
                            card: '#1a1a20',
                            accent: '#4A148C', // Roxo Baú
                            gold: '#FFB300',   // Ouro Baú
                            light: '#e2e8f0',
                            success: '#10B981'
                        }
                    }
                }
            }
        }
    </script>
    
    <style>
        /* Custom CSS para microinterações e Glassmorphism */
        body { background-color: #0f0f13; }
        .glass-card {
            background: rgba(26, 26, 32, 0.7);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(74, 20, 140, 0.3);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .glass-card:hover {
            transform: translateY(-8px);
            border-color: rgba(255, 179, 0, 0.6);
            box-shadow: 0 10px 30px -10px rgba(74, 20, 140, 0.5);
        }
        .text-gradient {
            background-clip: text;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-image: linear-gradient(90deg, #FFB300, #F59E0B);
        }
    </style>
</head>
<body class="text-bardo-light antialiased min-h-screen flex flex-col relative overflow-x-hidden">

    <div class="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-3xl h-64 bg-bardo-accent opacity-20 blur-[100px] -z-10 rounded-full pointer-events-none"></div>

    <header class="container mx-auto px-6 pt-16 pb-12 text-center relative z-10">
        <div class="inline-block mb-4 px-4 py-1.5 rounded-full bg-bardo-accent/20 border border-bardo-accent/30 text-bardo-gold text-sm font-semibold tracking-wide uppercase">
            Curadoria Automatizada 🤖
        </div>
        <h1 class="text-5xl md:text-6xl font-serif font-bold text-white mb-6 leading-tight">
            Bardo das <span class="text-gradient">Promoções</span>
        </h1>
        <p class="max-w-2xl mx-auto text-lg md:text-xl text-gray-400 mb-10 leading-relaxed">
            Nós mapeamos as masmorras da Amazon com precisão matemática. Fugimos da "metade do dobro" cruzando o preço atual com a <strong>média histórica de 30 dias</strong> de livros de Fantasia e Sci-Fi.
        </p>
        <a href="https://t.me/bardodaspromos" target="_blank" class="inline-flex items-center justify-center px-8 py-4 text-base font-bold text-bardo-dark bg-bardo-gold hover:bg-yellow-400 rounded-lg shadow-lg hover:shadow-yellow-500/30 transition-all duration-200 gap-3">
            <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.19-.08-.05-.19-.02-.27 0-.11.03-1.83 1.16-5.17 3.42-.49.33-.93.49-1.32.48-.43-.01-1.26-.24-1.87-.44-.75-.24-1.34-.37-1.29-.79.03-.22.33-.44.92-.68 3.58-1.56 5.96-2.58 7.15-3.08 3.4-1.42 4.1-1.66 4.56-1.67.1 0 .32.02.43.14.09.1.11.23.11.33 0 .04-.01.12-.02.21z"/></svg>
            Entrar no Canal do Telegram
        </a>
    </header>

    <main class="container mx-auto px-6 py-8 flex-grow z-10">
        <div class="flex items-center justify-between mb-8">
            <h2 class="text-2xl font-bold text-white flex items-center gap-2">
                <span class="w-2 h-6 bg-bardo-gold rounded-full"></span>
                Loot Rastreado Atualmente
            </h2>
            <span class="text-sm text-gray-500">Atualizado via GitHub Actions</span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">"""

    for item in ofertas:
        item_id = item["id"]
        titulo = item["titulo"]
        preco_atual = item["preco_atual"]
        url = item["url"]
        
        dados_item = historico.get(item_id, {})
        precos_30 = [v["preco"] for v in dados_item.get("valores_30_dias", [])]
        media = sum(precos_30) / len(precos_30) if precos_30 else preco_atual
        menor = dados_item.get("menor_preco_historico", preco_atual)
        
        # Lógica visual para indicar se o desconto é bom
        status_badge = ""
        if preco_atual < menor:
            status_badge = '<span class="px-2 py-1 text-xs font-bold text-red-100 bg-red-900/60 border border-red-700 rounded absolute -top-3 -right-3 rotate-3 shadow-sm">Recorde!</span>'
        elif preco_atual < media:
            status_badge = '<span class="px-2 py-1 text-xs font-bold text-green-100 bg-green-900/60 border border-green-700 rounded absolute -top-3 -right-3 shadow-sm">Queda de Preço</span>'

        card_html = f"""
            <article class="glass-card rounded-xl p-6 relative flex flex-col h-full group">
                {status_badge}
                <div class="flex-grow">
                    <h3 class="text-lg font-bold text-gray-100 leading-snug mb-5 group-hover:text-bardo-gold transition-colors">{titulo}</h3>
                    
                    <div class="space-y-3 mb-6">
                        <div class="flex justify-between items-end border-b border-gray-700/50 pb-3">
                            <span class="text-sm text-gray-400">Preço Agora</span>
                            <span class="text-2xl font-bold text-bardo-success">R$ {preco_atual:.2f}</span>
                        </div>
                        <div class="flex justify-between items-center text-sm">
                            <span class="text-gray-500">Média (30 dias)</span>
                            <span class="font-medium text-gray-300">R$ {media:.2f}</span>
                        </div>
                        <div class="flex justify-between items-center text-sm">
                            <span class="text-gray-500">Menor Histórico</span>
                            <span class="font-medium text-gray-300">R$ {menor:.2f}</span>
                        </div>
                    </div>
                </div>
                
                <a href="{url}" target="_blank" rel="noopener noreferrer" class="w-full block text-center py-3 px-4 bg-gray-800 hover:bg-bardo-accent text-white font-medium rounded-lg transition-colors border border-gray-700 hover:border-bardo-accent">
                    Ver na Loja &rarr;
                </a>
            </article>"""
        html_template += card_html

    html_template += f"""
        </div>
    </main>

    <footer class="mt-20 border-t border-gray-800/60 bg-black/20 relative z-10">
        <div class="container mx-auto px-6 py-8 flex flex-col md:flex-row justify-between items-center gap-4">
            <div class="text-sm text-gray-500">
                &copy; {datetime.now().year} Bardo das Promoções. Nenhum dado de usuário é coletado.
            </div>
            <div class="text-xs text-gray-600 bg-gray-900/50 px-3 py-1.5 rounded-md border border-gray-800">
                Última sincronização: {datetime.now().strftime('%d/%m/%Y %H:%M')} (BRT)
            </div>
        </div>
    </footer>
</body>
</html>"""
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_template)
    print("✅ index.html (UI Alto Padrão) gerado com sucesso!")


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
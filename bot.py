import os
import csv
import json
import asyncio
import requests
from datetime import datetime, timedelta
from src.telegram import enviar_mensagem_telegram
# from src.twitter import postar_no_twitter

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
        response.encoding = 'utf-8'  # Garante leitura correta de acentos
        response.raise_for_status()

        linhas_csv = [linha for linha in response.text.splitlines() if linha.strip()]
        
        if not linhas_csv:
            print("-> AVISO: O CSV baixado está vazio.")
            return []

        # Deteta se o separador do Google Sheets é ponto e vírgula (;) ou vírgula (,)
        primeira_linha = linhas_csv[0]
        delimitador = ';' if ';' in primeira_linha else ','

        leitor = csv.DictReader(linhas_csv, delimiter=delimitador)

        ofertas = []
        for linha in leitor:
            # Remove espaços extras das chaves e valores
            linha_limpa = {k.strip(): v.strip() for k, v in linha.items() if k}

            id_item = linha_limpa.get("id", "")
            titulo = linha_limpa.get("titulo", "")
            
            # Limpa o preço (remove 'R$', substitui vírgula por ponto)
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
# LÓGICA PRINCIPAL DO BOT
# ==========================================================
async def processar_ofertas():
    postar = True  # Variável para controlar se deve postar no Twitter/Telegram
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
        
        # Inicializa o item no histórico se for novo
        if item_id not in historico:
            historico[item_id] = {
                "menor_preco_historico": preco_atual,
                "ultimo_preco_divulgado": None,
                "valores_30_dias": []
            }
        
        dados_item = historico[item_id]
        
        # Registra a data/preço e limpa entradas com mais de 30 dias
        dados_item["valores_30_dias"].append({"data": data_hoje, "preco": preco_atual})
        dados_item["valores_30_dias"] = limpar_historico_antigo(dados_item["valores_30_dias"])
        houve_mudanca_no_historico = True
        
        precos_30_dias = [v["preco"] for v in dados_item["valores_30_dias"]]
        media_preco = sum(precos_30_dias) / len(precos_30_dias) if precos_30_dias else preco_atual
        
        menor_historico = dados_item["menor_preco_historico"]
        ultimo_divulgado = dados_item["ultimo_preco_divulgado"]
        
        # Regras de avaliação de preço
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
                detalhe_gatilho = "📉 ABAIXO DA MÉDIA!"
            else:
                detalhe_gatilho = "✨ OFERTA DO DIA!"
            
            mensagem = (
                f"{detalhe_gatilho}\n\n"
                f"📚 *{item['titulo']}*\n"
                f"💰 Por apenas: *R$ {preco_atual:.2f}*\n"
                f"📊 Média de 30 dias: R$ {media_preco:.2f}\n\n"
                f"🛒 Compre pelo link:\n{item['url']}"
            )
            
            try:
                await enviar_mensagem_telegram(mensagem)
                texto_twitter = mensagem.replace("*", "")
                # postar_no_twitter(texto_twitter[:275])
                
                dados_item["ultimo_preco_divulgado"] = preco_atual
                if preco_atual < menor_historico:
                    dados_item["menor_preco_historico"] = preco_atual
                postar = False
            except Exception as e:
                print(f"Erro ao enviar postagem: {e}")
        else:
            print(f"❌ Retido pelas regras de preço: {item['titulo']} (Atual: R$ {preco_atual:.2f} | Média: R$ {media_preco:.2f} | Recorde: R$ {menor_historico:.2f})")


    # Salva o histórico atualizado
    if houve_mudanca_no_historico:
        salvar_json(HISTORICO_FILE, historico)

if __name__ == "__main__":
    asyncio.run(processar_ofertas())
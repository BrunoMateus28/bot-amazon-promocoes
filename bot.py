import json
import os
import asyncio
from datetime import datetime, timedelta
from src.telegram import enviar_mensagem_telegram
from src.twitter import postar_no_twitter

HISTORICO_FILE = "historico_precos.json"
OFERTAS_FILE = "ofertas.json"

def carregar_json(caminho, default):
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)

def limpar_historico_antigo(valores):
    """Remove registros com mais de 30 dias para manter a média móvel correta."""
    limite_30_dias = datetime.now() - timedelta(days=30)
    return [
        v for v in valores 
        if datetime.strptime(v["data"], "%Y-%m-%d") >= limite_30_dias
    ]

async def processar_ofertas():
    ofertas = carregar_json(OFERTAS_FILE, [])
    historico = carregar_json(HISTORICO_FILE, {})
    
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    houve_mudanca_no_historico = False

    for item in ofertas:
        item_id = item["id"]
        preco_atual = float(item["preco_atual"])
        
        # Se o item nunca foi visto, inicializa o histórico dele
        if item_id not in historico:
            historico[item_id] = {
                "menor_preco_historico": preco_atual,
                "ultimo_preco_divulgado": None,
                "valores_30_dias": []
            }
        
        dados_item = historico[item_id]
        
        # Atualiza a lista dos últimos 30 dias e limpa os antigos
        dados_item["valores_30_dias"].append({"data": data_hoje, "preco": preco_atual})
        dados_item["valores_30_dias"] = limpar_historico_antigo(dados_item["valores_30_dias"])
        houve_mudanca_no_historico = True
        
        # Cálculos de métricas
        precos_30_dias = [v["preco"] for v in dados_item["valores_30_dias"]]
        media_preco = sum(precos_30_dias) / len(precos_30_dias)
        
        menor_historico = dados_item["menor_preco_historico"]
        ultimo_divulgado = dados_item["ultimo_preco_divulgado"]
        
        # Regras de Decisão para Postagem
        condicao_1 = preco_atual < menor_historico
        
        condicao_2 = False
        if ultimo_divulgado is not None:
            condicao_2 = (preco_atual < media_preco) and (preco_atual < ultimo_divulgado)
        elif preco_atual < media_preco:
            # Se nunca foi divulgado antes, mas está abaixo da média, aceita
            condicao_2 = True

        if condicao_1 or condicao_2:
            print(f"🔥 Aprovado para postagem: {item['titulo']} (R$ {preco_atual:.2f})")
            
            # Monta o gatilho visual da mensagem
            detalhe_gatilho = "🚨 MENOR PREÇO HISTÓRICO!" if condicao_1 else "📉 ABAIXO DA MÉDIA!"
            
            mensagem = (
                f"{detalhe_gatilho}\n\n"
                f"📚 *{item['titulo']}*\n"
                f"💰 Por apenas: *R$ {preco_atual:.2f}*\n"
                f"📊 Média de 30 dias: R$ {media_preco:.2f}\n\n"
                f"🛒 Compre pelo link:\n{item['url']}"
            )
            
            # Dispara as postagens
            try:
                await enviar_mensagem_telegram(mensagem)
                texto_twitter = mensagem.replace("*", "")
                # postar_no_twitter(texto_twitter[:275])
                
                # Atualiza os estados de divulgação
                dados_item["ultimo_preco_divulgado"] = preco_atual
            except Exception as e:
                print(f"Erro ao enviar postagem: {e}")
        else:
            print(f"❌ Retido pelas regras de preço: {item['titulo']} (Atual: R$ {preco_atual:.2f} | Média: R$ {media_preco:.2f} | Histórico: R$ {menor_historico:.2f})")

        # Atualiza o menor preço histórico se o atual for imbatível
        if preco_atual < menor_historico:
            dados_item["menor_preco_historico"] = preco_atual

    # Salva o histórico atualizado
    if houve_mudanca_no_historico:
        salvar_json(HISTORICO_FILE, historico)

if __name__ == "__main__":
    asyncio.run(processar_ofertas())
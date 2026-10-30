import re
import time
import unicodedata
import gspread
from urllib.parse import quote_plus
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ============================================================
# CONFIGURAÇÕES
# ============================================================
TAG_AFILIADO = "promolivro025-20"
PLANILHA_NOME = "Lista Amazon"
CREDENCIAIS_JSON = "credenciais_google.json"

ABA_CANDIDATOS = "Candidatos_Fisicos"
ABA_FINAL = "pagina1" # Aba que o bot consome
PAUSA_MINIMA = 3.0

PESQUISAS = [
    "fantasia épica",
    "alta fantasia",
    "fantasia medieval",
    "fantasia sombria",
    "dark fantasy",
    "grimdark",
    "romantasia",
    "fantasia urbana",
    "fantasia mitológica",
    "fantasia brasileira",
    "ficção científica",
    "space opera",
    "cyberpunk",
    "distopia",
    "ficção científica militar",
    "horror cósmico",
    "terror sobrenatural",
    "ficção de vampiros",
    "ficção pós-apocalíptica",
    "RPG de mesa",
    "Dungeons and Dragons",
    "Tormenta RPG",
    "Pathfinder RPG",
    "LitRPG",
    "progression fantasy",
    "Brandon Sanderson",
    "J. R. R. Tolkien",
    "Joe Abercrombie",
    "Robin Hobb",
    "Andrzej Sapkowski",
    "Ursula K. Le Guin",
    "Isaac Asimov",
    "Frank Herbert",
    "Adrian Tchaikovsky",
    "N. K. Jemisin",
    "R. F. Kuang",
    "H. P. Lovecraft",
    "Neil Gaiman",
    "George R. R. Martin",
    "Brent Weeks",
    "Rebecca Yarros",
    "Sarah J. Maas",
    "James Islington",
    "Martha Wells",
    "Pierce Brown",
    "Terry Pratchett",
    "Octavia Butler",
    "C. S. Lewis",
    "Patrick Rothfuss",
]

TERMOS_BLOQUEADOS = [
    "educação financeira", "educacao financeira", "marketing digital",
    "gestão empresarial", "gestao empresarial", "liderança empresarial",
    "lideranca empresarial", "desenvolvimento pessoal", "autoajuda",
    "emagrecimento", "receitas culinárias", "receitas culinarias",
    "livro de colorir", "livro para colorir", "contabilidade empresarial",
    "administração financeira", "administracao financeira", "curso",
]

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================
def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower().strip()

def gerar_id(titulo):
    texto = normalizar(titulo)
    texto = re.sub(r'[^a-z0-9]', '_', texto)
    texto = re.sub(r'_+', '_', texto).strip('_')
    return texto

def livro_bloqueado(titulo):
    texto_titulo = normalizar(titulo)
    for termo in TERMOS_BLOQUEADOS:
        if normalizar(termo) in texto_titulo:
            return True, f"Título contém termo bloqueado: {termo}"
    return False, ""

def extrair_asin_da_url(url):
    match = re.search(r"/dp/([A-Z0-9]{10})", url)
    if match:
        return match.group(1)
    return None

def construir_link_amazon(asin):
    return f"https://www.amazon.com.br/dp/{asin}?tag={TAG_AFILIADO}"

def verificar_idioma_portugues(page, url_livro):
    """
    Acessa rapidamente a página do produto para confirmar se o idioma é Português
    com base na ficha técnica da Amazon (ex: 'Idioma ‏ : ‎ Português').
    """
    context_temp = page.context.new_page()
    try:
        context_temp.goto(url_livro, wait_until="domcontentloaded", timeout=10000)
        # Procura pelos detalhes do produto na página
        detalhes_texto = context_temp.inner_text("body").lower()
        context_temp.close()
        
        # Verifica se consta explicitamente idioma português e se não é edição em outro idioma óbvio
        if "idioma" in detalhes_texto:
            if "português" in detalhes_texto or "portugues" in detalhes_texto:
                # Checagem de segurança contra falsos positivos (ex: livro em inglês que cita português)
                if "english edition" in detalhes_texto and "português" not in detalhes_texto.split("english edition")[0]:
                    return False
                return True
        return False
    except Exception:
        try:
            context_temp.close()
        except:
            pass
        return False

# ============================================================
# GOOGLE SHEETS
# ============================================================
def conectar_google_sheets():
    escopo = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    credenciais = ServiceAccountCredentials.from_json_keyfile_name(CREDENCIAIS_JSON, escopo)
    return gspread.authorize(credenciais).open(PLANILHA_NOME)

def obter_ids_existentes(planilha, nome_aba):
    try:
        aba = planilha.worksheet(nome_aba)
        registros = aba.get_all_records()
        return {str(r.get("id", "")).strip() for r in registros if r.get("id")}
    except Exception:
        return set()

def obter_ou_criar_aba(planilha, nome, cabecalho):
    try:
        aba = planilha.worksheet(nome)
    except gspread.WorksheetNotFound:
        aba = planilha.add_worksheet(title=nome, rows=1000, cols=len(cabecalho))
        
    primeira_linha = aba.row_values(1)
    if not primeira_linha:
        aba.append_row(cabecalho)
    return aba

def salvar_candidatos(planilha, livros):
    cabecalho = ["id", "titulo", "preco_atual", "url", "imagem_url"]
    aba = obter_ou_criar_aba(planilha, ABA_CANDIDATOS, cabecalho)
    
    ids_candidatos_existentes = obter_ids_existentes(planilha, ABA_CANDIDATOS)
    linhas = []

    for livro in livros:
        if livro["id"] in ids_candidatos_existentes:
            continue
            
        linhas.append([
            livro["id"], 
            livro["titulo"], 
            livro["preco_atual"], 
            livro["url"], 
            livro["imagem_url"]
        ])
        ids_candidatos_existentes.add(livro["id"])

    if linhas:
        aba.append_rows(linhas, value_input_option="USER_ENTERED")

    print("\n" + "=" * 60)
    print("RESULTADO FINAL")
    print("=" * 60)
    print(f"Novos livros salvos na aba '{ABA_CANDIDATOS}' prontos para o bot: {len(linhas)}")

# ============================================================
# SCRAPING COM PLAYWRIGHT
# ============================================================
def descobrir_livros_amazon(ids_na_pagina1):
    livros_encontrados = {}
    total_pesquisas = len(PESQUISAS)

    print("\n" + "=" * 60)
    print("DESCOBERTA DE LIVROS FÍSICOS — AMAZON SCRAPING")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for indice, termo in enumerate(PESQUISAS, 1):
            print(f"\nPesquisa {indice}/{total_pesquisas}: {termo}")
            url = f"https://www.amazon.com.br/s?k={quote_plus(termo)}&i=stripbooks"
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_selector("div[data-component-type='s-search-result']", timeout=10000)
            except PlaywrightTimeoutError:
                print(f"  [Erro] Timeout ao carregar a página para '{termo}'. Pulando...")
                continue

            resultados = page.query_selector_all("div[data-component-type='s-search-result']")
            novos = 0
            
            for item in resultados:
                titulo_el = item.query_selector("h2 a span") or item.query_selector("h2 span")
                titulo = titulo_el.inner_text().strip() if titulo_el else ""
                
                if not titulo:
                    continue

                livro_id = gerar_id(titulo)
                if livro_id in ids_na_pagina1:
                    print(f"  [Descartado] '{titulo}' - Já consta na {ABA_FINAL}.")
                    continue
                
                if livro_id in livros_encontrados:
                    continue

                bloqueado, motivo = livro_bloqueado(titulo)
                if bloqueado:
                    print(f"  [Descartado] '{titulo}' - {motivo}")
                    continue

                formatos = item.query_selector_all("a.a-text-bold")
                url_fisico, formato_fisico = None, None
                
                for f in formatos:
                    texto = f.inner_text().lower()
                    if "capa comum" in texto or "capa dura" in texto:
                        url_fisico = f.get_attribute("href")
                        formato_fisico = f.inner_text().strip()
                        break 
                
                if not url_fisico:
                    print(f"  [Descartado] '{titulo}' - Nenhuma edição física na vitrine.")
                    continue
                
                asin_correto = extrair_asin_da_url(url_fisico)
                if not asin_correto:
                    continue

                link_produto = construir_link_amazon(asin_correto)

                # --- VERIFICAÇÃO ATIVA DO IDIOMA NA PÁGINA DO PRODUTO ---
                print(f"  [Verificando idioma] '{titulo}'...")
                if not verificar_idioma_portugues(page, link_produto):
                    print(f"  [Descartado] '{titulo}' - Não é edição em Português.")
                    continue
                # -------------------------------------------------------

                bloco_preco = None
                for a_tag in item.query_selector_all("a"):
                    texto_a = a_tag.inner_text().lower()
                    if "capa comum" in texto_a or "capa dura" in texto_a:
                        try:
                           parent_div = a_tag.evaluate_handle('el => el.closest("div.puis-padding-right-small")')
                           if parent_div:
                               preco_el = parent_div.as_element().query_selector("span.a-price span.a-offscreen")
                               if preco_el:
                                   bloco_preco = preco_el.inner_text().strip()
                        except:
                            pass
                        
                if not bloco_preco:
                     preco_el_fallback = item.query_selector("span.a-price span.a-offscreen")
                     if preco_el_fallback:
                         bloco_preco = preco_el_fallback.inner_text().strip()
                         
                if not bloco_preco:
                     print(f"  [Descartado] '{titulo}' ({formato_fisico}) - Preço oculto ou indisponível.")
                     continue
                     
                texto_bloco_total = item.inner_text().lower()
                if "indisponível" in texto_bloco_total or "não disponível" in texto_bloco_total:
                    continue

                img_el = item.query_selector("img.s-image")
                imagem_url = img_el.get_attribute("src") if img_el else ""

                livros_encontrados[livro_id] = {
                    "id": livro_id,
                    "titulo": titulo,
                    "preco_atual": bloco_preco,
                    "url": link_produto,
                    "imagem_url": imagem_url,
                }
                novos += 1

            print(f"  Resultados: {len(resultados)} blocos analisados, {novos} livros adicionados aos candidatos.")
            time.sleep(PAUSA_MINIMA)

        browser.close()

    resultado_final = list(livros_encontrados.values())
    print(f"\nTotal de novos candidatos: {len(resultado_final)}")
    return resultado_final

# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================
def main():
    print("Iniciando rotina e conectando ao Google Sheets...")
    try:
        planilha = conectar_google_sheets()
    except Exception as erro:
        print(f"Erro crítico ao conectar no Sheets: {erro}")
        return

    print(f"Mapeando livros já existentes na aba '{ABA_FINAL}'...")
    ids_na_pagina1 = obter_ids_existentes(planilha, ABA_FINAL)
    print(f"-> Encontrados {len(ids_na_pagina1)} livros salvos na base do Bot.")
    
    try:
        livros = descobrir_livros_amazon(ids_na_pagina1)
    except KeyboardInterrupt:
        print("\nExecução de raspagem interrompida pelo usuário.")
        return

    if not livros:
        print("\nNenhum candidato inédito foi encontrado na Amazon.")
        return

    print("\nSalvando os dados na planilha...")
    try:
        salvar_candidatos(planilha, livros)
    except KeyboardInterrupt:
        print("\nInterrupção durante a gravação no Sheets.")

if __name__ == "__main__":
    try:
        main()
    except Exception as erro:
        print(f"\nErro crítico detectado: {erro}")
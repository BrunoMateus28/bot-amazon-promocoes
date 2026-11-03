"""
Teste do fluxo de artigos SEO. NÃO faz commit/push, NÃO mexe em posts/, index.html,
sitemap.xml nem historico_precos.json. Tudo é gerado numa pasta temporária.

Uso (na raiz do projeto, com o venv ativado):
    python testar_artigos.py              # teste completo (1 chamada real ao Gemini)
    python testar_artigos.py --sem-api    # tudo, menos a chamada ao Gemini
"""
import csv
import os
import sys
import tempfile
import traceback

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)
sys.path.insert(0, RAIZ)

SEM_API = "--sem-api" in sys.argv
falhas = []


def ok(msg):
    print(f"  ✅ {msg}")


def erro(msg):
    print(f"  ❌ {msg}")
    falhas.append(msg)


def checar(cond, msg_ok, msg_erro):
    ok(msg_ok) if cond else erro(msg_erro)
    return cond


def titulo_bloco(t):
    print(f"\n── {t}")


def buscar_titulos_csv(url):
    from curl_cffi import requests
    r = requests.get(url, impersonate="chrome", timeout=15)
    r.encoding = "utf-8"
    r.raise_for_status()
    linhas = [l.strip() for l in r.text.splitlines() if l.strip()]
    delim = ";" if ";" in linhas[0] else ","
    return [
        {"titulo": (l.get("titulo") or "").strip(), "url": (l.get("url") or "").strip(),
         "imagem_url": (l.get("imagem_url") or "").strip()}
        for l in csv.DictReader(linhas, delimiter=delim) if (l.get("titulo") or "").strip()
    ]


def main():
    from dotenv import load_dotenv
    load_dotenv()

    # 1 ─ Arquivos e edições no bot.py (leitura de texto, sem executar nada)
    titulo_bloco("1. Arquivos do projeto")
    for arq in ("src/artigos.py", "src/layout.py", "src/site.py"):
        checar(os.path.exists(arq), f"{arq} existe", f"{arq} NÃO existe")
    if os.path.exists("artigos.py"):
        erro("artigos.py solto na raiz: apague (o bot importa de src/artigos.py)")
    try:
        bot = open("bot.py", encoding="utf-8-sig").read()
        compile(bot, "bot.py", "exec")  # só checa sintaxe, não executa
        ok("bot.py com sintaxe válida")
        for trecho in ["from src.artigos import gerar_artigo_do_dia", "from src.site import gerar_site",
                       "aprovados.append", "gerar_artigo_do_dia(aprovados, ofertas)", "gerar_site(ofertas, historico)"]:
            checar(trecho in bot, f"bot.py contém {trecho!r}", f"bot.py NÃO contém {trecho!r}")
    except Exception as e:
        erro(f"bot.py: {e}")

    # 2 ─ Dependências e ambiente
    titulo_bloco("2. Dependências e .env")
    try:
        import markdown, pydantic  # noqa: F401
        from google import genai  # noqa: F401
        ok("markdown, pydantic e google-genai instalados")
    except ImportError as e:
        erro(f"{e}  →  rode: pip install -r requirements.txt")
        return
    try:
        from src import artigos
        ok("src.artigos importa sem erro")
    except Exception as e:
        erro(f"src.artigos falhou ao importar: {e}")
        return
    checar(bool(os.getenv("GEMINI_API_KEY")), "GEMINI_API_KEY encontrada", "GEMINI_API_KEY ausente no .env")
    url_csv = os.getenv("GOOGLE_SHEETS_CSV_URL")
    checar(bool(url_csv), "GOOGLE_SHEETS_CSV_URL encontrada", "GOOGLE_SHEETS_CSV_URL ausente no .env")

    posts_reais_antes = sorted(os.listdir("posts")) if os.path.isdir("posts") else None
    pasta_teste = tempfile.mkdtemp(prefix="teste_artigos_")
    artigos.POSTS_DIR = os.path.join(pasta_teste, "posts")  # tudo vai para a pasta temporária

    # 3 ─ Planilha (somente leitura)
    titulo_bloco("3. Planilha")
    ofertas = []
    if url_csv:
        try:
            ofertas = buscar_titulos_csv(url_csv)
            ok(f"{len(ofertas)} livros lidos da planilha")
            slugs = [artigos.gerar_slug(o["titulo"]) for o in ofertas]
            for o, s in list(zip(ofertas, slugs))[:3]:
                print(f"     {o['titulo'][:55]!r} -> {s}")
            por_slug = {}
            for o, sl in zip(ofertas, slugs):
                por_slug.setdefault(sl, set()).add(o["titulo"])
            repetidos = [t for t in por_slug.values() if len(t) == 1 and
                         sum(1 for x in ofertas if x["titulo"] in t) > 1]
            colisoes = {sl: t for sl, t in por_slug.items() if len(t) > 1}
            if repetidos:
                print(f"     ℹ️  {len(repetidos)} título(s) repetido(s) na planilha (compartilham o mesmo artigo, ok)")
            if colisoes:
                for sl, t in list(colisoes.items())[:5]:
                    print(f"     {sl} <- {sorted(t)}")
            checar(not colisoes, "nenhum título DIFERENTE gera o mesmo slug",
                   f"{len(colisoes)} slug(s) compartilhado(s) por títulos diferentes (só o 1º ganharia artigo)")
            reais = {a[:-3] for a in (posts_reais_antes or []) if a.endswith(".md")}
            print(f"     {len(reais)} artigo(s) já existem em posts/; {len([s for s in slugs if s not in reais])} livro(s) sem artigo")
        except Exception as e:
            erro(f"não consegui ler a planilha: {e}")
    amostra = ofertas[0] if ofertas else {"titulo": "Duna", "url": "https://exemplo.com/oferta", "imagem_url": ""}

    # 4 ─ Lógica de seleção + trava (sem IA)
    titulo_bloco("4. Seleção e trava anti-duplicação (dados fictícios)")
    fake = [{"titulo": "Livro A"}, {"titulo": "Livro B"}, {"titulo": "Livro C"}]
    aprov = [{"titulo": "Livro A", "desconto": 0.1}, {"titulo": "Livro B", "desconto": 0.4}]
    checar(artigos.escolher_candidato(aprov, fake) == "Livro B", "escolhe a maior promoção", "não escolheu a maior promoção")
    os.makedirs(artigos.POSTS_DIR, exist_ok=True)
    open(os.path.join(artigos.POSTS_DIR, "livro-b.md"), "w").close()
    checar(artigos.escolher_candidato(aprov, fake) == "Livro A", "pula quem já tem artigo", "não pulou livro existente")
    open(os.path.join(artigos.POSTS_DIR, "livro-a.html"), "w").close()
    checar(artigos.escolher_candidato(aprov, fake) == "Livro C", "cai no fallback (livro qualquer sem artigo)", "fallback falhou")
    open(os.path.join(artigos.POSTS_DIR, "livro-c.md"), "w").close()
    checar(artigos.escolher_candidato(aprov, fake) is None, "retorna None quando tudo já tem artigo", "deveria retornar None")
    for f in os.listdir(artigos.POSTS_DIR):
        os.remove(os.path.join(artigos.POSTS_DIR, f))

    # 5 ─ Geração do artigo (Gemini real, numa pasta temporária)
    titulo_bloco("5. Geração do artigo")
    if SEM_API:
        print("  ⏭️  pulado (--sem-api): usando um artigo fictício para testar o resto")
        corpo = "".join(f"## Seção {i}\n" + "palavra " * 120 + "\n\n" for i in range(6))
        corpo += "**Este livro é para:**\n- Fãs de terror.\n- Leitores de clássicos.\n"
        art = artigos.ArtigoIA(title="Teste: resenha e guia", description="d" * 130,
                               keywords=["a", "b", "c"], corpo_markdown=corpo)
        md = artigos.montar_markdown(art, "teste", amostra["url"], amostra["imagem_url"])
        os.makedirs(artigos.POSTS_DIR, exist_ok=True)
        slug = "teste"
        open(os.path.join(artigos.POSTS_DIR, f"{slug}.md"), "w", encoding="utf-8").write(md)
    else:
        print(f"  ⏳ chamando o Gemini para: {amostra['titulo'][:60]!r} (pode levar ~30s)")
        slug = artigos.gerar_artigo_do_dia([], [amostra])
        if not checar(bool(slug), "artigo gerado e gravado na pasta temporária",
                      "Gemini não devolveu artigo válido (veja as mensagens acima)"):
            return

    # 6 ─ Conteúdo e SEO do artigo gerado
    titulo_bloco("6. Qualidade e SEO do artigo")
    caminho_md = os.path.join(artigos.POSTS_DIR, f"{slug}.md")
    post = artigos.ler_post(caminho_md)
    if not checar(post is not None, "front matter lido corretamente", "front matter ilegível"):
        return
    for campo in ["title", "description", "keywords", "slug", "date"]:
        checar(bool(post.get(campo)), f"front matter tem '{campo}'", f"front matter sem '{campo}'")
    print(f"     title ({len(post['title'])} car.): {post['title']}")
    print(f"     description ({len(post['description'])} car.): {post['description']}")
    print(f"     palavras no corpo: {len(post['corpo'].split())}")
    checar(len(post["title"]) <= 70, "título dentro do limite", "título muito longo (>70)")
    checar("t.me/bardodaspromos" in post["corpo"], "CTA do Telegram presente", "CTA do Telegram ausente")
    checar("R$" not in post["corpo"], "sem preço no texto", "há 'R$' no texto (preço envelhece)")
    checar(post["corpo"].count("## ") >= 5, "estrutura com seções (##)", "poucas seções no artigo")

    # 7 ─ HTML, home e sitemap
    titulo_bloco("7. HTML, home e sitemap (temporários)")
    html_post = artigos.renderizar_html(post)
    caminho_html = os.path.join(artigos.POSTS_DIR, f"{slug}.html")
    open(caminho_html, "w", encoding="utf-8").write(html_post)
    for marca in ['name="description"', 'rel="canonical"', 'property="og:title"',
                  'name="twitter:card"', "application/ld+json", "<h1>"]:
        checar(marca in html_post, f"HTML contém {marca}", f"HTML sem {marca}")
    if post.get("url"):
        checar('rel="sponsored' in html_post and "Associado da Amazon" in html_post,
               "botão de compra + aviso de afiliado", "botão/aviso de afiliado ausente")
    import re as _re
    checar(not _re.search(r"<p>[^<]*\n- ", html_post), "listas renderizadas como <ul> (não coladas em parágrafo)",
           "há itens '- ' soltos dentro de um parágrafo (lista quebrada)")
    checar(len(_re.search(r"<title>(.*?)</title>", html_post).group(1)) <= 70, "tag <title> com tamanho adequado",
           "tag <title> muito longa (>70)")
    checar("<script>alert" not in html_post, "sem <script> cru no corpo", "HTML cru perigoso no corpo")
    from src import site
    site.gerar_site([{"id": "t", "titulo": "Livro de Teste", "preco_atual": 39.9, "url": "https://x.co/t",
                      "imagem_url": ""}], {}, destino=pasta_teste)
    lido = lambda n: open(os.path.join(pasta_teste, n), encoding="utf-8").read()
    for pagina in ("index.html", "guias.html", "sobre.html", "site.css", "site.js", "sitemap.xml"):
        checar(os.path.exists(os.path.join(pasta_teste, pagina)), f"{pagina} gerado", f"{pagina} NÃO foi gerado")
    checar(f"posts/{slug}.html" in lido("guias.html"), "post aparece em guias.html", "post não aparece em guias.html")
    checar(f"posts/{slug}.html" in lido("sitemap.xml"), "post entra no sitemap", "post não entra no sitemap")
    checar("tailwind" not in lido("index.html").lower(), "home sem Tailwind/CDN externo", "home ainda usa Tailwind")
    checar("Ã" not in lido("index.html") and "Ã" not in html_post, "sem acentos corrompidos (mojibake)", "TEXTO CORROMPIDO (Ã) no HTML")

    posts_reais_depois = sorted(os.listdir("posts")) if os.path.isdir("posts") else None
    checar(posts_reais_antes == posts_reais_depois, "pasta posts/ real intocada", "a pasta posts/ real foi alterada!")
    print(f"\n📂 Arquivos de teste em: {artigos.POSTS_DIR}  (abra o .html no navegador para ver)")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        falhas.append("exceção inesperada")
    print("\n" + ("=" * 50))
    print("🎉 TUDO OK" if not falhas else f"⚠️ {len(falhas)} PROBLEMA(S):\n   - " + "\n   - ".join(falhas))
    sys.exit(1 if falhas else 0)
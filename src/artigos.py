"""
Artigos SEO do Bardo das Promoções.

Fase 1: slug, prompt, chamada ao Gemini e montagem do Markdown.
Fase 2: trava de existência, escolha do livro, gravação .md/.html em posts/,
        listagem para o index e para o sitemap.

Ponto de entrada no bot.py:  gerar_artigo_do_dia(aprovados, ofertas)
"""

import html
import json
import os
import random
import re
import unicodedata
from datetime import datetime
from typing import List, Optional

from google import genai
from google.genai import types
import markdown as md_lib
from pydantic import BaseModel, Field

from src.layout import NOME_SITE, PLACEHOLDER, card_guia, esc, pagina

MODELO_GEMINI = "gemini-3.5-flash"  # mesmo modelo já usado em bot.py
TELEGRAM_URL = "https://t.me/bardodaspromos"
MAX_TENTATIVAS = 2
MIN_PALAVRAS = 600
POSTS_DIR = "posts"
BASE_URL = "https://brunomateus28.github.io/bot-amazon-promocoes/"


# ----------------------------------------------------------------------
# Saída estruturada: o Gemini devolve campos separados e o Python monta o
# YAML. Assim slug/date nunca dependem do modelo e o front matter não quebra
# por aspas ou dois-pontos dentro do título.
# ----------------------------------------------------------------------
class ArtigoIA(BaseModel):
    title: str = Field(description="Título SEO, até 60 caracteres")
    description: str = Field(description="Meta description, 120 a 155 caracteres")
    keywords: List[str] = Field(description="5 a 8 palavras-chave")
    corpo_markdown: str = Field(description="Corpo do artigo em Markdown, sem H1")


def gerar_slug(titulo: str, limite: int = 70) -> str:
    """'O Caminho dos Reis' -> 'o-caminho-dos-reis' (corta em fronteira de palavra)."""
    sem_acento = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")
    if len(slug) > limite:
        slug = slug[:limite].rsplit("-", 1)[0]
    return slug


def montar_prompt_artigo(titulo_livro: str) -> str:
    return f"""
Você é um crítico literário brasileiro especializado em Fantasia e Ficção
Científica, escrevendo para o blog do canal @bardodaspromos.

LIVRO: "{titulo_livro}"

OBJETIVO: escrever um guia de leitura/resenha que seja genuinamente útil para
quem está decidindo se vale a pena ler este livro (Helpful Content, E-E-A-T).
O leitor chega pelo Google com intenção de compra: quer saber se combina com ele.

REGRAS DE CONTEÚDO
- Português brasileiro natural, tom de leitor experiente, sem clichês de vendedor.
- ZERO spoilers: nada de final, mortes, reviravoltas ou revelações.
- NÃO invente fatos. Se não tiver certeza de autor, editora, número de páginas,
  prêmios, adaptações ou posição na série, NÃO mencione. Prefira falar do tipo
  de história, tom e estilo a afirmar detalhes duvidosos.
- NÃO cite preço, desconto, promoção, "menor preço" ou urgência (o artigo é
  perene e preço desatualizado prejudica o leitor).
- NÃO inclua links nem o CTA final (o sistema adiciona depois).
- NÃO use H1 (o título já vem do front matter). Comece direto pela introdução.

ESTRUTURA DO CORPO (Markdown, use ## e ###)
1. Introdução (2 parágrafos): a premissa sem spoilers e por que o livro chama atenção.
2. ## Sobre o que é {titulo_livro}: premissa, ambientação, tipo de conflito.
3. ## Worldbuilding e atmosfera: como o mundo/universo é construído e sentido.
4. ## Ritmo da leitura: é rápido, lento, denso? Onde exige paciência?
5. ## Personagens e tom: o que esperar, sem revelar arcos.
6. ## Para quem este livro é (e para quem não é): 2 listas curtas e honestas.
7. ## Vale a pena ler? Veredito claro em 1 parágrafo, ajudando a decidir a compra.
8. ## Perguntas frequentes: 3 perguntas em ### com respostas de 2 a 3 frases
   (ex.: precisa ler outros livros antes? é indicado para iniciantes no gênero?).

TAMANHO: 800 a 1100 palavras no corpo.

CAMPOS DE SEO
- title: até 60 caracteres, com o nome do livro e termo como "resenha" ou "vale a pena".
- description: 120 a 155 caracteres, convidativa, sem spoilers, sem preço.
- keywords: 5 a 8 termos que um leitor realmente pesquisaria.

Responda apenas com o JSON do schema solicitado.
""".strip()


def _yaml(valor) -> str:
    """JSON é um subconjunto válido de YAML: escapa aspas e ':' com segurança."""
    return json.dumps(valor, ensure_ascii=False)


def montar_markdown(artigo: ArtigoIA, slug: str, url: str = "", image: str = "", book: str = "") -> str:
    corpo = re.sub(r"^#\s+.*\n+", "", artigo.corpo_markdown.strip())  # remove H1 se vier
    front_matter = "\n".join([
        "---",
        f"title: {_yaml(artigo.title.strip())}",
        f"description: {_yaml(artigo.description.strip())}",
        f"keywords: {_yaml([k.strip() for k in artigo.keywords])}",
        f"slug: {_yaml(slug)}",
        *([f"book: {_yaml(book)}"] if book else []),
        *([f"url: {_yaml(url)}"] if url else []),
        *([f"image: {_yaml(image)}"] if image else []),
        f"date: {datetime.now().strftime('%Y-%m-%d')}",
        "---",
    ])
    cta = (
        "---\n\n"
        "📣 **Quer ser avisado quando este e outros livros de Fantasia e Ficção "
        f"Científica entrarem em promoção?** Entre no canal do Telegram: "
        f"[@bardodaspromos]({TELEGRAM_URL})"
    )
    return f"{front_matter}\n\n{corpo}\n\n{cta}\n"


def _artigo_valido(artigo: ArtigoIA) -> bool:
    palavras = len(artigo.corpo_markdown.split())
    return (
        0 < len(artigo.title) <= 70
        and 80 <= len(artigo.description) <= 170
        and len(artigo.keywords) >= 3
        and palavras >= MIN_PALAVRAS
        and "##" in artigo.corpo_markdown
    )


def gerar_artigo_markdown(titulo_livro: str, slug: str, url: str = "", image: str = "") -> Optional[str]:
    """Retorna o Markdown completo (front matter + corpo + CTA) ou None se falhar."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ GEMINI_API_KEY ausente: artigo não gerado.")
        return None

    client = genai.Client(api_key=api_key)

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resposta = client.models.generate_content(
                model=MODELO_GEMINI,
                contents=montar_prompt_artigo(titulo_livro),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ArtigoIA,
                    temperature=0.7,
                ),
            )
            artigo = ArtigoIA.model_validate_json(resposta.text)
            if _artigo_valido(artigo):
                return montar_markdown(artigo, slug, url, image, titulo_livro)
            print(f"⚠️ Artigo reprovado na validação (tentativa {tentativa}).")
        except Exception as e:
            print(f"❌ Erro ao gerar artigo (tentativa {tentativa}): {e}")

    return None  # nunca salvar artigo quebrado/curto


# ======================================================================
# FASE 2 — Arquivos, seleção do livro, HTML e listagem
# ======================================================================
def artigo_existe(slug: str) -> bool:
    """Trava anti-duplicação/canibalização: .md OU .html já presente."""
    return any(
        os.path.exists(os.path.join(POSTS_DIR, f"{slug}.{ext}")) for ext in ("md", "html")
    )


def escolher_candidato(aprovados: list, ofertas: list) -> Optional[str]:
    """
    1) Entre as promoções aprovadas hoje, a de maior desconto que ainda não tem artigo.
    2) Se todas já tiverem, qualquer oferta da planilha sem artigo (aleatória).
    3) Se tudo já tiver artigo, None.
    `aprovados`: [{"titulo": str, "desconto": float}, ...]
    """
    for c in sorted(aprovados, key=lambda c: c["desconto"], reverse=True):
        if not artigo_existe(gerar_slug(c["titulo"])):
            return c["titulo"]
    pendentes = [o for o in ofertas if not artigo_existe(gerar_slug(o["titulo"]))]
    return random.choice(pendentes)["titulo"] if pendentes else None


_FRONT_RE = re.compile(r"---\n(.*?)\n---\n(.*)", re.S)


def ler_post(caminho_md: str) -> Optional[dict]:
    """Lê front matter (escrito por nós em JSON-style) + corpo de um .md."""
    try:
        with open(caminho_md, "r", encoding="utf-8") as f:
            m = _FRONT_RE.match(f.read())
        if not m:
            return None
        meta = {}
        for linha in m.group(1).splitlines():
            chave, _, valor = linha.partition(": ")
            meta[chave.strip()] = valor.strip() if chave == "date" else json.loads(valor)
        meta["corpo"] = m.group(2)
        return meta
    except Exception as e:
        print(f"⚠️ Post ilegível {caminho_md}: {e}")
        return None


def listar_posts() -> list:
    """Todos os posts, do mais recente para o mais antigo."""
    if not os.path.isdir(POSTS_DIR):
        return []
    posts = [
        p for f in os.listdir(POSTS_DIR)
        if f.endswith(".md") and (p := ler_post(os.path.join(POSTS_DIR, f)))
    ]
    return sorted(posts, key=lambda p: p.get("date", ""), reverse=True)


_ITEM_LISTA = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _normalizar_listas(texto: str) -> str:
    """Markdown exige linha em branco antes de uma lista; o modelo nem sempre coloca."""
    saida, anterior = [], ""
    for linha in texto.split("\n"):
        if _ITEM_LISTA.match(linha) and anterior.strip() and not _ITEM_LISTA.match(anterior):
            saida.append("")
        saida.append(linha)
        anterior = linha
    return "\n".join(saida)


def _data_br(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _botao_compra(post: dict) -> str:
    if not post.get("url"):
        return ""
    return (f'<a class="btn btn-gold" href="{esc(post["url"])}" target="_blank" '
            'rel="sponsored nofollow noopener">Ver oferta atual na Amazon</a>'
            f'<p class="aviso">Como Associado da Amazon, o {NOME_SITE} recebe comissão por compras '
            "qualificadas, sem custo extra para você. Preço e disponibilidade podem variar.</p>")


def renderizar_html(post: dict) -> str:
    """Markdown -> página completa no layout do site (meta tags, JSON-LD, migalhas, Leia também)."""
    corpo_seguro = re.sub(r"</?[a-zA-Z][^>]*>", "", post["corpo"])  # sem HTML cru do modelo
    corpo_html = md_lib.markdown(_normalizar_listas(corpo_seguro), extensions=["sane_lists"])
    url = f"{BASE_URL}posts/{post['slug']}.html"
    imagem = post.get("image", "")
    nome = post.get("book") or post["title"]
    # Google corta o <title> perto de 60 caracteres: só anexa o nome do site se couber
    titulo_tag = post["title"] if len(post["title"]) + 23 > 60 else f"{post['title']} | {NOME_SITE}"

    ld_artigo = {
        "@context": "https://schema.org", "@type": "Article", "headline": post["title"],
        "description": post["description"], "datePublished": post["date"], "dateModified": post["date"],
        "inLanguage": "pt-BR", "mainEntityOfPage": url,
        "author": {"@type": "Organization", "name": NOME_SITE},
        "publisher": {"@type": "Organization", "name": NOME_SITE},
    }
    if imagem:
        ld_artigo["image"] = imagem
    ld_trilha = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Início", "item": BASE_URL},
            {"@type": "ListItem", "position": 2, "name": "Guias", "item": BASE_URL + "guias.html"},
            {"@type": "ListItem", "position": 3, "name": post["title"], "item": url},
        ],
    }

    botao = _botao_compra(post)
    caixa = ""
    if botao or imagem:
        caixa = (f'<aside class="livro-box" aria-label="Sobre o livro">'
                 f'<img src="{esc(imagem or PLACEHOLDER)}" alt="Capa do livro {esc(nome)}" width="112" height="149">'
                 f'<div><strong>{esc(nome)}</strong>{botao}</div></aside>')
    relacionados = [p for p in listar_posts() if p["slug"] != post["slug"]][:3]
    rel_html = ""
    if relacionados:
        cards = "".join(card_guia(p, base="", i=i) for i, p in enumerate(relacionados))
        rel_html = f'<section class="relacionados"><h2>Leia também</h2><div class="guias-grid">{cards}</div></section>'
    compra_final = f'<div class="compra">{botao}</div>' if botao else ""

    corpo = (f'<div class="container"><nav class="crumbs" aria-label="Você está em">'
             f'<a href="../index.html">Início</a> › <a href="../guias.html">Guias</a> › <span>{esc(post["title"])}</span></nav>'
             f'<article class="prose"><header><h1>{esc(post["title"])}</h1>'
             f'<p class="post-meta">Guia de leitura · {_data_br(post["date"])}</p></header>'
             f'{caixa}{corpo_html}{compra_final}</article>{rel_html}</div>')
    return pagina(titulo=titulo_tag, descricao=post["description"], caminho=f"posts/{post['slug']}.html",
                  corpo=corpo, ativo="guias", prefixo="../", imagem=imagem, tipo="article",
                  jsonld=[ld_artigo, ld_trilha])


def gerar_artigo_do_dia(aprovados: list, ofertas: list) -> Optional[str]:
    """Gera no máximo UM artigo por execução. Retorna o slug criado ou None."""
    titulo = escolher_candidato(aprovados, ofertas)
    if not titulo:
        print("📝 Todos os livros já têm artigo. Nada a gerar.")
        return None

    slug = gerar_slug(titulo)
    if not slug or artigo_existe(slug):  # trava final, defesa em profundidade
        return None

    print(f"📝 Gerando artigo SEO: {titulo[:50]} -> posts/{slug}.html")
    oferta = next((o for o in ofertas if o["titulo"] == titulo), {})
    markdown_completo = gerar_artigo_markdown(
        titulo, slug, oferta.get("url", ""), oferta.get("imagem_url", "")
    )
    if not markdown_completo:
        return None

    os.makedirs(POSTS_DIR, exist_ok=True)
    caminho_md = os.path.join(POSTS_DIR, f"{slug}.md")
    with open(caminho_md, "w", encoding="utf-8") as f:
        f.write(markdown_completo)
    post = ler_post(caminho_md)
    with open(os.path.join(POSTS_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(renderizar_html(post))
    print(f"✅ Artigo publicado em posts/{slug}.html")
    return slug
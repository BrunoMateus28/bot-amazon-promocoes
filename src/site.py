"""
Gera o site estático: index.html (ofertas), guias.html, sobre.html, site.css, site.js,
sitemap.xml e re-renderiza posts/*.html a partir dos .md (para manter o visual em dia).
Ponto de entrada: gerar_site(ofertas, historico, destino=".")
"""
import os
from datetime import datetime
from pathlib import Path

from src import artigos
from src.layout import (BASE_URL, ICONE_BUSCA, ICONE_GRAFICO, ICONE_TELEGRAM, NOME_SITE, PLACEHOLDER,
                        TELEGRAM_URL, card_guia, esc, normalizar, pagina, salvar_assets_estaticos)


def _brl(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _info_preco(item: dict, historico: dict) -> dict:
    """Média por DIA (várias execuções no mesmo dia não pesam mais) e selos de oferta."""
    preco = item["preco_atual"]
    h = historico.get(item["id"]) or {}
    por_dia = {v.get("data"): v["preco"] for v in h.get("valores_30_dias", [])}  # último preço do dia
    dias = len(por_dia)
    media = sum(por_dia.values()) / dias if dias else preco
    off = round((media - preco) / media * 100) if dias >= 2 and media > 0 and preco < media else 0
    menor = h.get("menor_preco_historico", preco)
    baixo = off > 0 and dias >= 3 and preco <= menor * 1.0001
    return {"media": media, "off": off if off >= 1 else 0, "baixo": baixo}


def _card(i: int, item: dict, info: dict, destino: Path, prioridade: bool = False) -> str:
    iid = item["id"]
    capa_local, graf_local = f"assets/capa_{iid}.jpg", f"assets/grafico_{iid}.png"
    capa = capa_local if (destino / capa_local).exists() else (item.get("imagem_url") or PLACEHOLDER)
    titulo = item["titulo"]
    selos = ""
    if info["off"]:
        selos += f'<span class="badge badge-off">−{info["off"]}%</span>'
    if info["baixo"]:
        selos += '<span class="badge badge-low">Mínima histórica</span>'
    selos = f'<div class="badges">{selos}</div>' if selos else ""
    media = f'<small>Média 30d: R$ {_brl(info["media"])}</small>' if info["off"] else "<small></small>"
    grafico = ""
    if (destino / graf_local).exists():
        grafico = (f'<button type="button" class="chart-btn" data-chart="{graf_local}" '
                   f'data-title="{esc(titulo)}" aria-label="Ver histórico de preços de {esc(titulo)}" '
                   f'title="Histórico de preços">{ICONE_GRAFICO}</button>')
    nome = esc(normalizar(f'{titulo} {item.get("categoria", "")}'))
    carga = 'loading="eager" fetchpriority="high"' if prioridade else 'loading="lazy"'
    return (f'<article class="card" data-i="{i}" data-nome="{nome}" data-price="{item["preco_atual"]}" '
            f'data-off="{info["off"]}" data-low="{int(info["baixo"])}" data-cat="{esc(item.get("categoria", ""))}">'
            f'<div class="thumb">{selos}{grafico}<img src="{esc(capa)}" alt="Capa de {esc(titulo)}" width="300" height="400" '
            f'{carga} decoding="async"></div>'
            f'<div class="card-body"><h3>{esc(titulo)}</h3>'
            f'<div class="price"><strong>R$ {_brl(item["preco_atual"])}</strong>{media}</div>'
            f'<div class="card-actions"><a class="btn btn-gold btn-sm" href="{esc(item["url"])}" target="_blank" '
            f'rel="sponsored nofollow noopener">Ver na Amazon</a></div></div></article>')


_DIALOGO = ('<dialog id="dlg-grafico" aria-labelledby="dlg-titulo"><div class="dlg-head"><h3 id="dlg-titulo"></h3>'
            '<button type="button" class="btn btn-ghost btn-sm" data-fechar>Fechar</button></div>'
            '<img alt="" width="560" height="360"></dialog>')


def _pagina_home(livros: list, posts: list, destino: Path) -> str:
    n = len(livros)
    promo = [l for l in livros if l["info"]["off"]]
    destaques = sorted(promo, key=lambda l: -l["info"]["off"])[:8]
    categorias = sorted({l["item"].get("categoria") for l in livros if l["item"].get("categoria")})
    agora = datetime.now().strftime("%d/%m/%Y às %H:%M")

    chips = ['<button type="button" class="chip" data-f="todos" aria-pressed="true">Todos</button>']
    if promo:
        chips.append('<button type="button" class="chip" data-f="promo" aria-pressed="false">Em promoção</button>')
    if any(l["info"]["baixo"] for l in livros):
        chips.append('<button type="button" class="chip" data-f="low" aria-pressed="false">Mínima histórica</button>')
    if len(categorias) >= 2:
        chips += [f'<button type="button" class="chip" data-f="cat:{esc(c)}" aria-pressed="false">{esc(c)}</button>'
                  for c in categorias]

    bloco_destaques = ""
    if destaques:
        cards = "".join(_card(i, l["item"], l["info"], destino, prioridade=i < 4) for i, l in enumerate(destaques))
        bloco_destaques = (f'<section class="section" aria-labelledby="h-dest"><div class="container">'
                           f'<div class="section-head"><div><h2 id="h-dest">Destaques: maiores quedas</h2>'
                           f'<p>Livros mais abaixo da média de preço dos últimos 30 dias.</p></div>'
                           f'<a href="#ofertas">Ver todas ↓</a></div><div class="feature">{cards}</div></div></section>')

    bloco_guias = ""
    if posts:
        cards = "".join(card_guia(p, "posts/", i) for i, p in enumerate(posts[:3]))
        bloco_guias = (f'<section class="section" aria-labelledby="h-guias"><div class="container">'
                       f'<div class="section-head"><div><h2 id="h-guias">Guias de leitura</h2>'
                       f'<p>Resenhas sem spoilers para decidir o que vale a pena ler.</p></div>'
                       f'<a href="guias.html">Ver todos os guias →</a></div>'
                       f'<div class="guias-grid">{cards}</div></div></section>')

    todos = "".join(_card(i, l["item"], l["info"], destino) for i, l in enumerate(livros))
    stats = (f'<div><strong>{n}</strong>livros monitorados</div>'
             f'<div><strong>{len(promo)}</strong>abaixo da média de 30 dias</div>'
             + (f'<div><strong>{len(posts)}</strong>guias de leitura</div>' if posts else ""))
    segundo_cta = ('<a class="btn btn-ghost" href="guias.html">Ler os guias</a>' if posts
                   else '<a class="btn btn-ghost" href="#ofertas">Ver ofertas</a>')

    corpo = f"""<section class="hero"><div class="container">
<span class="eyebrow">Ofertas de livros na Amazon</span>
<h1>Livros de Fantasia e Ficção Científica com preço em queda</h1>
<p>Acompanhamos o preço de {n} livros na Amazon e destacamos o que realmente baixou, com histórico dos últimos 30 dias.</p>
<div class="hero-actions"><a class="btn btn-gold" href="{TELEGRAM_URL}" target="_blank" rel="noopener">{ICONE_TELEGRAM} Entrar no canal do Telegram</a>{segundo_cta}</div>
<div class="stats">{stats}</div>
<p class="atualizado">Última atualização: {agora}</p></div></section>
{bloco_destaques}
{bloco_guias}
<section class="section" id="ofertas" data-filtravel data-passo="24"><div class="container">
<div class="section-head"><div><h2>Todas as ofertas</h2><p>Busque pelo título e filtre pelo que interessa.</p></div></div>
<div class="toolbar" data-barra hidden>
<div class="search">{ICONE_BUSCA}<input type="search" data-busca placeholder="Buscar livro pelo título…" aria-label="Buscar livro pelo título"></div>
<div class="toolbar-row"><div class="chips" role="group" aria-label="Filtros">{"".join(chips)}</div>
<label class="ordem">Ordenar por <select data-ordem><option value="desconto">Maior queda</option><option value="preco-asc">Menor preço</option><option value="preco-desc">Maior preço</option><option value="az">A–Z</option></select></label></div></div>
<p class="count" data-contagem aria-live="polite"></p>
<div class="grid" data-lista>{todos}</div>
<div class="empty" data-vazio hidden><p>Nenhum livro encontrado com esse filtro.</p></div>
<div class="more"><button type="button" class="btn btn-ghost" data-mais hidden>Mostrar mais livros</button></div>
</div></section>"""
    return pagina(
        titulo=f"{NOME_SITE}: ofertas de Fantasia e Ficção Científica",
        descricao=("Promoções de livros de Fantasia e Ficção Científica na Amazon, com histórico de preços "
                   "e guias de leitura sem spoilers."),
        caminho="index.html", corpo=corpo, ativo="ofertas", extra_fim=_DIALOGO,
        imagem=next((l["item"]["imagem_url"] for l in livros if l["item"].get("imagem_url")), ""),
        jsonld=[{"@context": "https://schema.org", "@type": "WebSite", "name": NOME_SITE, "url": BASE_URL,
                 "inLanguage": "pt-BR"}])


def _pagina_guias(posts: list) -> str:
    if posts:
        cards = "".join(card_guia(p, "posts/", i) for i, p in enumerate(posts))
        corpo_lista = (f'<div class="toolbar" data-barra hidden><div class="search">{ICONE_BUSCA}'
                       f'<input type="search" data-busca placeholder="Buscar guia…" aria-label="Buscar guia"></div></div>'
                       f'<p class="count" data-contagem aria-live="polite"></p>'
                       f'<div class="guias-grid" data-lista>{cards}</div>'
                       f'<div class="empty" data-vazio hidden><p>Nenhum guia encontrado.</p></div>'
                       f'<div class="more"><button type="button" class="btn btn-ghost" data-mais hidden>Mostrar mais guias</button></div>')
    else:
        corpo_lista = (f'<div class="empty"><p>Os primeiros guias estão a caminho.</p>'
                       f'<p><a class="btn btn-gold" href="{TELEGRAM_URL}" target="_blank" rel="noopener">'
                       f'Entre no canal para ser avisado</a></p></div>')
    corpo = (f'<div class="container"><div class="page-title"><h1>Guias de leitura</h1>'
             f'<p>Resenhas sem spoilers: sobre o que é cada livro, o ritmo, o clima e para quem ele funciona.</p></div>'
             f'<section class="section" data-filtravel data-passo="24">{corpo_lista}</section></div>')
    return pagina(titulo=f"Guias de leitura de Fantasia e Ficção Científica | {NOME_SITE}",
                  descricao="Resenhas e guias de leitura sem spoilers de livros de Fantasia e Ficção Científica.",
                  caminho="guias.html", corpo=corpo, ativo="guias")


def _pagina_sobre() -> str:
    corpo = f"""<div class="container"><div class="page-title"><h1>Sobre o {NOME_SITE}</h1>
<p>Um site para quem lê Fantasia e Ficção Científica e não quer pagar mais caro do que precisa.</p></div>
<section class="section prose" style="margin-inline:0">
<h2>Como funciona</h2>
<div class="passos">
<div class="passo"><b>1</b><strong>Monitoramos</strong><p>Acompanhamos o preço de uma seleção de livros na Amazon.</p></div>
<div class="passo"><b>2</b><strong>Guardamos o histórico</strong><p>Registramos os preços dos últimos 30 dias para comparar.</p></div>
<div class="passo"><b>3</b><strong>Destacamos quedas</strong><p>Mostramos quem está abaixo da média e avisamos no Telegram.</p></div></div>
<h2>Sobre os números do site</h2>
<p>A "média de 30 dias" é a média dos preços que registramos para aquele livro, e não um preço de tabela da Amazon. O selo "Mínima histórica" aparece quando o preço atual é o menor que já registramos. Preços e estoque mudam rápido: confirme sempre na página da Amazon antes de comprar.</p>
<h2>Guias de leitura</h2>
<p>Os guias são escritos com apoio de inteligência artificial, sem spoilers, a partir do título do livro. Podem conter imprecisões: se notar algum erro, avise pelo Telegram.</p>
<h2>Transparência</h2>
<p>Como Associado da Amazon, o {NOME_SITE} recebe comissão por compras qualificadas, sem custo extra para você. Os links de compra são identificados como patrocinados.</p>
<h2>Contato</h2>
<p><a href="{TELEGRAM_URL}" target="_blank" rel="noopener">Canal @bardodaspromos no Telegram</a></p>
</section></div>"""
    return pagina(titulo=f"Sobre o {NOME_SITE}", caminho="sobre.html", ativo="sobre", corpo=corpo,
                  descricao="Como o Bardo das Promoções monitora preços de livros, como lemos os números e como o site se mantém.")


def _sitemap(posts: list) -> str:
    hoje = datetime.now().strftime("%Y-%m-%d")
    linhas = [f"   <url><loc>{BASE_URL}</loc><lastmod>{hoje}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>",
              f"   <url><loc>{BASE_URL}guias.html</loc><lastmod>{hoje}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>",
              f"   <url><loc>{BASE_URL}sobre.html</loc><lastmod>{hoje}</lastmod><changefreq>yearly</changefreq><priority>0.3</priority></url>"]
    linhas += [f'   <url><loc>{BASE_URL}posts/{p["slug"]}.html</loc><lastmod>{p["date"]}</lastmod>'
               f"<changefreq>monthly</changefreq><priority>0.8</priority></url>" for p in posts]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(linhas) + "\n</urlset>\n")


def gerar_site(ofertas: list, historico: dict, destino: str = ".") -> None:
    raiz = Path(destino)
    livros = []
    for item in ofertas:
        if item.get("preco_atual", 0) > 0:  # sem preço válido, não exibe "R$ 0,00"
            livros.append({"item": item, "info": _info_preco(item, historico)})
    livros.sort(key=lambda l: (-l["info"]["off"], l["item"]["titulo"].lower()))
    posts = artigos.listar_posts()

    salvar_assets_estaticos(destino)
    (raiz / "index.html").write_text(_pagina_home(livros, posts, raiz), encoding="utf-8")
    (raiz / "guias.html").write_text(_pagina_guias(posts), encoding="utf-8")
    (raiz / "sobre.html").write_text(_pagina_sobre(), encoding="utf-8")
    (raiz / "sitemap.xml").write_text(_sitemap(posts), encoding="utf-8")
    for p in posts:  # mantém os artigos com o visual e o "Leia também" atuais
        os.makedirs(artigos.POSTS_DIR, exist_ok=True)
        Path(artigos.POSTS_DIR, f'{p["slug"]}.html').write_text(artigos.renderizar_html(p), encoding="utf-8")
    print(f"🌐 Site gerado: {len(livros)} livros, {len(posts)} guia(s).")
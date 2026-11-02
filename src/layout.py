"""
Layout compartilhado do site (home, guias, sobre e artigos).
Gera o HTML "casca" (head, cabeçalho, rodapé) e fornece o CSS e o JS do site.
"""
import hashlib
import html
import json
from pathlib import Path
from datetime import datetime

BASE_URL = "https://brunomateus28.github.io/bot-amazon-promocoes/"
TELEGRAM_URL = "https://t.me/bardodaspromos"
NOME_SITE = "Bardo das Promoções"
PLACEHOLDER = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 400'%3E"
    "%3Crect width='300' height='400' fill='%23222'/%3E%3Ctext x='150' y='215' font-size='90' "
    "text-anchor='middle'%3E%F0%9F%93%96%3C/text%3E%3C/svg%3E"
)

esc = lambda t: html.escape(str(t), quote=True)

ICONE_TELEGRAM = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                  'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                  '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7z"/></svg>')
ICONE_BUSCA = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
               'stroke-width="2" stroke-linecap="round" aria-hidden="true">'
               '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>')
ICONE_GRAFICO = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                 'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                 '<path d="M3 3v18h18"/><path d="m7 15 4-5 3 3 5-7"/></svg>')

CSS = """
:root{--bg:#0b0b0f;--surface:#14141a;--surface-2:#1c1c24;--border:rgba(255,255,255,.09);
--text:#ececf0;--muted:#a0a0ad;--gold:#ffb300;--gold-ink:#1b1403;--link:#ffb300;
--ok:#34d399;--ok-bg:rgba(52,211,153,.12);--hot:#ffb300;--hot-bg:rgba(255,179,0,.14);
--radius:16px;--shadow:0 12px 32px rgba(0,0,0,.4);color-scheme:dark light}
@media(prefers-color-scheme:light){:root{--bg:#faf9f7;--surface:#fff;--surface-2:#f1efea;
--border:rgba(0,0,0,.1);--text:#1b1b1f;--muted:#63636e;--link:#8a5700;--ok:#047857;
--ok-bg:rgba(4,120,87,.1);--hot:#8a5700;--hot-bg:rgba(255,179,0,.22);--shadow:0 12px 32px rgba(0,0,0,.1)}}
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);min-height:100vh;display:flex;flex-direction:column;
font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
main{flex:1}img{max-width:100%;display:block}a{color:var(--link)}
h1,h2,h3,h4{line-height:1.2;margin:0}
.container{width:min(1200px,100% - 40px);margin-inline:auto}
.skip{position:absolute;left:-999px;top:8px;background:var(--gold);color:var(--gold-ink);
padding:8px 14px;border-radius:8px;z-index:100;font-weight:700}.skip:focus{left:8px}
:focus-visible{outline:3px solid var(--gold);outline-offset:2px;border-radius:6px}
[hidden]{display:none!important}
/* cabeçalho */
.site-header{position:sticky;top:0;z-index:50;border-bottom:1px solid var(--border);
background:color-mix(in srgb,var(--bg) 86%,transparent);-webkit-backdrop-filter:saturate(1.4) blur(12px);
backdrop-filter:saturate(1.4) blur(12px)}
.bar{display:flex;align-items:center;gap:12px;height:64px}
.brand{display:flex;align-items:center;gap:10px;font-weight:800;color:var(--text);text-decoration:none;
letter-spacing:-.01em;font-size:1.05rem;white-space:nowrap}
.logo{display:grid;place-items:center;width:34px;height:34px;border-radius:10px;
background:var(--gold);color:var(--gold-ink);font-size:18px}
.nav{display:flex;gap:2px;margin-left:auto}
.nav a{color:var(--muted);text-decoration:none;font-weight:600;font-size:.95rem;padding:8px 12px;border-radius:10px}
.nav a:hover,.nav a[aria-current=page]{color:var(--text);background:var(--surface-2)}
/* botões */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;font:inherit;font-weight:700;
font-size:.95rem;padding:11px 20px;border-radius:12px;border:1px solid transparent;cursor:pointer;
text-decoration:none;transition:transform .15s,filter .15s,background .15s}
.btn-gold{background:var(--gold);color:var(--gold-ink)}.btn-gold:hover{transform:translateY(-1px);filter:brightness(1.07)}
.btn-ghost{background:transparent;color:var(--text);border-color:var(--border)}.btn-ghost:hover{background:var(--surface-2)}
.btn-sm{padding:9px 14px;font-size:.88rem;border-radius:10px}
@media(max-width:640px){.bar{gap:6px}.brand .full{display:none}.hide-sm{display:none}.nav a{padding:8px 9px}}
/* hero */
.hero{padding:56px 0 28px;background:radial-gradient(60% 90% at 50% -20%,rgba(255,179,0,.16),transparent 70%)}
.eyebrow{display:inline-block;font-size:.78rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
color:var(--hot);background:var(--hot-bg);padding:5px 12px;border-radius:999px;margin-bottom:16px}
.hero h1{font-size:clamp(2rem,5vw,3.2rem);font-weight:800;letter-spacing:-.03em;max-width:20ch}
.hero p{color:var(--muted);font-size:1.1rem;max-width:58ch;margin:16px 0 26px}
.hero-actions{display:flex;flex-wrap:wrap;gap:12px}
.stats{display:flex;flex-wrap:wrap;gap:14px 36px;margin-top:34px;color:var(--muted);font-size:.9rem}
.stats strong{display:block;color:var(--text);font-size:1.6rem;letter-spacing:-.02em;line-height:1.1}
/* seções */
.section{padding:34px 0}
.section-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:20px}
.section-head h2{font-size:1.45rem;letter-spacing:-.015em}
.section-head p{margin:4px 0 0;color:var(--muted);font-size:.95rem}
.section-head a{font-weight:700;font-size:.92rem;text-decoration:none;white-space:nowrap}
.page-title{padding:44px 0 8px}.page-title h1{font-size:clamp(1.8rem,4vw,2.5rem);letter-spacing:-.025em}
.page-title p{color:var(--muted);margin:10px 0 0;max-width:60ch}
/* cards de livro */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:20px}
.feature{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(190px,215px);gap:16px;overflow-x:auto;
scroll-snap-type:x proximity;padding-bottom:12px;margin-inline:-20px;padding-inline:20px;scrollbar-width:thin}
.feature>*{scroll-snap-align:start}
@media(max-width:480px){.grid{grid-template-columns:repeat(2,1fr);gap:12px}.feature{grid-auto-columns:minmax(165px,175px)}}
.card{position:relative;display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--border);
border-radius:var(--radius);overflow:hidden;transition:border-color .2s,transform .2s,box-shadow .2s}
.card:hover{border-color:rgba(255,179,0,.5);transform:translateY(-3px);box-shadow:var(--shadow)}
.thumb{position:relative;aspect-ratio:3/4;background:var(--surface-2);display:grid;place-items:center;padding:16px}
.thumb img{width:100%;height:100%;object-fit:contain;filter:drop-shadow(0 10px 16px rgba(0,0,0,.35))}
.badges{position:absolute;top:10px;left:10px;display:flex;flex-direction:column;gap:6px;align-items:flex-start}
.badge{font-size:.72rem;font-weight:800;padding:4px 9px;border-radius:999px;letter-spacing:.02em;border:1px solid transparent}
.badge-off{background:var(--ok-bg);color:var(--ok);border-color:color-mix(in srgb,var(--ok) 35%,transparent)}
.badge-low{background:var(--hot-bg);color:var(--hot);border-color:color-mix(in srgb,var(--gold) 45%,transparent)}
.card-body{display:flex;flex-direction:column;gap:12px;padding:14px 14px 16px;flex:1}
.card h3{font-size:.95rem;font-weight:600;line-height:1.35;min-height:2.7em;display:-webkit-box;
-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.price{margin-top:auto}.price strong{font-size:1.4rem;letter-spacing:-.02em}
.price small{display:block;color:var(--muted);font-size:.78rem;min-height:1.2em}
.card-actions{display:flex;gap:8px}.card-actions .btn-gold{flex:1}
/* cards de guia */
.guias-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:16px}
.guia{display:flex;gap:14px;align-items:flex-start;padding:14px;background:var(--surface);color:var(--text);
border:1px solid var(--border);border-radius:var(--radius);text-decoration:none;transition:border-color .2s,transform .2s}
.guia:hover{border-color:rgba(255,179,0,.5);transform:translateY(-2px)}
.guia img{width:76px;aspect-ratio:3/4;object-fit:contain;background:var(--surface-2);border-radius:8px;flex:none}
.guia .tag{font-size:.7rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--link)}
.guia h3{font-size:1rem;margin:4px 0 6px;line-height:1.3}
.guia p{margin:0;color:var(--muted);font-size:.88rem;display:-webkit-box;-webkit-line-clamp:3;
-webkit-box-orient:vertical;overflow:hidden}
/* filtros */
.toolbar{display:grid;gap:14px;margin-bottom:22px}
.search{position:relative}.search svg{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--muted)}
.search input{width:100%;font:inherit;color:var(--text);background:var(--surface);border:1px solid var(--border);
border-radius:12px;padding:12px 14px 12px 44px}
.search input::placeholder{color:var(--muted)}
.toolbar-row{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{font:inherit;font-size:.88rem;font-weight:600;color:var(--muted);background:var(--surface);
border:1px solid var(--border);border-radius:999px;padding:7px 15px;cursor:pointer}
.chip:hover{color:var(--text)}.chip[aria-pressed=true]{background:var(--gold);color:var(--gold-ink);border-color:var(--gold)}
.ordem{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:.9rem}
select{font:inherit;font-size:.9rem;color:var(--text);background:var(--surface);border:1px solid var(--border);
border-radius:10px;padding:8px 10px}
.count{color:var(--muted);font-size:.9rem;margin:0 0 16px}
.more{display:flex;justify-content:center;margin-top:30px}
.empty{text-align:center;color:var(--muted);padding:56px 0}
/* diálogo do gráfico */
dialog{border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);color:var(--text);
padding:0;width:min(560px,94vw)}dialog::backdrop{background:rgba(0,0,0,.7)}
.dlg-head{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 16px;
border-bottom:1px solid var(--border)}.dlg-head h3{font-size:.98rem;line-height:1.3}
dialog img{width:100%;background:var(--surface-2)}
/* artigos / texto */
.crumbs{font-size:.85rem;color:var(--muted);margin:26px 0 14px}
.crumbs a{color:var(--muted);text-decoration:none}.crumbs a:hover{color:var(--text)}
.prose{max-width:740px;margin-inline:auto}
.prose h1{font-size:clamp(1.75rem,4vw,2.5rem);letter-spacing:-.025em;font-weight:800}
.post-meta{color:var(--muted);font-size:.9rem;margin:12px 0 24px}
.prose h2{font-size:1.5rem;margin:2.2em 0 .6em;letter-spacing:-.01em;padding-left:12px;border-left:4px solid var(--gold)}
.prose h3{font-size:1.12rem;margin:1.7em 0 .3em}
.prose p,.prose li{font-size:1.06rem;line-height:1.8}
.prose ul,.prose ol{padding-left:1.3em}.prose li{margin:.3em 0}
.prose hr{border:0;border-top:1px solid var(--border);margin:2.4em 0}
.livro-box{display:flex;gap:20px;align-items:center;padding:16px;background:var(--surface);
border:1px solid var(--border);border-radius:var(--radius);margin:0 0 28px}
.livro-box img{width:112px;aspect-ratio:3/4;object-fit:contain;background:var(--surface-2);border-radius:10px;flex:none}
.livro-box strong{display:block;font-size:1.05rem;line-height:1.3;margin-bottom:12px}
.aviso{color:var(--muted);font-size:.78rem;line-height:1.5;margin:10px 0 0}
.compra{text-align:center;margin:36px 0 8px}
.relacionados{max-width:740px;margin:48px auto 0}.relacionados h2{font-size:1.25rem;margin-bottom:16px}
.relacionados .guias-grid{grid-template-columns:1fr}
@media(max-width:520px){.livro-box{flex-direction:column;text-align:center}}
.passos{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));margin:20px 0 4px}
.passo{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:18px}
.passo b{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:var(--gold);
color:var(--gold-ink);margin-bottom:10px}.passo p{margin:6px 0 0;color:var(--muted);font-size:.95rem}
/* rodapé */
.site-footer{border-top:1px solid var(--border);margin-top:56px;padding:38px 0 28px;color:var(--muted);font-size:.9rem}
.foot{display:grid;gap:28px;grid-template-columns:2fr 1fr 1fr}@media(max-width:700px){.foot{grid-template-columns:1fr}}
.site-footer h4{color:var(--text);margin:0 0 10px;font-size:.9rem}
.site-footer a{color:var(--muted);text-decoration:none;display:block;padding:3px 0}.site-footer a:hover{color:var(--text)}
.legal{margin-top:26px;padding-top:18px;border-top:1px solid var(--border);font-size:.8rem;line-height:1.55}
@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
"""

JS = """(function(){
var norm=function(s){return(s||"").toLowerCase().normalize("NFD").replace(/[\\u0300-\\u036f]/g,"")};
var dlg=document.getElementById("dlg-grafico");
if(dlg){document.addEventListener("click",function(e){
  var b=e.target.closest("[data-chart]");
  if(b){var im=dlg.querySelector("img");im.src=b.dataset.chart;im.alt="Histórico de preços: "+b.dataset.title;
    dlg.querySelector("h3").textContent=b.dataset.title;dlg.showModal();return}
  if(e.target.closest("[data-fechar]")||e.target===dlg)dlg.close()})}
var raiz=document.querySelector("[data-filtravel]");if(!raiz)return;
var lista=raiz.querySelector("[data-lista]"),itens=[].slice.call(lista.children);
var busca=raiz.querySelector("[data-busca]"),ordem=raiz.querySelector("[data-ordem]"),
    mais=raiz.querySelector("[data-mais]"),cont=raiz.querySelector("[data-contagem]"),
    vazio=raiz.querySelector("[data-vazio]"),barra=raiz.querySelector("[data-barra]");
var passo=parseInt(raiz.dataset.passo||"24",10),st={q:"",f:"todos",n:passo};
var num=function(el,k){return parseFloat(el.dataset[k])||0};
var ord={desconto:function(a,b){return num(b,"off")-num(a,"off")||num(a,"i")-num(b,"i")},
  "preco-asc":function(a,b){return num(a,"price")-num(b,"price")},
  "preco-desc":function(a,b){return num(b,"price")-num(a,"price")},
  az:function(a,b){return a.dataset.nome<b.dataset.nome?-1:1},
  recentes:function(a,b){return num(a,"i")-num(b,"i")}};
function aplicar(){
  var f=itens.filter(function(el){
    if(st.q&&el.dataset.nome.indexOf(st.q)<0)return false;
    if(st.f==="promo")return num(el,"off")>0;
    if(st.f==="low")return el.dataset.low==="1";
    if(st.f.indexOf("cat:")===0)return el.dataset.cat===st.f.slice(4);
    return true});
  f.sort(ord[ordem?ordem.value:"recentes"]||ord.recentes);
  itens.forEach(function(el){el.hidden=true});
  f.forEach(function(el,i){lista.appendChild(el);el.hidden=i>=st.n});
  var vis=Math.min(st.n,f.length);
  if(cont)cont.textContent=f.length?("Mostrando "+vis+" de "+f.length):"";
  if(mais)mais.hidden=vis>=f.length;
  if(vazio)vazio.hidden=f.length>0}
if(barra)barra.hidden=false;
var t;if(busca)busca.addEventListener("input",function(){clearTimeout(t);t=setTimeout(function(){
  st.q=norm(busca.value.trim());st.n=passo;aplicar()},120)});
if(ordem)ordem.addEventListener("change",function(){st.n=passo;aplicar()});
raiz.addEventListener("click",function(e){
  var c=e.target.closest(".chip");
  if(c){raiz.querySelectorAll(".chip").forEach(function(x){x.setAttribute("aria-pressed",x===c)});
    st.f=c.dataset.f;st.n=passo;aplicar()}
  if(e.target.closest("[data-mais]")){st.n+=passo;aplicar()}});
aplicar()})();
"""

_VERSAO = hashlib.md5((CSS + JS).encode()).hexdigest()[:8]  # força o navegador a baixar CSS/JS novos


def salvar_assets_estaticos(diretorio: str = ".") -> None:
    raiz = Path(diretorio)
    (raiz / "site.css").write_text(CSS, encoding="utf-8")
    (raiz / "site.js").write_text(JS, encoding="utf-8")


def cabecalho(prefixo: str, ativo: str) -> str:
    def link(chave, texto, destino):
        atual = ' aria-current="page"' if chave == ativo else ""
        return f'<a href="{prefixo}{destino}"{atual}>{texto}</a>'
    return f"""<a class="skip" href="#conteudo">Ir para o conteúdo</a>
<header class="site-header"><div class="container bar">
<a class="brand" href="{prefixo}index.html" aria-label="{NOME_SITE}: página inicial"><span class="logo" aria-hidden="true">📖</span><span><span class="full">Bardo das </span>Promoções</span></a>
<nav class="nav" aria-label="Principal">{link("ofertas", "Ofertas", "index.html")}{link("guias", "Guias", "guias.html")}{link("sobre", "Sobre", "sobre.html")}</nav>
<a class="btn btn-gold btn-sm" href="{TELEGRAM_URL}" target="_blank" rel="noopener" aria-label="Entrar no canal do Telegram">{ICONE_TELEGRAM}<span class="hide-sm">Telegram</span></a>
</div></header>"""


def rodape(prefixo: str) -> str:
    return f"""<footer class="site-footer"><div class="container">
<div class="foot">
<div><h4>{NOME_SITE}</h4><p>Acompanhamos o preço de livros de Fantasia e Ficção Científica na Amazon e mostramos o que realmente baixou.</p></div>
<div><h4>Navegue</h4><a href="{prefixo}index.html">Ofertas</a><a href="{prefixo}guias.html">Guias de leitura</a><a href="{prefixo}sobre.html">Sobre o site</a></div>
<div><h4>Fique por dentro</h4><a href="{TELEGRAM_URL}" target="_blank" rel="noopener">Canal no Telegram</a></div>
</div>
<p class="legal">Como Associado da Amazon, o {NOME_SITE} recebe comissão por compras qualificadas, sem custo extra para você. Preços e disponibilidade podem mudar a qualquer momento: confirme sempre na página da Amazon antes de comprar. © {datetime.now().year} {NOME_SITE}.</p>
</div></footer>"""


def card_guia(post: dict, base: str = "posts/") -> str:
    capa = esc(post.get("image") or PLACEHOLDER)
    nome = esc(post.get("book") or post["title"])
    return (f'<a class="guia" href="{base}{esc(post["slug"])}.html" data-nome="" data-i="">'
            f'<img src="{capa}" alt="Capa do livro {nome}" width="76" height="101" loading="lazy" decoding="async">'
            f'<div><span class="tag">Guia de leitura</span><h3>{esc(post["title"])}</h3>'
            f'<p>{esc(post["description"])}</p></div></a>')


def pagina(*, titulo, descricao, caminho, corpo, ativo="", prefixo="", imagem="", tipo="website",
           jsonld=None, extra_fim="") -> str:
    url = BASE_URL + caminho
    og_img = (f'<meta property="og:image" content="{esc(imagem)}">\n'
              f'<meta name="twitter:image" content="{esc(imagem)}">') if imagem else ""
    ld = "".join(f'<script type="application/ld+json">{json.dumps(d, ensure_ascii=False).replace("</", "<\\/")}</script>\n'
                 for d in (jsonld or []))
    favicon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%F0%9F%93%96%3C/text%3E%3C/svg%3E"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0b0b0f">
<title>{esc(titulo)}</title>
<meta name="description" content="{esc(descricao)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="{url}">
<link rel="icon" href="{favicon}">
<meta property="og:type" content="{tipo}">
<meta property="og:site_name" content="{NOME_SITE}">
<meta property="og:locale" content="pt_BR">
<meta property="og:title" content="{esc(titulo)}">
<meta property="og:description" content="{esc(descricao)}">
<meta property="og:url" content="{url}">
<meta name="twitter:card" content="{'summary_large_image' if imagem else 'summary'}">
<meta name="twitter:title" content="{esc(titulo)}">
<meta name="twitter:description" content="{esc(descricao)}">
{og_img}
{ld}<link rel="stylesheet" href="{prefixo}site.css?v={_VERSAO}">
</head>
<body>
{cabecalho(prefixo, ativo)}
<main id="conteudo">
{corpo}
</main>
{rodape(prefixo)}
{extra_fim}
<script src="{prefixo}site.js?v={_VERSAO}" defer></script>
</body>
</html>
"""
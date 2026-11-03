"""
Ajusta o bot.py para o novo site (src/site.py).

Uso, na raiz do repositório:
    python aplicar_redesign.py            # edita ./bot.py
    python aplicar_redesign.py caminho/bot.py

- Cria bot.py.bak antes de alterar. Só grava se tudo encaixar. Pode rodar de novo.
- Funciona tanto com o bot.py original quanto com o que já usa src.layout.
"""
import re
import shutil
import sys

caminho = sys.argv[1] if len(sys.argv) > 1 else "bot.py"
with open(caminho, "r", encoding="utf-8-sig") as f:  # aceita BOM e CRLF
    s = f.read()

if "from src.site import gerar_site" in s:
    print("✅ Já aplicado anteriormente. Nada a fazer.")
    sys.exit(0)

NOVA_FUNCAO = '''def gerar_site_estatico(ofertas, historico):
    """Gera index, guias, sobre, CSS/JS, artigos e sitemap (ver src/site.py)."""
    gerar_site(ofertas, historico)


'''

try:
    # 1) imports
    novas, inserido = [], False
    for linha in s.split("\n"):
        if linha.startswith(("from src.artigos import", "from src.layout import")):
            if not inserido:
                novas += ["from src.artigos import gerar_artigo_do_dia", "from src.site import gerar_site"]
                inserido = True
            continue
        novas.append(linha)
    if not inserido:
        raise ValueError("não achei 'from src.artigos import' no bot.py")
    s = "\n".join(novas)

    # 2) troca a geração antiga (sitemap + cards + página única) pela nova
    ini = s.index("def gerar_sitemap():")
    fim = s.index("# ====", s.index("def gerar_site_estatico"))
    s = s[:ini] + NOVA_FUNCAO + s[fim:]

    # 3) coluna opcional "categoria" na planilha (vira filtro no site)
    s, n = re.subn(r'("url": url, "imagem_url": imagem_url)(\s*\})',
                   r'\1, "categoria": linha_limpa.get("categoria", "")\2', s, count=1)
    if n == 0:
        print("⚠️ Não consegui ligar a coluna opcional 'categoria' (o resto funciona normalmente).")
except ValueError as e:
    print(f"❌ Nada foi alterado: {e}.\nO bot.py mudou em relação ao esperado. Me envie o arquivo atual.")
    sys.exit(1)

shutil.copyfile(caminho, caminho + ".bak")
with open(caminho, "w", encoding="utf-8") as f:
    f.write(s)
print(f"✅ bot.py atualizado (backup em {caminho}.bak).")
import os
import tempfile
import unittest
from pathlib import Path

from bot import gerar_site_estatico
from src.artigos import renderizar_html


class LayoutIntegrationTests(unittest.TestCase):
    def test_renderizar_html_usa_o_layout_compartilhado(self):
        post = {
            "title": "O Nome do Vento",
            "description": "Uma resenha do livro O Nome do Vento.",
            "keywords": ["fantasia", "resenha", "livros"],
            "slug": "o-nome-do-vento",
            "date": "2026-11-02",
            "book": "O Nome do Vento",
            "url": "https://example.com/oferta",
            "image": "https://example.com/capa.jpg",
            "corpo": "## Sobre o livro\n\nTexto de exemplo para verificar a renderização.",
        }

        html = renderizar_html(post)

        self.assertIn('class="site-header"', html)
        self.assertIn('site.css?v=', html)
        self.assertNotIn('tailwind', html.lower())

    def test_gerar_site_estatico_usa_o_layout_compartilhado(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmp_dir)
                ofertas = [{
                    "id": "livro-1",
                    "titulo": "Livro de Teste",
                    "preco_atual": 39.90,
                    "url": "https://example.com/livro",
                    "imagem_url": "https://example.com/capa.jpg",
                }]

                gerar_site_estatico(ofertas, {})

                index_text = Path("index.html").read_text(encoding="utf-8")
                self.assertIn('class="site-header"', index_text)
                self.assertIn('site.css?v=', index_text)
                self.assertNotIn('tailwind', index_text.lower())
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()

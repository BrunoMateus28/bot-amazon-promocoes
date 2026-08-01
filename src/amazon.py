import os
from amazon_paapi import AmazonApi

def buscar_promocoes(keywords="livros", search_index="Books"):
    """Busca produtos em oferta na Amazon baseados em uma palavra-chave."""
    try:
        amazon = AmazonApi(
            os.getenv("AMAZON_ACCESS_KEY"),
            os.getenv("AMAZON_SECRET_KEY"),
            os.getenv("AMAZON_TAG"),
            country="BR"
        )
        
        produtos = amazon.search_items(
            keywords=keywords,
            search_index=search_index,
            item_count=3
        )
        
        lista_produtos = []
        if produtos and sorted(produtos):
            for produto in produtos:
                lista_produtos.append({
                    "titulo": produto.item_info.title.display_value,
                    "url": produto.detail_page_url,
                    "preco": produto.offers.listings[0].price.display_amount if produto.offers else "Ver no site"
                })
        return lista_produtos
    except Exception as e:
        print(f"Erro ao buscar na Amazon: {e}")
        return []

def buscar_capa_por_titulo(titulo):
    """Usa a PA-API da Amazon para buscar a URL da capa oficial em alta resolução."""
    try:
        amazon = AmazonApi(
            os.getenv("AMAZON_ACCESS_KEY"),
            os.getenv("AMAZON_SECRET_KEY"),
            os.getenv("AMAZON_TAG"),
            country="BR"
        )
        # Pesquisa pelo nome exato do livro
        produtos = amazon.search_items(keywords=titulo, search_index="Books", item_count=1)
        
        # Extrai a URL da imagem em resolução 'Large' (perfeita para o banner)
        if produtos and getattr(produtos[0], 'images', None) and getattr(produtos[0].images, 'primary', None):
            return produtos[0].images.primary.large.url
            
    except Exception as e:
        print(f"⚠️ Erro ao buscar capa na API da Amazon para '{titulo[:20]}...': {e}")
    return None
import os
from amazon_paapi import AmazonAPI

def buscar_promocoes(keywords="livros", search_index="Books"):
    """Busca produtos em oferta na Amazon baseados em uma palavra-chave."""
    try:
        amazon = AmazonAPI(
            os.getenv("AMAZON_ACCESS_KEY"),
            os.getenv("AMAZON_SECRET_KEY"),
            os.getenv("AMAZON_TAG"),
            country="BR"
        )
        
        # Busca itens recomendados ou com desconto
        produtos = amazon.search_items(
            keywords=keywords,
            search_index=search_index,
            item_count=3  # Limita a 3 produtos por execução
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
        print(format(f"Erro ao buscar na Amazon: {e}"))
        return []
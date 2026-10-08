"""
lojas.py — Configuração das lojas suportadas.

Para adicionar uma loja nova, basta incluir uma entrada no dicionário LOJAS:
    "dominio.com.br": {
        "nome": "Nome bonito",
        "seletores": ["css do preço 1", "css do preço 2", ...],
    }

Os seletores são tentados em ordem e só entram em ação se a página NÃO tiver
o preço em JSON-LD ou meta tags (que são mais estáveis).
Cada seletor pode apontar para:
  - um elemento cujo TEXTO é o preço ("R$ 1.299,90");
  - um elemento com atributo "content" (meta/itemprop) contendo o preço.

O bloco "busca" de cada loja configura a BUSCA DE PRESAS (busca.py):
    "url":         URL de busca; {termo} é trocado pelo texto digitado
                   (o gato usa a URL de busca em vez de digitar na barra: é mais estável)
    "separador":   como as palavras são unidas na URL ("-" ou "+")
    "cartao":      CSS de cada cartão de resultado
    "titulo":      CSS do título dentro do cartão
    "preco":       CSS do preço ATUAL (o "por"); se casar vários elementos,
                   os textos são unidos (ex.: "R$" + "123,90")
    "fracao"/"centavos": opcionais, para lojas que quebram o preço em partes
    "link":        CSS do link (None = o próprio cartão é o <a>)
    "imagem":      CSS da foto
    "patrocinado": CSS e/ou textos que denunciam anúncio pago (o gato pula)
"""

from urllib.parse import urlparse

LOJAS: dict[str, dict] = {
    "mercadolivre.com.br": {
        "nome": "Mercado Livre",
        "seletores": [
            # Preço principal da página do produto (o primeiro .andes-money-amount
            # dentro do bloco de preço atual; o riscado fica em <s>)
            "div.ui-pdp-price__second-line span.andes-money-amount",
            "div.ui-pdp-price__main-container span.andes-money-amount:not(.andes-money-amount--previous)",
            "meta[itemprop='price']",
        ],
        # O Mercado Livre separa reais e centavos em spans diferentes
        "fracao": "span.andes-money-amount__fraction",
        "centavos": "span.andes-money-amount__cents",
        "busca": {
            "url": "https://lista.mercadolivre.com.br/{termo}",
            "separador": "-",
            "cartao": "li.ui-search-layout__item",
            "titulo": ".poly-component__title",
            # Preço "por": fica em .poly-price__current; o "de" fica num <s> à parte
            "preco": ".poly-price__current .andes-money-amount",
            "fracao": "span.andes-money-amount__fraction",
            "centavos": "span.andes-money-amount__cents",
            "link": "a.poly-component__title",
            "imagem": "img.poly-component__picture, img",
            "patrocinado": {"seletor": ".poly-component__ads-promotions", "textos": ["Patrocinado"]},
        },
    },
    "amazon.com.br": {
        "nome": "Amazon",
        "seletores": [
            # Preço atual do bloco principal; o riscado ("De:") fica em .a-text-price
            "#corePrice_feature_div span.a-price:not(.a-text-price) span.a-offscreen",
            "#corePriceDisplay_desktop_feature_div span.a-price:not(.a-text-price) span.a-offscreen",
        ],
        "busca": {
            "url": "https://www.amazon.com.br/s?k={termo}",
            "separador": "+",
            "cartao": "div[data-component-type='s-search-result']",
            "titulo": "h2",
            # a-offscreen guarda o preço completo ("R$ 227,99"); .a-text-price é o riscado.
            # Só o bloco price-recipe: o "multi-offer-display" é o preço de OUTRAS ofertas.
            "preco": "[data-cy='price-recipe'] span.a-price:not(.a-text-price) span.a-offscreen",
            "link": "a:has(h2), h2 a",
            "imagem": "img.s-image",
            # Anúncios da Amazon passam por /sspa/click e levam o selo "Patrocinado"
            "patrocinado": {"seletor": "a[href*='/sspa/click'], .puis-sponsored-label-text",
                            "textos": ["Patrocinado"]},
        },
    },
    "kabum.com.br": {
        "nome": "KaBuM!",
        "seletores": [
            # Layout atual (2026): o preço é um web component <number-flow-react>
            # com o valor num JSON no atributo "data". O 1º da página é o preço à vista.
            "number-flow-react",
            # Layout antigo, mantido como reserva
            "h4.finalPrice",
            "[class*='finalPrice']",
            "b.regularPrice",
            "[class*='regularPrice']",
        ],
        "busca": {
            "url": "https://www.kabum.com.br/busca/{termo}",
            "separador": "-",
            # Layout Tailwind (2026): o cartão inteiro é um <a href="/produto/...">
            "cartao": "main a[href*='/produto/']",
            "titulo": "span.line-clamp-2",
            # O "de" fica em span.line-through; o "por" em dois spans: "R$" + "123,90"
            "preco": "span.text-base.font-semibold",
            "link": None,
            "imagem": "img",
            "patrocinado": {"seletor": None, "textos": ["Patrocinado"]},
        },
    },
    "pichau.com.br": {
        "nome": "Pichau",
        "seletores": ["div[class*='price_vista']"],
        # O JSON-LD da Pichau traz o preço no cartão; a busca mostra o à vista (PIX)
        "css_primeiro": True,
        "busca": {
            "url": "https://www.pichau.com.br/search?q={termo}",
            "separador": "+",
            # Layout Material UI: o cartão é um <a data-cy="list-product">
            "cartao": "a[data-cy='list-product']",
            "titulo": "h2[class*='product_info_title']",
            # price_vista = preço "por" à vista; o "de" fica em .strikeThrough
            # (div: os <span> price_vista_text/_additional são só textos de apoio)
            "preco": "div[class*='price_vista']",
            "link": None,
            "imagem": "img",
            "patrocinado": {"seletor": None, "textos": ["Patrocinado"]},
        },
    },
    "terabyteshop.com.br": {
        "nome": "Terabyte",
        "seletores": ["#valVista", ".product-item__new-price span"],
        "busca": {
            "url": "https://www.terabyteshop.com.br/busca?str={termo}",
            "separador": "+",
            "cartao": "div.product-item__box",
            "titulo": "a.product-item__name h2",
            # O "de" fica num <del> em .product-item__old-price
            "preco": ".product-item__new-price span",
            "link": "a.product-item__name",
            "imagem": "img.image-thumbnail, img",
            "patrocinado": {"seletor": None, "textos": ["Patrocinado"]},
        },
    },
    "epocacosmeticos.com.br": {
        "nome": "Época Cosméticos",
        "seletores": ["[datatype='spotPrice']"],
        "busca": {
            "url": "https://www.epocacosmeticos.com.br/pesquisa?q={termo}",
            "separador": "+",
            "cartao": "div[data-testid='productItemComponent']",
            "titulo": "div[class*='product-item_name']",
            # spotPrice = preço "por"; o "de" fica em .product-price_priceList
            "preco": "span[datatype='spotPrice']",
            # O link passa por um rastreador; limpar_link() extrai o endereço real (parâmetro "ct")
            "link": "a[data-content-item]",
            "imagem": "img",
            "patrocinado": {"seletor": None, "textos": ["Patrocinado"]},
        },
    },
    "kalunga.com.br": {
        "nome": "Kalunga",
        "seletores": [],  # a página do produto traz o preço em JSON-LD
        "busca": {
            "url": "https://www.kalunga.com.br/busca/1?q={termo}",
            "separador": "+",
            "cartao": "div.blocoproduto",
            "titulo": "h2.blocoproduto__title",
            # O parcelado ("3x de R$ 123,00") fica num <p> à parte
            "preco": "span[class*='blocoproduto__pr']",
            "link": "a.blocoproduto__link",
            "imagem": "img.blocoproduto__image, img",
            "patrocinado": {"seletor": None, "textos": ["Patrocinado"]},
        },
    },
    "fastshop.com.br": {
        "nome": "Fast Shop",
        "seletores": [],
        "busca": {
            "url": "https://site.fastshop.com.br/s?q={termo}",
            "separador": "+",
            "cartao": "[data-fs-product-card]",
            "titulo": "[data-fs-product-card-title]",
            # Vários preços no cartão: o principal (o mesmo do JSON-LD da página do produto),
            # o "listing" (riscado) e, fora desse bloco, o preço no cartão e as parcelas
            "preco": "[data-fs-product-card-price-div] span[data-fs-price-variant='selling']",
            "link": "a[data-fs-link]",
            "imagem": "img",
            "patrocinado": {"seletor": None, "textos": ["Patrocinado"]},
        },
    },
    "centauro.com.br": {
        "nome": "Centauro",
        "seletores": ["[data-testid='price-current']"],
        "busca": {
            "url": "https://www.centauro.com.br/busca/{termo}",
            "separador": "-",
            "cartao": "section[data-testid='new-product-listing-card']",
            "titulo": "[data-testid='new-product-name']",
            # price-current = preço "por" no Pix; price-promotion é o riscado
            "preco": "[data-testid='price-current']",
            "link": "a[href*='.html']",
            "imagem": "img",
            "patrocinado": {"seletor": None, "textos": ["Patrocinado"]},
        },
    },
}

# Lojas testadas e deixadas de fora porque bloqueiam o robô:
# Magazine Luiza, Beleza na Web, Netshoes e Shopee.

# Sinais de que a loja barrou o robô (anti-bot, login forçado, captcha).
# Se aparecerem, o gato desiste na hora em vez de esperar o timeout inteiro.
SINAIS_DE_BLOQUEIO = {
    "url": ["account-verification", "/login", "captcha", "/challenge"],
    "titulo": ["não é possível acessar", "access denied", "just a moment",
               "attention required", "acesso negado", "iniciar sessão"],
}

# Seletores genéricos usados quando a loja não está cadastrada
SELETORES_GENERICOS = [
    "[itemprop='price']",
    "[class*='price'] [class*='value']",
    "[data-testid*='price']",
]


def lojas_com_busca() -> list[dict]:
    """Lojas que têm o bloco "busca" configurado, na ordem do dicionário."""
    return [cfg for cfg in LOJAS.values() if cfg.get("busca")]


def identificar_loja(url: str) -> tuple[str, dict]:
    """Descobre a loja pelo domínio do link. Retorna (nome, config)."""
    dominio = urlparse(url).netloc.lower()
    for chave, config in LOJAS.items():
        if dominio == chave or dominio.endswith("." + chave):
            return config["nome"], config
    nome = dominio.removeprefix("www.") or "Loja desconhecida"
    return nome, {"nome": nome, "seletores": SELETORES_GENERICOS}

"""
extrator.py — Extração e conversão de preços a partir do HTML de uma página.

Ordem de tentativa (da fonte mais confiável para a mais frágil):
  1) Dados estruturados JSON-LD (schema.org Product / Offer / AggregateOffer);
  2) Meta tags de preço (itemprop="price", product:price:amount, og:price:amount);
  3) Seletores CSS específicos da loja (configurados em lojas.py).

Este módulo não depende do Selenium: recebe o HTML pronto. Isso facilita
testar a extração isoladamente.
"""

import json
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from .lojas import identificar_loja


@dataclass
class ResultadoExtracao:
    preco: float | None
    metodo: str | None      # "JSON-LD", "meta tag" ou "CSS"
    titulo: str | None = None


# ---------------------------------------------------------------------------
# Conversão de texto -> float
# ---------------------------------------------------------------------------
def converter_preco_br(valor) -> float | None:
    """
    Converte preço em texto para float, aceitando formato brasileiro e o
    formato "de máquina" usado em JSON-LD/meta tags.

        "R$ 1.299,90"  -> 1299.9
        "1.299"        -> 1299.0   (ponto como milhar)
        "1299.90"      -> 1299.9   (ponto como decimal)
        "R$ 49,9"      -> 49.9
        1299.9         -> 1299.9
    """
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor) if valor > 0 else None

    texto = re.sub(r"[^\d,.]", "", str(valor))  # remove "R$", espaços, nbsp...
    texto = texto.strip(".,")
    if not texto or not re.search(r"\d", texto):
        return None

    tem_virgula, tem_ponto = "," in texto, "." in texto
    if tem_virgula and tem_ponto:
        # O separador que aparece por último é o decimal
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")   # 1.299,90
        else:
            texto = texto.replace(",", "")                     # 1,299.90
    elif tem_virgula:
        partes = texto.split(",")
        if len(partes) == 2 and len(partes[1]) <= 2:
            texto = texto.replace(",", ".")                    # 49,90
        else:
            texto = texto.replace(",", "")                     # 1,299
    elif tem_ponto:
        partes = texto.split(".")
        if len(partes) > 2 or len(partes[-1]) == 3:
            texto = texto.replace(".", "")                     # 1.299 / 1.299.000
        # senão: 1299.90 já está no formato do Python

    try:
        preco = float(texto)
    except ValueError:
        return None
    return preco if preco > 0 else None


# ---------------------------------------------------------------------------
# 1) JSON-LD
# ---------------------------------------------------------------------------
def _tipos(no: dict) -> list[str]:
    tipo = no.get("@type", [])
    return [t.lower() for t in (tipo if isinstance(tipo, list) else [tipo]) if isinstance(t, str)]


def _preco_da_oferta(oferta) -> float | None:
    """Lê o preço de um nó Offer/AggregateOffer (ou lista deles)."""
    if isinstance(oferta, list):
        precos = [p for p in (_preco_da_oferta(o) for o in oferta) if p]
        return min(precos) if precos else None
    if not isinstance(oferta, dict):
        return None
    for chave in ("price", "lowPrice"):
        preco = converter_preco_br(oferta.get(chave))
        if preco:
            return preco
    espec = oferta.get("priceSpecification")
    if isinstance(espec, list):
        espec = espec[0] if espec else None
    if isinstance(espec, dict):
        return converter_preco_br(espec.get("price"))
    return None


def _percorrer_jsonld(no, achados: list):
    """Busca recursiva por nós Product (com offers) ou Offer soltos.
    Cada achado é (preco, nome, url) — a url ajuda a escolher a variante certa."""
    if isinstance(no, list):
        for item in no:
            _percorrer_jsonld(item, achados)
    elif isinstance(no, dict):
        tipos = _tipos(no)
        if "offers" in no:
            preco = _preco_da_oferta(no["offers"])
            if preco:
                ofertas = no["offers"]
                url_oferta = ofertas.get("url") if isinstance(ofertas, dict) else None
                achados.append((preco, no.get("name"), no.get("url") or url_oferta))
        elif "offer" in tipos or "aggregateoffer" in tipos:
            preco = _preco_da_oferta(no)
            if preco:
                achados.append((preco, None, no.get("url")))
        for valor in no.values():
            if isinstance(valor, (dict, list)):
                _percorrer_jsonld(valor, achados)


def _id_da_url(url: str | None) -> str:
    """Normaliza a URL para comparação (sem query, fragmento e barra final)."""
    if not url:
        return ""
    return url.split("#")[0].split("?")[0].rstrip("/").lower()


def extrair_jsonld(soup: BeautifulSoup, url: str = "") -> tuple[float | None, str | None]:
    achados: list = []
    for script in soup.find_all("script", type="application/ld+json"):
        conteudo = script.string or script.get_text()
        if not conteudo:
            continue
        try:
            dados = json.loads(conteudo.strip())
        except json.JSONDecodeError:
            continue
        _percorrer_jsonld(dados, achados)
    if not achados:
        return None, None
    # Páginas com variantes (ex.: ProductGroup do Mercado Livre, uma oferta por cor)
    # → prefere a oferta cuja URL é a do próprio link visitado
    alvo = _id_da_url(url)
    for preco, nome, url_oferta in achados:
        if alvo and _id_da_url(url_oferta) == alvo:
            return preco, nome
    preco, nome, _ = achados[0]
    return preco, nome


# ---------------------------------------------------------------------------
# 2) Meta tags
# ---------------------------------------------------------------------------
META_PRECO = [
    {"itemprop": "price"},
    {"property": "product:price:amount"},
    {"property": "og:price:amount"},
]


def extrair_meta(soup: BeautifulSoup) -> float | None:
    for atributos in META_PRECO:
        for tag in soup.find_all(attrs=atributos):
            preco = converter_preco_br(tag.get("content") or tag.get_text(strip=True))
            if preco:
                return preco
    return None


# ---------------------------------------------------------------------------
# 3) Seletores CSS por loja
# ---------------------------------------------------------------------------
def extrair_css(soup: BeautifulSoup, config: dict) -> float | None:
    for seletor in config.get("seletores", []):
        for elemento in soup.select(seletor):
            # Lojas que quebram reais/centavos em spans separados (ex.: Mercado Livre)
            if config.get("fracao"):
                fracao = elemento.select_one(config["fracao"])
                if fracao:
                    centavos = elemento.select_one(config.get("centavos", "")) if config.get("centavos") else None
                    texto = fracao.get_text(strip=True)
                    if centavos:
                        texto += "," + centavos.get_text(strip=True)
                    preco = converter_preco_br(texto)
                    if preco:
                        return preco
            preco = _preco_do_elemento(elemento)
            if preco:
                return preco
    return None


def _preco_do_elemento(elemento) -> float | None:
    """Lê o preço de um elemento: atributo content, JSON do atributo data ou texto."""
    if elemento.get("content"):
        return converter_preco_br(elemento["content"])
    # Web components como <number-flow-react> (KaBuM!) guardam o valor num JSON no
    # atributo "data" — o texto visível fica no shadow DOM, fora do HTML
    if elemento.get("data", "").startswith("{"):
        try:
            dados = json.loads(elemento["data"])
            preco = converter_preco_br(dados.get("value") or dados.get("valueAsString"))
            if preco:
                return preco
        except json.JSONDecodeError:
            pass
    return converter_preco_br(elemento.get_text(" ", strip=True))


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------
def extrair_preco(html: str, url: str) -> ResultadoExtracao:
    """Tenta JSON-LD → meta tags → CSS e devolve o primeiro preço válido."""
    soup = BeautifulSoup(html, "html.parser")
    titulo = soup.title.get_text(strip=True) if soup.title else None
    _, config = identificar_loja(url)

    # Lojas cujo JSON-LD traz o preço parcelado (e não o à vista mostrado na busca)
    # pedem "css_primeiro": assim a caçada e a busca comparam o mesmo preço.
    if config.get("css_primeiro"):
        preco = extrair_css(soup, config)
        if preco:
            return ResultadoExtracao(preco, "CSS", titulo)

    preco, nome = extrair_jsonld(soup, url)
    if preco:
        return ResultadoExtracao(preco, "JSON-LD", nome or titulo)

    preco = extrair_meta(soup)
    if preco:
        return ResultadoExtracao(preco, "meta tag", titulo)

    preco = extrair_css(soup, config)
    if preco:
        return ResultadoExtracao(preco, "CSS", titulo)

    return ResultadoExtracao(None, None, titulo)

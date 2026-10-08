"""
busca.py — BUSCA DE PRESAS: pesquisa um produto em todas as lojas configuradas.

Fluxo:
  1. para cada loja com bloco "busca" em lojas.py (uma por vez, sem paralelismo):
     abre a URL de busca, espera os cartões de resultado (WebDriverWait)
     e coleta até POR_LOJA resultados válidos;
  2. junta tudo, remove duplicados, ordena do menor para o maior preço
     e devolve no máximo LIMITE_FINAL presas;
  3. para as presas sem foto no cartão, tenta a og:image da página do produto.

Como em robo.py, `buscar_presas()` é um generator que emite eventos para o
log ao vivo da interface. O modo demo (demo.simular_busca) emite os mesmos.

Se uma loja mostrar captcha/bloqueio, o gato NÃO tenta burlar: registra o
"chega pra lá" e segue para a próxima.
"""

import difflib
import random
import re
import time
import unicodedata
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from . import persona
from .extrator import converter_preco_br
from .lojas import lojas_com_busca
from .robo import LojaBloqueouError, NavegadorGato, evento, pagina_bloqueada

POR_LOJA = 5            # quantos resultados válidos coletar de cada loja
LIMITE_FINAL = 10       # quantas presas mostrar no fim (as mais baratas)
TIMEOUT_BUSCA = 20      # segundos de espera explícita pelos cartões
MAX_FOTOS_EXTRAS = 4    # quantas páginas de produto visitar atrás da og:image
# Frases que as lojas mostram quando a busca não acha nada (a espera termina na hora)
SEM_RESULTADOS = ("não encontramos", "nenhum resultado", "não encontrou", "sem resultados",
                  "nenhum produto encontrado")
LIMIAR_SIMILARIDADE = 0.85  # difflib: "bluetoth" ~ "bluetooth" (só palavras de 5+ letras)


@dataclass
class Presa:
    titulo: str
    preco: float
    loja: str
    link: str
    imagem: str | None = None
    relevancia: float = 0.0

    def como_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Texto: normalização e relevância
# ---------------------------------------------------------------------------
# Palavras que não ajudam a decidir se o resultado tem a ver com a busca
STOPWORDS = {"de", "da", "do", "das", "dos", "para", "pra", "com", "sem", "e", "o", "a",
             "os", "as", "em", "no", "na", "um", "uma", "kit", "novo", "original"}

# Acessórios que costumam "pegar carona" na busca (buscar "fone JBL" e vir
# "Almofada para JBL Tune"). Se uma dessas palavras aparece no COMEÇO do título
# e o usuário não pediu por ela, o resultado é descartado.
ACESSORIOS = {"capa", "capinha", "case", "pelicula", "almofada", "almofadas", "espuma",
              "espumas", "protetor", "suporte", "adesivo", "skin", "estojo", "bolsa",
              "cabo", "adaptador", "controle", "refil", "peca", "pecas"}


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos e sem pontuação: "Fone JBL Tune-520!" → "fone jbl tune 520"."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def palavras_chave(texto: str) -> list[str]:
    return [p for p in normalizar(texto).split() if p not in STOPWORDS and len(p) > 1]


def _palavra_presente(palavra: str, titulo_norm: str, palavras_titulo: list[str]) -> bool:
    """
    A palavra do termo aparece no título?
      - números/modelos ("520", "s23") precisam aparecer literalmente
        (também vale grudado, como "tune520bt");
      - palavras curtas (até 3 letras, ex.: "jbl") só valem iguais;
      - plural/sufixo curto vale ("fone" → "fones");
      - palavras de 5+ letras toleram erro de digitação pelo difflib
        ("bluetoth" ~ "bluetooth"). Isso evita falsos positivos como
        "fone" ~ "one" ou "jbl" ~ "bl", que o difflib acharia parecidos.
    """
    if any(c.isdigit() for c in palavra):
        return palavra in titulo_norm.replace(" ", "")
    if palavra in palavras_titulo:
        return True
    if len(palavra) <= 3:
        return False
    for p in palavras_titulo:
        if p.startswith(palavra) and len(p) - len(palavra) <= 2:
            return True
        if (len(palavra) >= 5 and p[:1] == palavra[:1]
                and difflib.SequenceMatcher(None, palavra, p).ratio() >= LIMIAR_SIMILARIDADE):
            return True
    return False


def relevancia(termo: str, titulo: str) -> float:
    """
    Nota de 0 a 1 de quanto o título tem a ver com o termo buscado.

    Combina duas medidas simples:
      - cobertura (peso 85%): fração das palavras-chave do termo encontradas no
        título (com tolerância a plural/erro de digitação via difflib);
      - similaridade geral (peso 15%): difflib.SequenceMatcher entre o termo e o
        começo do título, só para desempatar resultados parecidos.
    """
    chaves = palavras_chave(termo)
    if not chaves:
        return 1.0
    titulo_norm = normalizar(titulo)
    palavras_titulo = titulo_norm.split()
    encontradas = sum(_palavra_presente(p, titulo_norm, palavras_titulo) for p in chaves)
    cobertura = encontradas / len(chaves)
    similaridade = difflib.SequenceMatcher(None, normalizar(termo),
                                           titulo_norm[: len(termo) + 20]).ratio()
    return round(0.85 * cobertura + 0.15 * similaridade, 3)


def e_relevante(termo: str, titulo: str) -> bool:
    """
    Regra de corte:
      - termos curtos (até 2 palavras-chave): TODAS precisam aparecer;
      - termos longos: pelo menos 2/3 das palavras-chave;
      - e o título não pode começar com um acessório que o usuário não pediu.
    """
    chaves = palavras_chave(termo)
    titulo_norm = normalizar(titulo)
    palavras_titulo = titulo_norm.split()
    encontradas = sum(_palavra_presente(p, titulo_norm, palavras_titulo) for p in chaves)
    minimo = len(chaves) if len(chaves) <= 2 else -(-2 * len(chaves) // 3)  # teto de 2/3
    if encontradas < minimo:
        return False
    # Números/modelos são obrigatórios: buscar "tune 520" não deve trazer "tune 510"
    modelos = [p for p in chaves if any(c.isdigit() for c in p)]
    if not all(_palavra_presente(m, titulo_norm, palavras_titulo) for m in modelos):
        return False
    inicio_titulo = set(palavras_titulo[:3])
    acessorio = (inicio_titulo & ACESSORIOS) - set(chaves)
    return not acessorio


# ---------------------------------------------------------------------------
# Fotos
# ---------------------------------------------------------------------------
PLACEHOLDERS = ("blank", "placeholder", "spacer", "loading", "lazy", "transparent", "1x1", "pixel")


def imagem_valida(url: str | None) -> bool:
    """Descarta placeholders de lazy loading (base64 minúsculo, "blank", "placeholder"...)."""
    if not url:
        return False
    url = url.strip()
    if url.startswith("data:"):
        return len(url) > 2000  # base64 pequeno = gif/png 1x1 de placeholder
    if not url.startswith(("http://", "https://", "//")):
        return False
    nome = url.lower().rsplit("/", 1)[-1]
    return not any(p in nome for p in PLACEHOLDERS)


def _maior_do_srcset(srcset: str) -> str | None:
    """'a.webp 320w, b.webp 640w' → 'b.webp' (a de maior resolução)."""
    candidatos = []
    for parte in srcset.split(","):
        pedacos = parte.strip().split()
        if not pedacos:
            continue
        peso = 0
        if len(pedacos) > 1:
            numero = re.sub(r"[^\d.]", "", pedacos[1])
            peso = float(numero) if numero else 0
        candidatos.append((peso, pedacos[0]))
    return max(candidatos)[1] if candidatos else None


def url_da_imagem(img, base: str) -> str | None:
    """Ordem de tentativa: data-src → data-original → srcset → src."""
    if img is None:
        return None
    for atributo in ("data-src", "data-original", "data-lazy-src", "srcset", "data-srcset", "src"):
        valor = img.get(atributo)
        if not valor:
            continue
        if "srcset" in atributo:
            valor = _maior_do_srcset(valor)
        if valor and valor.startswith("//"):
            valor = "https:" + valor
        elif valor and valor.startswith("/"):
            valor = urljoin(base, valor)
        if imagem_valida(valor):
            return valor
    return None


# ---------------------------------------------------------------------------
# Extração dos cartões (sem Selenium: recebe o HTML pronto — fácil de testar)
# ---------------------------------------------------------------------------
def _texto(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def _preco_do_cartao(cartao, cfg: dict) -> float | None:
    elementos = cartao.select(cfg["preco"]) if cfg.get("preco") else []
    if not elementos:
        return None
    if cfg.get("fracao"):
        # Lojas que separam reais e centavos (Mercado Livre): usa o 1º preço do bloco "por"
        bloco = elementos[0]
        fracao = bloco.select_one(cfg["fracao"])
        if fracao:
            centavos = bloco.select_one(cfg["centavos"]) if cfg.get("centavos") else None
            texto = _texto(fracao) + ("," + _texto(centavos) if centavos else "")
            return converter_preco_br(texto)
    # Se o 1º elemento já tem um preço completo, ele basta (os seguintes podem ser parcelas).
    # Senão, junta os dois primeiros: KaBuM! → ["R$", "123,90"] vira "R$ 123,90"
    texto = _texto(elementos[0])
    if not re.search(r"\d,\d{2}", texto):
        texto = " ".join(_texto(e) for e in elementos[:2])
    # Se o texto tiver "de R$ X por R$ Y", fica com o último valor (o "por")
    valores = re.findall(r"\d[\d.]*,\d{2}|\d[\d.]*", texto)
    return converter_preco_br(valores[-1]) if valores else None


def _patrocinado(cartao, cfg: dict) -> bool:
    regra = cfg.get("patrocinado") or {}
    if regra.get("seletor") and cartao.select_one(regra["seletor"]):
        return True
    textos = regra.get("textos") or []
    return any(cartao.find(string=lambda s, t=t: s and s.strip() == t) for t in textos)


def limpar_link(link: str) -> str:
    """
    Remove o fragmento (#rastreio) — o mesmo produto fica com o mesmo link.
    Links de rastreador de clique (ex.: Época Cosméticos) trazem o endereço
    real no parâmetro "ct": nesse caso, usamos ele direto.
    """
    destino = parse_qs(urlparse(link).query).get("ct", [""])[0]
    if destino.startswith("http"):
        link = destino
    return link.split("#")[0]


def extrair_resultados(html: str, cfg_loja: dict, termo: str) -> tuple[list[Presa], dict]:
    """
    Lê a página de busca e devolve (presas_validas, contagem_de_descartes).
    Pula: anúncios patrocinados, itens sem preço e itens irrelevantes.
    """
    cfg = cfg_loja["busca"]
    base = cfg["url"].split("/{termo}")[0]
    soup = BeautifulSoup(html, "html.parser")
    presas: list[Presa] = []
    descartes = {"patrocinado": 0, "sem_preco": 0, "irrelevante": 0}

    for cartao in soup.select(cfg["cartao"]):
        titulo = _texto(cartao.select_one(cfg["titulo"]))
        if not titulo:
            continue
        if _patrocinado(cartao, cfg):
            descartes["patrocinado"] += 1
            continue
        preco = _preco_do_cartao(cartao, cfg)
        if not preco:
            descartes["sem_preco"] += 1
            continue
        if not e_relevante(termo, titulo):
            descartes["irrelevante"] += 1
            continue

        link_el = cartao.select_one(cfg["link"]) if cfg.get("link") else cartao
        href = link_el.get("href") if link_el else None
        if not href:
            continue
        presas.append(Presa(
            titulo=titulo,
            preco=preco,
            loja=cfg_loja["nome"],
            link=limpar_link(urljoin(base, href)),
            imagem=url_da_imagem(cartao.select_one(cfg["imagem"]), base),
            relevancia=relevancia(termo, titulo),
        ))
        if len(presas) >= POR_LOJA:
            break
    return presas, descartes


# ---------------------------------------------------------------------------
# Consolidação
# ---------------------------------------------------------------------------
def consolidar(presas: list[Presa], limite: int = LIMITE_FINAL) -> list[Presa]:
    """
    Remove duplicados, ordena do mais barato ao mais caro e corta no limite.
    Duplicado = mesmo link, OU mesma loja com título quase igual (≥ 92% no
    difflib) e mesmo preço (o mesmo anúncio repetido na página).
    O mesmo produto em lojas DIFERENTES não é duplicado: é comparação de preço!
    """
    unicas: list[Presa] = []
    links = set()
    for presa in sorted(presas, key=lambda p: (p.preco, -p.relevancia)):
        if presa.link in links:
            continue
        repetida = any(
            u.loja == presa.loja and abs(u.preco - presa.preco) < 0.01
            and difflib.SequenceMatcher(None, normalizar(u.titulo), normalizar(presa.titulo)).ratio() >= 0.92
            for u in unicas
        )
        if repetida:
            continue
        links.add(presa.link)
        unicas.append(presa)
    return unicas[:limite]


# ---------------------------------------------------------------------------
# Navegação (Selenium)
# ---------------------------------------------------------------------------
def montar_url(cfg_busca: dict, termo: str) -> str:
    separador = cfg_busca.get("separador", "-")
    palavras = normalizar(termo).split() if separador == "-" else termo.split()
    return cfg_busca["url"].format(termo=separador.join(quote_plus(p) for p in palavras))


def _esperar_resultados(driver, cfg_busca: dict, timeout: int) -> None:
    """Espera explícita: até aparecerem cartões, a página de 'sem resultados' ou um bloqueio."""
    tentativas = {"n": 0}

    def pronto(d):
        if pagina_bloqueada(d):
            raise LojaBloqueouError("captcha/bloqueio")
        if d.find_elements(By.CSS_SELECTOR, cfg_busca["cartao"]):
            return True
        # Ler o texto visível (innerText) é caro: só confere "sem resultados" a cada 4 tentativas.
        # (textContent seria mais rápido, mas inclui o texto de <script>, que pode ter essas frases)
        tentativas["n"] += 1
        if tentativas["n"] % 4:
            return False
        corpo = (d.execute_script("return document.body ? document.body.innerText : ''") or "").lower()
        return any(s in corpo for s in SEM_RESULTADOS)
    WebDriverWait(driver, timeout, poll_frequency=0.5).until(pronto)
    # Rola a página um pouco para disparar o lazy loading das primeiras fotos
    driver.execute_script("window.scrollBy(0, 900)")
    WebDriverWait(driver, 3).until(lambda d: d.execute_script("return document.readyState") != "loading")


def imagem_acessivel(url: str | None) -> bool:
    """
    Confere se a foto realmente abre (HTTP 200 e Content-Type de imagem).
    O Streamlit remove o "onerror" das <img>, então não dá para trocar a
    foto quebrada no navegador: a checagem é feita aqui, antes de exibir.
    """
    if not url:
        return False
    if url.startswith("data:"):
        return True
    try:
        resposta = requests.get(url, stream=True, timeout=4,
                                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        ok = resposta.ok and resposta.headers.get("Content-Type", "").startswith("image/")
        resposta.close()
        return ok
    except requests.RequestException:
        return False


def _og_image(driver, link: str) -> str | None:
    try:
        driver.get(link)
        WebDriverWait(driver, 10).until(
            lambda d: pagina_bloqueada(d) or d.find_elements(By.CSS_SELECTOR, "meta[property='og:image']"))
        if pagina_bloqueada(driver):
            return None
        meta = driver.find_element(By.CSS_SELECTOR, "meta[property='og:image']")
        url = meta.get_attribute("content")
        return url if imagem_valida(url) and imagem_acessivel(url) else None
    except (TimeoutException, WebDriverException):
        return None


def buscar_presas(termo: str, headless: bool = False) -> Iterator[dict]:
    """Executa a busca real em cada loja, uma por vez, emitindo eventos para o log."""
    termo = (termo or "").strip()
    yield evento("log", persona.fala("busca_inicio", termo=termo))
    todas: list[Presa] = []
    lojas_ok, lojas_falha = [], []

    try:
        with NavegadorGato(headless=headless, timeout=TIMEOUT_BUSCA) as navegador:
            if navegador.falhas:
                yield evento("log", f"O Chrome não quis brincar (bloqueado pelo Windows?). "
                             f"Vou de {navegador.nome}. 😼", "aviso", detalhe=navegador.falhas[0])
            driver = navegador.driver
            for i, cfg_loja in enumerate(lojas_com_busca()):
                loja = cfg_loja["nome"]
                if i > 0:
                    time.sleep(random.uniform(1.0, 2.0))  # pausa educada entre as lojas
                yield evento("loja", persona.fala("loja_espreitando", loja=loja), "info", loja=loja)
                try:
                    for tentativa in range(2):
                        try:
                            driver.get(montar_url(cfg_loja["busca"], termo))
                        except TimeoutException:
                            pass  # página pesada: seguimos com o que já carregou
                        try:
                            _esperar_resultados(driver, cfg_loja["busca"], TIMEOUT_BUSCA)
                            break
                        except LojaBloqueouError:
                            if tentativa:
                                raise
                            # Bloqueio costuma ser passageiro: espera um pouco e tenta 1 vez mais
                            yield evento("log", persona.fala("loja_nova_tentativa", loja=loja), "aviso")
                            time.sleep(random.uniform(4.0, 7.0))
                    presas, descartes = extrair_resultados(driver.page_source, cfg_loja, termo)
                except LojaBloqueouError:
                    lojas_falha.append(loja)
                    yield evento("erro", persona.fala("loja_bloqueio", loja=loja), "erro", loja=loja,
                                 detalhe=f"página de bloqueio: {driver.title[:80]}")
                    continue
                except (TimeoutException, WebDriverException) as erro:
                    lojas_falha.append(loja)
                    yield evento("erro", persona.fala("loja_erro", loja=loja), "erro", loja=loja,
                                 detalhe=(getattr(erro, "msg", None) or erro.__class__.__name__)[:150])
                    continue

                lojas_ok.append(loja)
                total_descartes = sum(descartes.values())
                if presas:
                    yield evento("log", persona.fala("loja_avistadas", loja=loja, n=len(presas)),
                                 "sucesso", loja=loja, n=len(presas))
                else:
                    yield evento("log", persona.fala("loja_vazia", loja=loja, termo=termo), "aviso", loja=loja)
                if total_descartes:
                    yield evento("log", persona.fala("loja_descartes", n=total_descartes), "info",
                                 detalhe=", ".join(f"{k.replace('_', ' ')}: {v}"
                                                   for k, v in descartes.items() if v))
                todas.extend(presas)

            finais = consolidar(todas)

            # Fotos: valida as do cartão; as que faltam ou não abrem vão atrás
            # da og:image da página do produto (sem foto → o card usa o gato procurando)
            for presa in finais:
                if not imagem_acessivel(presa.imagem):
                    presa.imagem = None
            sem_foto = [p for p in finais if not p.imagem][:MAX_FOTOS_EXTRAS]
            if sem_foto:
                yield evento("log", persona.fala("buscando_fotos"), "info")
                for presa in sem_foto:
                    presa.imagem = _og_image(driver, presa.link)
    except WebDriverException as erro:
        detalhe = (getattr(erro, "msg", None) or str(erro)).splitlines()[0][:200]
        yield evento("erro", "O navegador caiu da estante (ou nem abriu). 🙀", "erro", detalhe=detalhe)
        finais = consolidar(todas)  # aproveita o que já tinha sido coletado

    yield from _eventos_finais(finais, lojas_ok, lojas_falha)


def _eventos_finais(finais: list[Presa], lojas_ok: list[str], lojas_falha: list[str]) -> Iterator[dict]:
    if finais:
        yield evento("log", persona.fala("busca_fim", n=len(finais)), "sucesso")
    else:
        yield evento("log", persona.fala("nenhuma_presa"), "aviso")
    yield evento("resultado", "", "info", presas=[p.como_dict() for p in finais],
                 lojas_ok=lojas_ok, lojas_falha=lojas_falha)

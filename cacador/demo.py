"""
demo.py — Modo Demonstração do Gato Caçador. 🎭

Simula uma caçada completa SEM abrir o navegador, com dados fictícios
realistas e pequenas pausas (para parecer o robô trabalhando). Serve de
plano B para apresentações, caso alguma loja esteja fora do ar ou bloqueie
o robô.

A simulação emite exatamente os mesmos eventos de robo.cacar() e usa as
mesmas regras de negócio (histórico, comparação, alerta no Telegram).
Também gera um histórico fictício de vários dias para o gráfico.
"""

import random
import time
from collections.abc import Iterator
from datetime import datetime, timedelta

import pandas as pd

from . import busca, persona, planilhas
from .lojas import LOJAS, identificar_loja
from .robo import evento, processar_captura, resumo

METODO_DEMO = "Demo 🎭"

# Lista de desejos de exemplo (links reais; metas escolhidas para a demonstração)
LISTA_EXEMPLO = pd.DataFrame([
    {"Produto": "Kindle 11ª Geração (Preto)",
     "Link": "https://www.mercadolivre.com.br/leitor-de-livro-eletronico-kindle-11th-gen-2024-16gb-preto/p/MLB43661868",
     "Preço meta": 650.00},
    {"Produto": "Kindle 11ª Geração (Verde)",
     "Link": "https://www.mercadolivre.com.br/e-reader-kindle-11th-gen-2024-16gb-verde-claro-com-tela-de-6-300ppp/p/MLB46676867",
     "Preço meta": 699.00},
    {"Produto": "Headset HyperX Cloud III",
     "Link": "https://www.kabum.com.br/produto/543665/headset-gamer-hyperx-cloud-iii-driver-53mm-usb-multi-plataformas-preto-727a8aa",
     "Preço meta": 380.00},
    {"Produto": "Headset Razer BlackShark V2 X",
     "Link": "https://www.kabum.com.br/produto/128544/headset-gamer-razer-blackshark-v2-x-drivers-50mm-microfone-cardioide-surround-7-1-3-5-mm-preto-rz04-03240100",
     "Preço meta": 365.00},
])

# Preço "de referência" de cada produto, usado para gerar o histórico fictício
# (próximo dos valores reais observados em out/2026)
PRECO_BASE = {
    "Kindle 11ª Geração (Preto)": 737.27,
    "Kindle 11ª Geração (Verde)": 789.00,
    "Headset HyperX Cloud III": 409.99,
    "Headset Razer BlackShark V2 X": 359.99,
}


def _pausa(minimo: float = 0.6, maximo: float = 1.6) -> None:
    """Pausa curta e variável — só no modo demo, para parecer o robô navegando."""
    time.sleep(random.uniform(minimo, maximo))


def _base(produto: str, meta: float) -> float:
    return PRECO_BASE.get(produto, round(meta * random.uniform(1.10, 1.25), 2))


# ---------------------------------------------------------------------------
# Caçada simulada
# ---------------------------------------------------------------------------
def simular_cacada(lista: pd.DataFrame) -> Iterator[dict]:
    """Simula a caçada: uma queda que bate a meta, uma nova tentativa e um erro."""
    yield evento("log", persona.fala("demo"), "aviso")
    _pausa()
    yield evento("log", persona.fala("acordando"))

    if lista.empty:
        yield evento("log", persona.fala("lista_vazia"), "aviso")
        yield resumo(0, 0, 0, 0)
        return

    _pausa()
    yield evento("log", persona.fala("abrindo_navegador") + " (de mentirinha)")

    total = len(lista)
    # Roteiro da demonstração: quem vai cair na meta, quem dá trabalho e quem falha
    indice_bote = random.randrange(total)
    indice_retry = (indice_bote + 1) % total if total > 1 else None
    indice_erro = (indice_bote + 3) % total if total > 3 else None

    visitados = presas = erros = enviados = 0
    for posicao, (_, item) in enumerate(lista.iterrows()):
        produto, link, meta = item["Produto"], item["Link"], float(item["Preço meta"])
        loja, _ = identificar_loja(link)
        visitados += 1
        _pausa(0.8, 1.8)
        yield evento("log", persona.fala("espreitando", produto=produto) + f"  ({loja})", "info",
                     produto=produto)
        _pausa(1.0, 2.2)

        if posicao == indice_retry:
            yield evento("log", persona.fala("tentando_de_novo", produto=produto), "aviso")
            _pausa(1.0, 2.0)

        if posicao == indice_erro:
            erros += 1
            planilhas.registrar_captura(produto, loja, None, meta, None, planilhas.STATUS_ERRO,
                                        METODO_DEMO, link)
            yield evento("erro", persona.fala("bloqueado", produto=produto), "erro", produto=produto,
                         detalhe="(simulado) a loja pediu verificação anti-robô")
            continue

        historico = planilhas.ler_historico()
        anterior = planilhas.ultimo_preco(produto, historico) or _base(produto, meta)
        if posicao == indice_bote:
            # A presa da demonstração: queda forte, abaixo da meta
            preco = min(meta * random.uniform(0.93, 0.98), anterior * 0.85)
        else:
            # Oscilação normal de preço, sem chegar na meta
            preco = max(anterior * random.uniform(0.99, 1.04), meta * 1.03)
        preco = round(preco, 2)

        for ev in processar_captura(produto, link, meta, loja, preco, METODO_DEMO, historico,
                                    demo=True, alertar=bool(item.get("Alertar", True))):
            presas += ev.get("presa", 0)
            if ev["tipo"] == "alerta" and ev.get("enviado"):
                enviados += 1
            yield ev

    _pausa()
    yield resumo(visitados, presas, erros, enviados)


# ---------------------------------------------------------------------------
# Dados de exemplo
# ---------------------------------------------------------------------------
def gerar_historico_ficticio(lista: pd.DataFrame | None = None, dias: int = 10,
                             semente: int | None = 7) -> pd.DataFrame:
    """
    Cria um histórico fictício (2 capturas por dia) para cada produto da lista,
    com oscilações realistas e algumas quedas. Sobrescreve data/historico.xlsx
    e data/alertas.xlsx.
    """
    rnd = random.Random(semente)
    lista = LISTA_EXEMPLO if lista is None or lista.empty else lista
    agora = datetime.now().replace(second=0, microsecond=0)
    inicio = (agora - timedelta(days=dias)).replace(hour=9, minute=0)

    linhas, alertas_linhas = [], []
    for _, item in lista.iterrows():
        produto, link, meta = item["Produto"], item["Link"], float(item["Preço meta"])
        loja, _ = identificar_loja(link)
        base = _base(produto, meta)
        # Começa mais caro e passeia até perto do preço de referência
        preco = base * rnd.uniform(1.12, 1.20)
        anterior = None
        dia_promo = rnd.randrange(3, dias - 1)  # um dia de "promoção relâmpago"

        for d in range(dias):
            for hora in (9, 18):
                momento = inicio + timedelta(days=d, hours=hora - 9, minutes=rnd.randint(0, 40))
                if momento > agora:
                    continue
                alvo = base * 1.06
                preco += (alvo - preco) * 0.18 + base * rnd.uniform(-0.02, 0.02)
                capturado = preco * (0.91 if d == dia_promo and hora == 18 else 1)
                capturado = round(capturado, 2)

                variacao = (capturado - anterior) / anterior if anterior else None
                if capturado <= meta:
                    status = planilhas.STATUS_META
                elif anterior and capturado < anterior - 0.009:
                    status = planilhas.STATUS_CAIU
                elif anterior is None:
                    status = planilhas.STATUS_PRIMEIRA
                elif capturado > anterior + 0.009:
                    status = planilhas.STATUS_SUBIU
                else:
                    status = planilhas.STATUS_ESTAVEL

                linhas.append({
                    "Data/Hora": momento, "Produto": produto, "Loja": loja,
                    "Preço capturado": capturado, "Preço meta": meta,
                    "Variação (%)": round(variacao * 100, 2) if variacao is not None else None,
                    "Status": status, "Método": METODO_DEMO, "Link": link,
                })
                # Só quedas relevantes (>= 3%) ou meta viram alerta de exemplo
                if status == planilhas.STATUS_META or (variacao is not None and variacao <= -0.03):
                    abertura = persona.fala("bote" if status == planilhas.STATUS_META else "queda",
                                            produto=produto, preco=persona.formatar_reais(capturado),
                                            variacao=persona.formatar_variacao(variacao))
                    alertas_linhas.append({
                        "Data/Hora": momento, "Produto": produto, "Preço": capturado,
                        "Preço meta": meta,
                        "Variação (%)": round(variacao * 100, 2) if variacao is not None else None,
                        "Enviado ao Telegram": "Não (exemplo)", "Mensagem": abertura,
                    })
                anterior = capturado

    historico = pd.DataFrame(linhas, columns=planilhas.COLUNAS_HISTORICO).sort_values("Data/Hora")
    planilhas.salvar_historico(historico)
    alertas_df = pd.DataFrame(alertas_linhas, columns=planilhas.COLUNAS_ALERTAS).sort_values("Data/Hora")
    planilhas.salvar_alertas(alertas_df)
    return historico


def restaurar_dados_exemplo() -> None:
    """Recria lista de desejos, histórico e alertas de exemplo."""
    planilhas.salvar_lista(LISTA_EXEMPLO)
    gerar_historico_ficticio(LISTA_EXEMPLO)


# ---------------------------------------------------------------------------
# Busca de presas simulada
# ---------------------------------------------------------------------------
# Categorias de produto do demo: palavras que identificam a categoria,
# ilustração local (assets/produtos), faixa de preço e variações de título
CATEGORIAS_DEMO = [
    {"chaves": {"fone", "fones", "headset", "headphone", "earbuds", "airpods", "jbl", "tune"},
     "imagem": "produtos/fone.svg", "preco": (89, 420),
     "variacoes": ["Bluetooth 5.3 Preto", "Sem Fio com Microfone, Branco", "Azul - Original",
                   "On-Ear Dobrável, Rosa", "com Cancelamento de Ruído", "Pure Bass, Preto",
                   "Bluetooth, Bateria 40h, Roxo", "Edição Especial, Verde"]},
    {"chaves": {"celular", "smartphone", "iphone", "galaxy", "motorola", "xiaomi", "redmi"},
     "imagem": "produtos/celular.svg", "preco": (899, 3900),
     "variacoes": ["128GB, 8GB RAM, Preto", "256GB, Câmera 50MP, Azul", "128GB 5G, Verde",
                   "256GB, Tela 6.7\", Grafite", "64GB, Dual Chip, Branco", "512GB, Titânio"]},
    {"chaves": {"notebook", "laptop", "macbook", "chromebook", "ultrabook"},
     "imagem": "produtos/notebook.svg", "preco": (1899, 6999),
     "variacoes": ["Intel Core i5, 8GB, SSD 512GB", "Ryzen 7, 16GB, SSD 1TB",
                   "Intel Core i3, 8GB, SSD 256GB, 15.6\"", "Ryzen 5, 8GB, SSD 512GB, Prata",
                   "Core i7, 16GB, RTX 4050", "14\" Full HD, 8GB, Cinza"]},
    {"chaves": {"kindle", "ereader", "leitor", "kobo"},
     "imagem": "produtos/ereader.svg", "preco": (499, 1399),
     "variacoes": ["16GB, Tela 6\" 300ppi, Preto", "16GB, Verde", "Paperwhite 16GB, À Prova D'Água",
                   "11ª Geração, Luz Embutida", "Colorsoft 16GB", "com Capa, Preto"]},
]
CATEGORIA_GENERICA = {"imagem": "produtos/caixa.svg", "preco": (59, 899),
                      "variacoes": ["Original", "Preto", "Branco", "Kit Completo", "Edição 2026",
                                    "Premium", "Compacto", "Azul"]}
# Lojas "gerais" da demonstração (as especializadas, como a Época, ficariam estranhas com qualquer termo)
LOJAS_DEMO = ["Mercado Livre", "Amazon", "KaBuM!"]


def _config_busca(nome_loja: str) -> dict:
    return next(cfg["busca"] for cfg in LOJAS.values() if cfg["nome"] == nome_loja)


def _categoria_demo(termo: str) -> dict:
    palavras = set(busca.normalizar(termo).split())
    for categoria in CATEGORIAS_DEMO:
        if palavras & categoria["chaves"]:
            return categoria
    return CATEGORIA_GENERICA


def simular_busca(termo: str) -> Iterator[dict]:
    """
    Simula a Busca de Presas com resultados fictícios realistas.
    Os números são sorteados com uma semente derivada do termo: a mesma busca
    sempre dá o mesmo resultado (bom para ensaiar o vídeo), e termos diferentes
    rendem quantidades diferentes (alguns com menos de 10 presas).
    """
    termo = (termo or "").strip()
    rnd = random.Random(busca.normalizar(termo))
    categoria = _categoria_demo(termo)
    nome_base = " ".join(p[:1].upper() + p[1:] for p in termo.split())  # respeita "JBL"
    preco_min, preco_max = categoria["preco"]
    preco_ref = rnd.uniform(preco_min, preco_max)

    yield evento("log", persona.fala("demo"), "aviso")
    _pausa(0.5, 1.0)
    yield evento("log", persona.fala("busca_inicio", termo=termo))

    todas: list = []
    for loja in LOJAS_DEMO:
        url_busca = busca.montar_url(_config_busca(loja), termo)
        url_busca += "&" if "?" in url_busca else "?"
        _pausa(0.8, 1.5)
        yield evento("loja", persona.fala("loja_espreitando", loja=loja), "info", loja=loja)
        _pausa(1.0, 2.0)
        quantidade = rnd.randint(1, 5)
        variacoes = rnd.sample(categoria["variacoes"], k=min(quantidade, len(categoria["variacoes"])))
        presas = []
        for variacao in variacoes:
            titulo = f"{nome_base} {variacao}"
            presas.append(busca.Presa(
                titulo=titulo,
                preco=round(preco_ref * rnd.uniform(0.78, 1.30) - rnd.choice([0, 0.01, 0.1]), 2),
                loja=loja,
                link=url_busca + f"presa-demo={len(todas) + len(presas) + 1}",
                imagem="asset:" + categoria["imagem"],
                relevancia=busca.relevancia(termo, titulo),
            ))
        yield evento("log", persona.fala("loja_avistadas", loja=loja, n=len(presas)), "sucesso",
                     loja=loja, n=len(presas))
        descartes = rnd.randint(0, 4)
        if descartes:
            yield evento("log", persona.fala("loja_descartes", n=descartes), "info",
                         detalhe="(simulado) patrocinados e itens fora do assunto")
        todas.extend(presas)

    _pausa(0.5, 1.0)
    yield from busca._eventos_finais(busca.consolidar(todas), LOJAS_DEMO, [])

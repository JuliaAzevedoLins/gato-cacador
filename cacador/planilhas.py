"""
planilhas.py — Leitura e escrita das planilhas Excel do projeto.

  data/lista_desejos.xlsx  → produtos que o gato deve vigiar
  data/historico.xlsx      → todas as capturas de preço
  data/alertas.xlsx        → alertas disparados (enviados ou não ao Telegram)
"""

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import re

import pandas as pd

PASTA_DADOS = Path(__file__).resolve().parent.parent / "data"
ARQ_LISTA = PASTA_DADOS / "lista_desejos.xlsx"
ARQ_HISTORICO = PASTA_DADOS / "historico.xlsx"
ARQ_ALERTAS = PASTA_DADOS / "alertas.xlsx"

COLUNAS_LISTA = ["Produto", "Link", "Preço meta", "Alertar"]
COLUNAS_HISTORICO = ["Data/Hora", "Produto", "Loja", "Preço capturado", "Preço meta",
                     "Variação (%)", "Status", "Método", "Link"]
COLUNAS_ALERTAS = ["Data/Hora", "Produto", "Preço", "Preço meta", "Variação (%)",
                   "Enviado ao Telegram", "Mensagem"]

# Status possíveis de uma captura
STATUS_META = "🎯 Meta atingida"
STATUS_CAIU = "📉 Caiu"
STATUS_ESTAVEL = "😐 Sem queda"
STATUS_SUBIU = "📈 Subiu"
STATUS_PRIMEIRA = "🆕 Primeira espiada"
STATUS_ERRO = "❌ Erro"


class PlanilhaBloqueadaError(Exception):
    """A planilha está aberta em outro programa (ex.: Excel) e não pode ser salva."""


# ---------------------------------------------------------------------------
# Utilitários internos
# ---------------------------------------------------------------------------
def _ler(caminho: Path, colunas: list[str]) -> pd.DataFrame:
    if not caminho.exists():
        return pd.DataFrame(columns=colunas)
    df = pd.read_excel(caminho)
    for coluna in colunas:
        if coluna not in df.columns:
            df[coluna] = None
    return df[colunas]


def _salvar(df: pd.DataFrame, caminho: Path) -> None:
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    try:
        df.to_excel(caminho, index=False)
    except PermissionError as erro:
        raise PlanilhaBloqueadaError(
            f"Não consegui salvar {caminho.name}. Ela está aberta no Excel? Feche e tente de novo. 😾"
        ) from erro


def _anexar(caminho: Path, colunas: list[str], linha: dict) -> None:
    df = _ler(caminho, colunas)
    df = pd.DataFrame(df.to_dict("records") + [linha], columns=colunas)
    _salvar(df, caminho)


# ---------------------------------------------------------------------------
# Lista de desejos
# ---------------------------------------------------------------------------
def ler_lista() -> pd.DataFrame:
    df = _ler(ARQ_LISTA, COLUNAS_LISTA)
    df["Preço meta"] = pd.to_numeric(df["Preço meta"], errors="coerce")
    df["Alertar"] = df["Alertar"].map(_como_bool)
    return df


def _como_bool(valor) -> bool:
    """
    Coluna "Alertar": vazia (listas antigas, sem a coluna) vale True, para manter
    o comportamento de antes. Aceita também "Não"/"false"/0 digitados no Excel.
    """
    if pd.isna(valor):
        return True
    if isinstance(valor, str):
        return valor.strip().lower() not in ("nao", "não", "false", "0", "n")
    return bool(valor)


def validar_lista(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Limpa e valida a lista de desejos.
    Retorna (lista_limpa, erros). Se houver erros, a lista não deve ser salva.
    """
    erros: list[str] = []
    df = df.copy()
    # Linhas totalmente vazias (ex.: a "linha nova" do data_editor) são descartadas
    df = df.dropna(how="all")
    df = df[~df.apply(lambda l: all(str(v).strip() in ("", "nan", "None") for v in l), axis=1)]

    for posicao, (i, linha) in enumerate(df.iterrows(), start=1):
        produto = str(linha.get("Produto") or "").strip()
        link = str(linha.get("Link") or "").strip()
        meta = pd.to_numeric(linha.get("Preço meta"), errors="coerce")
        rotulo = produto or f"Linha {posicao}"

        if not produto:
            erros.append(f"{rotulo}: falta o nome do produto.")
        url = urlparse(link)
        if url.scheme not in ("http", "https") or "." not in url.netloc:
            erros.append(f"{rotulo}: link inválido (precisa começar com http:// ou https://).")
        if pd.isna(meta) or meta <= 0:
            erros.append(f"{rotulo}: a meta precisa ser um número maior que zero.")

        df.at[i, "Produto"] = produto
        df.at[i, "Link"] = link
        df.at[i, "Preço meta"] = meta

    duplicados = df["Produto"][df["Produto"].duplicated()].unique()
    for nome in duplicados:
        erros.append(f"{nome}: produto repetido na lista (use nomes diferentes).")

    return df.reset_index(drop=True), erros


def salvar_lista(df: pd.DataFrame) -> None:
    df = df.reindex(columns=COLUNAS_LISTA)
    df["Alertar"] = df["Alertar"].map(_como_bool)
    _salvar(df, ARQ_LISTA)


def adicionar_a_lista(produto: str, link: str, meta: float, loja: str = "") -> tuple[bool, str]:
    """
    Adiciona um produto vindo da Busca de Presas à lista de desejos.
    Retorna (adicionou, nome_usado). Não duplica links já vigiados e garante
    nomes únicos (a validação da lista exige isso).
    """
    lista = ler_lista()
    if (lista["Link"].astype(str).str.split("#").str[0] == link.split("#")[0]).any():
        return False, produto
    nome = produto.strip()
    if len(nome) > 60:
        nome = nome[:57].rsplit(" ", 1)[0] + "..."
    existentes = set(lista["Produto"].astype(str))
    if nome in existentes and loja:
        nome = f"{nome} ({loja})"
    base, n = nome, 2
    while nome in existentes:
        nome, n = f"{base} #{n}", n + 1
    nova = pd.DataFrame([{"Produto": nome, "Link": link, "Preço meta": round(meta, 2), "Alertar": True}])
    salvar_lista(nova if lista.empty else pd.concat([lista, nova], ignore_index=True))
    return True, nome


# ---------------------------------------------------------------------------
# Histórico
# ---------------------------------------------------------------------------
def ler_historico() -> pd.DataFrame:
    df = _ler(ARQ_HISTORICO, COLUNAS_HISTORICO)
    df["Data/Hora"] = pd.to_datetime(df["Data/Hora"], errors="coerce")
    for coluna in ("Preço capturado", "Preço meta", "Variação (%)"):
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    return df


def ultimo_preco(produto: str, historico: pd.DataFrame | None = None) -> float | None:
    """Último preço válido capturado para o produto (para comparar quedas)."""
    if historico is None:
        historico = ler_historico()
    capturas = historico[(historico["Produto"] == produto) & historico["Preço capturado"].notna()]
    if capturas.empty:
        return None
    return float(capturas.sort_values("Data/Hora")["Preço capturado"].iloc[-1])


def registrar_captura(produto: str, loja: str, preco: float | None, meta: float,
                      variacao: float | None, status: str, metodo: str | None,
                      link: str, momento: datetime | None = None) -> None:
    _anexar(ARQ_HISTORICO, COLUNAS_HISTORICO, {
        "Data/Hora": momento or datetime.now().replace(microsecond=0),
        "Produto": produto,
        "Loja": loja,
        "Preço capturado": preco,
        "Preço meta": meta,
        "Variação (%)": round(variacao * 100, 2) if variacao is not None else None,
        "Status": status,
        "Método": metodo,
        "Link": link,
    })


def salvar_historico(df: pd.DataFrame) -> None:
    _salvar(df[COLUNAS_HISTORICO], ARQ_HISTORICO)


# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------
def ler_alertas() -> pd.DataFrame:
    df = _ler(ARQ_ALERTAS, COLUNAS_ALERTAS)
    df["Data/Hora"] = pd.to_datetime(df["Data/Hora"], errors="coerce")
    return df


def salvar_alertas(df: pd.DataFrame) -> None:
    _salvar(df[COLUNAS_ALERTAS], ARQ_ALERTAS)


def registrar_alerta(produto: str, preco: float, meta: float, variacao: float | None,
                     enviado: bool, mensagem: str) -> None:
    _anexar(ARQ_ALERTAS, COLUNAS_ALERTAS, {
        "Data/Hora": datetime.now().replace(microsecond=0),
        "Produto": produto,
        "Preço": preco,
        "Preço meta": meta,
        "Variação (%)": round(variacao * 100, 2) if variacao is not None else None,
        "Enviado ao Telegram": "Sim" if enviado else "Não",
        "Mensagem": re.sub(r"<[^>]+>", "", mensagem),  # guarda sem as tags HTML do Telegram
    })


# ---------------------------------------------------------------------------
# Renomear
# ---------------------------------------------------------------------------
def renomear_produto(antigo: str, novo: str) -> None:
    """
    Renomeia o produto no histórico e nos alertas. O vínculo entre a lista de
    desejos e essas planilhas é o nome: sem isso, editar o nome "perderia" o
    histórico de preços do produto.
    """
    if antigo == novo:
        return
    for arquivo, ler, salvar in ((ARQ_HISTORICO, ler_historico, salvar_historico),
                                 (ARQ_ALERTAS, ler_alertas, salvar_alertas)):
        if not arquivo.exists():
            continue
        df = ler()
        if (df["Produto"] == antigo).any():
            df.loc[df["Produto"] == antigo, "Produto"] = novo
            salvar(df)

"""
robo.py — A automação web (Selenium) do Gato Caçador.

Fluxo da caçada:
  1. abre o Chrome (ou o Edge, com o msedgedriver baixado em drivers/);
  2. visita cada link da lista de desejos;
  3. espera (WebDriverWait) até que um preço possa ser extraído da página;
  4. registra a captura no histórico, compara com a meta e com a última captura;
  5. dispara o alerta no Telegram quando encontra uma presa.

A função `cacar()` é um *generator*: a cada passo ela emite um "evento"
(dicionário) que a interface usa para montar o log ao vivo. O modo demo
(demo.py) emite exatamente os mesmos eventos.
"""

import io
import os
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait

from . import alertas, persona, planilhas
from .alertas import ARQ_ENV
from .extrator import ResultadoExtracao, extrair_preco
from .lojas import SINAIS_DE_BLOQUEIO, identificar_loja

TENTATIVAS_POR_PRODUTO = 2   # 1 tentativa + 1 nova tentativa
TIMEOUT_PAGINA = 25          # segundos de espera explícita pelo preço


# ---------------------------------------------------------------------------
# Eventos emitidos para a interface
# ---------------------------------------------------------------------------
def evento(tipo: str, texto: str = "", nivel: str = "info", **extras) -> dict:
    """tipo: log | captura | alerta | erro | resumo ; nivel: info | sucesso | aviso | erro"""
    return {"tipo": tipo, "texto": texto, "nivel": nivel, **extras}


class LojaBloqueouError(WebDriverException):
    """A loja mostrou uma página de bloqueio/verificação em vez do produto."""


def pagina_bloqueada(driver) -> bool:
    url = (driver.current_url or "").lower()
    titulo = (driver.title or "").lower()
    return (any(s in url for s in SINAIS_DE_BLOQUEIO["url"])
            or any(s in titulo for s in SINAIS_DE_BLOQUEIO["titulo"]))


# ---------------------------------------------------------------------------
# Navegador
# ---------------------------------------------------------------------------
def navegadores_preferidos() -> list[str]:
    """
    Ordem de navegadores a tentar, definida por NAVEGADOR no .env:
      auto (padrão) → Chrome e, se não abrir, Microsoft Edge
      chrome / edge → só o escolhido
    O fallback existe porque o Smart App Control do Windows 11 pode bloquear
    o chromedriver (binário sem assinatura digital); o msedgedriver é assinado.
    """
    load_dotenv(ARQ_ENV)
    escolha = os.getenv("NAVEGADOR", "auto").strip().lower()
    if escolha in ("chrome", "edge"):
        return [escolha]
    return ["chrome", "edge"]


# O Smart App Control do Windows 11 pode bloquear o selenium-manager.exe (sem
# assinatura) e aí nem o Chrome nem o Edge abrem. O msedgedriver é assinado pela
# Microsoft, então o gato baixa ele sozinho (via requests) para a pasta drivers/.
PASTA_DRIVERS = Path(__file__).resolve().parent.parent / "drivers"
URL_EDGEDRIVER = "https://msedgedriver.microsoft.com/{versao}/edgedriver_win64.zip"


def versao_do_edge() -> str | None:
    """Versão do Edge instalado, lida do registro do Windows (None fora do Windows)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Edge\BLBeacon") as chave:
            return winreg.QueryValueEx(chave, "version")[0]
    except OSError:
        return None


def servico_edge() -> EdgeService | None:
    """
    Devolve um Service apontando para drivers/msedgedriver.exe, baixando o driver
    da mesma versão do Edge quando ele falta ou está desatualizado.
    None = deixa o Selenium Manager resolver (outros sistemas, ou download falhou).
    """
    versao = versao_do_edge()
    if not versao:
        return None
    exe = PASTA_DRIVERS / "msedgedriver.exe"
    marcador = PASTA_DRIVERS / "msedgedriver.versao"
    atual = marcador.read_text().strip() if marcador.exists() else ""
    if not exe.exists() or atual != versao:
        try:
            resposta = requests.get(URL_EDGEDRIVER.format(versao=versao), timeout=60)
            resposta.raise_for_status()
            PASTA_DRIVERS.mkdir(exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(resposta.content)) as pacote:
                exe.write_bytes(pacote.read("msedgedriver.exe"))
            marcador.write_text(versao)
        except (requests.RequestException, zipfile.BadZipFile, KeyError, OSError):
            if not exe.exists():
                return None
    return EdgeService(executable_path=str(exe))


class NavegadorGato:
    """Envolve o webdriver (Chrome, ou Edge como plano B). Use com `with NavegadorGato() as nav:`."""

    NOMES = {"chrome": "Google Chrome", "edge": "Microsoft Edge"}

    def __init__(self, headless: bool = False, timeout: int = TIMEOUT_PAGINA):
        self.headless = headless
        self.timeout = timeout
        self.driver = None
        self.nome = None
        self.falhas: list[str] = []   # navegadores que não abriram (e por quê)

    def _opcoes(self, tipo: str):
        opcoes = ChromeOptions() if tipo == "chrome" else EdgeOptions()
        if self.headless:
            opcoes.add_argument("--headless=new")
        opcoes.add_argument("--window-size=1366,900")
        opcoes.add_argument("--lang=pt-BR")
        # Deixa o navegador com "cara" de usuário comum (menos bloqueios)
        opcoes.add_argument("--disable-blink-features=AutomationControlled")
        opcoes.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        opcoes.add_experimental_option("useAutomationExtension", False)
        opcoes.add_argument("--log-level=3")
        # "eager": não espera imagens/anúncios carregarem; quem espera o preço é o WebDriverWait
        opcoes.page_load_strategy = "eager"
        return opcoes

    def __enter__(self):
        for tipo in navegadores_preferidos():
            try:
                # Selenium 4: o Selenium Manager baixa/acha o driver automaticamente
                if tipo == "chrome":
                    self.driver = webdriver.Chrome(options=self._opcoes(tipo))
                else:
                    self.driver = webdriver.Edge(options=self._opcoes(tipo), service=servico_edge())
                self.nome = self.NOMES[tipo]
                break
            except (WebDriverException, OSError) as erro:
                motivo = str(getattr(erro, "msg", None) or erro).splitlines()[0][:160]
                self.falhas.append(f"{self.NOMES[tipo]}: {motivo}")
        if self.driver is None:
            raise WebDriverException("nenhum navegador abriu → " + " | ".join(self.falhas))

        self.driver.set_page_load_timeout(self.timeout + 15)
        if self.headless:
            # No modo headless o user-agent denuncia "HeadlessChrome"; trocamos só essa palavra
            # (o resto continua igual ao navegador real, para não destoar dos client hints)
            agente = self.driver.execute_script("return navigator.userAgent")
            self.driver.execute_cdp_cmd("Network.setUserAgentOverride",
                                        {"userAgent": agente.replace("Headless", "")})
        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
        return self

    def __exit__(self, *_):
        if self.driver:
            try:
                self.driver.quit()
            except WebDriverException:
                pass

    def capturar(self, url: str) -> ResultadoExtracao:
        """
        Abre a página e espera explicitamente até um preço ser extraível
        (JSON-LD, meta tag ou seletor CSS). Levanta TimeoutException se não achar.
        """
        try:
            self.driver.get(url)
        except TimeoutException:
            pass  # página pesada: seguimos com o que já carregou

        def preco_disponivel(driver):
            if pagina_bloqueada(driver):
                raise LojaBloqueouError(f"a loja pediu verificação/bloqueou o acesso ({driver.title})")
            resultado = extrair_preco(driver.page_source, url)
            return resultado if resultado.preco else False

        espera = WebDriverWait(self.driver, self.timeout, poll_frequency=1)
        return espera.until(preco_disponivel, message="preço não apareceu na página")


# ---------------------------------------------------------------------------
# Regras de negócio (compartilhadas com o modo demo)
# ---------------------------------------------------------------------------
def processar_captura(produto: str, link: str, meta: float, loja: str, preco: float,
                      metodo: str, historico: pd.DataFrame, demo: bool = False,
                      alertar: bool = True) -> Iterator[dict]:
    """
    Compara o preço com a meta e com a última captura, grava o histórico e,
    se for uma presa, dispara o alerta. Emite os eventos correspondentes.
    alertar=False (interruptor 🔔 desligado na lista): o preço é registrado,
    mas não vai alerta para o Telegram nem para a planilha de alertas.
    """
    anterior = planilhas.ultimo_preco(produto, historico)
    variacao = (preco - anterior) / anterior if anterior else None
    atingiu_meta = preco <= meta
    caiu = anterior is not None and preco < anterior - 0.009

    if atingiu_meta:
        status = planilhas.STATUS_META
    elif caiu:
        status = planilhas.STATUS_CAIU
    elif anterior is None:
        status = planilhas.STATUS_PRIMEIRA
    elif preco > anterior + 0.009:
        status = planilhas.STATUS_SUBIU
    else:
        status = planilhas.STATUS_ESTAVEL

    planilhas.registrar_captura(produto, loja, preco, meta, variacao, status, metodo, link)

    dados = {"produto": produto, "preco": persona.formatar_reais(preco),
             "variacao": persona.formatar_variacao(variacao)}
    yield evento("captura", "", "info", produto=produto, loja=loja, preco=preco, meta=meta,
                 variacao=variacao, status=status, metodo=metodo,
                 presa=int(atingiu_meta or caiu))

    if not (atingiu_meta or caiu):
        yield evento("log", persona.fala("sem_queda", **dados), "info")
        return

    abertura = persona.fala("bote" if atingiu_meta else "queda", **dados)
    yield evento("log", abertura, "sucesso" if atingiu_meta else "aviso")

    if not alertar:
        yield evento("log", persona.fala("alerta_desligado", produto=produto), "info")
        return

    mensagem = persona.mensagem_alerta(abertura, produto, preco, meta, variacao, link)
    if demo:
        mensagem += "\n\n🎭 <i>Alerta gerado no Modo Demo (preço simulado)</i>"
    enviado, detalhe = alertas.enviar_telegram(mensagem)
    planilhas.registrar_alerta(produto, preco, meta, variacao, enviado, mensagem)

    if enviado:
        yield evento("alerta", persona.fala("telegram_ok"), "sucesso", produto=produto, enviado=True)
    elif not alertas.configurado():
        yield evento("alerta", persona.fala("telegram_sem_config"), "aviso", produto=produto, enviado=False)
    else:
        yield evento("alerta", persona.fala("telegram_falhou", erro=detalhe), "erro",
                     produto=produto, enviado=False)


def resumo(visitados: int, presas: int, erros: int, alertas_enviados: int) -> dict:
    return evento("resumo", persona.fala("encerrando"), "info", visitados=visitados,
                  presas=presas, erros=erros, alertas=alertas_enviados)


# ---------------------------------------------------------------------------
# A caçada
# ---------------------------------------------------------------------------
def cacar(lista: pd.DataFrame, headless: bool = False) -> Iterator[dict]:
    """Executa a caçada real com Selenium, emitindo eventos passo a passo."""
    yield evento("log", persona.fala("acordando"))

    if lista.empty:
        yield evento("log", persona.fala("lista_vazia"), "aviso")
        yield resumo(0, 0, 0, 0)
        return

    visitados = presas = erros = enviados = 0
    yield evento("log", persona.fala("navegador_oculto" if headless else "abrindo_navegador"))

    try:
        with NavegadorGato(headless=headless) as navegador:
            if navegador.falhas:
                yield evento("log", f"O {navegador.falhas[0].split(':')[0]} não quis brincar "
                             f"(bloqueado pelo Windows?). Pulei pro {navegador.nome}. 😼", "aviso",
                             detalhe=navegador.falhas[0])
            else:
                yield evento("log", f"Navegador: {navegador.nome}. 🐾")

            for _, item in lista.iterrows():
                produto, link, meta = item["Produto"], item["Link"], float(item["Preço meta"])
                loja, _ = identificar_loja(link)
                visitados += 1
                yield evento("log", persona.fala("espreitando", produto=produto) + f"  ({loja})",
                             "info", produto=produto)

                # 1 tentativa + 1 nova tentativa antes de desistir do produto
                resultado = None
                ultimo_erro = ""
                for tentativa in range(1, TENTATIVAS_POR_PRODUTO + 1):
                    try:
                        resultado = navegador.capturar(link)
                        break
                    except (TimeoutException, WebDriverException) as erro:
                        ultimo_erro = getattr(erro, "msg", None) or erro.__class__.__name__
                        if tentativa < TENTATIVAS_POR_PRODUTO:
                            yield evento("log", persona.fala("tentando_de_novo", produto=produto), "aviso")

                try:
                    if resultado is None:
                        erros += 1
                        planilhas.registrar_captura(produto, loja, None, meta, None,
                                                    planilhas.STATUS_ERRO, None, link)
                        situacao = "bloqueado" if "verificação" in str(ultimo_erro) else "erro"
                        yield evento("erro", persona.fala(situacao, produto=produto), "erro",
                                     produto=produto, detalhe=str(ultimo_erro).splitlines()[0][:150])
                        continue

                    for ev in processar_captura(produto, link, meta, loja, resultado.preco,
                                                resultado.metodo, planilhas.ler_historico(),
                                                alertar=bool(item["Alertar"])):
                        presas += ev.get("presa", 0)
                        if ev["tipo"] == "alerta" and ev.get("enviado"):
                            enviados += 1
                        yield ev
                except planilhas.PlanilhaBloqueadaError as erro:
                    erros += 1
                    yield evento("erro", str(erro), "erro", produto=produto)
    except WebDriverException as erro:
        erros += 1
        detalhe = (getattr(erro, "msg", None) or str(erro)).splitlines()[0][:300]
        yield evento("erro", "Não consegui abrir nenhum navegador. Alguém escondeu o Chrome? 🙀",
                     "erro", detalhe=detalhe)

    yield resumo(visitados, presas, erros, enviados)

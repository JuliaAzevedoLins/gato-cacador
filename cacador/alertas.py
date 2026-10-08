"""
alertas.py — Integração com a API REST do Telegram (via requests).

Endpoint usado:
    POST https://api.telegram.org/bot<TOKEN>/sendMessage
    corpo JSON: {"chat_id": ..., "text": ..., "parse_mode": "HTML"}

O token e o chat_id NUNCA ficam no código: são lidos do arquivo .env
(variáveis TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID).
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv, set_key

ARQ_ENV = Path(__file__).resolve().parent.parent / ".env"
URL_API = "https://api.telegram.org/bot{token}/{metodo}"
TIMEOUT = 15


def carregar_config() -> tuple[str, str]:
    """Lê (token, chat_id) do .env — recarrega sempre, para pegar alterações."""
    load_dotenv(ARQ_ENV, override=True)
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()


def salvar_config(token: str, chat_id: str) -> None:
    """Grava token e chat_id no .env (cria o arquivo se não existir)."""
    ARQ_ENV.touch(exist_ok=True)
    set_key(str(ARQ_ENV), "TELEGRAM_BOT_TOKEN", token.strip(), quote_mode="never")
    set_key(str(ARQ_ENV), "TELEGRAM_CHAT_ID", chat_id.strip(), quote_mode="never")


def configurado() -> bool:
    token, chat_id = carregar_config()
    return bool(token and chat_id)


def enviar_telegram(texto: str, token: str | None = None, chat_id: str | None = None) -> tuple[bool, str]:
    """
    Envia uma mensagem pelo endpoint sendMessage.
    Retorna (sucesso, detalhe). Nunca levanta exceção: a caçada não pode parar
    por causa de um alerta que falhou.
    """
    if token is None or chat_id is None:
        token_env, chat_env = carregar_config()
        token, chat_id = token or token_env, chat_id or chat_env
    if not token or not chat_id:
        return False, "Telegram não configurado (.env sem TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)."

    try:
        resposta = requests.post(
            URL_API.format(token=token, metodo="sendMessage"),
            json={
                "chat_id": chat_id,
                "text": texto,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=TIMEOUT,
        )
        dados = resposta.json()
    except requests.RequestException as erro:
        return False, f"falha de conexão ({erro.__class__.__name__})"
    except ValueError:
        return False, f"resposta inesperada (HTTP {resposta.status_code})"

    if resposta.ok and dados.get("ok"):
        return True, "mensagem entregue"
    return False, dados.get("description", f"HTTP {resposta.status_code}")


def descobrir_chat_id(token: str) -> tuple[str | None, str]:
    """
    Ajuda a descobrir o chat_id: consulta o endpoint getUpdates e devolve o
    chat da mensagem mais recente enviada ao bot.
    """
    try:
        resposta = requests.get(URL_API.format(token=token, metodo="getUpdates"), timeout=TIMEOUT)
        dados = resposta.json()
    except (requests.RequestException, ValueError) as erro:
        return None, f"falha ao consultar o Telegram ({erro.__class__.__name__})"
    if not dados.get("ok"):
        return None, dados.get("description", "token inválido?")
    for update in reversed(dados.get("result", [])):
        mensagem = update.get("message") or update.get("channel_post") or {}
        chat = mensagem.get("chat")
        if chat:
            nome = chat.get("first_name") or chat.get("title") or ""
            return str(chat["id"]), f"chat encontrado: {nome}"
    return None, "nenhuma mensagem encontrada. Mande um 'oi' para o seu bot no Telegram e tente de novo."

"""
ui/log.py — O "terminal" do gato: log ao vivo usado na Caçada e na Busca.
"""

import html
from datetime import datetime

CSS_LOG = """
<style>
.log-gato {
    background: #2B2118; color: #F7EBDD; border-radius: 14px; padding: 1rem 1.2rem;
    font-family: "Cascadia Code", Consolas, monospace; font-size: .9rem; line-height: 1.6;
    max-height: 520px; overflow-y: auto; border: 2px solid #2B2118; box-shadow: 3px 3px 0 #F2A65A;
    margin-top: 1rem;
    /* column-reverse mantém a rolagem "grudada" na última linha do log */
    display: flex; flex-direction: column-reverse;
}
.log-gato .hora {color: #B89478; margin-right: .6rem;}
.log-gato .sucesso {color: #9BE39B; font-weight: 600;}
.log-gato .aviso {color: #FFC870;}
.log-gato .erro {color: #FF9A8A;}
.log-gato .detalhe {color: #B89478; font-size: .8rem; margin-left: 4.4rem; display: block;}
</style>
"""


def linha_do_evento(ev: dict) -> dict:
    """Converte um evento do robô numa linha do log (com horário)."""
    return {"hora": datetime.now().strftime("%H:%M:%S"), "texto": ev["texto"],
            "nivel": ev["nivel"], "detalhe": ev.get("detalhe")}


def render_log(linhas: list[dict], vazio: str = "Zzz... aguardando você me soltar.") -> str:
    partes = []
    for linha in linhas:
        texto = html.escape(linha["texto"])
        detalhe = (f'<span class="detalhe">↳ {html.escape(linha["detalhe"])}</span>'
                   if linha.get("detalhe") else "")
        partes.append(f'<div><span class="hora">{linha["hora"]}</span>'
                      f'<span class="{linha["nivel"]}">{texto}</span>{detalhe}</div>')
    return f'<div class="log-gato"><div>{"".join(partes) or html.escape(vazio)}</div></div>'

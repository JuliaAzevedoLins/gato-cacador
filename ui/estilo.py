"""
ui/estilo.py — Identidade visual "papel e nanquim" do Gato Caçador.

Os gatinhos (assets/gatos/*.png) foram recortados de ilustrações em traço de
rabisco. O resto da interface imita esse traço: fundo de papel, contorno
escuro de 2px e sombras "carimbadas" (deslocadas e sem desfoque).

Truque dos gatos espiando: cada PNG tem a linha de "apoio" embaixo das patas.
Posicionado em cima da borda de uma caixa, o gato parece debruçado nela.
"""

import base64
import html
from functools import lru_cache
from pathlib import Path

PASTA_ASSETS = Path(__file__).resolve().parent.parent / "assets"

# Paleta (as mesmas cores do .streamlit/config.toml)
TINTA = "#2B2118"      # contorno e texto, o "nanquim"
PAPEL = "#FBF6EE"      # fundo
LARANJA = "#F2A65A"    # destaque (pelagem do gato laranja)
ROSA = "#F6C9C2"       # almofadinhas das patas
VERDE = "#CFE8C6"      # meta atingida
SUAVE = "#6B5A4A"      # texto secundário

MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg"}


@lru_cache(maxsize=64)
def asset_data_uri(caminho_relativo: str) -> str:
    """Converte um arquivo de assets/ em data URI (o st.markdown não serve arquivos locais)."""
    caminho = PASTA_ASSETS / caminho_relativo
    mime = MIME.get(caminho.suffix.lower(), "application/octet-stream")
    return f"data:{mime};base64," + base64.b64encode(caminho.read_bytes()).decode()


def gato(nome: str, largura: int, classe: str = "", alt: str = "") -> str:
    """<img> de um gatinho de assets/gatos (decorativo, a não ser que receba alt)."""
    return (f'<img class="gato {classe}" src="{asset_data_uri(f"gatos/{nome}.png")}" '
            f'width="{largura}" alt="{html.escape(alt)}"{"" if alt else " aria-hidden=\"true\""}>')


def gato_espiando(nome: str, largura: int = 96, lado: str = "direita") -> str:
    """Gato apoiado na borda de cima da caixa seguinte (use dentro de um st.container com key caixa_*)."""
    return gato(nome, largura, classe=f"espiando espiando-{lado}")


def cabecalho() -> str:
    return (
        '<div class="cabecalho">'
        '<div class="cabecalho-texto">'
        '<span class="cabecalho-selo">robô de preços · RPA em Python</span>'
        "<h1>Gato Caçador de Ofertas</h1>"
        "<p>Preguiçoso por natureza, implacável com preço baixo. "
        "Eu vigio as lojas, você só agradece com sachê.</p>"
        "</div>"
        f'{gato("caixa", 150, classe="cabecalho-gato", alt="Gatinho dentro de uma caixa de papelão")}'
        "</div>"
    )


def titulo(texto: str, subtitulo: str | None = None) -> str:
    sub = f'<p class="titulo-sub">{html.escape(subtitulo)}</p>' if subtitulo else ""
    return f'<div class="titulo"><h2>{html.escape(texto)}</h2>{sub}</div>'


def vazio(mensagem: str, nome_gato: str = "laranja_feliz") -> str:
    return (f'<div class="vazio">{gato(nome_gato, 120)}'
            f"<p>{html.escape(mensagem)}</p></div>")


def pilula(texto: str, tipo: str = "neutra") -> str:
    """Etiqueta pequena: neutra, ok (verde), alerta (rosa) ou destaque (laranja)."""
    return f'<span class="pilula pilula-{tipo}">{html.escape(texto)}</span>'


CSS_GLOBAL = f"""
<style>
:root {{
    --tinta: {TINTA}; --papel: {PAPEL}; --laranja: {LARANJA};
    --rosa: {ROSA}; --verde: {VERDE}; --suave: {SUAVE};
    --sombra: 3px 3px 0 {TINTA};
}}
.block-container {{padding-top: 4rem; max-width: 1200px;}}
h1, h2, h3, h4 {{color: var(--tinta); letter-spacing: -.01em;}}

/* ---------- Botões: contorno + sombra carimbada que "afunda" no clique ---------- */
.stButton button, .stFormSubmitButton button, .stDownloadButton button {{
    border: 2px solid var(--tinta) !important; border-radius: 12px !important;
    background: #FFFFFF; color: var(--tinta) !important; box-shadow: var(--sombra);
    font-weight: 800; transition: transform .08s ease, box-shadow .08s ease;
}}
.stButton button p, .stFormSubmitButton button p, .stDownloadButton button p {{
    color: var(--tinta) !important; font-weight: 800;
}}
.stButton button:hover, .stFormSubmitButton button:hover, .stDownloadButton button:hover {{
    transform: translate(-1px, -1px); box-shadow: 4px 4px 0 var(--tinta); background: #FFFFFF;
}}
.stButton button:active, .stFormSubmitButton button:active, .stDownloadButton button:active {{
    transform: translate(2px, 2px); box-shadow: 1px 1px 0 var(--tinta);
}}
button[kind="primary"], button[kind="primaryFormSubmit"] {{background: var(--laranja) !important;}}
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {{background: #F5B472 !important;}}

/* ---------- Campos (seletores do Streamlit 1.65, que usa react-aria) ---------- */
[data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"],
[data-testid="stSelectbox"] [role="group"] {{
    border: 2px solid var(--tinta) !important; border-radius: 12px !important; background: #FFFFFF !important;
}}
[data-testid="stTextInputRootElement"] input, [data-testid="stNumberInputContainer"] input {{
    background: #FFFFFF !important;
}}

/* ---------- Abas em formato de etiqueta ---------- */
.stTabs [role="tablist"] {{gap: .5rem; padding-bottom: .6rem; border: none; box-shadow: none;}}
.stTabs [role="tablist"]::after, .stTabs [role="tablist"]::before {{display: none;}}
.stTabs [data-testid="stTab"] {{
    border: 2px solid var(--tinta) !important; border-radius: 999px; padding: .3rem 1.05rem;
    background: #FFFFFF; box-shadow: 2px 2px 0 var(--tinta); cursor: pointer;
}}
.stTabs .react-aria-SelectionIndicator {{display: none;}}  /* a linha laranja padrão da aba ativa */
.stTabs [data-testid="stTab"] p {{font-weight: 800; color: var(--tinta) !important;}}
.stTabs [data-testid="stTab"][aria-selected="true"] {{background: var(--laranja);}}
.stTabs [data-testid="stTab"]:hover {{background: #FCE3C8;}}
.stTabs [data-testid="stTab"][aria-selected="true"]:hover {{background: var(--laranja);}}

/* ---------- Blocos padrão do Streamlit no mesmo traço ---------- */
div[data-testid="stMetric"] {{
    background: #FFFFFF; border: 2px solid var(--tinta); border-radius: 14px;
    padding: .8rem 1rem; box-shadow: var(--sombra);
}}
div[data-testid="stMetricLabel"] p {{font-weight: 700; color: var(--suave);}}
div[data-testid="stExpander"] details {{
    border: 2px solid var(--tinta); border-radius: 12px; background: #FFFFFF;
}}
div[data-testid="stDataFrame"] {{border: 2px solid var(--tinta); border-radius: 12px; overflow: hidden;}}
section[data-testid="stSidebar"] {{border-right: 2px solid var(--tinta);}}

/* ---------- Cabeçalho ---------- */
.cabecalho {{
    display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem;
    background: #FCE3C8; border: 2px solid var(--tinta); border-radius: 20px;
    padding: 1.3rem 1.6rem 0 1.6rem; box-shadow: 4px 4px 0 var(--tinta); margin-bottom: 1.4rem;
}}
.cabecalho-texto {{padding-bottom: 1.3rem;}}
.cabecalho-selo {{
    display: inline-block; font-size: .78rem; font-weight: 800; color: var(--tinta);
    background: #FFFFFF; border: 2px solid var(--tinta); border-radius: 999px; padding: .1rem .7rem;
}}
.cabecalho h1 {{font-size: 2.5rem; font-weight: 900; margin: .5rem 0 .2rem 0; padding: 0; line-height: 1.1;}}
.cabecalho p {{margin: 0; color: var(--tinta); font-size: 1.05rem; max-width: 34rem;}}
.cabecalho-gato {{height: auto; margin-bottom: -2px; flex-shrink: 0;}}
@media (max-width: 640px) {{
    .cabecalho {{padding: 1rem 1rem 0 1rem;}}
    .cabecalho h1 {{font-size: 1.8rem;}}
    .cabecalho-gato {{width: 96px;}}
}}

/* ---------- Títulos de seção ---------- */
.titulo h2 {{font-size: 1.6rem; font-weight: 900; margin: 0; padding: 0;}}
.titulo-sub {{color: var(--suave); margin: .2rem 0 0 0;}}

/* ---------- Caixas (st.container com key caixa_*) e gatos espiando ---------- */
div[class*="st-key-caixa_"] {{
    position: relative; background: #FFFFFF; border: 2px solid var(--tinta); border-radius: 18px;
    padding: 1.1rem 1.3rem; box-shadow: 4px 4px 0 var(--tinta); margin-top: 3.8rem; overflow: visible;
}}
img.espiando {{
    position: absolute; top: 0; transform: translateY(calc(-100% + 8px));
    pointer-events: none; z-index: 2; height: auto;
}}
img.espiando-direita {{right: 2rem;}}
img.espiando-esquerda {{left: 2rem;}}
@media (max-width: 640px) {{img.espiando {{width: 72px;}} div[class*="st-key-caixa_"] {{margin-top: 3rem;}}}}

/* ---------- Estado vazio e etiquetas ---------- */
.vazio {{
    text-align: center; padding: 1.4rem 1rem 1.6rem 1rem; color: var(--suave);
    background: #FFFFFF; border: 2px dashed var(--tinta); border-radius: 18px;
}}
.vazio p {{font-size: 1.05rem; font-weight: 700; margin: .6rem 0 0 0;}}
.pilula {{
    display: inline-block; font-size: .8rem; font-weight: 800; border: 2px solid var(--tinta);
    border-radius: 999px; padding: .05rem .6rem; color: var(--tinta); background: #FFFFFF; white-space: nowrap;
}}
.pilula-ok {{background: var(--verde);}}
.pilula-alerta {{background: var(--rosa);}}
.pilula-destaque {{background: var(--laranja);}}
.dica {{font-size: .9rem; color: var(--suave);}}

/* ---------- Barra lateral ---------- */
.lateral-topo {{text-align: center; margin-bottom: .4rem;}}
.lateral-topo strong {{display: block; font-size: 1.1rem; margin-top: .2rem;}}
.lateral-rotulo {{font-weight: 800; margin: .2rem 0 .4rem 0;}}
.lojas {{display: flex; flex-wrap: wrap; gap: .35rem;}}
</style>
"""

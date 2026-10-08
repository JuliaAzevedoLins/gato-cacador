"""
ui/cards.py — Componentes visuais da Busca de Presas (HTML/CSS via st.markdown).

Cada presa vira um "card" dentro de um st.container com key própria
(st-key-presa_N). O CSS abaixo transforma esse contêiner no card inteiro,
assim o botão "➕ Vigiar essa presa" (um st.button de verdade) fica dentro
do card, junto da foto, do título e do preço.
"""

import html

from cacador import persona
from ui.estilo import asset_data_uri, gato, vazio

# Selo de cada loja: (fundo, texto). Cores escolhidas com contraste >= 4.5:1
CORES_LOJAS = {
    "Mercado Livre": ("#FFE600", "#2D3277"),
    "KaBuM!": ("#0060B1", "#FFFFFF"),
    "Amazon": ("#FF9900", "#131921"),
    "Pichau": ("#C8102E", "#FFFFFF"),
    "Terabyte": ("#1B1B1B", "#FFFFFF"),
    "Época Cosméticos": ("#A3004F", "#FFFFFF"),
    "Kalunga": ("#00539F", "#FFFFFF"),
    "Fast Shop": ("#B5121B", "#FFFFFF"),
    "Centauro": ("#E30613", "#FFFFFF"),
}
COR_LOJA_PADRAO = ("#7A4A2A", "#FFFFFF")

CSS_BUSCA = """
<style>
/* ---------- Campo de busca (dentro da caixa_busca, estilizada em ui/estilo.py) ---------- */
.st-key-caixa_busca input {font-size: 1.2rem !important; padding: .8rem 1rem !important;}
.st-key-caixa_busca [data-testid="stFormSubmitButton"] button {min-height: 3.2rem;}
.st-key-caixa_busca [data-testid="stFormSubmitButton"] button p {font-size: 1.1rem !important;}
.busca-dica {color: var(--suave); font-size: .92rem; margin: .1rem 0 .4rem 0;}

/* ---------- Resumo ---------- */
.resumo-busca {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: .9rem; margin: .6rem 0 1rem 0;
}
.resumo-item {
    background: #FFFFFF; border: 2px solid var(--tinta); border-radius: 14px;
    padding: .75rem 1rem; box-shadow: var(--sombra);
}
.resumo-item .rotulo {font-size: .85rem; color: var(--suave); font-weight: 700;}
.resumo-item .valor {font-size: 1.55rem; font-weight: 900; color: var(--tinta); line-height: 1.25;}
.resumo-item .extra {font-size: .85rem; font-weight: 800;}
.resumo-item.economia {background: var(--verde);}

/* ---------- Card de presa (o st.container com key "presa_*") ---------- */
div[class*="st-key-presa_"] {
    position: relative; overflow: visible;
    background: #FFFFFF; border: 2px solid var(--tinta); border-radius: 16px;
    padding: .8rem .8rem .9rem .8rem; gap: .5rem; box-shadow: var(--sombra);
    transition: transform .12s ease, box-shadow .12s ease; height: 100%;
}
div[class*="st-key-presa_"]:hover {transform: translate(-2px, -2px); box-shadow: 5px 5px 0 var(--tinta);}
div.st-key-presa_top {background: #FFF4DE;}
/* Espaço para o gato do #1 não encostar no resumo */
.espaco-gato {height: 3.4rem;}

.presa {position: relative; display: flex; flex-direction: column; gap: .45rem;}
.presa .espiando {right: .6rem; top: -.8rem;}
.presa-topo {display: flex; justify-content: space-between; align-items: center; min-height: 1.8rem;}
.presa-rank {
    background: var(--tinta); color: #FFFFFF; font-weight: 900; border-radius: 999px;
    padding: .08rem .6rem; font-size: .9rem;
}
.st-key-presa_top .presa-rank {background: var(--laranja); color: var(--tinta); border: 2px solid var(--tinta);}
.presa-trofeu {
    background: var(--laranja); color: var(--tinta); font-weight: 900; font-size: .78rem;
    border: 2px solid var(--tinta); border-radius: 999px; padding: .05rem .55rem; white-space: nowrap;
}
.presa-foto {
    position: relative; height: 180px; border-radius: 12px; background: var(--papel);
    border: 2px solid var(--tinta);
    display: flex; align-items: center; justify-content: center; overflow: hidden;
}
/* object-fit: contain alinha fotos de tamanhos diferentes sem cortar nem distorcer */
.presa-foto img {width: 100%; height: 100%; object-fit: contain; padding: .6rem; background: #FFFFFF;}
.presa-fala {
    position: absolute; left: .4rem; right: .4rem; bottom: .4rem;
    background: #FFFFFF; color: var(--tinta); font-size: .78rem; font-weight: 700;
    border: 2px solid var(--tinta); border-radius: 12px; padding: .3rem .5rem; line-height: 1.3;
}
.presa-loja {
    align-self: flex-start; font-size: .74rem; font-weight: 800; letter-spacing: .2px;
    border: 2px solid var(--tinta); border-radius: 8px; padding: .05rem .5rem;
}
.presa-titulo {
    color: var(--tinta); font-size: .93rem; font-weight: 700; line-height: 1.35;
    height: 2.7em; overflow: hidden; display: -webkit-box;
    -webkit-line-clamp: 2; -webkit-box-orient: vertical; text-overflow: ellipsis;
}
.presa-preco {color: var(--tinta); font-size: 1.65rem; font-weight: 900; line-height: 1.1;}
.presa-preco small {font-size: .9rem; font-weight: 800; margin-right: .15rem;}
a.presa-botao {
    display: block; text-align: center; text-decoration: none !important;
    background: var(--laranja); color: var(--tinta) !important; font-weight: 800;
    border: 2px solid var(--tinta); border-radius: 12px; padding: .45rem .5rem;
    box-shadow: 2px 2px 0 var(--tinta); transition: transform .08s ease, box-shadow .08s ease;
}
a.presa-botao:hover {transform: translate(-1px, -1px); box-shadow: 3px 3px 0 var(--tinta);}
a.presa-botao:focus-visible {outline: 3px solid var(--tinta); outline-offset: 2px;}
div[class*="st-key-presa_"] .stButton button {box-shadow: 2px 2px 0 var(--tinta);}
</style>
"""


def imagem_gato() -> str:
    return asset_data_uri("gato_procurando.svg")


def src_da_imagem(imagem: str | None) -> str:
    """URL remota → como está; "asset:..." → SVG local; vazio → gato procurando."""
    if not imagem:
        return imagem_gato()
    if imagem.startswith("asset:"):
        return asset_data_uri(imagem.removeprefix("asset:"))
    return imagem


def compacto(trecho_html: str) -> str:
    """Junta o HTML numa linha só: no Markdown, linhas indentadas virariam bloco de código."""
    return " ".join(linha.strip() for linha in trecho_html.splitlines() if linha.strip())


def _esc(texto) -> str:
    return html.escape(str(texto), quote=True)


def _preco_html(preco: float) -> str:
    texto = persona.formatar_reais(preco)  # "R$ 1.299,90"
    return f"<small>R$</small>{_esc(texto.removeprefix('R$ '))}"


# ---------------------------------------------------------------------------
# Componentes
# ---------------------------------------------------------------------------
def html_resumo(presas: list[dict]) -> str:
    precos = [p["preco"] for p in presas]
    menor, maior = min(precos), max(precos)
    economia = maior - menor
    pct = (economia / maior * 100) if maior else 0
    pct_txt = f"{pct:.1f}".replace(".", ",")
    lojas = len({p["loja"] for p in presas})
    return compacto(f"""
<div class="resumo-busca">
  <div class="resumo-item"><div class="rotulo">Presas encontradas</div>
    <div class="valor">{len(presas)}</div><div class="rotulo">em {lojas} loja(s)</div></div>
  <div class="resumo-item"><div class="rotulo">Menor preço</div>
    <div class="valor">{_esc(persona.formatar_reais(menor))}</div></div>
  <div class="resumo-item"><div class="rotulo">Maior preço</div>
    <div class="valor">{_esc(persona.formatar_reais(maior))}</div></div>
  <div class="resumo-item economia"><div class="rotulo">Economia (mais caro → mais barato)</div>
    <div class="valor">{_esc(persona.formatar_reais(economia))}</div>
    <div class="extra">{pct_txt}% a menos</div></div>
</div>
""")


def html_card(presa: dict, posicao: int, fala_melhor: str | None = None) -> str:
    """HTML do conteúdo de um card. O #1 recebe o selo de troféu e a fala do gato."""
    fundo, texto = CORES_LOJAS.get(presa["loja"], COR_LOJA_PADRAO)
    trofeu = '<span class="presa-trofeu">Melhor preço</span>' if posicao == 1 else ""
    fala = f'<div class="presa-fala">{_esc(fala_melhor)}</div>' if posicao == 1 and fala_melhor else ""
    # O gatinho acenando fica debruçado na borda de cima do card #1
    espiando = gato("acenando", 84, classe="espiando") if posicao == 1 else ""
    titulo = _esc(presa["titulo"])
    # A foto já chega validada pelo busca.py (inválida → None → gato procurando).
    # Obs.: o Streamlit remove "onerror" de <img>, por isso a validação é no Python.
    foto = _esc(src_da_imagem(presa.get("imagem")))
    # Ilustrações locais (Modo Demo): gira o matiz para cada card ter uma "cor" diferente
    estilo_foto = ""
    if (presa.get("imagem") or "").startswith("asset:"):
        estilo_foto = f' style="filter: hue-rotate({(posicao * 53) % 360}deg)"'
    return compacto(f"""
<div class="presa">{espiando}
  <div class="presa-topo"><span class="presa-rank">#{posicao}</span>{trofeu}</div>
  <div class="presa-foto">
    <img src="{foto}" alt="Foto: {titulo}" loading="lazy" referrerpolicy="no-referrer"{estilo_foto}>{fala}
  </div>
  <span class="presa-loja" style="background:{fundo};color:{texto}">{_esc(presa["loja"])}</span>
  <div class="presa-titulo" title="{titulo}">{titulo}</div>
  <div class="presa-preco">{_preco_html(presa["preco"])}</div>
  <a class="presa-botao" href="{_esc(presa["link"])}" target="_blank" rel="noopener noreferrer">Ver na loja ↗</a>
</div>
""")


def html_vazio(mensagem: str, nome_gato: str = "laranja_feliz") -> str:
    return vazio(mensagem, nome_gato)

"""
ui/aba_busca.py — A aba "Buscar" (Busca de Presas, o destaque do app).

O usuário digita um produto; o gato pesquisa em cada loja (busca.py, ou
demo.simular_busca no Modo Demo), mostra o log ao vivo num st.status e, no
fim, exibe as presas mais baratas numa grade de cards (ui/cards.py).
"""

import streamlit as st

from cacador import busca, demo, persona, planilhas
from cacador.lojas import lojas_com_busca
from ui import cards, estilo
from ui.log import linha_do_evento, render_log

CARDS_POR_LINHA = 4


def _executar_busca(termo: str, modo_demo: bool, mostrar_navegador: bool) -> None:
    eventos = (demo.simular_busca(termo) if modo_demo
               else busca.buscar_presas(termo, headless=not mostrar_navegador))
    linhas, resultado = [], None

    with st.status(persona.fala("busca_status"), expanded=True) as status:
        area_log = st.empty()
        for ev in eventos:
            if ev["tipo"] == "resultado":
                resultado = ev
                continue
            if ev["tipo"] == "loja":
                # O título do st.status muda a cada loja, com uma frase do gato
                status.update(label=f"{persona.fala('busca_status')}  ·  {ev['loja']}", expanded=True)
            linhas.append(linha_do_evento(ev))
            area_log.markdown(render_log(linhas), unsafe_allow_html=True)

        presas = resultado["presas"] if resultado else []
        rotulo = (f"🐾 {len(presas)} presa(s) encontrada(s) para \"{termo}\"" if presas
                  else f"😿 Nenhuma presa para \"{termo}\"")
        status.update(label=rotulo, state="complete", expanded=False)

    st.session_state["busca"] = {
        "termo": termo, "presas": presas, "linhas": linhas, "demo": modo_demo,
        "lojas_falha": resultado["lojas_falha"] if resultado else [],
        "fala_melhor": persona.fala("melhor_preco"),
        "fala_vazio": persona.fala("nenhuma_presa"),
    }


def _vigiar(presa: dict) -> None:
    """Botão ➕: manda a presa para a Lista de Desejos com meta 10% abaixo do preço atual."""
    meta = round(presa["preco"] * 0.9, 2)
    try:
        adicionou, nome = planilhas.adicionar_a_lista(presa["titulo"], presa["link"], meta, presa["loja"])
    except planilhas.PlanilhaBloqueadaError as erro:
        st.toast(str(erro), icon="😾")
        return
    if adicionou:
        st.toast(persona.fala("vigiar_ok", produto=nome, meta=persona.formatar_reais(meta)), icon="🐾")
    else:
        st.toast(persona.fala("vigiar_repetido"), icon="😒")


def _grade(presas: list[dict], fala_melhor: str) -> None:
    """Grade de cards: 4 por linha (o Streamlit empilha as colunas em telas pequenas)."""
    for inicio in range(0, len(presas), CARDS_POR_LINHA):
        colunas = st.columns(CARDS_POR_LINHA, gap="medium")
        for deslocamento, presa in enumerate(presas[inicio:inicio + CARDS_POR_LINHA]):
            posicao = inicio + deslocamento + 1
            with colunas[deslocamento]:
                chave = "presa_top" if posicao == 1 else f"presa_{posicao}"
                with st.container(key=chave):
                    st.markdown(cards.html_card(presa, posicao, fala_melhor), unsafe_allow_html=True)
                    if st.button("+ Vigiar preço", key=f"vigiar_{posicao}",
                                 use_container_width=True,
                                 help=f"Meta sugerida: {persona.formatar_reais(presa['preco'] * 0.9)} "
                                      "(10% abaixo). Dá pra editar na aba Minha lista."):
                        _vigiar(presa)


def render(modo_demo: bool) -> None:
    st.markdown(cards.CSS_BUSCA, unsafe_allow_html=True)
    nomes = [cfg["nome"] for cfg in lojas_com_busca()]
    st.markdown(estilo.titulo("Busca de Presas",
                              f"Diga o que você quer e eu farejo em {len(nomes)} lojas. "
                              "Trago as 10 ofertas mais baratas."), unsafe_allow_html=True)

    # st.form: apertar Enter no campo também dispara a busca.
    # (o st.container com key é quem recebe o estilo .st-key-caixa_busca)
    with st.container(key="caixa_busca"):
        st.markdown(estilo.gato_espiando("piscando", 100), unsafe_allow_html=True)
        with st.form(key="form_busca", border=False):
            col_termo, col_botao = st.columns([4, 1.3], vertical_alignment="bottom")
            termo = col_termo.text_input("O que vamos caçar hoje?", placeholder="ex.: fone JBL Tune 520",
                                         key="termo_busca")
            farejar = col_botao.form_submit_button("Farejar", type="primary", use_container_width=True)
            mostrar_navegador = st.toggle("Mostrar o navegador enquanto procuro", value=True,
                                          disabled=modo_demo, key="navegador_busca",
                                          help="Algumas lojas (ex.: Mercado Livre) bloqueiam o modo invisível.")
            if modo_demo:
                st.caption("Modo Demo: resultados fictícios, sem abrir o navegador.")
        st.markdown(f'<p class="busca-dica">Lojas: {", ".join(nomes)}.</p>', unsafe_allow_html=True)

    if farejar:
        if len(termo.strip()) < 2:
            st.warning("Me dá uma pista melhor, humano. Digite o nome de um produto. 😾")
        else:
            _executar_busca(termo.strip(), modo_demo, mostrar_navegador)

    ultima = st.session_state.get("busca")
    if not ultima:
        st.markdown(cards.html_vazio("Digite um produto ali em cima e me solte nas lojas.",
                                     "branco_patinhas"), unsafe_allow_html=True)
        return

    if not farejar:  # depois de um rerun (ex.: clicou em "Vigiar"), o log fica guardado aqui
        titulo = f"Diário da última busca: \"{ultima['termo']}\"" + (" (demo)" if ultima["demo"] else "")
        with st.expander(titulo):
            st.markdown(render_log(ultima["linhas"]), unsafe_allow_html=True)

    if ultima["lojas_falha"]:
        st.caption(f"Não consegui entrar em: {', '.join(ultima['lojas_falha'])}. "
                   "Os resultados abaixo são das outras lojas.")

    presas = ultima["presas"]
    if not presas:
        st.markdown(cards.html_vazio(ultima["fala_vazio"], "cinza_emburrado"), unsafe_allow_html=True)
        return

    st.markdown(cards.html_resumo(presas), unsafe_allow_html=True)
    st.markdown('<div class="espaco-gato"></div>', unsafe_allow_html=True)
    _grade(presas, ultima["fala_melhor"])

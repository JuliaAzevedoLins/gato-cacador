"""
ui/aba_lista.py — A aba "Minha lista" (lista de desejos).

Cada produto vira um cartão com o último preço, a meta, o interruptor
"🔔 Alertar" (escolhe se a Caçada manda alerta desse produto) e dois botões:
  - Editar: troca o cartão por um formulário (nome, link e meta);
  - Remover: pede confirmação antes de apagar (o histórico de preços fica guardado).
Tudo é salvo na hora em data/lista_desejos.xlsx, sempre passando pela
validação de planilhas.validar_lista().
"""

import html

import pandas as pd
import streamlit as st

from cacador import persona, planilhas
from cacador.lojas import identificar_loja
from ui import estilo

# Um gatinho diferente para cada produto (só enfeite)
AVATARES = ["acenando", "branco_coracao", "cinza_piscando", "tricolor", "preto",
            "laranja_feliz", "branco_feliz", "cinza_emburrado", "tricolor_feliz", "piscando"]


def _salvar(lista: pd.DataFrame) -> bool:
    """Valida e salva a lista inteira. Mostra os erros e devolve False se não deu."""
    limpa, erros = planilhas.validar_lista(lista)
    if erros:
        st.error("Não salvei. Arrume isso primeiro:\n\n" + "\n".join(f"- {e}" for e in erros))
        return False
    try:
        planilhas.salvar_lista(limpa)
    except planilhas.PlanilhaBloqueadaError as erro:
        st.error(str(erro))
        return False
    return True


def _formulario_adicionar(lista: pd.DataFrame) -> None:
    with st.container(key="caixa_adicionar"):
        st.markdown(estilo.gato_espiando("branco_acenando", 92), unsafe_allow_html=True)
        st.markdown("**Adicionar um produto**")
        with st.form("form_adicionar", clear_on_submit=True, border=False):
            c_nome, c_link, c_meta, c_botao = st.columns([2.2, 3, 1.3, 1.2], vertical_alignment="bottom")
            nome = c_nome.text_input("Nome", placeholder="ex.: Kindle 11ª geração")
            link = c_link.text_input("Link do produto", placeholder="https://...")
            meta = c_meta.number_input("Preço meta (R$)", min_value=0.0, step=10.0, format="%.2f", value=None)
            enviar = c_botao.form_submit_button("Adicionar", type="primary", use_container_width=True)
        st.markdown('<p class="dica">Dica: na aba Buscar, o botão "Vigiar preço" de cada resultado '
                    "já adiciona o produto aqui com uma meta 10% abaixo do preço atual.</p>",
                    unsafe_allow_html=True)
    if enviar:
        nova = pd.DataFrame([{"Produto": nome, "Link": link, "Preço meta": meta}])
        if _salvar(nova if lista.empty else pd.concat([lista, nova], ignore_index=True)):
            st.toast(persona.fala("lista_salva"))
            st.rerun()


def _situacao(produto: str, meta: float, historico: pd.DataFrame) -> str:
    """Último preço + etiqueta (na meta / quanto falta / ainda não visitado)."""
    ultimo = planilhas.ultimo_preco(produto, historico) if not historico.empty else None
    if ultimo is None:
        return f'<div class="item-preco">—</div>{estilo.pilula("ainda não espiei")}'
    falta = ultimo - meta
    etiqueta = (estilo.pilula("na meta!", "ok") if falta <= 0
                else estilo.pilula(f"faltam {persona.formatar_reais(falta)}", "alerta"))
    return f'<div class="item-preco">{html.escape(persona.formatar_reais(ultimo))}</div>{etiqueta}'


def _interruptor_alerta(i: int, item: pd.Series, lista: pd.DataFrame) -> None:
    """🔔 Liga/desliga os alertas (Telegram + aba Alertas) deste produto. Salva na hora."""
    ligado = bool(item["Alertar"])
    # A chave usa o nome (único na lista): se fosse a posição, remover um item
    # faria o interruptor "herdar" o estado do vizinho
    novo = st.toggle("🔔 Alertar quando cair", value=ligado, key=f"alertar_{item['Produto']}",
                     help="Desligado: a Caçada ainda anota o preço, mas não manda alerta.")
    if novo != ligado:
        lista = lista.copy()
        lista.loc[i, "Alertar"] = novo
        try:
            planilhas.salvar_lista(lista)
        except planilhas.PlanilhaBloqueadaError as erro:
            st.error(str(erro))
            return
        st.toast("Alertas ligados. Vou miar quando cair! 🔔" if novo
                 else "Alertas desligados. Só vou anotar o preço. 🔕")


def _cartao(i: int, item: pd.Series, lista: pd.DataFrame, historico: pd.DataFrame) -> None:
    loja, _ = identificar_loja(item["Link"])
    c_gato, c_info, c_preco, c_acoes = st.columns([0.7, 4, 2, 1.4], vertical_alignment="center")
    c_gato.markdown(estilo.gato(AVATARES[i % len(AVATARES)], 64), unsafe_allow_html=True)
    c_info.markdown(
        f'<div class="item-nome">{html.escape(item["Produto"])}</div>'
        f'<div class="item-meta">{estilo.pilula(loja)} '
        f'<span>meta {html.escape(persona.formatar_reais(item["Preço meta"]))}</span> · '
        f'<a href="{html.escape(item["Link"], quote=True)}" target="_blank" rel="noopener noreferrer">'
        "abrir na loja ↗</a></div>", unsafe_allow_html=True)
    with c_info:
        _interruptor_alerta(i, item, lista)
    c_preco.markdown(_situacao(item["Produto"], item["Preço meta"], historico), unsafe_allow_html=True)
    with c_acoes:
        if st.button("Editar", key=f"editar_{i}", use_container_width=True):
            st.session_state["lista_editando"] = i
            st.session_state.pop("lista_removendo", None)
            st.rerun()
        if st.button("Remover", key=f"remover_{i}", use_container_width=True):
            st.session_state["lista_removendo"] = i
            st.session_state.pop("lista_editando", None)
            st.rerun()


def _edicao(i: int, item: pd.Series, lista: pd.DataFrame) -> None:
    with st.form(f"form_editar_{i}", border=False):
        st.markdown(f"**Editando:** {html.escape(item['Produto'])}")
        c_nome, c_link, c_meta = st.columns([2.2, 3, 1.3])
        nome = c_nome.text_input("Nome", value=item["Produto"])
        link = c_link.text_input("Link do produto", value=item["Link"])
        meta = c_meta.number_input("Preço meta (R$)", min_value=0.0, step=10.0, format="%.2f",
                                   value=float(item["Preço meta"]))
        c_salvar, c_cancelar, _ = st.columns([1, 1, 3])
        salvar = c_salvar.form_submit_button("Salvar", type="primary", use_container_width=True)
        cancelar = c_cancelar.form_submit_button("Cancelar", use_container_width=True)
    if cancelar:
        st.session_state.pop("lista_editando", None)
        st.rerun()
    if salvar:
        nova = lista.copy()
        nova.loc[i, ["Produto", "Link", "Preço meta"]] = [nome.strip(), link.strip(), meta]
        if _salvar(nova):
            # O histórico é ligado pelo nome: renomeia lá também
            planilhas.renomear_produto(item["Produto"], nome.strip())
            st.session_state.pop("lista_editando", None)
            st.toast("Produto atualizado. 🐾")
            st.rerun()


def _confirmar_remocao(i: int, item: pd.Series, lista: pd.DataFrame) -> None:
    st.markdown(f"Remover **{html.escape(item['Produto'])}** da lista? "
                "O histórico de preços dele continua guardado.")
    c_sim, c_nao, _ = st.columns([1.3, 1, 3])
    if c_sim.button("Sim, remover", key=f"confirma_remover_{i}", type="primary", use_container_width=True):
        try:
            planilhas.salvar_lista(lista.drop(index=i).reset_index(drop=True))
        except planilhas.PlanilhaBloqueadaError as erro:
            st.error(str(erro))
            return
        st.session_state.pop("lista_removendo", None)
        st.toast("Produto removido da lista. 😿")
        st.rerun()
    if c_nao.button("Cancelar", key=f"cancela_remover_{i}", use_container_width=True):
        st.session_state.pop("lista_removendo", None)
        st.rerun()


CSS_LISTA = """
<style>
div[class*="st-key-item_"] {
    background: #FFFFFF; border: 2px solid var(--tinta); border-radius: 16px;
    padding: .7rem 1rem; box-shadow: var(--sombra); margin-bottom: .3rem;
}
div[class*="st-key-item_"] .stButton button {min-height: 2.1rem; padding: .1rem .6rem;}
.item-nome {font-weight: 800; font-size: 1.05rem; line-height: 1.3;}
.item-meta {color: var(--suave); font-size: .9rem; margin-top: .25rem;
            display: flex; flex-wrap: wrap; gap: .4rem; align-items: center;}
.item-meta a {color: #B0561A; font-weight: 700;}
.item-preco {font-size: 1.35rem; font-weight: 900; line-height: 1.2; margin-bottom: .2rem;}
</style>
"""


def render() -> None:
    st.markdown(CSS_LISTA, unsafe_allow_html=True)
    st.markdown(estilo.titulo("Minha lista",
                              "Os produtos que eu vigio. Na Caçada, visito cada link e comparo com a sua meta."),
                unsafe_allow_html=True)

    lista = planilhas.ler_lista()
    _formulario_adicionar(lista)

    st.markdown(f"#### {len(lista)} produto(s) na mira")
    if lista.empty:
        st.markdown(estilo.vazio("Lista vazia. Adicione um produto acima ou use a aba Buscar.", "caixa"),
                    unsafe_allow_html=True)
        return

    historico = planilhas.ler_historico()
    editando = st.session_state.get("lista_editando")
    removendo = st.session_state.get("lista_removendo")
    for i, item in lista.iterrows():
        with st.container(key=f"item_{i}"):
            if i == editando:
                _edicao(i, item, lista)
            elif i == removendo:
                _confirmar_remocao(i, item, lista)
            else:
                _cartao(i, item, lista, historico)

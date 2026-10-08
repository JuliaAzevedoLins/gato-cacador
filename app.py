"""
app.py — Interface Streamlit do Gato Caçador de Ofertas. 🐱

Rode com:  streamlit run app.py
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from cacador import alertas, demo, persona, planilhas, robo
from cacador.lojas import lojas_com_busca
from ui import aba_busca, aba_lista, estilo
from ui.log import CSS_LOG, linha_do_evento, render_log

st.set_page_config(page_title="Gato Caçador de Ofertas", page_icon="🐱", layout="wide")

# ---------------------------------------------------------------------------
# Estilo (complementa o tema de .streamlit/config.toml)
# ---------------------------------------------------------------------------
# Cores das linhas do gráfico (combinam com os gatinhos: laranja, nanquim, azul, rosa...)
CORES_PRODUTOS = ["#E07A2E", "#2B2118", "#4F7CC2", "#D9668A", "#4E9A62", "#B8901C", "#8C6BB1"]

st.markdown(estilo.CSS_GLOBAL + """
<style>
.st-key-botao_gato button {min-height: 3.6rem;}
.st-key-botao_gato button p {font-size: 1.35rem !important; font-weight: 900 !important;}
</style>
""" + CSS_LOG, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Primeira execução: cria os dados de exemplo
# ---------------------------------------------------------------------------
if not planilhas.ARQ_LISTA.exists():
    demo.restaurar_dados_exemplo()


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f'<div class="lateral-topo">{estilo.gato("oi", 120, alt="Gatinho segurando uma placa escrito Hi")}'
                "<strong>Cesto do Gato</strong></div>", unsafe_allow_html=True)
    modo_demo = st.toggle("Modo Demo", value=False,
                          help="Simula a busca e a caçada com preços fictícios, sem abrir o navegador. "
                               "Plano B para apresentações.")
    if modo_demo:
        st.info("Modo Demo ligado: o gato vai caçar presas de mentirinha.")

    st.divider()
    st.markdown('<p class="lateral-rotulo">Telegram</p>', unsafe_allow_html=True)
    if alertas.configurado():
        st.markdown(estilo.pilula("conectado: os alertas chegam no celular", "ok"), unsafe_allow_html=True)
    else:
        st.markdown(estilo.pilula("não configurado (veja a aba Alertas)", "alerta"), unsafe_allow_html=True)

    st.divider()
    st.markdown('<p class="lateral-rotulo">Lojas que eu conheço</p>', unsafe_allow_html=True)
    st.markdown('<div class="lojas">' + "".join(estilo.pilula(cfg["nome"]) for cfg in lojas_com_busca())
                + "</div>", unsafe_allow_html=True)
    st.caption("Na caçada, outras lojas também funcionam se publicarem o preço em JSON-LD ou meta tags.")

    st.divider()
    with st.expander("Dados de exemplo"):
        st.caption("Recria a lista de desejos e um histórico fictício de 10 dias.")
        if st.button("Restaurar dados de exemplo", use_container_width=True):
            demo.restaurar_dados_exemplo()
            st.session_state.pop("ultima_cacada", None)
            st.toast("Dados de exemplo restaurados. 🐾")
            st.rerun()


# ---------------------------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------------------------
st.markdown(estilo.cabecalho(), unsafe_allow_html=True)

aba_busca_presas, aba_minha_lista, aba_cacada, aba_historico, aba_alertas = st.tabs(
    ["Buscar", "Minha lista", "Caçada", "Histórico", "Alertas"])


def fmt_reais(valor) -> str:
    return persona.formatar_reais(None if pd.isna(valor) else float(valor))


# ===========================================================================
# 0) BUSCA DE PRESAS (lógica em cacador/busca.py, visual em ui/)
# ===========================================================================
with aba_busca_presas:
    aba_busca.render(modo_demo)


# ===========================================================================
# 1) LISTA DE DESEJOS
# ===========================================================================
with aba_minha_lista:
    aba_lista.render()


# ===========================================================================
# 2) CAÇADA
# ===========================================================================
def mostrar_resumo(res: dict) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Produtos visitados", res["visitados"])
    c2.metric("Presas encontradas", res["presas"])
    c3.metric("Erros", res["erros"])
    c4.metric("Alertas no Telegram", res["alertas"])


with aba_cacada:
    st.markdown(estilo.titulo("Hora da caçada",
                              "Visito cada produto da sua lista, anoto o preço e aviso se caiu ou bateu a meta."),
                unsafe_allow_html=True)
    with st.container(key="caixa_cacada"):
        st.markdown(estilo.gato_espiando("cinza_acenando", 96, "esquerda"), unsafe_allow_html=True)
        col_botao, col_opcoes = st.columns([2, 3], vertical_alignment="center")
        with col_opcoes:
            mostrar_navegador = st.toggle("Mostrar o navegador enquanto caço", value=True,
                                          disabled=modo_demo,
                                          help="Desligado = modo headless (invisível). Algumas lojas "
                                               "(ex.: Mercado Livre) bloqueiam o modo invisível.")
            if modo_demo:
                st.caption("No Modo Demo não abro navegador: é tudo simulado.")
            elif not mostrar_navegador:
                st.caption("Modo furtivo: mais rápido, mas algumas lojas desconfiam e me barram.")
        with col_botao:
            with st.container(key="botao_gato"):
                soltar = st.button("Soltar o gato!", type="primary", use_container_width=True)

    area_log = st.empty()
    area_resumo = st.container()

    if soltar:
        lista = planilhas.ler_lista()
        lista, erros_lista = planilhas.validar_lista(lista)
        if erros_lista:
            st.error("A lista de desejos tem problemas. Arrume na aba Minha lista antes de me soltar.")
        else:
            linhas, capturas, resultado = [], [], None
            eventos = (demo.simular_cacada(lista) if modo_demo
                       else robo.cacar(lista, headless=not mostrar_navegador))
            with st.spinner("O gato está caçando... 🐾"):
                for ev in eventos:
                    if ev["tipo"] == "captura":
                        capturas.append(ev)
                        continue
                    if ev["tipo"] == "resumo":
                        resultado = ev
                    linhas.append(linha_do_evento(ev))
                    area_log.markdown(render_log(linhas), unsafe_allow_html=True)
            st.session_state["ultima_cacada"] = {"linhas": linhas, "capturas": capturas,
                                                 "resumo": resultado, "demo": modo_demo}
            if resultado and resultado["presas"]:
                st.balloons()

    ultima = st.session_state.get("ultima_cacada")
    if ultima:
        area_log.markdown(render_log(ultima["linhas"]), unsafe_allow_html=True)
        with area_resumo:
            st.markdown("#### Resumo da caçada" + (" (demo)" if ultima["demo"] else ""))
            if ultima["resumo"]:
                mostrar_resumo(ultima["resumo"])
            if ultima["capturas"]:
                tabela = pd.DataFrame([{
                    "Produto": c["produto"], "Loja": c["loja"], "Preço": c["preco"],
                    "Meta": c["meta"],
                    "Variação": (c["variacao"] * 100) if c["variacao"] is not None else None,
                    "Status": c["status"], "Método": c["metodo"],
                } for c in ultima["capturas"]])
                st.dataframe(tabela, hide_index=True, use_container_width=True, column_config={
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Meta": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Variação": st.column_config.NumberColumn("Variação (%)", format="%.1f%%"),
                })
    else:
        area_log.markdown(render_log([]), unsafe_allow_html=True)


# ===========================================================================
# 3) HISTÓRICO
# ===========================================================================
with aba_historico:
    st.markdown(estilo.titulo("Diário de caça", "Como o preço de cada produto mudou ao longo do tempo."),
                unsafe_allow_html=True)
    historico = planilhas.ler_historico()

    if historico.empty:
        st.markdown(estilo.vazio(persona.fala("historico_vazio"), "cinza_piscando"), unsafe_allow_html=True)
    else:
        produtos = sorted(historico["Produto"].dropna().unique())
        todos = "Todos os produtos"
        escolha = st.selectbox("Filtrar por produto", [todos] + produtos)
        filtrado = historico if escolha == todos else historico[historico["Produto"] == escolha]
        validos = filtrado.dropna(subset=["Preço capturado"]).sort_values("Data/Hora")

        fig = go.Figure()
        for produto in sorted(validos["Produto"].unique()):
            cor = CORES_PRODUTOS[produtos.index(produto) % len(CORES_PRODUTOS)]
            dados = validos[validos["Produto"] == produto]
            fig.add_trace(go.Scatter(
                x=dados["Data/Hora"], y=dados["Preço capturado"], mode="lines+markers",
                name=produto, line=dict(color=cor, width=3, shape="spline", smoothing=0.6),
                marker=dict(size=7), customdata=dados[["Status"]],
                hovertemplate="<b>%{fullData.name}</b><br>%{x|%d/%m %H:%M}<br>"
                              "R$ %{y:,.2f}<br>%{customdata[0]}<extra></extra>",
            ))
            # Linha da meta destacada (tracejada, mesma cor do produto)
            meta = dados["Preço meta"].iloc[-1]
            # (com todos os produtos, a meta fica sem rótulo para não embolar; passar
            # annotation_text=None faria o Plotly escrever "new text" no lugar)
            unico = escolha != todos
            rotulo = (dict(annotation_text=f"meta {fmt_reais(meta)}", annotation_position="top left",
                           annotation_font=dict(color=cor, size=13)) if unico else {})
            fig.add_hline(y=meta, line=dict(color=cor, width=2.5 if unico else 1.5, dash="dash"), **rotulo)
            # Patinhas onde o gato deu o bote (meta atingida)
            botes = dados[dados["Status"] == planilhas.STATUS_META]
            if not botes.empty:
                fig.add_trace(go.Scatter(
                    x=botes["Data/Hora"], y=botes["Preço capturado"], mode="markers+text",
                    text=["🐾"] * len(botes), textposition="top center", textfont=dict(size=18),
                    marker=dict(size=13, color=cor, line=dict(color="#2B2118", width=2)),
                    name=f"Bote: {produto}", showlegend=False, hoverinfo="skip"))

        fig.update_layout(
            height=470, margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
            font=dict(color="#2B2118", family="Nunito, sans-serif"), hovermode="closest",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            yaxis=dict(title="Preço (R$)", tickprefix="R$ ", separatethousands=True,
                       gridcolor="#EFE4D3", linecolor="#2B2118", linewidth=2, showline=True),
            xaxis=dict(gridcolor="#EFE4D3", tickformat="%d/%m", hoverformat="%d/%m %H:%M",
                       linecolor="#2B2118", linewidth=2, showline=True),
            separators=",.",
        )
        with st.container(key="caixa_grafico"):
            st.markdown(estilo.gato_espiando("tricolor_feliz", 90), unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Todas as capturas")
        st.dataframe(
            filtrado.sort_values("Data/Hora", ascending=False),
            hide_index=True, use_container_width=True,
            column_config={
                "Data/Hora": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
                "Preço capturado": st.column_config.NumberColumn(format="R$ %.2f"),
                "Preço meta": st.column_config.NumberColumn(format="R$ %.2f"),
                "Variação (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Link": st.column_config.LinkColumn(display_text="abrir"),
            },
        )
        st.download_button("Baixar histórico (Excel)", planilhas.ARQ_HISTORICO.read_bytes(),
                           file_name="historico.xlsx")


# ===========================================================================
# 4) ALERTAS
# ===========================================================================
with aba_alertas:
    st.markdown(estilo.titulo("Miados no Telegram",
                              "Quando um preço cai ou bate a meta, eu mando uma mensagem no seu celular."),
                unsafe_allow_html=True)
    token_env, chat_env = alertas.carregar_config()

    with st.container(key="caixa_telegram"):
        st.markdown(estilo.gato_espiando("preto", 90), unsafe_allow_html=True)
        col_form, col_ajuda = st.columns([3, 2], gap="large")
        with col_form:
            token = st.text_input("Token do bot", value=token_env, type="password",
                                  help="Lido de TELEGRAM_BOT_TOKEN no arquivo .env")
            chat_id = st.text_input("chat_id", value=chat_env,
                                    help="Lido de TELEGRAM_CHAT_ID no arquivo .env")
            b1, b2, b3 = st.columns(3)
            if b1.button("Miau de teste", type="primary", use_container_width=True):
                ok, detalhe = alertas.enviar_telegram(persona.fala("teste_telegram"), token, chat_id)
                if ok:
                    st.success("Miau entregue! Olha o seu Telegram. 😼")
                else:
                    st.error(f"Não consegui miar: {detalhe}")
            if b2.button("Salvar", use_container_width=True, help="Grava o token e o chat_id no arquivo .env"):
                alertas.salvar_config(token, chat_id)
                st.success("Guardei no .env (ele fica fora do Git).")
            if b3.button("Achar chat_id", use_container_width=True,
                         help="Mande qualquer mensagem pro seu bot no Telegram e clique aqui."):
                if not token:
                    st.warning("Preciso do token primeiro.")
                else:
                    achado, detalhe = alertas.descobrir_chat_id(token)
                    if achado:
                        st.success(f"chat_id: `{achado}` ({detalhe}). Cole no campo acima e salve.")
                    else:
                        st.warning(detalhe)
        with col_ajuda:
            st.markdown("""
**Como configurar (1 minuto):**
1. No Telegram, fale com **@BotFather**, mande `/newbot` e copie o **token**.
2. Abra o seu bot e mande um "oi".
3. Cole o token aqui e clique em **Achar chat_id**.
4. Clique em **Salvar** e mande um **Miau de teste**.
""")

    st.markdown("#### Alertas já disparados")
    lista_alertas = planilhas.ler_alertas()
    if lista_alertas.empty:
        st.markdown(estilo.vazio("Nenhum alerta ainda. Nenhuma presa caiu na armadilha... por enquanto.",
                                 "cinza_emburrado"), unsafe_allow_html=True)
    else:
        st.dataframe(
            lista_alertas.sort_values("Data/Hora", ascending=False), hide_index=True,
            use_container_width=True,
            column_config={
                "Data/Hora": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
                "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                "Preço meta": st.column_config.NumberColumn(format="R$ %.2f"),
                "Variação (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Mensagem": st.column_config.TextColumn(width="large"),
            },
        )

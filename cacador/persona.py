"""
persona.py — Todas as falas do Gato Caçador. 🐱

O gato é preguiçoso, levemente arrogante, mas implacável quando avista uma presa
(um preço baixo). Cada situação tem várias variações, sorteadas aleatoriamente
para o gato não ficar repetindo a mesma frase.

Uso:
    from cacador import persona
    persona.fala("espreitando", produto="Kindle")
"""

import random

FALAS: dict[str, list[str]] = {
    # --- Ciclo da caçada -----------------------------------------------------
    "acordando": [
        "Acordei da soneca... vamos ver se tem presa hoje. 😼",
        "*espreguiça* Tá bom, tá bom, eu caço. Mas só porque eu quero. 🐱",
        "Bigodes calibrados, garras afiadas. Hora de caçar preço. 😼",
        "Interromperam meu cochilo das 14h. Espero que valha a pena.",
        "Lambendo a pata e abrindo o navegador... a caçada começou. 🐾",
    ],
    "abrindo_navegador": [
        "Abrindo o navegador com a pata esquerda (a boa)...",
        "Pulando pra dentro do navegador... 🖥️",
        "Subindo no teclado pra abrir o navegador. Ninguém mexe em nada agora.",
    ],
    "navegador_oculto": [
        "Modo furtivo ativado: vou caçar sem ninguém me ver. 🥷🐈‍⬛",
        "Caçando no escuro, como todo bom felino. 🌙",
    ],
    "espreitando": [
        "Espreitando o {produto}...",
        "Agachado atrás do sofá, mirando no {produto}... 👀",
        "Rabo balançando... analisando o {produto}.",
        "Farejando o preço do {produto}... 🐽 (não, isso é de porco. Enfim.)",
        "Pupilas dilatadas. Alvo: {produto}.",
    ],
    "sem_queda": [
        "{produto} a {preco}. Ainda não vale o pulo.",
        "{produto} por {preco}? Nem me levanto por isso. 😒",
        "{produto} continua em {preco}. Volto a dormir nesse assunto.",
        "{produto}: {preco}. Caro demais pra um gato do meu nível.",
        "{produto} a {preco}... bocejei só de ver. 🥱",
    ],
    "queda": [
        "Opa! {produto} caiu {variacao} e está em {preco}. Bigodes em alerta! 🙀",
        "{produto} deu uma escorregada: {preco} ({variacao}). Tô de olho.",
        "Cheirinho de presa... {produto} caiu {variacao}, agora {preco}. 😼",
    ],
    "bote": [
        "🐾 BOTE CERTEIRO! {produto} caiu {variacao} e está em {preco}. Pode me agradecer com sachê.",
        "🐾 PEGUEI! {produto} a {preco} ({variacao}). Quero meu sachê de salmão.",
        "🐾 PRESA ABATIDA! {produto} por {preco}. Eu sou incrível, eu sei. 😼",
        "🐾 NHAC! {produto} chegou na meta: {preco}. Pode deixar o petisco no pote.",
    ],
    "tentando_de_novo": [
        "Errei o pulo no {produto}... tentando de novo, ninguém viu. 😾",
        "A presa escapou ({produto}). Mais uma tentativa, com estilo.",
        "{produto} se escondeu. Vou cutucar mais uma vez.",
    ],
    "erro": [
        "Essa loja me deu um chega pra lá... pulei pra próxima. 🙀",
        "{produto}: a loja fechou a porta na minha cara. Seguindo a caçada. 😾",
        "Não consegui pegar o preço do {produto}. Fingindo que foi de propósito.",
        "{produto} fugiu pro telhado. Deixa ele, tem mais presa por aí. 🐈",
    ],
    "bloqueado": [
        "{produto}: a loja pediu RG e CPF pro gato. Não tenho bolso. Pulei pra próxima. 🙀",
        "{produto}: fui barrado na portaria (anti-robô). Que desfeita. 😾",
        "{produto}: a loja me pediu pra provar que sou humano. Não sou, e tenho orgulho. 🐈",
    ],
    "encerrando": [
        "Caçada encerrada. Voltando pra minha soneca. 💤",
        "Pronto. Trabalhei demais por hoje. Zzz... 💤",
        "Fim da ronda. Agora, um cochilo de 16 horas. 😴",
        "Missão cumprida. Me acorde só se o atum entrar em promoção. 💤",
    ],
    "lista_vazia": [
        "Lista de desejos vazia? Me acordou à toa. 😾",
        "Não tem nada pra caçar... vou voltar pro meu cesto.",
    ],
    # --- Busca de presas -----------------------------------------------------
    "busca_inicio": [
        "Hmm, \"{termo}\"? Deixa eu esticar as patas e farejar por aí. 😼",
        "Procurando \"{termo}\"... Você tem sorte que eu estava acordado. 🐱",
        "\"{termo}\", anotado. Vou rondar as lojas atrás disso. 🐾",
    ],
    "busca_status": [
        "Afiando as garras...",
        "Farejando as prateleiras...",
        "Pulando de loja em loja...",
        "Espiando por trás das vitrines...",
        "Contando as presas na tigela...",
    ],
    "loja_espreitando": [
        "Espreitando o {loja}...",
        "Entrando de fininho no {loja}... 👀",
        "Pulando a janela do {loja}...",
    ],
    "loja_avistadas": [
        "{loja}: {n} presas avistadas. 👀",
        "{loja}: {n} presas na mira. 😼",
        "{loja} rendeu {n} presas. Nada mal.",
    ],
    "loja_descartes": [
        "Descartei {n} itens que não tinham nada a ver (ou eram anúncio). Tenho padrões. 😒",
        "{n} itens foram pro lixo: sem preço, patrocinados ou fora do assunto.",
    ],
    "loja_vazia": [
        "{loja}: nenhuma presa por lá. Só poeira e bolinhas de pelo.",
        "{loja} não tinha nada de \"{termo}\". Que decepção. 😿",
    ],
    "loja_bloqueio": [
        "{loja} me deu um chega pra lá (captcha/bloqueio). Não vou forçar a porta: sigo pra próxima. 🙀",
        "{loja} pediu pra eu provar que sou humano. Não sou. Próxima loja! 😾",
    ],
    "loja_nova_tentativa": [
        "{loja} fechou a porta na minha cara. Vou esperar uns segundos e tentar de novo... 😼",
        "{loja} desconfiou de mim. Finjo que é só uma soneca e volto já. 💤",
    ],
    "loja_erro": [
        "{loja} tropeçou no próprio rabo (deu erro). Sigo com as outras. 🙀",
    ],
    "buscando_fotos": [
        "Algumas presas vieram sem retrato... vou buscar a foto na página delas. 📸",
    ],
    "busca_fim": [
        "Pronto! {n} presas enfileiradas, da mais barata pra mais cara. 😼",
        "Caçada de busca encerrada: {n} presas na bandeja. 🐾",
    ],
    "nenhuma_presa": [
        "Nenhuma presa à vista... esse produto deve estar escondido debaixo do sofá. 😿",
        "Rodei tudo e nada. Esse produto deve estar escondido debaixo do sofá. 😿",
    ],
    "melhor_preco": [
        "Essa presa é minha. Melhor preço da caçada!",
        "Esse aqui eu já marquei com a pata. Mais barato não tem!",
        "Melhor preço da caçada. De nada. 😼",
    ],
    "vigiar_ok": [
        "Presa marcada! Vou vigiar \"{produto}\" e miar se baixar de {meta}. 🐾",
        "\"{produto}\" entrou na lista. Meta: {meta}. Agora é comigo. 😼",
    ],
    "vigiar_repetido": [
        "Essa presa já está na minha mira, humano. 😒",
    ],
    # --- Alertas / Telegram --------------------------------------------------
    "teste_telegram": [
        "Miau de teste! 🐱 Se você está lendo isso, o Gato Caçador sabe onde você mora (no Telegram).",
        "Miau! 🐾 Teste de alerta. Tudo certo por aqui, humano.",
        "Teste, teste... miau? 😼 Conexão com o Telegram funcionando.",
    ],
    "alerta_desligado": [
        "Alertas de {produto} estão desligados na lista. Anotei o preço e fiquei quietinho. 🤫",
        "Não vou miar sobre {produto}: você desligou o 🔔 dele. Só anotei o preço.",
    ],
    "telegram_ok": [
        "Recado entregue no Telegram. 📬",
        "Miei no seu Telegram. 📲",
    ],
    "telegram_sem_config": [
        "Sem token do Telegram, só posso miar aqui mesmo. 🔕",
        "Telegram não configurado. Guardei o alerta pra mim. 🔕",
    ],
    "telegram_falhou": [
        "O Telegram não quis ouvir meu miado: {erro} 🙀",
    ],
    # --- Interface -----------------------------------------------------------
    "lista_salva": [
        "Lista guardada debaixo da almofada. 🐾",
        "Anotado. Vou ficar de olho nessas presas. 😼",
    ],
    "historico_vazio": [
        "Ainda não cacei nada. Me solte primeiro! 🐾",
        "Histórico vazio... nem um ratinho por enquanto.",
    ],
    "demo": [
        "🎭 Modo Demo: caçando presas de mentirinha (mas com muita convicção).",
    ],
}


def fala(situacao: str, **dados) -> str:
    """Sorteia uma fala para a situação e preenche os campos (produto, preco...)."""
    opcoes = FALAS.get(situacao) or [situacao]
    texto = random.choice(opcoes)
    try:
        return texto.format(**dados)
    except (KeyError, IndexError):
        return texto


def formatar_reais(valor: float | None) -> str:
    """1299.9 -> 'R$ 1.299,90' (formato brasileiro)."""
    if valor is None:
        return "—"
    texto = f"{valor:,.2f}"  # 1,299.90
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_variacao(pct: float | None) -> str:
    """-0.18 -> '18,0%' ; None -> 'pra dentro da meta' (primeira captura)."""
    if pct is None:
        return "pra dentro da meta"
    return f"{abs(pct) * 100:.1f}%".replace(".", ",")


def _escapar_html(texto: str) -> str:
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def mensagem_alerta(abertura: str, produto: str, preco: float, meta: float,
                    variacao: float | None, link: str) -> str:
    """Monta o texto (HTML do Telegram) do alerta de queda de preço."""
    if variacao is None:
        linha_var = "primeira espiada (sem comparação ainda)"
    else:
        sinal = "▼" if variacao < 0 else "▲"
        linha_var = f"{sinal} {formatar_variacao(variacao)} desde a última espiada"

    abertura, produto = _escapar_html(abertura), _escapar_html(produto)
    link = _escapar_html(link).replace('"', "&quot;")
    return (
        f"{abertura}\n\n"
        f"🛍️ <b>{produto}</b>\n"
        f"💰 Preço atual: <b>{formatar_reais(preco)}</b>\n"
        f"🎯 Meta: {formatar_reais(meta)}\n"
        f"📉 Variação: {linha_var}\n"
        f"🔗 <a href=\"{link}\">Ver a presa</a>"
    )

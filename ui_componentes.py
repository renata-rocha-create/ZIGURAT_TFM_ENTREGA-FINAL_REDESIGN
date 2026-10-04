"""
ui_componentes.py — Componentes visuais e TEXTOS DE EXPLICAÇÃO compartilhados.

Tudo aqui gera HTML puro (strings). É usado pelo app (nbr9050_app.py),
pelo dashboard (dashboard.py) e pelo relatório exportado (relatorios.py),
para que as três telas expliquem os conceitos com AS MESMAS palavras.

Princípio de redação: escrever para quem nunca ouviu falar de IFC ou LLM.
O termo técnico aparece entre parênteses, para a banca reconhecer.
"""
from html import escape

from ui_style import (CORES_STATUS, SIMBOLO_STATUS, CORES_CONFIANCA,
                      SIMBOLO_CONFIANCA)
from verificacoes import classificar_status, CATEGORIAS

ORDEM_STATUS = ["Conforme", "Parcial", "Não Conforme", "Indeterminado", "N/A"]

# Rótulo curto (plural) de cada status, para listas e legendas
ROTULO_STATUS_PLURAL = {
    "Conforme": "Conformes",
    "Parcial": "Parciais",
    "Não Conforme": "Não conformes",
    "Indeterminado": "Indeterminados",
    "N/A": "Não se aplicam (N/A)",
}

# O que cada status significa, em uma linha
SIGNIFICADO_STATUS = {
    "Conforme": "atende à norma",
    "Parcial": "parte dos elementos atende, parte não",
    "Não Conforme": "não atende à norma",
    "Indeterminado": "faltou informação no modelo para concluir",
    "N/A": "o item não existe neste modelo (ex.: não há rampa)",
}

# ── Origem do dado (antes: "confiança ALTA/MÉDIA/BAIXA") ─────────────────────
# Mesma lógica de verificacoes.confianca_por_fonte(), em linguagem leiga.
ORIGEM_DADO = {
    "ALTA": {
        "rotulo": "Lido do modelo",
        "curto": "lido do modelo",
        "explica": "o valor está escrito no arquivo IFC (ex.: largura cadastrada da porta).",
    },
    "MEDIA": {
        "rotulo": "Calculado da geometria",
        "curto": "calculado da geometria",
        "explica": "o sistema mediu a forma ou a posição do elemento "
                   "(ex.: inclinação da rampa pela diferença de cotas).",
    },
    "BAIXA": {
        "rotulo": "Estimado pelo nome",
        "curto": "estimado pelo nome",
        "explica": "deduzido do nome do elemento ou da relação entre elementos "
                   "(ex.: “maçaneta alavanca” no nome da porta). Vale conferir.",
    },
}


def rotulo_origem(nivel: str) -> str:
    """'ALTA' -> '▮▮▮ Lido do modelo' (texto puro, para tabelas)."""
    info = ORIGEM_DADO.get(nivel)
    return f"{SIMBOLO_CONFIANCA[nivel]} {info['rotulo']}" if info else (nivel or "—")


def fmt_pct(valor) -> str:
    """'100.0%' -> '100%' · '41.7%' -> '41,7%' · 87.25 -> '87,3%' · None -> '—'."""
    if valor is None or valor == "—":
        return "—"
    try:
        num = float(str(valor).replace("%", "").replace(",", ".").strip())
    except ValueError:
        return str(valor)
    if abs(num - round(num)) < 0.05:
        return f"{round(num):.0f}%"
    return f"{num:.1f}%".replace(".", ",")


# ══════════════════════════════════════════════════════════════════════════════
# CARDS
# ══════════════════════════════════════════════════════════════════════════════
def kpi(valor, rotulo: str, contexto: str = "", cor: str = "", extra_html: str = "") -> str:
    """Card de indicador: rótulo em cima, número grande, linha de contexto."""
    ctx = f'<div class="metric-ctx">{contexto}</div>' if contexto else ""
    return (f'<div class="metric-card">'
            f'<div class="metric-label">{rotulo}</div>'
            f'<div class="metric-num {cor}">{valor}</div>{ctx}{extra_html}</div>')


def linha_kpis(cards: list[str]) -> str:
    return f'<div class="metric-row">{"".join(cards)}</div>'


def mini_barra(partes: list[tuple[float, str]]) -> str:
    """Barrinha segmentada para dentro de um card: [(qtd, cor), ...]."""
    total = sum(q for q, _ in partes) or 1
    segs = "".join(f'<span style="flex:{q / total};background:{c}"></span>'
                   for q, c in partes if q)
    return f'<div class="mini-seg" aria-hidden="true">{segs}</div>'


# ══════════════════════════════════════════════════════════════════════════════
# BARRA SEGMENTADA + LISTA  (inspiração: "Department Load")
# ══════════════════════════════════════════════════════════════════════════════
def barra_segmentada(itens: list[dict], titulo_total: str = "Total") -> str:
    """
    itens: [{"rotulo", "qtd", "cor", "simbolo", "detalhe"(opcional)}, ...]
    Desenha uma barra única dividida + lista com quantidade e percentual.
    """
    total = sum(i["qtd"] for i in itens)
    if not total:
        return '<div class="texto-suave">Sem dados.</div>'
    segs, linhas = [], []
    for i in itens:
        if not i["qtd"]:
            continue
        pct = i["qtd"] / total * 100
        segs.append(f'<span class="seg" style="flex:{i["qtd"]};background:{i["cor"]}" '
                    f'title="{escape(i["rotulo"])}: {i["qtd"]}"></span>')
    for i in itens:
        pct = i["qtd"] / total * 100
        det = f'<div class="seg-det">{i["detalhe"]}</div>' if i.get("detalhe") else ""
        apagado = " seg-zero" if not i["qtd"] else ""
        linhas.append(f"""
        <div class="seg-row{apagado}">
          <span class="seg-dot" style="background:{i['cor']}">{i.get('simbolo', '')}</span>
          <div class="seg-txt"><div class="seg-lbl">{i['rotulo']}</div>{det}</div>
          <span class="seg-qtd">{i['qtd']}</span>
          <span class="seg-pct">{fmt_pct(pct)}</span>
        </div>""")
    return f"""
    <div class="seg-head"><span>{titulo_total}</span><strong>{total}</strong></div>
    <div class="segbar" role="img" aria-label="Distribuição">{''.join(segs)}</div>
    <div class="seg-list">{''.join(linhas)}</div>"""


def segmentos_status(contagens: dict) -> list[dict]:
    """Converte {status: qtd} nos itens da barra segmentada."""
    return [{"rotulo": ROTULO_STATUS_PLURAL[s], "qtd": int(contagens.get(s, 0)),
             "cor": CORES_STATUS[s], "simbolo": SIMBOLO_STATUS[s],
             "detalhe": SIGNIFICADO_STATUS[s]} for s in ORDEM_STATUS]


def segmentos_origem(contagens: dict) -> list[dict]:
    """Converte {'ALTA': n, ...} nos itens da barra segmentada."""
    return [{"rotulo": f"{SIMBOLO_CONFIANCA[n]}&nbsp; {ORIGEM_DADO[n]['rotulo']}",
             "qtd": int(contagens.get(n, 0)), "cor": CORES_CONFIANCA[n], "simbolo": "",
             "detalhe": ORIGEM_DADO[n]["explica"]} for n in ("ALTA", "MEDIA", "BAIXA")]


# ══════════════════════════════════════════════════════════════════════════════
# LEGENDAS / EXPLICAÇÕES
# ══════════════════════════════════════════════════════════════════════════════
def legenda_origem_html() -> str:
    linhas = "".join(
        f'<div class="leg-row"><span class="leg-sym">{SIMBOLO_CONFIANCA[n]}</span>'
        f'<div><strong>{ORIGEM_DADO[n]["rotulo"]}:</strong> {ORIGEM_DADO[n]["explica"]}</div></div>'
        for n in ("ALTA", "MEDIA", "BAIXA"))
    return f"""
    <div class="legenda">
      <div class="leg-title">De onde vem cada medida?</div>
      {linhas}
      <div class="leg-nota">Quanto mais barras, mais direto é o dado. Na metodologia do TFM,
      isso corresponde ao nível de confiança (alta, média, baixa) por proveniência do dado.</div>
    </div>"""


def conformidade_cards_html(resumo: dict) -> str:
    """Os dois percentuais de conformidade, cada um com sua explicação."""
    total = resumo.get("total", 0)
    na = resumo.get("na", 0)
    aplicaveis = total - na
    bruta = fmt_pct(resumo.get("percentual_conformidade"))
    sem_na = fmt_pct(resumo.get("percentual_sobre_verificaveis"))
    nota_igual = ("Os dois valores ficam iguais quando nenhum item é N/A, como neste modelo."
                  if na == 0 else
                  f"{na} {'item não se aplica' if na == 1 else 'itens não se aplicam'} a este modelo "
                  f"e {'sai' if na == 1 else 'saem'} da segunda conta.")
    return f"""
    <div class="conf-row">
      <div class="conf-card">
        <div class="metric-label">Conformidade geral <span class="tec">(bruta)</span></div>
        <div class="conf-num">{bruta}</div>
        <div class="conf-exp">Considera <strong>todos os {total} itens</strong> da norma avaliados,
        inclusive os que não existem no modelo.</div>
      </div>
      <div class="conf-card">
        <div class="metric-label">Conformidade dos itens aplicáveis <span class="tec">(sem N/A)</span></div>
        <div class="conf-num">{sem_na}</div>
        <div class="conf-exp">Considera <strong>só os {aplicaveis} itens</strong> que existem neste
        modelo. É a medida mais justa do projeto.</div>
      </div>
    </div>
    <div class="conf-nota">{nota_igual} Itens <em>parciais</em> contam como meio ponto.</div>"""


def como_calculamos_md(resumo: dict) -> str:
    """Texto (markdown) para o popover 'Como calculamos?'."""
    total = resumo.get("total", 0)
    na = resumo.get("na", 0)
    return f"""
**Conformidade geral (bruta)**
(conformes + ½ × parciais) ÷ **{total}** itens avaliados

**Conformidade dos itens aplicáveis (sem N/A)**
(conformes + ½ × parciais) ÷ **{total - na}** itens que se aplicam ao modelo

*Por que meio ponto para "parcial"?* Contar como conforme esconderia os elementos
que falham; contar como não conforme esconderia os que já atendem.

*Analogia:* é como a taxa de ocupação calculada sobre o terreno inteiro versus
sobre a área edificável. As duas estão certas, mas respondem perguntas diferentes.
"""


def _chips(itens: list[dict]) -> str:
    return "".join(
        f'<span class="chip">{escape(str(r.get("item_nbr", "")))} · '
        f'{escape(CATEGORIAS.get(str(r.get("item_nbr")), r.get("categoria", "")))}</span>'
        for r in itens)


def analise_geral_html(resultado: dict) -> str:
    """
    'Análise geral' estruturada, a partir dos status FINAIS (mesmos dados do
    texto de verificacoes.gerar_observacoes, só que organizados para leitura).
    """
    itens = resultado.get("resultados", [])
    resumo = resultado.get("resumo", {})
    por_status = {s: [r for r in itens if classificar_status(r.get("status", "")) == s]
                  for s in ORDEM_STATUS}
    total = resumo.get("total", len(itens))
    conf = len(por_status["Conforme"])
    atencao = por_status["Não Conforme"] + por_status["Parcial"]

    if not atencao and not por_status["Indeterminado"]:
        manchete = f"<strong>{conf} de {total}</strong> itens avaliados atendem à NBR 9050."
        classe = "ok"
    else:
        n = len(atencao) + len(por_status["Indeterminado"])
        manchete = (f"<strong>{n} {'ponto precisa' if n == 1 else 'pontos precisam'} de atenção</strong> · "
                    f"{conf} de {total} itens atendem à norma.")
        classe = "atencao"

    blocos = []
    grupos = [
        ("Não Conforme", "Não atendem", "Corrigir no projeto — ver recomendação na tabela."),
        ("Parcial", "Atendem em parte", "Alguns elementos falham — ver a coluna “Encontrado”."),
        ("Indeterminado", "Precisam de verificação manual", "Faltou informação no modelo."),
        ("Conforme", "Atendem", ""),
        ("N/A", "Não se aplicam a este modelo", ""),
    ]
    for s, titulo, dica in grupos:
        if por_status[s]:
            d = f'<span class="an-dica">{dica}</span>' if dica else ""
            blocos.append(f"""
            <div class="an-bloco">
              <div class="an-tit"><span class="an-sym" style="color:{CORES_STATUS[s]}">{SIMBOLO_STATUS[s]}</span>
                {titulo} <span class="an-qtd">{len(por_status[s])}</span>{d}</div>
              <div class="chips">{_chips(por_status[s])}</div>
            </div>""")

    corrigidos = [r for r in itens if r.get("fonte_veredito") == "python"
                  and r.get("status_llm_original") not in (None, "—")
                  and classificar_status(r["status_llm_original"]) != classificar_status(r.get("status", ""))]
    corr_html = ""
    if corrigidos:
        linhas = "".join(
            f'<div class="corr-row"><span class="chip">{escape(str(r["item_nbr"]))} · '
            f'{escape(CATEGORIAS.get(str(r["item_nbr"]), ""))}</span>'
            f'<span class="corr-de">IA: {escape(classificar_status(r["status_llm_original"]))}</span>'
            f'<span class="corr-seta">→</span>'
            f'<span class="corr-para">Cálculo: {escape(classificar_status(r["status"]))}</span></div>'
            for r in corrigidos)
        corr_html = f"""
        <div class="an-corr">
          <div class="an-tit">Onde o cálculo corrigiu a IA <span class="an-qtd">{len(corrigidos)}</span></div>
          <div class="an-dica" style="margin:0.15rem 0 0.5rem 0">Nos itens medidos, o resultado do cálculo
          (Python) prevalece sobre o parecer da IA (LLM). Estes são os itens em que os dois discordaram.</div>
          {linhas}
        </div>"""

    return f"""
    <div class="analise">
      <div class="an-manchete an-{classe}">{manchete}</div>
      {''.join(blocos)}
      {corr_html}
    </div>"""

"""
dashboard.py — Visualizações dos resultados da auditoria.

Etapa 2: aba "Por Elemento" — tabela de verificação elemento a elemento,
nível de confiança e comparação LLM × Python.
(Etapa 3: aba "Dashboard" — KPIs, gráficos Altair e lista de ação.)
"""
import altair as alt
import pandas as pd
import streamlit as st

from verificacoes import classificar_prototipo, CATEGORIAS
from bcf_export import gerar_bcfzip

from ui_style import (CORES_STATUS, CORES_CONFIANCA, SIMBOLO_STATUS,
                      SIMBOLO_CONFIANCA, FONTE_UI, PALETA)
from ui_componentes import (kpi, linha_kpis, mini_barra, barra_segmentada, segmentos_status,
                            segmentos_origem, legenda_origem_html, rotulo_origem, fmt_pct,
                            ORIGEM_DADO, ORDEM_STATUS)

# Status: símbolo + rótulo (sem emoji colorido — a forma já diferencia)
ICONE_STATUS = {s: f"{SIMBOLO_STATUS[s]} {s}" for s in SIMBOLO_STATUS}
# Confiança: "barras de sinal" (não usa verde/vermelho, que são cores de status)
ICONE_CONF = {n: rotulo_origem(n) for n in ("ALTA", "MEDIA", "BAIXA")}


def _card(valor, rotulo, cor=""):
    return (f'<div class="metric-card"><div class="metric-num {cor}">{valor}</div>'
            f'<div class="metric-label">{rotulo}</div></div>')


def render_aba_elementos(linhas: list[dict] | None, comparacao: dict | None) -> None:
    if not linhas:
        st.markdown(
            '<div class="info-box">Nenhuma verificação por elemento disponível. '
            'Execute a auditoria na aba <strong>Nova auditoria</strong>.</div>',
            unsafe_allow_html=True)
        return

    df = pd.DataFrame(linhas)

    # ── Abertura: a lógica da aba em uma frase ────────────────────────────────
    st.markdown(
        '<div class="passo-a-passo">Cada item da norma é checado de <strong>duas formas '
        'independentes</strong>: um <strong>cálculo</strong> com as medidas do modelo e uma '
        '<strong>leitura pela IA</strong>. Quando as duas discordam, <strong>vale o cálculo</strong> — '
        'e a divergência aparece aqui para você conferir.</div>', unsafe_allow_html=True)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    n = len(df)
    conf = int((df.status == "Conforme").sum())
    nconf = int((df.status == "Não Conforme").sum())
    indet = int((df.status == "Indeterminado").sum())
    alta = int((df.confianca == "ALTA").sum())
    cont_origem = df.confianca.value_counts().to_dict()
    ok = comparacao.get("concordantes") if comparacao else None
    comp = comparacao.get("comparaveis") if comparacao else None
    taxa = comparacao.get("taxa_concordancia") if comparacao else None
    st.markdown(linha_kpis([
        kpi(n, "Verificações feitas", f"{df.global_id.nunique()} elementos × itens da norma"),
        kpi(conf, "Conformes", "verificações que atendem à norma", "c-green"),
        kpi(nconf, "Não conformes", "verificações que não atendem", "c-red"),
        kpi(indet, "Indeterminadas", "faltou informação no modelo", "c-amber"),
        kpi(f"{alta}<span class='tec' style='font-size:1rem'>/{n}</span>", "Medidas lidas direto do modelo",
            "as demais foram calculadas ou estimadas — ver legenda",
            extra_html=mini_barra([(cont_origem.get(k, 0), CORES_CONFIANCA[k]) for k in ("ALTA", "MEDIA", "BAIXA")])),
        kpi(f"{ok}<span class='tec' style='font-size:1rem'>/{comp}</span>" if comp else "—",
            "IA e cálculo concordaram",
            f"itens com o mesmo resultado ({fmt_pct(taxa)}) <span class='tec'>· concordância LLM × Python</span>"
            if comp else "sem itens comparáveis", "c-purple"),
    ]), unsafe_allow_html=True)

    st.markdown(legenda_origem_html(), unsafe_allow_html=True)

    # ── Comparação IA × cálculo ───────────────────────────────────────────────
    if comparacao and comparacao.get("tabela"):
        st.markdown('<div class="section-title">Parecer da IA × resultado do cálculo '
                    '<span class="section-sub">por item da norma</span></div>',
                    unsafe_allow_html=True)
        dc = pd.DataFrame(comparacao["tabela"])
        dc["status_llm"] = dc["status_llm"].map(lambda s: ICONE_STATUS.get(s, s))
        dc["status_python"] = dc["status_python"].map(lambda s: ICONE_STATUS.get(s, s))
        dc["concorda"] = dc["concorda"].map({True: "✓ Sim", False: "✕ Não — vale o cálculo", None: "—"})
        dc["tipo"] = dc["tipo"].map({"Numérico": "Medição", "Qualitativo (texto)": "Leitura de texto"}).fillna(dc["tipo"])
        st.dataframe(
            dc[["item_nbr", "categoria", "status_python", "status_llm", "concorda", "tipo"]],
            hide_index=True, use_container_width=True,
            column_config={
                "item_nbr": "Item NBR", "categoria": "O que foi checado",
                "status_python": st.column_config.TextColumn(
                    "Resultado do cálculo", help="Medição feita em Python a partir da geometria e dos dados do IFC. É o resultado que vale."),
                "status_llm": st.column_config.TextColumn(
                    "Parecer da IA", help="Resposta do modelo de linguagem (LLM) lendo os mesmos dados."),
                "concorda": st.column_config.TextColumn(
                    "IA e cálculo concordam?", help="Quando discordam, prevalece o cálculo."),
                "tipo": st.column_config.TextColumn(
                    "Como foi checado", help="Medição = valores numéricos; Leitura de texto = deduzido do nome do elemento."),
            })
        st.caption(f"A IA e o cálculo chegaram ao mesmo resultado em {ok} de {comp} itens. "
                   "Uma divergência não é necessariamente um erro do projeto: indica que vale "
                   "olhar o item com atenção (a IA pode ter se enganado, ou a regra de cálculo precisa de ajuste).")

    # ── Filtros ───────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Verificação por elemento</div>',
                unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.2])
    f_status = c1.multiselect("Status", sorted(df.status.unique()), key="fe_status")
    f_item = c2.multiselect("Item NBR", sorted(df.item_nbr.unique()), key="fe_item")
    f_conf = c3.multiselect("Origem do dado", ["ALTA", "MEDIA", "BAIXA"], key="fe_conf",
                            format_func=lambda k: ORIGEM_DADO[k]["rotulo"])
    f_gid = c4.text_input("Buscar GlobalId", key="fe_gid")

    dv = df.copy()
    if f_status: dv = dv[dv.status.isin(f_status)]
    if f_item:   dv = dv[dv.item_nbr.isin(f_item)]
    if f_conf:   dv = dv[dv.confianca.isin(f_conf)]
    if f_gid:    dv = dv[dv.global_id.str.contains(f_gid.strip(), case=False, na=False)]

    dv_show = dv.assign(
        status=dv.status.map(lambda s: ICONE_STATUS.get(s, s)),
        confianca=dv.confianca.map(lambda c: ICONE_CONF.get(c, c)),
    )[["item_nbr", "categoria", "status", "confianca", "nome", "global_id", "pavimento",
       "valor_medido", "valor_exigido", "mensagem", "ifc_class", "fonte_dado"]]

    st.dataframe(
        dv_show, hide_index=True, use_container_width=True, height=420,
        column_config={
            "item_nbr": "Item", "categoria": "Categoria", "status": "Status",
            "confianca": "Origem do dado", "nome": "Elemento", "global_id": "GlobalId",
            "pavimento": "Pavimento", "valor_medido": "Medido", "valor_exigido": "Exigido",
            "mensagem": "Observação", "ifc_class": "Classe IFC", "fonte_dado": "Fonte técnica",
        })
    st.caption(f"Exibindo {len(dv)} de {n} verificações.")

    st.download_button(
        "Baixar tabela por elemento (CSV)",
        data=df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="verificacao_por_elemento.csv", mime="text/csv",
    )


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 3 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
# Gráficos em Altair — biblioteca que JÁ vem instalada junto com o Streamlit,
# então não é preciso mexer no requirements.txt.

# Cores vêm do ui_style.py (fonte única da identidade visual)
CORES_CONF = CORES_CONFIANCA
ROTULO_CONF = {"ALTA": "Alta", "MEDIA": "Média", "BAIXA": "Baixa"}
FONTE = FONTE_UI


def _escala(mapa, dominio=None):
    dom = dominio or list(mapa.keys())
    return alt.Scale(domain=dom, range=[mapa[d] for d in dom])


def _estilo(chart, altura):
    return (chart.properties(height=altura)
            .configure(font=FONTE)
            .configure_axis(labelFontSize=11, titleFontSize=11, grid=False)
            .configure_legend(orient="bottom", labelFontSize=11, titleFontSize=11)
            .configure_view(strokeWidth=0))


def _grafico_status_por_item(df):
    d = df.groupby(["item_label", "status"]).size().reset_index(name="qtd")
    ordem = sorted(df.item_label.unique())
    dom = [s for s in CORES_STATUS if s in set(d.status)]
    ch = alt.Chart(d).mark_bar(cornerRadiusEnd=4, height={"band": 0.65}).encode(
        y=alt.Y("item_label:N", title=None, sort=ordem,
                axis=alt.Axis(labelLimit=260, labelOverlap=False, domain=False, ticks=False)),
        x=alt.X("qtd:Q", title="Nº de elementos conferidos",
                axis=alt.Axis(tickMinStep=1, format="d")),
        color=alt.Color("status:N", title="Resultado", scale=_escala(CORES_STATUS, dom)),
        tooltip=[alt.Tooltip("item_label:N", title="Item"),
                 alt.Tooltip("status:N", title="Status"),
                 alt.Tooltip("qtd:Q", title="Elementos")],
    )
    return _estilo(ch, max(180, 40 * len(ordem)))


def _cor_celula(pct):
    """Interpola do verde-claro (0% falhas) ao vermelho (100% falhas)."""
    if pct is None:
        return "background-color:#F1F5F9;color:#64748B"
    a, b = (236, 253, 245), (185, 28, 28)   # verde muito claro -> vermelho 700
    t = pct / 100
    r, g, bl = (round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    txt = "#ffffff" if pct >= 70 else "#0B1F3B"   # troca só quando o contraste permite
    return f"background-color:rgb({r},{g},{bl});color:{txt};font-weight:700;text-align:center"


def _heatmap_pavimento_item(df):
    """
    Matriz pavimento × item como tabela colorida (Pandas Styler).
    Cada célula = "não conformes / avaliados"; cor pela % de não conformidade.
    """
    aval = df[df.status.isin(["Conforme", "Não Conforme"])]
    if aval.empty:
        return None
    g = (aval.assign(nc=(aval.status == "Não Conforme").astype(int))
             .groupby(["pavimento", "item_label"])
             .agg(nc=("nc", "sum"), total=("nc", "size")).reset_index())
    rotulo = g.assign(r=g.nc.astype(str) + "/" + g.total.astype(str)) \
              .pivot(index="pavimento", columns="item_label", values="r").fillna("—")
    pct = g.assign(p=g.nc / g.total * 100) \
           .pivot(index="pavimento", columns="item_label", values="p")
    estilos = pct.apply(lambda col: col.map(lambda v: _cor_celula(None if pd.isna(v) else v)))
    rotulo.index.name = "Pavimento"
    rotulo.columns.name = None
    return rotulo.style.apply(lambda _: estilos.values, axis=None)


def _grafico_confianca(df):
    d = df.groupby(["item_label", "confianca"]).size().reset_index(name="qtd")
    d["conf_rotulo"] = d.confianca.map(ROTULO_CONF)
    ordem = sorted(df.item_label.unique())
    ch = alt.Chart(d).mark_bar().encode(
        y=alt.Y("item_label:N", title=None, sort=ordem,
                axis=alt.Axis(labelLimit=260, labelOverlap=False)),
        x=alt.X("qtd:Q", title="Nº de verificações", stack="normalize",
                axis=alt.Axis(format="%")),
        color=alt.Color("conf_rotulo:N", title="Confiança",
                        scale=alt.Scale(domain=["Alta", "Média", "Baixa"],
                                        range=[CORES_CONF["ALTA"], CORES_CONF["MEDIA"],
                                               CORES_CONF["BAIXA"]])),
        tooltip=[alt.Tooltip("item_label:N", title="Item"),
                 alt.Tooltip("conf_rotulo:N", title="Confiança"),
                 alt.Tooltip("qtd:Q", title="Verificações")],
    )
    return _estilo(ch, max(180, 40 * len(ordem)))


def render_dashboard(linhas: list[dict] | None, resultado: dict | None,
                     malhas: dict | None = None, arquivo_ifc: str = "modelo.ifc") -> None:
    if not linhas:
        st.markdown(
            '<div class="info-box">Execute a auditoria na aba <strong>Nova auditoria</strong> '
            'para ver o dashboard.</div>', unsafe_allow_html=True)
        return

    df = pd.DataFrame(linhas)
    df["item_label"] = df.item_nbr + " · " + df.item_nbr.map(CATEGORIAS).fillna("")

    # ── Filtro de pavimento (vale para todo o dashboard) ─────────────────────
    pavs = sorted(df.pavimento.unique())
    if len(pavs) > 1:
        sel = st.multiselect("Filtrar pavimentos", pavs, key="dash_pav")
        if sel:
            df = df[df.pavimento.isin(sel)]

    # ── KPIs (rótulo · número · contexto · mini barra) ────────────────────────
    aval = df[df.status.isin(["Conforme", "Não Conforme"])]
    n_ok = int((aval.status == "Conforme").sum())
    pct = n_ok / len(aval) * 100 if len(aval) else None
    nc_df = df[df.status == "Não Conforme"]
    proto = classificar_prototipo((resultado or {}).get("resultados", []))
    cont_origem = df.confianca.value_counts().to_dict()
    alta_pct = (df.confianca == "ALTA").mean() * 100 if len(df) else 0
    cont_status = df.status.value_counts().to_dict()

    st.markdown(linha_kpis([
        kpi(fmt_pct(pct), "Conformidade dos elementos",
            f"<strong>{n_ok} de {len(aval)}</strong> elementos medidos atendem à norma", "c-green",
            mini_barra([(n_ok, CORES_STATUS["Conforme"]), (len(aval) - n_ok, CORES_STATUS["Não Conforme"])])),
        kpi(len(nc_df), "Precisam de correção",
            (f"elementos em <strong>{nc_df.item_nbr.nunique()}</strong> "
             f"{'item' if nc_df.item_nbr.nunique() == 1 else 'itens'} da norma") if len(nc_df)
            else "nenhum elemento fora da norma", "c-red" if len(nc_df) else ""),
        kpi(f"{proto['avaliados']}<span class='tec' style='font-size:1rem'>/{proto['aplicaveis']}</span>",
            "Itens da norma avaliados",
            f"cobertura <strong>{proto['classe'].lower()}</strong>"
            + (f" · {proto['indeterminados']} sem dados suficientes" if proto['indeterminados'] else ""),
            "c-blue"),
        kpi(fmt_pct(alta_pct), "Medidas lidas direto do modelo",
            "o restante foi calculado da geometria ou estimado pelo nome",
            extra_html=mini_barra([(cont_origem.get(k, 0), CORES_CONFIANCA[k]) for k in ("ALTA", "MEDIA", "BAIXA")])),
    ]), unsafe_allow_html=True)

    # ── Distribuição dos resultados  |  De onde vêm os dados ─────────────────
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown('<div class="card-tit">Resultado das verificações</div>'
                        '<div class="card-sub">Cada verificação = 1 elemento conferido contra 1 item da norma</div>',
                        unsafe_allow_html=True)
            st.markdown(barra_segmentada(segmentos_status(cont_status), "Verificações"),
                        unsafe_allow_html=True)
    with col2:
        with st.container(border=True):
            st.markdown('<div class="card-tit">De onde vêm os dados</div>'
                        '<div class="card-sub">Quanto mais direto o dado, mais confiável a verificação</div>',
                        unsafe_allow_html=True)
            st.markdown(barra_segmentada(segmentos_origem(cont_origem), "Medidas"),
                        unsafe_allow_html=True)

    # ── Status por item (resumo à esquerda, gráfico à direita) ───────────────
    with st.container(border=True):
        st.markdown('<div class="card-tit">Resultado por item da norma</div>'
                    '<div class="card-sub">Quantos elementos foram conferidos em cada item, e com que resultado</div>',
                    unsafe_allow_html=True)
        c_esq, c_dir = st.columns([1, 4])
        with c_esq:
            st.markdown(f"""
            <div class="resumo-lado">
              <div><div class="rl-num">{df.item_nbr.nunique()}</div><div class="rl-lbl">itens da norma com elementos medidos</div></div>
              <div><div class="rl-num">{df.global_id.nunique()}</div><div class="rl-lbl">elementos distintos auditados</div></div>
              <div><div class="rl-num">{len(df)}</div><div class="rl-lbl">verificações no total</div></div>
            </div>""", unsafe_allow_html=True)
        with c_dir:
            st.altair_chart(_grafico_status_por_item(df), use_container_width=True, theme=None)

    # ── Onde estão os problemas ──────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<div class="card-tit">Onde estão os problemas</div>'
                    '<div class="card-sub">Pavimento × item da norma · cada célula mostra '
                    '<strong>não conformes / elementos medidos</strong>; quanto mais vermelha, mais falhas</div>',
                    unsafe_allow_html=True)
        hm = _heatmap_pavimento_item(df)
        if hm is not None:
            st.dataframe(hm, use_container_width=True)
        else:
            st.caption("Sem elementos medidos (conforme / não conforme) para montar o mapa.")

    # ── Lista de ação: não conformidades ─────────────────────────────────────
    nc = nc_df.sort_values(["item_nbr", "pavimento"])
    with st.container(border=True):
        st.markdown(f'<div class="card-tit">Lista de ação</div>'
                    f'<div class="card-sub">{len(nc)} '
                    f'{"elemento precisa" if len(nc) == 1 else "elementos precisam"} de correção</div>',
                    unsafe_allow_html=True)
        if nc.empty:
            st.markdown('<div class="texto-suave">✓ Nenhum elemento fora da norma nas verificações medidas.</div>',
                        unsafe_allow_html=True)
        else:
            st.dataframe(
                nc[["item_label", "nome", "pavimento", "valor_medido", "valor_exigido",
                    "mensagem", "global_id"]],
                hide_index=True, use_container_width=True,
                column_config={
                    "item_label": "Item", "nome": "Elemento", "pavimento": "Pavimento",
                    "valor_medido": "Medido", "valor_exigido": "Exigido",
                    "mensagem": "Observação", "global_id": "GlobalId",
                })

    # ── Exportação BCF ────────────────────────────────────────────────────────
    todas = pd.DataFrame(linhas)
    n_nc_total = int((todas.status == "Não Conforme").sum())
    if n_nc_total:
        bcf_bytes, n_top = gerar_bcfzip(linhas, arquivo_ifc, malhas)
        st.download_button(
            f"Baixar {n_top} não conformidades em BCF (.bcfzip)",
            data=bcf_bytes,
            file_name=f"{arquivo_ifc.rsplit('.', 1)[0]}_NBR9050.bcfzip",
            mime="application/octet-stream",
        )
        st.caption("Abra no BIMcollab Zoom (gratuito): carregue o mesmo IFC e depois importe "
                   "o .bcfzip — cada não conformidade vira um tópico que leva direto ao "
                   "elemento. O BCF inclui todas as não conformidades, independente do filtro "
                   "de pavimento.")

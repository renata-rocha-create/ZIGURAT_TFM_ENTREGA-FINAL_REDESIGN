"""
♿ Auditor de Acessibilidade BIM — NBR 9050:2020
Streamlit App — Verificação Automatizada de Conformidade
Master Internacional em IA para Arquitetura e Construção — Zigurat Institute of Technology

Este arquivo contém apenas a INTERFACE (sidebar, abas, botões).
A lógica fica nos módulos:
    ui_style.py      → identidade visual (CSS) e badges
    extracao.py      → leitura do IFC
    regras.py        → regras da NBR 9050 (nbr9050_rules.json)
    llm_auditor.py   → prompt e chamada ao Claude/Gemini
    verificacoes.py  → classificação de status e resumo determinístico
    relatorios.py    → HTML e XLSX
"""

import streamlit as st
import json
import os
import tempfile
from datetime import datetime

# ── Page config (precisa ser o PRIMEIRO comando Streamlit) ───────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
_FAVICON = os.path.join(_DIR, "assets", "favicon.png")

st.set_page_config(
    page_title="access Ai · Auditoria BIM NBR 9050",
    page_icon=_FAVICON if os.path.exists(_FAVICON) else "♿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Módulos do projeto ───────────────────────────────────────────────────────
from ui_style import aplicar_estilo, status_badge, logo_html
from ui_componentes import (kpi, linha_kpis, conformidade_cards_html, como_calculamos_md,
                            analise_geral_html, SIMBOLO_STATUS, SIGNIFICADO_STATUS, ROTULO_STATUS_PLURAL,
                            ORIGEM_DADO, legenda_origem_html)
from extracao import extract_ifc_elements
from regras import obter_regras_lista
from llm_auditor import build_audit_prompt, call_anthropic, call_gemini
from verificacoes import (classificar_status, calcular_resumo,
                          gerar_verificacoes, comparar_com_llm,
                          aplicar_veredito_python, gerar_observacoes)
from dashboard import render_aba_elementos, render_dashboard
from visualizador_3d import extrair_malhas, render_aba_3d
from relatorios import gerar_relatorio_html, gerar_excel

aplicar_estilo()


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
for k, v in {
    "resultado": None,
    "elementos": None,
    "logs": [],
    "running": False,
    "ifc_nome": "",
    "verificacoes": None,   # tabela por elemento (Etapa 2)
    "comparacao": None,     # status LLM × Python (Etapa 2)
    "malhas": None,         # geometria 3D dos elementos auditados (Etapa 4)
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(logo_html(), unsafe_allow_html=True)

    st.markdown('<div class="sb-label">Configuração da IA</div>', unsafe_allow_html=True)

    provider = st.selectbox("Provedor", ["Anthropic (Claude)", "Google (Gemini)"])

    st.markdown('<div class="sb-hint">Chave não armazenada · válida só nesta sessão</div>',
                unsafe_allow_html=True)
    api_key = st.text_input(
        "Chave API",
        type="password",
        placeholder="sk-ant-..." if "Anthropic" in provider else "AIza...",
        help="Sua chave de API. Não é armazenada nem enviada a terceiros.",
    )

    if "Anthropic" in provider:
        model_options = [
            "claude-haiku-4-5",
            "claude-sonnet-4-5",
            "claude-opus-4-5",
        ]
        model_labels = {
            "claude-haiku-4-5":  "Claude Haiku 4.5 (rápido, econômico)",
            "claude-sonnet-4-5": "Claude Sonnet 4.5 (balanceado)",
            "claude-opus-4-5":   "Claude Opus 4.5 (máxima qualidade)",
        }
    else:
        model_options = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"]
        model_labels = {
            "gemini-1.5-flash": "Gemini 1.5 Flash (rápido)",
            "gemini-1.5-pro": "Gemini 1.5 Pro (balanceado)",
            "gemini-2.0-flash": "Gemini 2.0 Flash (novo)",
        }

    selected_model = st.selectbox(
        "Modelo LLM",
        model_options,
        format_func=lambda x: model_labels.get(x, x),
    )

    temperature = 0.0  # Fixo em 0.0 — determinístico para auditoria normativa

    st.markdown("---")
    st.markdown("""
    <div class="sb-footer">
      <strong>TFM · Grupo 1</strong><br>
      Kevin Dias Quintian<br>
      Renata Gomes Rocha<br>
      Sergio Rosenboim<br>
      Viviane Nishizaki Suzuke<br>
      William Felipe dos Santos Moura
    </div>
    <div class="sb-instituicao">
      <img src="https://www.e-zigurat.com/images/logo.svg" alt="Zigurat Institute of Technology" />
      Master Internacional em IA para Arquitetura e Construção<br>
      Zigurat Institute of Technology
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="hero-block">
  <div>
    <div class="hero-title">Auditoria BIM</div>
    <div class="hero-sub">Acessibilidade &nbsp;·&nbsp; ABNT NBR 9050:2020</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_upload, tab_resultado, tab_dashboard, tab_3d, tab_elementos, tab_ajuda = st.tabs(
    ["Nova auditoria", "Resultados", "Dashboard", "Modelo 3D", "Elementos", "Ajuda"])

# ─────────────────────────────────────────────
with tab_upload:

    # ── Upload card — só o IFC (checklist agora vem sempre de nbr9050_rules.json) ──
    st.markdown("""
    <div class="section-title">Carregue seu modelo</div>
    <div class="texto-suave" style="margin:-0.4rem 0 0.6rem 0">
      Arquivo IFC exportado do Revit, ArchiCAD ou Vectorworks ·
      <span class="pill">IFC2X3</span> <span class="pill">IFC4</span>
    </div>
    """, unsafe_allow_html=True)
    ifc_file = st.file_uploader(
        "Arquivo IFC",
        type=["ifc"],
        help="Formato IFC2X3 ou IFC4. Exportado via Revit, ArchiCAD, Vectorworks etc.",
        label_visibility="collapsed"
    )
    if ifc_file:
        st.markdown(f"""
        <div class="file-card">
          <span class="fc-ok" aria-hidden="true">✓</span>
          <strong>{ifc_file.name}</strong>
          <span class="fc-meta">{ifc_file.size / 1024 / 1024:.1f} MB</span>
        </div>""", unsafe_allow_html=True)

    n_regras = len(obter_regras_lista())
    st.markdown(f"""
    <div class="section-title" style="margin-top:1.5rem">Auditoria</div>
    <div class="file-card" style="margin-top:0">
      <strong>NBR 9050:2020 · Acessibilidade</strong>
      <span class="fc-meta">{n_regras} verificações · nbr9050_rules.json</span>
    </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Stepper — 3 passos (checklist deixou de ser upload, é automático) ────
    step1 = "done" if api_key else "active"
    step2 = "done" if (api_key and ifc_file) else ("active" if api_key else "pending")
    step3 = "active" if (api_key and ifc_file) else "pending"

    def step_html(state, n, label, sublabel):
        icone = "✓" if state == "done" else str(n)
        return f"""<div class="step step-{state}">
          <div class="step-dot">{icone}</div>
          <div><div class="step-label">{label}</div><div class="step-sub">{sublabel}</div></div>
        </div>"""

    arrow = '<div class="step-arrow" aria-hidden="true">→</div>'

    st.markdown(f"""
    <div class="stepper" style="margin-top:1.5rem">
      {step_html(step1, 1, "Chave da IA", "Barra lateral")}
      {arrow}
      {step_html(step2, 2, "Modelo IFC", "Arquivo .ifc")}
      {arrow}
      {step_html(step3, 3, "Executar", "Iniciar auditoria")}
    </div>
    """, unsafe_allow_html=True)

    # ── can_run e mensagens de estado ─────────────────────────────────────
    can_run = bool(ifc_file and api_key)

    # Mensagens de estado inline (sem warn-box solta)
    if not api_key and not ifc_file:
        st.markdown("""
        <div class="info-box">
          Complete os passos <strong>① e ②</strong> na barra lateral e acima para habilitar a auditoria.
        </div>""", unsafe_allow_html=True)
    elif not api_key:
        st.markdown('<div class="warn-box">Passo 1 — Insira sua chave de API na barra lateral.</div>', unsafe_allow_html=True)
    elif not ifc_file:
        st.markdown('<div class="warn-box">Passo 2 — Carregue um arquivo IFC acima.</div>', unsafe_allow_html=True)

    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        run = st.button("Executar auditoria  →", disabled=not can_run, use_container_width=True)

    # ── Execution ──────────────────────────────────────────────────────────────
    if run and can_run:
        st.session_state.logs = []
        st.session_state.resultado = None
        st.session_state.verificacoes = None
        st.session_state.comparacao = None
        st.session_state.malhas = None

        log_box = st.empty()
        step_box = st.empty()
        progress_bar = st.progress(0)

        def log(msg: str):
            ts = datetime.now().strftime("%H:%M:%S")
            st.session_state.logs.append(f"[{ts}] {msg}")
            log_content = "\n".join(st.session_state.logs[-20:])
            log_box.markdown(f'<div class="terminal">{log_content}</div>', unsafe_allow_html=True)

        try:
            # Step 1 — Save IFC
            log("🔄 Salvando arquivo IFC temporariamente...")
            progress_bar.progress(10)
            with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
                tmp.write(ifc_file.read())
                tmp_path = tmp.name
            st.session_state.ifc_nome = ifc_file.name
            log(f"✅ IFC salvo: {ifc_file.name} ({ifc_file.size/1024/1024:.1f} MB)")

            # Step 2 — Extract IFC elements
            log("🔍 Extraindo elementos do modelo IFC (IfcOpenShell)...")
            progress_bar.progress(25)
            elementos = extract_ifc_elements(tmp_path)
            if "error" in elementos:
                st.error(elementos["error"])
                st.stop()
            resumo_ext = {k: len(v) for k, v in elementos.get("elementos", {}).items()}
            log(f"✅ Elementos extraídos: {resumo_ext}")
            log(f"   Schema IFC detectado: {elementos.get('schema','?')}")
            st.session_state.elementos = elementos

            # Step 2b — Verificação por elemento (Python, determinística)
            linhas = gerar_verificacoes(elementos)
            st.session_state.verificacoes = linhas
            n_nc = sum(1 for l in linhas if l["status"] == "Não Conforme")
            log(f"🧮 Verificação por elemento (Python): {len(linhas)} verificações | ❌ {n_nc} não conformes")

            # Step 2c — Geometria 3D (para o visualizador e a câmera do BCF)
            log("🧊 Extraindo geometria 3D dos elementos auditados...")
            try:
                malhas = extrair_malhas(tmp_path, linhas)
                st.session_state.malhas = malhas
                log(f"   {len(malhas.get('auditados', []))} elementos auditados + "
                    f"{len(malhas.get('contexto', []))} de contexto com geometria")
            except Exception as e_geo:
                log(f"⚠️ Geometria 3D indisponível ({e_geo}) — auditoria continua sem o 3D")
            progress_bar.progress(45)

            # Step 3 — Load rules (sempre do JSON — sem upload de checklist)
            n_regras = len(obter_regras_lista())
            log(f"📋 Usando checklist de nbr9050_rules.json ({n_regras} itens).")
            progress_bar.progress(55)

            # Step 4 — Build prompt
            log("📝 Construindo prompt de auditoria...")
            prompt = build_audit_prompt(elementos, ifc_file.name)
            log(f"   Prompt: ~{len(prompt)//4:,} tokens estimados")
            progress_bar.progress(65)

            # Step 5 — Call LLM
            log(f"🤖 Chamando {selected_model} ({provider})...")
            log("   Aguarde — isso pode levar 30–90 segundos...")
            progress_bar.progress(70)

            if "Anthropic" in provider:
                resultado = call_anthropic(api_key, selected_model, prompt, temperature)
            else:
                resultado = call_gemini(api_key, selected_model, prompt, temperature)

            progress_bar.progress(90)
            log(f"✅ Auditoria concluída!")

            # Sobrescreve campos que o Python já conhece com certeza — não faz
            # sentido confiar que o LLM vai ecoar corretamente algo que já está
            # disponível antes mesmo da chamada (mesmo princípio do resumo abaixo).
            # Foi assim que pegamos o bug: numa rodada real, o LLM devolveu
            # "2024-01-15" no lugar da data certa (10/07/2026), ignorando o
            # exemplo que já estava no prompt.
            resultado["modelo"] = ifc_file.name
            resultado["schema_ifc"] = elementos.get("schema", resultado.get("schema_ifc", "—"))
            resultado["data_auditoria"] = datetime.now().strftime("%d/%m/%Y")

            # Comparação item a item: status ORIGINAL do LLM × status calculado em Python
            # (feita ANTES do veredito final, para a métrica de concordância ser honesta)
            comparacao = comparar_com_llm(st.session_state.verificacoes, resultado.get("resultados", []))

            # Veredito final: nos itens numéricos, o Python sobrescreve o LLM no relatório
            resultado["resultados"] = aplicar_veredito_python(
                resultado.get("resultados", []), st.session_state.verificacoes)
            log("⚖️ Itens numéricos: status final definido pela verificação em Python.")

            # Recalcula o resumo em Python — determinístico, não depende do LLM
            # ter feito a soma/divisão certa (ver calcular_resumo() para o porquê).
            resultado["resumo"] = calcular_resumo(resultado.get("resultados", []))
            log("🧮 Resumo e metadados recalculados em Python (não dependem do eco do LLM).")

            # Resumo executivo reescrito com os status FINAIS (o texto do LLM
            # citava valores que o Python corrigiu — ex: bacia 0,81 m)
            resultado["observacoes_llm_original"] = resultado.get("observacoes_gerais", "")
            resultado["observacoes_gerais"] = gerar_observacoes(resultado["resultados"], resultado["resumo"])
            st.session_state.comparacao = comparacao
            resultado["verificacoes_por_elemento"] = st.session_state.verificacoes
            resultado["comparacao_llm_python"] = comparacao
            if comparacao["taxa_concordancia"] is not None:
                log(f"🤝 Concordância LLM × Python: {comparacao['concordantes']}/{comparacao['comparaveis']} itens ({comparacao['taxa_concordancia']}%)")

            resumo = resultado["resumo"]
            log(f"   Total: {resumo.get('total',0)} | ✅ {resumo.get('conformes',0)} | ▲ {resumo.get('parciais',0)} | ❌ {resumo.get('nao_conformes',0)} | ⚠️ {resumo.get('indeterminados',0)}")
            log(f"   Conformidade: {resumo.get('percentual_conformidade')} (bruta) | {resumo.get('percentual_sobre_verificaveis')} (sobre itens verificáveis, exclui N/A)")

            st.session_state.resultado = resultado
            progress_bar.progress(100)
            log("🎉 Relatório pronto! Acesse a aba 'Resultados'.")

            # Cleanup
            os.unlink(tmp_path)

        except json.JSONDecodeError as e:
            log(f"❌ Erro ao parsear resposta JSON do modelo: {e}")
            st.error("O modelo não retornou JSON válido. Tente novamente ou ajuste o modelo/temperatura.")
        except Exception as e:
            log(f"❌ Erro: {e}")
            st.error(f"Erro durante a execução: {e}")


# ─────────────────────────────────────────────
with tab_resultado:
    if st.session_state.resultado is None:
        st.markdown("""
        <div class="empty-state">
          <div class="es-title">Nenhuma auditoria executada ainda</div>
          <div class="es-sub">
            Vá para <strong>Nova auditoria</strong>, carregue um IFC e clique em <strong>Executar auditoria</strong>.
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        resultado = st.session_state.resultado
        resumo = resultado.get("resumo", {})
        itens = resultado.get("resultados", [])

        # Metrics
        total   = resumo.get("total", len(itens))
        conf    = resumo.get("conformes", 0)
        parc    = resumo.get("parciais", 0)
        nconf   = resumo.get("nao_conformes", 0)
        indet   = resumo.get("indeterminados", 0)
        na      = resumo.get("na", 0)
        pct     = resumo.get("percentual_conformidade", "—")
        pct_ver = resumo.get("percentual_sobre_verificaveis", "—")

        # ── 1. Conformidade (duas medidas, cada uma explicada) ──────────────
        st.markdown('<div class="section-title">Conformidade do modelo</div>', unsafe_allow_html=True)
        st.markdown(conformidade_cards_html(resumo), unsafe_allow_html=True)
        with st.popover("ⓘ Como calculamos a conformidade?"):
            st.markdown(como_calculamos_md(resumo))

        # ── 2. Contagem por status ────────────────────────────────────────
        st.markdown(f'<div class="section-title">Itens da norma por resultado '
                    f'<span class="section-sub">{total} itens avaliados</span></div>',
                    unsafe_allow_html=True)
        contagem = [("Conforme", conf, "c-green"), ("Parcial", parc, "c-purple"),
                    ("Não Conforme", nconf, "c-red"), ("Indeterminado", indet, "c-amber"),
                    ("N/A", na, "c-muted")]
        st.markdown(linha_kpis([
            kpi(f'<span class="{cor}" aria-hidden="true" style="font-size:1.1rem;margin-right:6px">'
                f'{SIMBOLO_STATUS[s_]}</span>{n_}',
                ROTULO_STATUS_PLURAL[s_],
                SIGNIFICADO_STATUS[s_].capitalize())
            for s_, n_, cor in contagem
        ]), unsafe_allow_html=True)

        # ── 3. Análise geral (estruturada) ────────────────────────────────
        st.markdown('<div class="section-title">Análise geral</div>', unsafe_allow_html=True)
        st.markdown(analise_geral_html(resultado), unsafe_allow_html=True)

        # GlobalId explanation (recolhido para não poluir a tela)
        with st.expander("Como localizar um elemento no Revit ou no visualizador IFC (GlobalId)"):
            st.markdown("""
            <div style="font-size:0.85rem;line-height:1.6">
              O relatório inclui o <code>GlobalId</code> de cada elemento IFC verificado — é o identificador único do elemento no modelo, como um "CPF" do componente BIM.<br>
              <strong>Como usar no Revit:</strong> aba <em>Manage → Inquiry → IFC GUID</em> para localizar o elemento diretamente.
              No <strong>BIMcollab Zoom</strong>, <strong>Solibri</strong> ou <strong>usBIM viewer</strong> (gratuitos), cole o GlobalId no campo de busca para selecionar o elemento instantaneamente.
            </div>
            """, unsafe_allow_html=True)

        # Filters
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            filter_status = st.multiselect(
                "Filtrar por Status",
                ["Conforme", "Parcial", "Não Conforme", "Indeterminado", "N/A"],
                default=["Conforme", "Parcial", "Não Conforme", "Indeterminado", "N/A"]
            )
        with col_f2:
            cats = sorted(set(it.get("categoria","") for it in itens if it.get("categoria")))
            filter_cat = st.multiselect("Filtrar por Categoria", cats, default=cats)
        with col_f3:
            search_gid = st.text_input("Buscar GlobalId", placeholder="0yScV...", help="Filtra pelo GlobalId do elemento IFC")

        # Table
        itens_filtrados = [
            it for it in itens
            if it.get("status","") in filter_status
            and it.get("categoria","") in filter_cat
            and (not search_gid or search_gid.lower() in it.get("globalid","").lower())
        ]

        st.markdown(f"""
        <div class="section-title">
          Itens verificados
          <span class="section-sub">{len(itens_filtrados)} de {len(itens)} itens</span>
        </div>
        """, unsafe_allow_html=True)

        # Build table HTML
        rows_html = ""
        for it in itens_filtrados:
            gid = it.get("globalid", "—")
            gid_chip = f'<span class="globalid" title="GlobalId para filtro no Revit">{gid}</span>' if gid != "—" else "—"
            precisa_acao = classificar_status(it.get('status', '')) in ('Não Conforme', 'Parcial', 'Indeterminado')
            rec_html = (f'<span class="td-rec">{it.get("recomendacao", "—")}</span>'
                        if precisa_acao else '<span class="td-muted">—</span>')
            rows_html += f"""
            <tr>
              <td class="td-item">{it.get('item_nbr','—')}</td>
              <td class="td-muted">{it.get('categoria','—')}</td>
              <td class="td-strong">{it.get('elemento','—')}</td>
              <td>{status_badge(it.get('status','N/A'))}</td>
              <td class="td-mono">{it.get('valor_encontrado','—')}</td>
              <td class="td-mono">{it.get('valor_exigido','—')}</td>
              <td>{gid_chip}</td>
              <td class="td-mono td-muted">{it.get('tipo_ifc','—')}</td>
              <td>{rec_html}</td>
            </tr>"""

        st.markdown(f"""
        <div style="overflow-x:auto">
        <table class="result-table">
          <thead>
            <tr>
              <th>Item NBR</th><th>Categoria</th><th>Elemento</th><th>Status</th>
              <th>Encontrado</th><th>Exigido</th>
              <th>GlobalId</th><th>Tipo IFC</th><th>Recomendação</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<div class="section-title">Exportar relatório</div>', unsafe_allow_html=True)

        col_dl1, col_dl2, col_dl3 = st.columns(3)
        modelo_nome = st.session_state.ifc_nome or "modelo"
        ts = datetime.now().strftime("%Y%m%d_%H%M")

        with col_dl1:
            html_bytes = gerar_relatorio_html(resultado, modelo_nome).encode("utf-8")
            st.download_button(
                "Relatório HTML",
                data=html_bytes,
                file_name=f"relatorio_nbr9050_{ts}.html",
                mime="text/html",
                use_container_width=True,
            )

        with col_dl2:
            xlsx_bytes = gerar_excel(resultado, modelo_nome)
            if xlsx_bytes:
                st.download_button(
                    "Checklist XLSX",
                    data=xlsx_bytes,
                    file_name=f"checklist_nbr9050_{ts}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

        with col_dl3:
            json_bytes = json.dumps(resultado, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button(
                "JSON completo",
                data=json_bytes,
                file_name=f"auditoria_nbr9050_{ts}.json",
                mime="application/json",
                use_container_width=True,
            )

        # JSON expandable
        with st.expander("Ver JSON bruto da auditoria"):
            st.json(resultado)


# ─────────────────────────────────────────────
with tab_dashboard:
    render_dashboard(st.session_state.verificacoes, st.session_state.resultado,
                     st.session_state.malhas, st.session_state.ifc_nome or "modelo.ifc")


# ─────────────────────────────────────────────
with tab_3d:
    render_aba_3d(st.session_state.malhas, st.session_state.verificacoes)


# ─────────────────────────────────────────────
with tab_elementos:
    render_aba_elementos(st.session_state.verificacoes, st.session_state.comparacao)


# ─────────────────────────────────────────────
with tab_ajuda:
    st.markdown("""
    <div class="section-title">Como usar o access Ai</div>
    """, unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        **1. Configure a IA (barra lateral)**
        - Escolha o provedor: **Anthropic** (Claude) ou **Google** (Gemini)
        - Cole sua chave API
        - Selecione o modelo desejado
        - A temperatura é fixa em 0.0 (resposta determinística para auditoria)

        **2. Carregue o arquivo**
        - **IFC** (obrigatório): arquivo exportado do Revit, ArchiCAD etc.
          - Formatos suportados: IFC2X3, IFC4
          - O sistema detecta o schema automaticamente
        - O **checklist NBR 9050** já vem embutido em `nbr9050_rules.json`,
          na raiz do repositório — não é preciso enviar planilha nenhuma.

        **3. Execute a auditoria**
        - Clique em **Executar auditoria**
        - Acompanhe as etapas em tempo real
        - Aguarde 30–90 segundos (depende do modelo e tamanho do IFC)
        """)

    with col_b:
        st.markdown("""
        **4. Analise os resultados**
        - **Resultados:** conformidade do modelo e lista de itens da norma
        - **Dashboard:** visão geral, onde estão os problemas e lista de ação
        - **Modelo 3D:** elementos coloridos pelo resultado
        - **Elementos:** cada elemento medido e a comparação entre IA e cálculo
        - Filtre por status, categoria ou GlobalId

        **5. Como usar o GlobalId no Revit**
        - No Revit: `Manage → Select by ID` → cole o GlobalId
        - No Navisworks: filtro por GUID
        - No Solibri / BIMcollab: filtro por GlobalId no modelo IFC
        - No IfcOpenShell: `ifc.by_guid("0yScV...")`

        **6. Exporte os relatórios**
        - **HTML**: relatório visual completo com todos os dados
        - **XLSX**: checklist com formatação por status (conforme/não conforme)
        - **JSON**: dados brutos para integração com outros sistemas
        """)

    st.markdown("---")
    st.markdown('<div class="section-title">Termos usados no app</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="legenda">
      <div class="leg-row"><span class="leg-sym">✓ ◐ ✕</span><div><strong>Resultado de cada item:</strong>
        ✓ conforme ({SIGNIFICADO_STATUS["Conforme"]}) · ◐ parcial ({SIGNIFICADO_STATUS["Parcial"]}) ·
        ✕ não conforme ({SIGNIFICADO_STATUS["Não Conforme"]}).</div></div>
      <div class="leg-row"><span class="leg-sym">? —</span><div><strong>Indeterminado:</strong> {SIGNIFICADO_STATUS["Indeterminado"]}.
        <strong>N/A:</strong> {SIGNIFICADO_STATUS["N/A"]}.</div></div>
      <div class="leg-row"><span class="leg-sym">%</span><div><strong>Conformidade geral (bruta)</strong> considera todos os itens avaliados;
        <strong>conformidade dos itens aplicáveis (sem N/A)</strong> considera só os itens que existem no modelo.
        Itens parciais contam como meio ponto.</div></div>
      <div class="leg-row"><span class="leg-sym">IA×</span><div><strong>Parecer da IA × resultado do cálculo:</strong> cada item é checado
        de duas formas independentes — a IA (LLM) lê os dados do modelo e um cálculo (Python) mede os elementos.
        Quando discordam, vale o cálculo, e a divergência fica registrada na aba Elementos.</div></div>
      <div class="leg-row"><span class="leg-sym">GUID</span><div><strong>GlobalId:</strong> identificador único do elemento no IFC,
        como um "CPF" do componente. Serve para encontrá-lo no Revit ou num visualizador IFC.</div></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(legenda_origem_html(), unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    <div class="section-title">Itens da NBR 9050:2020 verificados</div>
    """, unsafe_allow_html=True)

    # Lê os mesmos 12 itens que o motor de auditoria usa — nbr9050_rules.json
    # ANTES: lista hardcoded "itens_padrao" duplicando (e podendo divergir de) o JSON.
    # DEPOIS: mesma fonte única (obter_regras_lista()) usada em build_audit_prompt().
    itens_padrao = [
        (r["item_nbr"], r["classificacao"], r["subcategoria"], r["item_verificavel"], r["entidades"]["primaria"])
        for r in obter_regras_lista()
    ]

    cat_colors = {"Geométrica": "#2563EB", "Condicional": "#B45309", "Relacional": "#047857", "Qualitativa": "#475569"}
    rows_help = ""
    for item_nbr, classificacao, cat, desc, entidade in itens_padrao:
        color = cat_colors.get(classificacao, "#64748B")
        rows_help += f"""
        <tr>
          <td class="td-item">{item_nbr}</td>
          <td><span style="color:{color};font-size:0.78rem;font-weight:600">{classificacao}</span></td>
          <td class="td-strong">{cat}</td>
          <td>{desc}</td>
          <td class="td-mono td-muted">{entidade}</td>
        </tr>"""

    st.markdown(f"""
    <table class="result-table">
      <thead>
        <tr><th>Item NBR</th><th>Tipo</th><th>Categoria</th><th>Verificação</th><th>Entidade IFC</th></tr>
      </thead>
      <tbody>{rows_help}</tbody>
    </table>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="warn-box" style="margin-top:1.5rem">
    <strong>Limitações conhecidas</strong><br>
    Itens qualitativos (maçaneta alavanca, lavatório suspenso) dependem de atributos textuais raramente preenchidos no IFC.
    Itens como espaço de giro (IfcSpace) ficam Indeterminados se o modelo não exportar espaços.
    Verificação manual complementar é sempre recomendada.
    </div>
    """, unsafe_allow_html=True)

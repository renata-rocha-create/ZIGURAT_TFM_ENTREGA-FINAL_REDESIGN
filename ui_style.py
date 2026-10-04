"""
ui_style.py — Identidade visual "access Ai" (CSS, paletas e componentes simples).

Só APARÊNCIA: nenhuma lógica de auditoria vive aqui.

Regra de ouro do sistema de cores
---------------------------------
Existem DUAS paletas separadas, que nunca se misturam:

1. MARCA (identidade): deep blue, azul e teal.
   - Azul  -> ações (botões, abas, links, foco).
   - Teal  -> só no logo e em detalhes mínimos de marca.
   - Deep blue -> textos e títulos.
2. STATUS (semântica): conforme, parcial, não conforme, indeterminado, N/A.
   - Cada status tem cor + símbolo + rótulo (nunca só cor -> daltonismo).

Assim um botão da marca nunca é confundido com um resultado "conforme".
Todas as cores de texto passam no contraste WCAG AA (>= 4,5:1).
"""
import streamlit as st

from verificacoes import classificar_status

# ══════════════════════════════════════════════════════════════════════════════
# PALETAS (fonte única — dashboard.py e visualizador_3d.py importam daqui)
# ══════════════════════════════════════════════════════════════════════════════
PALETA = {
    "deep":       "#0B1F3B",   # texto principal, títulos  (16,5:1 no branco)
    "azul":       "#2563EB",   # ação primária              (5,2:1)
    "azul_hover": "#1D4ED8",
    "teal":       "#10B981",   # SÓ marca/logo (2,5:1 -> nunca usar como texto)
    "teal_texto": "#047857",   # teal quando precisar ser texto (5,5:1)
    "canvas":     "#F8FAFC",   # fundo da página (off-white)
    "superficie": "#FFFFFF",   # cards, sidebar
    "suave":      "#F1F5F9",   # inputs, cabeçalho de tabela
    "linha":      "#E2E8F0",   # bordas e divisores
    "texto_2":    "#334155",   # texto secundário
    "muted":      "#64748B",   # legendas (4,8:1)
}

# Preenchimentos (gráficos, 3D, ícones) — contraste >= 3:1 no branco
CORES_STATUS = {
    "Conforme":      "#059669",
    "Parcial":       "#7C3AED",
    "Não Conforme":  "#DC2626",
    "Indeterminado": "#D97706",
    "N/A":           "#94A3B8",   # propositalmente apagado: "não se aplica"
}

# Símbolos de status — forma diferente para cada um (não depende de cor)
SIMBOLO_STATUS = {
    "Conforme":      "✓",
    "Parcial":       "◐",
    "Não Conforme":  "✕",
    "Indeterminado": "?",
    "N/A":           "—",
}

# Confiança usa OUTRO canal visual: escala de azul (escuro = mais confiável).
# Antes era verde/amarelo/vermelho, que se confundia com os status.
CORES_CONFIANCA = {"ALTA": "#0B1F3B", "MEDIA": "#2563EB", "BAIXA": "#94A3B8"}
SIMBOLO_CONFIANCA = {"ALTA": "▮▮▮", "MEDIA": "▮▮▯", "BAIXA": "▮▯▯"}

FONTE_UI = "Inter"
FONTE_DISPLAY = "Outfit"


# ══════════════════════════════════════════════════════════════════════════════
# LOGO (símbolo vetorial + wordmark em HTML)
# ══════════════════════════════════════════════════════════════════════════════
# Símbolo "Ai": o "A" é uma peça única (perna inclinada que lembra uma rampa +
# perna vertical, com recorte triangular por baixo) e o "i" é teal.
# Redesenhado em vetor a partir do ícone da marca (viewBox 410 x 370).
LOGO_SIMBOLO_SVG = """<svg viewBox="0 0 410 370" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="access Ai">
  <path d="M8,365 L152,146 Q164,127 188,127 L285,127 L285,365 L215,365 L215,180 L95,365 Z" fill="#2563EB"/>
  <rect x="322" y="125" width="80" height="240" fill="#10B981"/>
  <circle cx="360" cy="48" r="45" fill="#10B981"/>
</svg>"""


def logo_html(tamanho_px: int = 24, com_tagline: bool = True) -> str:
    """Bloco do logo para a sidebar: 'access' + símbolo + tagline.

    tamanho_px = altura total do símbolo (com o ponto do i). A barra do "i"
    ocupa ~65% dessa altura e deve coincidir com a altura das minúsculas.
    """
    tagline = (
        '<div class="brand-tagline">NBR 9050 · Accessibility Checker</div>'
        if com_tagline else ""
    )
    return f"""
    <div class="brand">
      <div class="brand-row">
        <span class="brand-word">access</span>
        <span class="brand-mark" style="height:{tamanho_px}px;width:{int(tamanho_px*410/370)}px">
          {LOGO_SIMBOLO_SVG}
        </span>
      </div>
      {tagline}
    </div>
    """


# ══════════════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════════════
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {{
    --deep:      {PALETA['deep']};
    --azul:      {PALETA['azul']};
    --azul-h:    {PALETA['azul_hover']};
    --teal:      {PALETA['teal']};
    --teal-txt:  {PALETA['teal_texto']};
    --canvas:    {PALETA['canvas']};
    --surface:   {PALETA['superficie']};
    --suave:     {PALETA['suave']};
    --linha:     {PALETA['linha']};
    --texto-2:   {PALETA['texto_2']};
    --muted:     {PALETA['muted']};

    --ok:   #047857;  --ok-bg:   #ECFDF5;
    --parc: #6D28D9;  --parc-bg: #F5F3FF;
    --nc:   #B91C1C;  --nc-bg:   #FEF2F2;
    --ind:  #B45309;  --ind-bg:  #FFFBEB;
    --na:   #475569;  --na-bg:   #F1F5F9;

    --font:    '{FONTE_UI}', system-ui, -apple-system, 'Segoe UI', Arial, sans-serif;
    --display: '{FONTE_DISPLAY}', '{FONTE_UI}', system-ui, sans-serif;
    --mono:    'JetBrains Mono', ui-monospace, 'Cascadia Mono', Consolas, monospace;

    --raio:    10px;
    --sombra:  0 1px 2px rgba(11,31,59,0.04), 0 1px 3px rgba(11,31,59,0.06);

    /* compatibilidade com estilos antigos (dashboard.py usa var(--border)) */
    --border:  {PALETA['linha']};
    --text:    {PALETA['deep']};
}}

/* ── Base ─────────────────────────────────────────────────────────────── */
html, body, .stApp, [class*="css"] {{ font-family: var(--font) !important; }}
.stApp {{ background-color: var(--canvas) !important; color: var(--deep); }}
.stApp h1, .stApp h2, .stApp h3 {{ font-family: var(--display) !important; color: var(--deep); letter-spacing: -0.01em; }}
code, pre, .stCode {{ font-family: var(--mono) !important; }}
hr {{ border-color: var(--linha) !important; }}
[data-testid="stMainBlockContainer"], .block-container {{ padding-top: 2rem !important; max-width: 1280px; }}

/* ── Sidebar ──────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background: var(--surface) !important;
    border-right: 1px solid var(--linha) !important;
}}
section[data-testid="stSidebar"] {{ min-width: 248px !important; max-width: 248px !important; }}
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] [data-baseweb="select"] > div {{
    background: var(--suave) !important; border: 1px solid var(--linha) !important; border-radius: 8px !important;
}}
.sb-label {{
    font-size: 0.68rem; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.08em; margin: 1.1rem 0 0.4rem 0;
}}
.sb-hint {{ font-size: 0.7rem; color: var(--muted); margin: -0.2rem 0 0.35rem 0; }}
.sb-footer {{ font-size: 0.68rem; color: var(--muted); line-height: 1.7; padding-top: 0.5rem; }}
.sb-footer strong {{ color: var(--texto-2); font-weight: 600; }}
.sb-instituicao {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--linha); font-size: 0.66rem; color: var(--muted); line-height: 1.5; }}
.sb-instituicao img {{ height: 18px; opacity: 0.8; display: block; margin-bottom: 0.45rem; }}

/* ── Marca ────────────────────────────────────────────────────────────── */
.brand {{ padding: 0.25rem 0 1rem 0; border-bottom: 1px solid var(--linha); margin-bottom: 0.25rem; }}
.brand-row {{ display: flex; align-items: flex-end; gap: 5px; line-height: 1; }}
.brand-word {{ font-family: var(--display); font-weight: 600; font-size: 1.75rem; color: var(--deep); letter-spacing: -0.03em; line-height: 1; }}
.brand-mark {{ display: inline-block; margin-bottom: 0.2em; flex-shrink: 0; }}   /* apoia o símbolo na linha de base */
.brand-mark svg {{ width: 100%; height: 100%; display: block; }}
.brand-tagline {{ font-size: 0.6rem; color: var(--muted); letter-spacing: 0.18em; text-transform: uppercase; margin-top: 0.45rem; }}

/* ── Cabeçalho da página (hero) ───────────────────────────────────────── */
.hero-block {{ display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem; margin-bottom: 1.25rem; }}
/* mesma tipografia do wordmark "access" (.brand-word) e da tagline (.brand-tagline) */
.hero-title {{ font-family: var(--display); font-size: 2.1rem; font-weight: 600; color: var(--deep); line-height: 1; letter-spacing: -0.03em; }}
.hero-sub {{ margin-top: 0.6rem; font-size: 0.66rem; color: var(--muted); letter-spacing: 0.18em; text-transform: uppercase; }}
.pill {{
    display: inline-flex; align-items: center; gap: 4px; font-size: 0.7rem; font-weight: 600;
    padding: 2px 9px; border-radius: 999px; background: var(--suave); color: var(--texto-2); border: 1px solid var(--linha);
}}
.pill-azul {{ background: #EFF6FF; color: var(--azul); border-color: #BFDBFE; }}

/* ── Títulos de seção ─────────────────────────────────────────────────── */
.section-title {{
    font-family: var(--display); font-size: 1.05rem; font-weight: 600; color: var(--deep);
    margin: 0.5rem 0 0.75rem 0; display: flex; align-items: center; gap: 0.5rem;
}}
.section-sub {{ font-family: var(--font); font-weight: 400; color: var(--muted); font-size: 0.8rem; }}
.texto-suave {{ font-size: 0.82rem; color: var(--muted); }}

/* ── Badges de status (cor + símbolo + rótulo) ────────────────────────── */
.badge {{
    display: inline-flex; align-items: center; gap: 5px; padding: 2px 9px; border-radius: 999px;
    font-size: 0.72rem; font-weight: 600; white-space: nowrap; border: 1px solid transparent;
}}
.badge .sym {{ font-weight: 700; }}
.badge-conforme {{ background: var(--ok-bg);   color: var(--ok);   border-color: #A7F3D0; }}
.badge-parcial  {{ background: var(--parc-bg); color: var(--parc); border-color: #DDD6FE; }}
.badge-nao      {{ background: var(--nc-bg);   color: var(--nc);   border-color: #FECACA; }}
.badge-indet    {{ background: var(--ind-bg);  color: var(--ind);  border-color: #FDE68A; }}
.badge-na       {{ background: var(--na-bg);   color: var(--na);   border-color: var(--linha); }}

/* ── Cards de métricas ────────────────────────────────────────────────── */
.metric-row {{ display: flex; gap: 0.75rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
.metric-card {{
    flex: 1; min-width: 150px; background: var(--surface); border: 1px solid var(--linha);
    border-radius: 12px; padding: 1rem 1.15rem; box-shadow: var(--sombra);
}}
.metric-label {{ font-size: 0.78rem; color: var(--texto-2); font-weight: 500; margin-bottom: 0.55rem; }}
.metric-num {{ font-family: var(--display); font-size: 1.95rem; font-weight: 600; line-height: 1; color: var(--deep); white-space: nowrap; }}
.metric-ctx {{ font-size: 0.72rem; color: var(--muted); margin-top: 0.5rem; line-height: 1.4; }}
.metric-ctx strong {{ color: var(--deep); font-weight: 600; }}
.tec {{ color: var(--muted); font-weight: 400; }}
.mini-seg {{ display: flex; gap: 2px; height: 6px; margin-top: 0.75rem; border-radius: 99px; overflow: hidden; background: var(--suave); }}
.mini-seg span {{ display: block; height: 100%; }}

/* ── Conformidade (Resultados) ────────────────────────────────────────── */
.conf-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }}
@media (max-width: 760px) {{ .conf-row {{ grid-template-columns: 1fr; }} }}
.conf-card {{ background: var(--surface); border: 1px solid var(--linha); border-radius: 12px; padding: 1.1rem 1.25rem; box-shadow: var(--sombra); }}
.conf-num {{ font-family: var(--display); font-size: 2.6rem; font-weight: 600; color: var(--deep); line-height: 1; }}
.conf-exp {{ font-size: 0.8rem; color: var(--texto-2); margin-top: 0.6rem; line-height: 1.5; }}
.conf-nota {{ font-size: 0.75rem; color: var(--muted); margin: 0.5rem 0 1.25rem 0.1rem; }}

/* ── Barra segmentada + lista ─────────────────────────────────────────── */
.seg-head {{ display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--texto-2); margin-bottom: 0.5rem; }}
.seg-head strong {{ color: var(--deep); font-weight: 600; }}
.segbar {{ display: flex; gap: 4px; height: 20px; margin-bottom: 0.9rem; }}
.segbar .seg {{ display: block; border-radius: 6px; min-width: 6px; }}
.seg-row {{ display: flex; align-items: flex-start; gap: 0.6rem; padding: 0.45rem 0; border-bottom: 1px dashed var(--linha); }}
.seg-row:last-child {{ border-bottom: none; }}
.seg-zero {{ opacity: 0.45; }}
.seg-dot {{ width: 18px; height: 18px; border-radius: 5px; color: #fff; font-size: 0.65rem; font-weight: 700;
            display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 1px; }}
.seg-txt {{ flex: 1; min-width: 0; }}
.seg-lbl {{ font-size: 0.84rem; color: var(--deep); font-weight: 500; }}
.seg-det {{ font-size: 0.72rem; color: var(--muted); margin-top: 1px; line-height: 1.4; }}
.seg-qtd {{ font-size: 0.84rem; font-weight: 600; color: var(--deep); min-width: 2.2rem; text-align: right; }}
.seg-pct {{ font-size: 0.8rem; color: var(--muted); min-width: 3.2rem; text-align: right; }}

/* ── Legenda (origem do dado) ─────────────────────────────────────────── */
.legenda {{ background: var(--surface); border: 1px solid var(--linha); border-radius: 12px; padding: 0.9rem 1.1rem; margin: 0.75rem 0 1.25rem 0; }}
.leg-title {{ font-family: var(--display); font-weight: 600; font-size: 0.95rem; color: var(--deep); margin-bottom: 0.5rem; }}
.leg-row {{ display: flex; gap: 0.6rem; font-size: 0.82rem; color: var(--texto-2); padding: 0.2rem 0; line-height: 1.5; }}
.leg-row strong {{ color: var(--deep); }}
.leg-sym {{ font-family: var(--mono); color: var(--azul); letter-spacing: 1px; flex-shrink: 0; min-width: 3.4rem; white-space: nowrap; }}
.leg-nota {{ font-size: 0.72rem; color: var(--muted); margin-top: 0.5rem; }}
.passo-a-passo {{ font-size: 0.85rem; color: var(--texto-2); line-height: 1.6; margin: 0 0 1rem 0; }}
.passo-a-passo strong {{ color: var(--deep); }}

/* ── Análise geral estruturada ────────────────────────────────────────── */
.analise {{ background: var(--surface); border: 1px solid var(--linha); border-radius: 12px; padding: 1.1rem 1.25rem; margin: 0.5rem 0 1.25rem 0; }}
.an-manchete {{ font-family: var(--display); font-size: 1.15rem; color: var(--deep); padding-bottom: 0.8rem; margin-bottom: 0.4rem; border-bottom: 1px solid var(--linha); }}
.an-manchete strong {{ font-weight: 600; }}
.an-bloco {{ padding: 0.55rem 0; }}
.an-tit {{ font-size: 0.84rem; font-weight: 600; color: var(--deep); display: flex; align-items: baseline; gap: 0.4rem; flex-wrap: wrap; }}
.an-sym {{ font-weight: 700; }}
.an-qtd {{ font-size: 0.72rem; font-weight: 600; color: var(--muted); background: var(--suave); border-radius: 99px; padding: 0 7px; }}
.an-dica {{ font-size: 0.75rem; font-weight: 400; color: var(--muted); }}
.chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 0.4rem; }}
.chip {{ font-size: 0.74rem; color: var(--texto-2); background: var(--suave); border: 1px solid var(--linha); border-radius: 99px; padding: 2px 9px; white-space: nowrap; }}
.an-corr {{ margin-top: 0.5rem; padding-top: 0.8rem; border-top: 1px solid var(--linha); }}
.corr-row {{ display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; padding: 0.25rem 0; font-size: 0.78rem; }}
.corr-de {{ color: var(--muted); text-decoration: line-through; }}
.corr-seta {{ color: var(--muted); }}
.corr-para {{ color: var(--deep); font-weight: 600; }}

/* ── Containers com borda (st.container(border=True)) viram cards ─────── */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{
    background: var(--surface); border-color: var(--linha) !important; border-radius: 12px !important; box-shadow: var(--sombra);
}}
.card-tit {{ font-family: var(--display); font-size: 1.02rem; font-weight: 600; color: var(--deep); margin-bottom: 0.15rem; }}
.card-sub {{ font-size: 0.75rem; color: var(--muted); margin-bottom: 0.8rem; }}
.resumo-lado {{ display: flex; flex-direction: column; gap: 1.1rem; padding-top: 0.4rem; }}
.resumo-lado .rl-num {{ font-family: var(--display); font-size: 1.8rem; font-weight: 600; color: var(--deep); line-height: 1; }}
.resumo-lado .rl-lbl {{ font-size: 0.75rem; color: var(--muted); margin-top: 0.25rem; line-height: 1.35; }}
.c-green  {{ color: var(--ok)   !important; }}
.c-purple {{ color: var(--parc) !important; }}
.c-red    {{ color: var(--nc)   !important; }}
.c-amber  {{ color: var(--ind)  !important; }}
.c-blue   {{ color: var(--azul) !important; }}
.c-muted  {{ color: var(--muted)!important; }}

/* ── Tabela de resultados ─────────────────────────────────────────────── */
.result-table {{
    width: 100%; border-collapse: separate; border-spacing: 0; font-size: 0.82rem;
    background: var(--surface); border: 1px solid var(--linha); border-radius: var(--raio); overflow: hidden;
}}
.result-table th {{
    font-size: 0.68rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em;
    padding: 10px 12px; text-align: left; background: var(--suave); border-bottom: 1px solid var(--linha);
}}
.result-table td {{ padding: 10px 12px; border-bottom: 1px solid var(--linha); vertical-align: top; color: var(--deep); }}
.result-table tr:last-child td {{ border-bottom: none; }}
.result-table tr:hover td {{ background: var(--canvas); }}
.td-mono   {{ font-family: var(--mono); font-size: 0.76rem; color: var(--texto-2); white-space: nowrap; }}
.td-muted  {{ color: var(--muted) !important; }}
.td-strong {{ font-weight: 500; }}
.td-rec    {{ color: var(--nc) !important; font-size: 0.8rem; }}
.td-item   {{ font-family: var(--mono); font-size: 0.76rem; color: var(--azul); font-weight: 500; white-space: nowrap; }}

/* ── GlobalId ─────────────────────────────────────────────────────────── */
.globalid {{
    font-family: var(--mono); font-size: 0.68rem; background: var(--suave); border: 1px solid var(--linha);
    border-radius: 6px; padding: 2px 6px; color: var(--texto-2); display: inline-block;
}}

/* ── Caixas de mensagem ───────────────────────────────────────────────── */
.info-box {{
    background: #EFF6FF; border: 1px solid #DBEAFE; border-radius: var(--raio);
    padding: 0.8rem 1rem; font-size: 0.84rem; color: #1E3A8A; margin: 0.75rem 0;
}}
.warn-box {{
    background: var(--ind-bg); border: 1px solid #FDE68A; border-radius: var(--raio);
    padding: 0.8rem 1rem; font-size: 0.84rem; color: #78350F; margin: 0.75rem 0;
}}
.empty-state {{ text-align: center; padding: 4rem 2rem; }}
.empty-state .es-title {{ font-family: var(--display); font-size: 1.15rem; font-weight: 600; color: var(--deep); }}
.empty-state .es-sub {{ font-size: 0.85rem; color: var(--muted); margin-top: 0.4rem; }}

/* ── Card de arquivo carregado ────────────────────────────────────────── */
.file-card {{
    display: flex; align-items: center; gap: 0.6rem; background: var(--surface); border: 1px solid var(--linha);
    border-radius: var(--raio); padding: 0.65rem 0.9rem; margin-top: 0.5rem; font-size: 0.85rem;
}}
.file-card .fc-ok {{ color: var(--ok); font-weight: 700; }}
.file-card .fc-meta {{ font-family: var(--mono); font-size: 0.72rem; color: var(--muted); }}

/* ── Stepper (passos da execução) ─────────────────────────────────────── */
.stepper {{
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 0.9rem 1.1rem;
    background: var(--surface); border: 1px solid var(--linha); border-radius: var(--raio); margin-bottom: 1.25rem;
}}
.step {{ display: flex; align-items: center; gap: 8px; }}
.step-dot {{
    width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-size: 0.72rem; font-weight: 700; flex-shrink: 0;
}}
.step-done   .step-dot {{ background: var(--deep); color: #fff; }}
.step-active .step-dot {{ background: var(--azul); color: #fff; }}
.step-pending .step-dot {{ background: var(--suave); color: var(--muted); border: 1px solid var(--linha); }}
.step-label {{ font-size: 0.82rem; font-weight: 600; color: var(--deep); }}
.step-pending .step-label {{ color: var(--muted); }}
.step-sub {{ font-size: 0.68rem; color: var(--muted); }}
.step-arrow {{ color: var(--linha); font-size: 0.9rem; }}

/* ── Log técnico ──────────────────────────────────────────────────────── */
.terminal {{
    background: var(--deep); border-radius: var(--raio); padding: 1rem 1.25rem; font-family: var(--mono);
    font-size: 0.74rem; color: #CBD5E1; max-height: 280px; overflow-y: auto; line-height: 1.7; white-space: pre-wrap;
}}

/* ── Inputs ───────────────────────────────────────────────────────────── */
.stTextInput input, .stTextArea textarea {{ border-radius: 8px !important; font-size: 0.85rem !important; }}

/* ── Upload ───────────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] section,
[data-testid="stFileUploaderDropzone"] {{
    background: var(--surface) !important; border: 1.5px dashed #CBD5E1 !important; border-radius: 12px !important;
    padding: 1.6rem !important; transition: border-color 0.15s ease, background-color 0.15s ease;
}}
[data-testid="stFileUploader"] section:hover,
[data-testid="stFileUploaderDropzone"]:hover {{ border-color: var(--azul) !important; background: #F8FAFF !important; }}

/* ── Botões ───────────────────────────────────────────────────────────── */
.stButton button {{
    background: var(--azul) !important; color: #FFFFFF !important; font-weight: 600 !important;
    font-size: 0.9rem !important; border: none !important; border-radius: 8px !important;
    padding: 0.6rem 1.5rem !important; box-shadow: var(--sombra) !important;
    transition: background-color 0.15s ease !important;
}}
.stButton button p {{ color: #FFFFFF !important; }}
.stButton button:hover {{ background: var(--azul-h) !important; }}
.stButton button:focus-visible {{ outline: 2px solid var(--azul) !important; outline-offset: 2px !important; }}
.stButton button:disabled {{ background: var(--suave) !important; color: var(--muted) !important; box-shadow: none !important; }}
.stButton button:disabled p {{ color: var(--muted) !important; }}

[data-testid="stDownloadButton"] button {{
    background: var(--surface) !important; color: var(--deep) !important; border: 1px solid var(--linha) !important;
    border-radius: 8px !important; font-weight: 500 !important; box-shadow: var(--sombra) !important;
    transition: border-color 0.15s ease !important;
}}
[data-testid="stDownloadButton"] button:hover {{ border-color: var(--azul) !important; color: var(--azul) !important; }}

/* ── Abas ─────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tab"] {{ font-size: 0.86rem !important; color: var(--muted) !important; }}
[data-testid="stTabs"] [role="tab"] p {{ font-weight: 500; }}
[data-testid="stTabs"] [role="tab"][aria-selected="true"],
[data-testid="stTabs"] [role="tab"][aria-selected="true"] p {{ color: var(--deep) !important; }}

/* ── Expander ─────────────────────────────────────────────────────────── */
[data-testid="stExpander"] details {{ border: 1px solid var(--linha) !important; border-radius: var(--raio) !important; background: var(--surface); }}

/* ── Rodapé ───────────────────────────────────────────────────────────── */
.footer-app {{ border-top: 1px solid var(--linha); padding: 1rem 0; margin-top: 2rem; font-size: 0.72rem; color: var(--muted); }}

/* ── Chrome do Streamlit ──────────────────────────────────────────────── */
#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}

/* ── Movimento reduzido (acessibilidade) ──────────────────────────────── */
@media (prefers-reduced-motion: reduce) {{
    * {{ transition: none !important; animation: none !important; }}
}}
</style>
"""

# Nome antigo mantido para compatibilidade
CSS_ZIGURAT = CSS


def aplicar_estilo() -> None:
    """Injeta o CSS da identidade visual na página."""
    st.markdown(CSS, unsafe_allow_html=True)


_CLASSE_BADGE = {
    "Conforme": "badge-conforme",
    "Parcial": "badge-parcial",
    "Não Conforme": "badge-nao",
    "Indeterminado": "badge-indet",
    "N/A": "badge-na",
}


def status_badge(status: str) -> str:
    """Badge de status: cor + símbolo + rótulo."""
    s = classificar_status(status)
    return (f'<span class="badge {_CLASSE_BADGE[s]}">'
            f'<span class="sym" aria-hidden="true">{SIMBOLO_STATUS[s]}</span>{s}</span>')


def rotulo_status(status: str) -> str:
    """Versão em texto puro (para st.dataframe): '✓ Conforme'."""
    s = classificar_status(status)
    return f"{SIMBOLO_STATUS[s]} {s}"

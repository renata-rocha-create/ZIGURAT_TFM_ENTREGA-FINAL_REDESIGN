"""
visualizador_3d.py — Modelo 3D colorido por status de conformidade.

1. extrair_malhas(): durante a auditoria, lê a geometria dos elementos
   auditados (+ lajes e paredes como contexto) com ifcopenshell.geom e guarda
   as malhas triangulares (vértices + faces).
2. render_aba_3d(): desenha tudo com Plotly Mesh3d, com o elemento escolhido
   em destaque.

Precisa de "plotly" no requirements.txt.
"""
import numpy as np
import pandas as pd
import streamlit as st

# Pior status "vence" quando o mesmo elemento aparece em mais de um item
# (ex: uma porta avaliada em 6.11.2 e em 4.6.6).
PRIORIDADE = {"Não Conforme": 4, "Indeterminado": 3, "Parcial": 2, "Conforme": 1, "N/A": 0}
from ui_style import CORES_STATUS, PALETA, FONTE_UI

CORES = CORES_STATUS                 # fonte única: ui_style.py
COR_DESTAQUE = PALETA["azul"]        # azul da marca = "selecionado" (não é cor de status)
CLASSES_CONTEXTO = ["IfcSlab", "IfcWall", "IfcWallStandardCase"]
MAX_CONTEXTO = 800      # limite de elementos de contexto (modelos grandes)
MAX_AUDITADOS = 600     # limite de elementos auditados desenhados


def status_por_elemento(linhas: list[dict]) -> dict:
    """GlobalId → {status (o pior), nome, itens}."""
    out = {}
    for l in linhas or []:
        gid = l["global_id"]
        atual = out.get(gid)
        if atual is None:
            out[gid] = {"status": l["status"], "nome": l["nome"], "itens": [l["item_nbr"]],
                        "ifc_class": l.get("ifc_class", "")}
        else:
            atual["itens"].append(l["item_nbr"])
            if PRIORIDADE.get(l["status"], 0) > PRIORIDADE.get(atual["status"], 0):
                atual["status"] = l["status"]
    return out


def extrair_malhas(ifc_path: str, linhas: list[dict]) -> dict:
    """
    Extrai malhas triangulares. Coordenadas do mundo (world coords) são
    guardadas também no bounding box ("caixa envolvente") de cada elemento —
    o BCF precisa delas para apontar a câmera no lugar certo do modelo real.
    """
    try:
        import ifcopenshell
        import ifcopenshell.geom
    except ImportError:
        return {"erro": "ifcopenshell.geom indisponível", "auditados": [], "contexto": []}

    ifc = ifcopenshell.open(ifc_path)
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)

    def malha(el):
        try:
            shape = ifcopenshell.geom.create_shape(settings, el)
            v = np.array(shape.geometry.verts, dtype=float).reshape(-1, 3)
            f = np.array(shape.geometry.faces, dtype=int).reshape(-1, 3)
            if len(v) == 0 or len(f) == 0:
                return None
            return v, f
        except Exception:
            return None

    info = status_por_elemento(linhas)
    auditados, falhas = [], 0
    for gid, dados in list(info.items())[:MAX_AUDITADOS]:
        try:
            el = ifc.by_guid(gid)
        except Exception:
            el = None
        m = malha(el) if el is not None else None
        if m is None:
            falhas += 1
            continue
        v, f = m
        auditados.append({
            "global_id": gid, "nome": dados["nome"], "status": dados["status"],
            "ifc_class": dados.get("ifc_class", ""),
            "itens": ", ".join(sorted(set(dados["itens"]))),
            "verts": v, "faces": f,
            "bbox_min": v.min(axis=0).tolist(), "bbox_max": v.max(axis=0).tolist(),
        })

    contexto = []
    ids_auditados = set(info)
    for classe in CLASSES_CONTEXTO:
        try:
            elementos = ifc.by_type(classe)
        except Exception:
            continue
        for el in elementos:
            if len(contexto) >= MAX_CONTEXTO:
                break
            if el.GlobalId in ids_auditados or (classe == "IfcWall" and el.is_a("IfcWallStandardCase")):
                continue  # evita desenhar duas vezes (IfcWallStandardCase é subtipo de IfcWall)
            m = malha(el)
            if m is not None:
                contexto.append({"verts": m[0], "faces": m[1]})

    return {"auditados": auditados, "contexto": contexto, "sem_geometria": falhas}


def _origem(malhas):
    todos = [a["verts"] for a in malhas["auditados"]] + [c["verts"] for c in malhas["contexto"]]
    return np.vstack(todos).min(axis=0) if todos else np.zeros(3)


def _juntar(lista, origem):
    """Une várias malhas num único Mesh3d (muito mais leve de desenhar)."""
    vs, fs, n = [], [], 0
    for m in lista:
        vs.append(m["verts"] - origem)
        fs.append(m["faces"] + n)
        n += len(m["verts"])
    return np.vstack(vs), np.vstack(fs)


def _figura(malhas, gid_destaque=None, status_visiveis=None, mostrar_contexto=True):
    import plotly.graph_objects as go

    origem = _origem(malhas)
    fig = go.Figure()

    if mostrar_contexto and malhas["contexto"]:
        v, f = _juntar(malhas["contexto"], origem)
        fig.add_trace(go.Mesh3d(
            x=v[:, 0], y=v[:, 1], z=v[:, 2], i=f[:, 0], j=f[:, 1], k=f[:, 2],
            color="#c5cad8", opacity=0.12, name="Contexto (lajes/paredes)",
            hoverinfo="skip", showlegend=True, flatshading=True))

    ja_na_legenda = set()
    # Espaços (IfcSpace) são volumes de AR: desenhados primeiro e bem
    # translúcidos, como um "ghost" — senão escondem as louças e barras.
    ordem = sorted(malhas["auditados"], key=lambda a: a.get("ifc_class") != "IfcSpace")
    for a in ordem:
        if status_visiveis and a["status"] not in status_visiveis:
            continue
        destaque = a["global_id"] == gid_destaque
        v = a["verts"] - origem
        f = a["faces"]
        cor = COR_DESTAQUE if destaque else CORES.get(a["status"], CORES_STATUS["N/A"])
        eh_espaco = a.get("ifc_class") == "IfcSpace"
        grupo = "Selecionado" if destaque else (f"{a['status']} (ambiente)" if eh_espaco else a["status"])
        if destaque:
            opac = 0.45 if eh_espaco else 1.0
        elif eh_espaco:
            opac = 0.10
        else:
            opac = 1.0 if not gid_destaque else 0.35
        fig.add_trace(go.Mesh3d(
            x=v[:, 0], y=v[:, 1], z=v[:, 2], i=f[:, 0], j=f[:, 1], k=f[:, 2],
            color=cor, opacity=opac,
            name=grupo, legendgroup=grupo, showlegend=grupo not in ja_na_legenda,
            flatshading=True,
            hovertemplate=(f"<b>{a['nome'][:60]}</b><br>Status: {a['status']}<br>"
                           f"Itens: {a['itens']}<br>GlobalId: {a['global_id']}<extra></extra>"),
        ))
        ja_na_legenda.add(grupo)

    fig.update_layout(
        height=620, margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)", font=dict(family=FONTE_UI),
        legend=dict(orientation="h", y=1.02, x=0),
        scene=dict(aspectmode="data",
                   xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
                   camera=dict(eye=dict(x=1.4, y=-1.4, z=0.9))),
    )
    return fig


def render_aba_3d(malhas: dict | None, linhas: list[dict] | None) -> None:
    if not malhas or not malhas.get("auditados"):
        msg = "Execute a auditoria para ver o modelo 3D."
        if malhas and malhas.get("erro"):
            msg = f"Geometria indisponível: {malhas['erro']}"
        elif malhas is not None:
            msg = "Nenhum elemento auditado com geometria 3D extraível."
        st.markdown(f'<div class="info-box">{msg}</div>', unsafe_allow_html=True)
        return

    try:
        import plotly  # noqa: F401
    except ImportError:
        st.error("Falta a biblioteca **plotly**. Adicione a linha `plotly>=5.20` "
                 "no requirements.txt e faça o deploy de novo.")
        return

    aud = malhas["auditados"]
    c1, c2, c3 = st.columns([2.2, 1.4, 1])
    opcoes = sorted(aud, key=lambda a: (-PRIORIDADE.get(a["status"], 0), a["nome"]))
    rotulos = {a["global_id"]: f"{a['status']} · {a['nome'][:70]} · {a['global_id']}" for a in opcoes}
    gid = c1.selectbox("Destacar elemento", [None] + [a["global_id"] for a in opcoes],
                       format_func=lambda g: "— nenhum —" if g is None else rotulos[g],
                       key="v3d_gid")
    todos_status = sorted({a["status"] for a in aud}, key=lambda s: -PRIORIDADE.get(s, 0))
    vis = c2.multiselect("Status visíveis", todos_status, default=todos_status, key="v3d_status")
    ctx = c3.toggle("Mostrar contexto", value=True, key="v3d_ctx")

    st.plotly_chart(_figura(malhas, gid, vis, ctx), use_container_width=True)

    info = []
    if malhas.get("sem_geometria"):
        info.append(f"{malhas['sem_geometria']} elemento(s) auditado(s) sem geometria 3D extraível")
    if len(malhas["contexto"]) >= MAX_CONTEXTO:
        info.append(f"contexto limitado a {MAX_CONTEXTO} lajes/paredes")
    st.caption("🖱️ Arraste para girar · roda do mouse para zoom · passe o mouse sobre um "
               "elemento para ver GlobalId e itens. " + (" · ".join(info) if info else ""))

    if gid and linhas:
        det = pd.DataFrame([l for l in linhas if l["global_id"] == gid])
        st.markdown('<div class="section-title">Verificações do elemento selecionado</div>',
                    unsafe_allow_html=True)
        st.dataframe(det[["item_nbr", "status", "valor_medido", "valor_exigido", "confianca",
                          "mensagem"]], hide_index=True, use_container_width=True)

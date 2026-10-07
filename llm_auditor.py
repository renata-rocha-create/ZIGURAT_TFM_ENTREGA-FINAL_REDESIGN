"""
llm_auditor.py — Montagem do prompt e chamada aos LLMs (Claude / Gemini).

Converte os elementos extraídos num resumo legível, monta o prompt com as
regras do JSON, chama o provedor escolhido e faz o parse robusto da resposta.
"""
import json
import re
from datetime import datetime

from regras import obter_regras_lista


def _resumo_elementos(elementos: dict) -> str:
    """
    Gera um resumo estruturado dos elementos extraídos, item por item da NBR.
    Em vez de despejar JSON bruto, apresenta os dados de forma orientada à verificação.
    """
    inv = elementos.get("inventario_modelo", {})
    linhas = []

    # ── Inventário ────────────────────────────────────────────────────────────
    linhas.append("## INVENTÁRIO DO MODELO")
    for entidade, qtd in inv.items():
        linhas.append(f"  {entidade}: {qtd} elementos")

    # ── Notas do modelo ───────────────────────────────────────────────────────
    for k, v in elementos.items():
        if k.startswith("nota_"):
            linhas.append(f"\n⚠️ NOTA — {k.replace('nota_','').upper()}: {v}")

    elems = elementos.get("elementos", {})

    # ── PORTAS ────────────────────────────────────────────────────────────────
    portas = elems.get("IfcDoor", [])
    if portas:
        linhas.append(f"\n## PORTAS (IfcDoor) — amostra de {len(portas)} elementos")
        for p in portas[:15]:
            gid  = p.get("GlobalId","?")
            nome = p.get("Name","?")
            oh   = p.get("OverallHeight_m") or p.get("OverallHeight")
            ow   = p.get("OverallWidth_m")  or p.get("OverallWidth")
            h_str = f"{oh:.3f}m" if oh else "N/D"
            w_str = f"{ow:.3f}m" if ow else "N/D"
            amb  = p.get("ambientes_adjacentes")
            pne  = "SIM" if p.get("pne_pcd_confirmado") else "não"
            linhas.append(f"  [{gid}] {nome} | Altura={h_str} | Largura={w_str} | "
                          f"Ambientes: {' ↔ '.join(amb) if amb else 'N/D'} | Porta de ambiente PNE/PCD (item 4.6.6)? {pne}")
        if len(portas) > 15:
            linhas.append(f"  ... +{len(portas)-15} portas na amostra (ver estatística completa abaixo)")

        est = elementos.get("estatisticas_portas")
        if est and est.get("com_dimensoes"):
            linhas.append(
                f"\n  📊 ESTATÍSTICA SOBRE TODAS AS {est['total']} PORTAS DO MODELO "
                f"(não apenas a amostra acima — use isto para o veredito do item 6.11.2):"
            )
            linhas.append(f"     Menor largura encontrada: {est['largura_min_m']}m [GlobalId: {est['largura_min_globalid']}]")
            linhas.append(f"     Menor altura encontrada: {est['altura_min_m']}m [GlobalId: {est['altura_min_globalid']}]")
            linhas.append(
                f"     Portas com largura < 0,80m: {est['n_nao_conformes_largura']} "
                f"| GlobalIds: {est['globalids_nao_conformes_largura'] or '—'}"
            )
            linhas.append(
                f"     Portas com altura < 2,10m: {est['n_nao_conformes_altura']} "
                f"| GlobalIds: {est['globalids_nao_conformes_altura'] or '—'}"
            )

    # ── ESCADAS ───────────────────────────────────────────────────────────────
    escadas = elems.get("Escadas", [])
    # Filtro robusto — tipo_ifc pode estar em chaves diferentes
    flights = [e for e in escadas if "StairFlight" in str(e.get("tipo_ifc",""))]
    stairs  = [e for e in escadas if e.get("tipo_ifc","") == "IfcStair"]
    linhas.append(f"\n## ESCADAS — {len(stairs)} IfcStair, {len(flights)} IfcStairFlight")
    if flights:
        linhas.append("  ⚠️ IMPORTANTE: RiserHeight_m e TreadLength_m já convertidos de pés→metros (×0.3048)")
        linhas.append("  Use desnivel_m = NumberOfRisers × RiserHeight_m para calcular desnível total")
        for f in flights[:12]:
            gid  = f.get("GlobalId","?")
            nome = (f.get("Name","") or "?")[:50]
            nr   = f.get("NumberOfRisers")
            rh   = f.get("RiserHeight_m")
            tl   = f.get("TreadLength_m")
            dv   = f.get("desnivel_m")
            # Formata com valores reais ou indica ausência
            nr_s = str(int(nr)) if nr else "N/D"
            rh_s = f"{float(rh):.4f}m" if rh else "N/D"
            tl_s = f"{float(tl):.4f}m" if tl else "N/D"
            dv_s = f"{float(dv):.3f}m" if dv else "N/D"
            linhas.append(f"  [{gid}] {nome}")
            linhas.append(f"    NumberOfRisers={nr_s} | RiserHeight_m={rh_s} | TreadLength_m={tl_s} | desnivel_m={dv_s}")
        # Resumo estatístico
        desniveis = [float(f["desnivel_m"]) for f in flights if f.get("desnivel_m")]
        if desniveis:
            linhas.append(f"  RESUMO: desnível mín={min(desniveis):.3f}m | máx={max(desniveis):.3f}m | médio={sum(desniveis)/len(desniveis):.3f}m")
            linhas.append(f"  Todos os {len([d for d in desniveis if d > 0.19])} lances com desnível > 0,19m REQUEREM corrimão.")
    else:
        linhas.append(f"  Nenhum IfcStairFlight com dados — IfcStair no inventário: {inv.get('IfcStair',0)}, IfcStairFlight: {inv.get('IfcStairFlight',0)}")

    # ── RAMPAS ────────────────────────────────────────────────────────────────
    rampas = elems.get("Rampas", [])
    linhas.append(f"\n## RAMPAS — {len(rampas)} elementos")
    if rampas:
        for r in rampas[:5]:
            gid   = r.get("GlobalId","?")
            nome  = r.get("Name","?")
            rise  = r.get("OverallRise_m","N/D")
            run_  = r.get("OverallRun_m","N/D")
            inc   = r.get("inclinacao_pct","?")
            fonte = r.get("fonte_dados_rampa","?")
            linhas.append(f"  [{gid}] {nome} | Rise={rise}m | Run={run_}m | Inclinação={inc}% | Fonte={fonte}")
            if r.get("deteccao_rampa"):
                linhas.append(f"    Detectada como rampa por: {r['deteccao_rampa']} (IfcSlab — não há IfcRamp no modelo)")
            for c in r.get("corrimaos_associados", []) or []:
                linhas.append(
                    f"    Corrimão ao lado: [{c.get('id')}] lado {c.get('lado')} | topo a {c.get('altura_topo_m')}m da superfície da rampa | "
                    f"níveis {c.get('alturas_m')} | 0,70m? {'SIM' if c.get('tem_070') else 'não'} | 0,92m? {'SIM' if c.get('tem_092') else 'não'} | "
                    f"acompanha a inclinação? {'SIM' if c.get('paralelo_a_rampa') else 'NÃO (varia ' + str(c.get('variacao_altura_m')) + 'm)'}")
            if fonte and "ESTIMATIVA" in fonte:
                linhas.append(f"    ⚠️ Rise/Run estimados por bounding box geométrico (Pset não trouxe OverallRise/Run) — conferir manualmente.")
            slope_bruto = r.get("Slope_pset_bruto")
            if slope_bruto is not None:
                linhas.append(f"    Valor bruto de 'Slope' no Pset: {slope_bruto} (unidade não confirmada — pode ser graus; comparar com Inclinação calculada acima antes de usar).")
    else:
        linhas.append("  Nenhuma rampa modelada (IfcRamp/IfcRampFlight ausentes)")

    # ── CORRIMÕES ─────────────────────────────────────────────────────────────
    corrimaos = elems.get("Corrimaos", [])
    linhas.append(f"\n## CORRIMÕES / GUARDA-CORPOS (IfcRailing) — {len(corrimaos)} elementos")
    for c in corrimaos[:8]:
        gid    = c.get("GlobalId","?")
        nome   = c.get("Name","?")
        tipo   = c.get("tipo_elemento","?")
        alturas = c.get("alturas_m", [])
        duplo  = c.get("corrimao_duplo_070_092", False)
        linhas.append(f"  [{gid}] {nome} | Tipo={tipo}")
        linhas.append(f"    Alturas encontradas nos Psets deste elemento: {alturas if alturas else 'N/D'} | Corrimão duplo (0,70m e 0,92m)? {'SIM' if duplo else 'não'}")
    if not corrimaos:
        linhas.append("  Nenhum IfcRailing encontrado")

    # ── SANITÁRIOS: BACIAS ───────────────────────────────────────────────────
    bacias = elems.get("Bacias", [])
    linhas.append(f"\n## BACIAS SANITÁRIAS (IfcFlowTerminal) — {len(bacias)} elementos")
    linhas.append("  VERIFICAR: MountingHeight (Pset) | Z_placement (coordenada Z do modelo) | altura_estimada")
    for b in bacias[:10]:
        gid  = b.get("GlobalId","?")
        nome = (b.get("Name","") or "?")[:55]
        mh   = b.get("MountingHeight_m","—")
        z    = b.get("Z_placement_m","—")
        alt  = b.get("altura_estimada_m","—")
        linhas.append(f"  [{gid}] {nome}")
        linhas.append(f"    MountingHeight={mh} | Z_placement={z}m | altura_estimada={alt}m")
    if bacias:
        linhas.append(f"  NBR 9050 item 7.7.2.1: altura bacia deve ser 0,43m ≤ h ≤ 0,45m (sem assento)")

    # ── SANITÁRIOS: LAVATÓRIOS ───────────────────────────────────────────────
    lavs = elems.get("Lavatorios", [])
    linhas.append(f"\n## LAVATÓRIOS (IfcFlowTerminal) — {len(lavs)} elementos")
    for lv in lavs[:8]:
        gid  = lv.get("GlobalId","?")
        nome = (lv.get("Name","") or "?")[:55]
        mh   = lv.get("MountingHeight_m","—")
        z    = lv.get("Z_placement_m","—")
        linhas.append(f"  [{gid}] {nome} | MountingHeight={mh} | Z={z}m")

    # ── SANITÁRIOS: BARRAS ───────────────────────────────────────────────────
    barras = elems.get("BarrasApoio", [])
    linhas.append(f"\n## BARRAS DE APOIO (IfcFlowTerminal) — {len(barras)} elementos")
    linhas.append("  NBR 9050 item 7.6-7.8: altura instalação ~0,75m | resistência mín 150 kgf")
    for b in barras[:10]:
        gid  = b.get("GlobalId","?")
        nome = (b.get("Name","") or "?")[:55]
        mh   = b.get("MountingHeight_m","—")
        z    = b.get("Z_placement_m","—")
        alt  = b.get("altura_estimada_m","—")
        linhas.append(f"  [{gid}] {nome}")
        linhas.append(f"    MountingHeight={mh} | Z_placement={z}m | altura_estimada={alt}m")

    # ── ESPAÇOS ───────────────────────────────────────────────────────────────
    espacos = elems.get("IfcSpace", [])
    n_total = len(espacos)
    linhas.append(f"\n## ESPAÇOS (IfcSpace) — {n_total} elementos")
    if not espacos:
        linhas.append("  AUSENTE: modelo não exportou IfcSpace")
        linhas.append("  → Corredores (6.11.1) e giro cadeira de rodas (7.5): Indeterminado")
        linhas.append("  → Para habilitar: exportar Rooms do Revit como IfcSpace")
    else:
        # Separa por tipo
        corredores    = [e for e in espacos if e.get("tipo_ambiente") == "corredor"]
        sanitarios_s  = [e for e in espacos if e.get("tipo_ambiente") == "sanitario"]
        sanit_nao_pne = [e for e in espacos if e.get("tipo_ambiente") == "sanitario_nao_pne"]
        outros        = [e for e in espacos if e.get("tipo_ambiente") == "outro"]

        linhas.append(
            f"  Corredores: {len(corredores)} | Sanitários PNE/PCD: {len(sanitarios_s)} | "
            f"Banheiros sem tag PNE/PCD (fora do escopo do item 7.5): {len(sanit_nao_pne)} | Outros: {len(outros)}"
        )

        # Resultados de giro por status — SÓ nos sanitários com tag PNE/PCD (item 7.5 é sobre
        # sanitário acessível, não sobre qualquer banheiro do modelo)
        conformes_giro  = [e for e in sanitarios_s if e.get("giro_150_status") == "Conforme"]
        nconf_giro      = [e for e in sanitarios_s if e.get("giro_150_status") == "Não Conforme"]
        indet_giro      = [e for e in sanitarios_s if e.get("giro_150_status") == "Indeterminado"]

        linhas.append(f"\n  TESTE GIRO ⌀1,50m (NBR 9050 item 7.5) — apenas sanitários PNE/PCD, via Shapely:")
        linhas.append(f"  ✅ Conformes: {len(conformes_giro)} | ❌ Não Conformes: {len(nconf_giro)} | ⚠️ Indeterminados: {len(indet_giro)}")
        if sanit_nao_pne:
            linhas.append(
                f"  ⚠️ {len(sanit_nao_pne)} banheiro(s) encontrados sem 'PNE'/'PCD' no nome — "
                f"EXCLUÍDOS do teste de giro por não serem sanitário acessível designado."
            )

        # Detalha sanitários
        if sanitarios_s:
            linhas.append(f"\n  SANITÁRIOS ACESSÍVEIS:")
            for e in sanitarios_s[:10]:
                gid  = e.get("GlobalId","?")
                nome = (e.get("Name","") or (e.get("LongName","") or "?"))[:40]
                area = e.get("area_geometrica_m2") or e.get("Area_m2","N/D")
                larg = e.get("largura_estimada_m","N/D")
                giro = e.get("giro_150_status","?")
                nota = e.get("giro_150_nota","")
                linhas.append(f"  [{gid}] {nome}")
                linhas.append(f"    Área={area}m² | Largura≈{larg}m | Giro⌀1,50m={giro}")
                if nota:
                    linhas.append(f"    Nota: {nota}")

        # Detalha corredores
        if corredores:
            linhas.append(f"\n  CORREDORES (item 6.11.1 — largura mín por comprimento):")
            for e in corredores[:10]:
                gid  = e.get("GlobalId","?")
                nome = (e.get("Name","") or (e.get("LongName","") or "?"))[:40]
                larg = e.get("largura_estimada_m","N/D")
                comp = e.get("comprimento_estimado_m","N/D")
                # Aplica regra NBR 9050 6.11.1
                if isinstance(larg, (int,float)) and isinstance(comp, (int,float)):
                    if comp <= 4.0:
                        limite = 0.90; regra = "≤4m → mín 0,90m"
                    elif comp <= 10.0:
                        limite = 1.20; regra = "≤10m → mín 1,20m"
                    else:
                        limite = 1.50; regra = ">10m → mín 1,50m"
                    status_corredor = "Conforme" if larg >= limite else "Não Conforme"
                    linhas.append(f"  [{gid}] {nome}")
                    linhas.append(f"    Largura={larg}m | Comp={comp}m | Regra: {regra} | Status: {status_corredor}")
                else:
                    linhas.append(f"  [{gid}] {nome} | Largura={larg}m | Comp={comp}m")

    # ── JANELAS ───────────────────────────────────────────────────────────────
    janelas = elems.get("IfcWindow", [])
    linhas.append(f"\n## JANELAS (IfcWindow) — {len(janelas)} elementos")
    for j in janelas[:5]:
        gid = j.get("GlobalId","?")
        nome = j.get("Name","?")
        sh = j.get("SillHeight_m","N/D")
        h  = j.get("OverallHeight_m","N/D")
        w  = j.get("OverallWidth_m","N/D")
        linhas.append(f"  [{gid}] {nome} | SillHeight={sh} | H={h}m | W={w}m")

    # ── DESNÍVEIS DE PISO (6.3.4) ─────────────────────────────────────────────
    desn = elems.get("Desniveis_pisos", [])
    linhas.append(f"\n## DESNÍVEIS DE PISO (item 6.3.4) — {len(desn)} pontos de passagem medidos na geometria")
    linhas.append("  Regra NBR 9050 6.3.4: ≤5mm dispensa tratamento | 5–20mm exige chanfro 1:2 | >20mm = degrau")
    for x in desn[:15]:
        linhas.append(f"  [{x.get('GlobalId')}] {x.get('tipo')}: {x.get('trecho')} | cotas {x.get('cota_lado_1_m')}m / "
                      f"{x.get('cota_lado_2_m')}m | desnível={x.get('desnivel_mm')}mm")
    chf = elems.get("Chanfros", [])
    linhas.append(f"  Chanfros/soleiras rampadas modelados: {len(chf)}")

    # ── PAREDES (fallback corredores) ─────────────────────────────────────────
    paredes = elems.get("IfcWall_amostra", [])
    if paredes:
        linhas.append(f"\n## PAREDES — amostra ({len(paredes)} de {inv.get('IfcWall',0)+inv.get('IfcWallStandardCase',0)} total)")
        linhas.append("  Use para estimar largura de corredores se IfcSpace ausente")
        for p in paredes[:5]:
            gid = p.get("GlobalId","?")
            nome = p.get("Name","?")
            w = p.get("Width_m","N/D")
            l = p.get("Length_m","N/D")
            linhas.append(f"  [{gid}] {nome} | Esp={w}m | Comp={l}m")

    return "\n".join(linhas)


def build_audit_prompt(elementos: dict, modelo_nome: str) -> str:
    """
    Constrói prompt de auditoria orientado a dados estruturados.
    Em vez de JSON bruto, envia resumo legível por item.
    Regras sempre vêm de nbr9050_rules.json (fonte única) — sem opção de planilha.
    """
    schema = elementos.get("schema", "IFC2X3")
    regras_uso = obter_regras_lista()

    # Instruções por item
    instrucoes = ""
    for r in regras_uso:
        status_possiveis = " | ".join(r.get("status_validacao_possiveis", ["Conforme","Não Conforme","Indeterminado","N/A"]))
        confianca_txt = "SIM — classificação qualitativa/heurística, marque requer_confirmacao_humana=true" if r.get("requer_nivel_confianca") else "não — dado geométrico/objetivo, requer_confirmacao_humana=false"
        instrucoes += f"""
### Item {r['item_nbr']} — {r['subcategoria']}
Verificação: {r['item_verificavel']}
Status possíveis para ESTE item: {status_possiveis}
Requer confirmação humana? {confianca_txt}
Entidade primária: {r['entidades']['primaria']} | Fallback: {r['entidades']['fallback']}
Estratégia primária: {r['estrategias']['primaria']}
Estratégia fallback: {r['estrategias']['fallback']}
Instrução: {r['prompt_llm']}
"""

    # Resumo estruturado dos dados (substitui JSON bruto)
    resumo_dados = _resumo_elementos(elementos)

    n = len(regras_uso)
    return f"""Você é um auditor especialista em acessibilidade arquitetônica — ABNT NBR 9050:2020.
Modelo: "{modelo_nome}" | Schema IFC: {schema}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGRAS OBRIGATÓRIAS DE AUDITORIA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. NUNCA retorne "Indeterminado" porque "não encontrou IfcSanitaryTerminal" — 
   este modelo usa IfcFlowTerminal para TODOS os equipamentos sanitários.
   As seções BACIAS, LAVATÓRIOS e BARRAS DE APOIO já estão classificadas para você.

2. Para ESCADAS: use o campo "desnivel_m" já calculado (NumberOfRisers × RiserHeight_m).
   RiserHeight já está convertido de pés para metros. Desnível > 0,19m → corrimão obrigatório.
   Para verificar o corrimão (item 5.4.3): um único IfcRailing pode conter VÁRIAS alturas
   diferentes (campo "alturas_m" — cada valor vem de um sub-Pset do mesmo elemento, ex:
   corrimão inferior + corrimão superior + guarda-corpo). NÃO conclua "sem corrimão duplo"
   só porque o Name do elemento diz "Guarda-corpo" — confira a lista "alturas_m" e o campo
   "corrimao_duplo_070_092" de cada IfcRailing antes de decidir o status.

3. Para CORREDORES sem IfcSpace: use a amostra de paredes para estimar distâncias,
   ou marque "Indeterminado" com recomendação específica de adicionar IfcSpace.

4. Para itens ausentes no modelo (ex: IfcWindow=0): retorne "N/A" com justificativa
   clara de que o elemento não existe no modelo, não "Indeterminado".

5. SEMPRE inclua o GlobalId do elemento mais representativo em cada resultado.

6. Z_placement_m e altura_estimada_m já estão em coordenadas RELATIVAS ao pavimento
   (valores entre 0,01m e 2,50m). Valores como 722m ou 732m foram FILTRADOS.
   Use esses campos para verificar alturas de bacias e barras de apoio.

7. LAVATÓRIOS: "cuba embutir", "cuba retang. embutir", "cuba-de-semiencaixe" são
   lavatórios SEM coluna → Conforme (item 7.8). "Coluna suspensa" → Não Conforme.

8. Gere EXATAMENTE {n} resultados — um por item listado abaixo.

9. Para PORTAS (item 6.11.2): a lista em "PORTAS (IfcDoor)" é só uma AMOSTRA
   ilustrativa. O veredito de conformidade deve usar a seção "ESTATÍSTICA SOBRE
   TODAS AS N PORTAS DO MODELO" — se n_nao_conformes_largura ou
   n_nao_conformes_altura forem > 0, o status é "Não Conforme" (não "Conforme"),
   mesmo que a amostra pareça toda ok. Cite os GlobalIds não conformes listados.

10. Para o item 4.6.6 (maçaneta tipo alavanca): avalie SOMENTE as portas com
    "pne_pcd_confirmado": true (ver "nota_portas_pne"). Portas sem essa tag NÃO
    entram nessa verificação — não as cite como não conformes nem indeterminadas
    para este item. Se nenhuma porta tiver "pne_pcd_confirmado": true, retorne
    status "N/A" para o item 4.6.6, explicando que nenhuma porta foi associada
    a sanitário/ambiente PNE/PCD. O item 6.11.2 (vão livre) continua valendo
    para todas as portas normalmente, independente dessa tag.

11. Status "Parcial": use SOMENTE nos itens cujo "Status possíveis para ESTE
    item" (ver seção ITENS A VERIFICAR) inclua "Parcial". Regra de limiar:
    conte X elementos conformes de Y elementos avaliados. X=Y → "Conforme".
    X=0 → "Não Conforme". 0<X<Y → "Parcial" (nunca arredonde pra Conforme ou
    Não Conforme). Não invente "Parcial" em itens que avaliam um único
    elemento/espaço — nesses, o status continua binário mesmo com esta opção
    disponível de forma geral no sistema.

12. Campo "requer_confirmacao_humana": true nos itens marcados como tal em
    "Requer confirmação humana?" na seção ITENS A VERIFICAR (tipicamente
    itens Qualitativos/Condicionais, como maçaneta e barras de apoio, cuja
    classificação vem de nome/tipo do elemento, não de medição direta).
    false nos itens objetivos/geométricos (ex: vão livre de porta, giro de
    cadeira de rodas).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ITENS A VERIFICAR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{instrucoes}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DADOS DO MODELO IFC (use estes dados para verificar cada item acima)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{resumo_dados}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMATO DE RESPOSTA — JSON VÁLIDO, SEM MARKDOWN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ O exemplo abaixo mostra APENAS A ESTRUTURA esperada. Os valores de
"elemento", "valor_encontrado" e "status" são fictícios — NÃO os copie nem
os use como referência de conteúdo. Preencha cada campo com o que você
efetivamente observou nos DADOS DO MODELO IFC acima, item por item.

{{
  "modelo": "{modelo_nome}",
  "schema_ifc": "{schema}",
  "data_auditoria": "{datetime.now().strftime('%d/%m/%Y')}",
  "resultados": [
    {{
      "item_nbr": "<código do item, ex: 6.11.2>",
      "categoria": "<categoria>",
      "subcategoria": "<subcategoria>",
      "elemento": "<contagem/descrição do(s) elemento(s) verificado(s) — preencher com dado real>",
      "globalid": "<GlobalId real do elemento mais representativo>",
      "tipo_ifc": "<classe IFC, ex: IfcDoor>",
      "valor_encontrado": "<valor medido/observado — se Parcial, escreva 'X de Y elementos conformes'>",
      "valor_exigido": "<critério normativo do item>",
      "status": "<use EXATAMENTE uma destas palavras, sem texto extra: Conforme | Parcial | Não Conforme | Indeterminado | N/A>",
      "requer_confirmacao_humana": "<true se o item tem classificação Qualitativa/Condicional (ver 'requer_nivel_confianca' de cada item), senão false>",
      "recomendacao": "<ação concreta — obrigatório se status for Não Conforme, Parcial ou Indeterminado>"
    }}
  ],
  "resumo": {{
    "total": {n},
    "conformes": 0,
    "nao_conformes": 0,
    "indeterminados": 0,
    "na": 0,
    "percentual_conformidade": "0%"
  }},
  "observacoes_gerais": "Análise geral do modelo..."
}}
"""



def _parse_json_robusto(raw: str) -> dict:
    """Tenta parsear JSON, com fallback para JSON truncado."""
    raw_clean = re.sub(r"```json|```", "", raw).strip()
    # Tentativa 1 — JSON completo
    try:
        return json.loads(raw_clean)
    except json.JSONDecodeError:
        pass
    # Tentativa 2 — extrair bloco { ... } mais externo
    try:
        start = raw_clean.index("{")
        # Fecha o JSON truncado adicionando estrutura mínima
        partial = raw_clean[start:]
        # Conta chaves abertas para tentar fechar
        depth = 0
        last_valid = 0
        for i, c in enumerate(partial):
            if c == "{": depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    last_valid = i + 1
                    break
        if last_valid:
            return json.loads(partial[:last_valid])
    except Exception:
        pass
    # Tentativa 3 — extrair resultados parciais com regex e montar estrutura
    try:
        resultados = []
        pattern = r'\{[^{}]*"item_nbr"[^{}]*\}'
        for m in re.finditer(pattern, raw_clean, re.DOTALL):
            try:
                resultados.append(json.loads(m.group()))
            except Exception:
                pass
        if resultados:
            return {
                "modelo": "Extração parcial — resposta truncada",
                "schema_ifc": "—",
                "data_auditoria": datetime.now().strftime("%d/%m/%Y"),
                "resultados": resultados,
                "resumo": {
                    "total": len(resultados),
                    "conformes": sum(1 for r in resultados if "conforme" in r.get("status","").lower() and "não" not in r.get("status","").lower()),
                    "nao_conformes": sum(1 for r in resultados if "não" in r.get("status","").lower() or "nao" in r.get("status","").lower()),
                    "indeterminados": sum(1 for r in resultados if "indet" in r.get("status","").lower()),
                    "na": sum(1 for r in resultados if r.get("status","").lower() == "n/a"),
                    "percentual_conformidade": "parcial"
                },
                "observacoes_gerais": "⚠️ Resposta truncada pelo limite de tokens — resultados parciais exibidos."
            }
    except Exception:
        pass
    raise json.JSONDecodeError("Não foi possível parsear a resposta do modelo.", raw_clean, 0)


# Limite de saída. Nos modelos com raciocínio (Claude Sonnet/Opus 5.5, Gemini 3)
# o limite cobre raciocínio + resposta, por isso é maior que os 8192 antigos.
# Abaixo de ~21 mil tokens o SDK da Anthropic aceita chamada sem streaming.
MAX_TOKENS_SAIDA = 16000


def _anthropic_aceita_temperature(model: str) -> bool:
    """
    Só Claude Haiku 4.5 e a geração Sonnet 4.x ainda aceitam `temperature`.
    Sonnet 5.5, Opus 4.7+ (incl. Opus 5.5) e Fable recusam qualquer valor
    diferente do padrão com erro 400 ("temperature is deprecated for this model").
    """
    return model.startswith(("claude-haiku-4", "claude-sonnet-4"))


def call_anthropic(api_key: str, model: str, prompt: str, temperature: float | None = 0.0) -> dict:
    """Chama a API da Anthropic e devolve o JSON da auditoria."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    kwargs = dict(
        model=model,
        max_tokens=MAX_TOKENS_SAIDA,
        messages=[{"role": "user", "content": prompt}],
    )
    if temperature is not None and _anthropic_aceita_temperature(model):
        # SDK anthropic >= 1.0 removeu o argumento `temperature` do create().
        # Via extra_body o valor vai direto no corpo da requisição HTTP.
        kwargs["extra_body"] = {"temperature": temperature}

    msg = client.messages.create(**kwargs)

    # Nos modelos 5.5 a resposta pode começar com um bloco de raciocínio
    # ("thinking"); o JSON vem nos blocos de texto.
    raw = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    if not raw.strip():
        raise RuntimeError(
            f"O modelo {model} não devolveu texto (stop_reason={msg.stop_reason}). "
            "Tente novamente ou escolha outro modelo."
        )
    return _parse_json_robusto(raw)


def call_gemini(api_key: str, model: str, prompt: str, temperature: float | None = None) -> dict:
    """
    Chama a API do Gemini (SDK google-genai) e devolve o JSON da auditoria.

    `temperature` é ignorado: o Google recomenda manter o padrão 1.0 nos
    modelos Gemini 3 — valores menores podem causar repetição ou piora.
    A reprodutibilidade da auditoria vem das verificações em Python.
    """
    from google import genai
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "max_output_tokens": MAX_TOKENS_SAIDA,
            "response_mime_type": "application/json",
        },
    )
    raw = resp.text or ""
    if not raw.strip():
        raise RuntimeError(
            f"O modelo {model} não devolveu texto. Tente novamente ou escolha outro modelo."
        )
    return _parse_json_robusto(raw)

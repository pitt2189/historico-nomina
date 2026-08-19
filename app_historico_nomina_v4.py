import streamlit as st
import pandas as pd
import sqlite3
import os, re, shutil
from io import BytesIO
from datetime import datetime

DB_FILE = "historico_nomina.db"
BACKUP_DIR = "backups_historico"

REQUIRED = ["agrupador","concepto","clave","nombre_completo","importe","periodo"]
ALIASES = {
    "agrupador": ["agrupador","grupo","agrupación"],
    "concepto": ["concepto","conceptos"],
    "clave": ["clave","nomina","nómina","numero de nomina","número de nómina"],
    "nombre_completo": ["nombre_completo","nombre completo","nombre","trabajador"],
    "importe": ["importe","monto","cantidad","importe total"],
    "periodo": ["periodo","período","semana","period"],
}

st.set_page_config(page_title="Auditoría de Nómina V4", page_icon="📊", layout="wide")

def inject_css():
    """Capa visual (solo estética). No altera datos, cálculos ni lógica."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap');

    :root{
        --bg:#0B1220;
        --panel:#111A2E;
        --panel-2:#16213A;
        --line:#243252;
        --gold:#D4A94F;
        --gold-soft:rgba(212,169,79,.14);
        --blue:#5B9BD5;
        --text:#F2F0EA;
        --text-dim:#9AA5B8;
        --green:#34D399;
        --red:#F87171;
        --amber:#FBBF24;
    }

    html, body, [class*="css"]{ font-family:'Inter', sans-serif; }
    .stApp{
        background:
            radial-gradient(1200px 500px at 15% -10%, rgba(212,169,79,.08), transparent 60%),
            radial-gradient(900px 500px at 100% 0%, rgba(91,155,213,.08), transparent 55%),
            var(--bg);
        color: var(--text);
    }

    h1,h2,h3,h4{
        font-family:'Space Grotesk', sans-serif !important;
        color: var(--text) !important;
        letter-spacing:.2px;
    }
    h3{
        border-left:3px solid var(--gold);
        padding-left:.6rem;
        margin-top:1.6rem !important;
    }
    p, span, label, div{ color: var(--text); }
    .stCaption, [data-testid="stCaptionContainer"]{ color: var(--text-dim) !important; }

    /* ---------- HERO ---------- */
    .lipu-hero{
        background:linear-gradient(135deg, var(--panel) 0%, var(--panel-2) 100%);
        border:1px solid var(--line);
        border-radius:16px;
        padding:1.6rem 1.9rem 1.4rem 1.9rem;
        margin-bottom:1.4rem;
        position:relative;
        overflow:hidden;
    }
    .lipu-hero h1{
        font-size:1.7rem !important;
        margin:0 0 .25rem 0 !important;
    }
    .lipu-hero .lipu-sub{
        color:var(--text-dim);
        font-size:.92rem;
        margin:0;
    }
    .lipu-route{
        margin-top:.9rem;
        height:4px;
        border-radius:4px;
        background:repeating-linear-gradient(
            90deg, var(--gold) 0 22px, transparent 22px 34px
        );
        opacity:.85;
    }

    /* ---------- SIDEBAR ---------- */
    [data-testid="stSidebar"]{
        background:linear-gradient(180deg, var(--panel) 0%, var(--bg) 100%);
        border-right:1px solid var(--line);
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3{
        font-size:1.02rem !important;
        color:var(--gold) !important;
        border-left:none;
        padding-left:0;
    }

    /* ---------- METRICS (KPI cards) ---------- */
    [data-testid="stMetric"]{
        background: var(--panel);
        border:1px solid var(--line);
        border-radius:12px;
        padding:.9rem 1rem .7rem 1rem;
        box-shadow: 0 1px 0 rgba(255,255,255,.02) inset;
    }
    [data-testid="stMetricLabel"]{
        color: var(--text-dim) !important;
        font-size:.78rem !important;
        text-transform:uppercase;
        letter-spacing:.06em;
    }
    [data-testid="stMetricValue"]{
        color: var(--gold) !important;
        font-family:'Space Grotesk', sans-serif !important;
        font-size:1.55rem !important;
    }

    /* ---------- TABS ---------- */
    [data-testid="stTabs"] button[role="tab"]{
        background:var(--panel);
        border:1px solid var(--line);
        border-radius:10px 10px 0 0;
        color:var(--text-dim);
        font-weight:600;
        padding:.55rem 1rem;
        margin-right:4px;
    }
    [data-testid="stTabs"] button[aria-selected="true"]{
        background:var(--gold-soft);
        color:var(--gold) !important;
        border-color:var(--gold);
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"]{ background-color:var(--gold); }
    [data-testid="stTabs"] [data-baseweb="tab-border"]{ background-color:var(--line); }

    /* ---------- DATAFRAMES / TABLES ---------- */
    [data-testid="stDataFrame"]{
        border:1px solid var(--line);
        border-radius:10px;
        overflow:hidden;
    }
    [data-testid="stDataFrame"] div[role="columnheader"]{
        background:var(--panel-2) !important;
        color:var(--gold) !important;
        font-weight:600 !important;
        font-family:'Space Grotesk', sans-serif !important;
    }

    /* ---------- BUTTONS ---------- */
    .stButton>button, [data-testid="stDownloadButton"]>button{
        background:linear-gradient(135deg, var(--gold) 0%, #B98A34 100%);
        color:#1A1300;
        border:none;
        border-radius:8px;
        font-weight:700;
        padding:.5rem 1.1rem;
        transition:filter .15s ease;
    }
    .stButton>button:hover, [data-testid="stDownloadButton"]>button:hover{
        filter:brightness(1.08);
        color:#1A1300;
    }

    /* ---------- INPUTS ---------- */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"]>div{
        background:var(--panel) !important;
        border:1px solid var(--line) !important;
        color:var(--text) !important;
        border-radius:8px !important;
    }
    [data-testid="stFileUploaderDropzone"]{
        background:var(--panel) !important;
        border:1.5px dashed var(--line) !important;
        border-radius:12px !important;
    }

    /* ---------- ALERTS ---------- */
    [data-testid="stAlert"]{
        border-radius:10px;
        border:1px solid var(--line);
        background:var(--panel);
    }

    /* ---------- DIVIDER ---------- */
    hr{ border-color:var(--line) !important; }

    /* ---------- SECTION CARD WRAPPER ---------- */
    .lipu-section-tag{
        display:inline-block;
        background:var(--gold-soft);
        color:var(--gold);
        border:1px solid var(--gold);
        border-radius:999px;
        font-size:.72rem;
        font-weight:700;
        letter-spacing:.06em;
        text-transform:uppercase;
        padding:.15rem .65rem;
        margin-bottom:.3rem;
    }
    </style>
    """, unsafe_allow_html=True)

def clean_col(c):
    return re.sub(r"\s+", " ", str(c).strip().lower())

def period_key(period):
    m = re.search(r"(\d+)", str(period))
    return (0, int(m.group(1))) if m else (1, str(period))

def ordered_periods(df):
    return sorted(df["periodo"].dropna().astype(str).unique(), key=period_key)

def detect_columns(df):
    normalized = {clean_col(c): c for c in df.columns}
    found = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            if clean_col(alias) in normalized:
                found[target] = normalized[clean_col(alias)]
                break
    return found

def normalize(df):
    # The supplied Excel has headers in row 2 (index 1), so retry that layout.
    found = detect_columns(df)
    if len(found) < len(REQUIRED):
        for header in [1, 2, 0]:
            try:
                test = pd.read_excel(current_file_bytes, header=header)
                found = detect_columns(test)
                if len(found) == len(REQUIRED):
                    df = test
                    break
            except Exception:
                pass
    found = detect_columns(df)
    missing = [x for x in REQUIRED if x not in found]
    if missing:
        raise ValueError(
            "No pude identificar: " + ", ".join(missing) +
            ". Encabezados encontrados: " + ", ".join(map(str, df.columns))
        )
    out = pd.DataFrame({k: df[v] for k,v in found.items()})
    out["clave"] = out["clave"].astype(str).str.strip().str.replace(r"\.0$","",regex=True)
    out["nombre_completo"] = out["nombre_completo"].astype(str).str.strip()
    out["concepto"] = out["concepto"].astype(str).str.strip()
    out["periodo"] = out["periodo"].astype(str).str.strip()
    out["agrupador"] = out["agrupador"].astype(str).str.strip()
    out["importe"] = pd.to_numeric(out["importe"], errors="coerce").fillna(0)
    return out[REQUIRED]

def get_conn():
    return sqlite3.connect(DB_FILE)

def init_db():
    c = get_conn()
    c.execute("""
    CREATE TABLE IF NOT EXISTS movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agrupador TEXT,
        concepto TEXT,
        clave TEXT,
        nombre_completo TEXT,
        importe REAL,
        periodo TEXT,
        UNIQUE(agrupador, concepto, clave, nombre_completo, importe, periodo)
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS config (
        clave TEXT PRIMARY KEY,
        valor TEXT
    )""")
    c.commit(); c.close()

def get_history():
    c = get_conn()
    df = pd.read_sql_query(
        "SELECT agrupador, concepto, clave, nombre_completo, importe, periodo FROM movimientos", c
    )
    c.close()
    return df

def add_history(df):
    c = get_conn()
    inserted = dup = 0
    for r in df.itertuples(index=False, name=None):
        cur = c.execute("""
        INSERT OR IGNORE INTO movimientos
        (agrupador, concepto, clave, nombre_completo, importe, periodo)
        VALUES (?,?,?,?,?,?)
        """, r)
        if cur.rowcount: inserted += 1
        else: dup += 1
    c.commit(); c.close()
    return inserted, dup

def make_backup():
    if not os.path.exists(DB_FILE):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    name = datetime.now().strftime("historico_%Y%m%d_%H%M%S.db")
    path = os.path.join(BACKUP_DIR, name)
    shutil.copy2(DB_FILE, path)
    return path

def compare_periods(df, previous, current):
    p = df[df.periodo.isin([previous,current])]
    if p.empty: return pd.DataFrame()
    piv = p.pivot_table(
        index=["clave","nombre_completo","concepto"],
        columns="periodo", values="importe", aggfunc="sum", fill_value=0
    ).reset_index()
    for col in [previous,current]:
        if col not in piv.columns: piv[col] = 0.0
    piv["diferencia"] = piv[current] - piv[previous]
    piv["tipo"] = piv["diferencia"].apply(
        lambda x: "Aumento" if x > 0 else ("Disminución" if x < 0 else "Sin cambio")
    )
    return piv

def affected_workers(df, previous, current):
    comp = compare_periods(df, previous, current)
    if comp.empty: return pd.DataFrame()
    out = comp.groupby(["clave","nombre_completo"], as_index=False).agg(
        importe_anterior=(previous,"sum"),
        importe_actual=(current,"sum"),
        diferencia=("diferencia","sum"),
        conceptos_afectados=("tipo", lambda s: (s != "Sin cambio").sum())
    )
    out["perdida"] = out.diferencia.apply(lambda x: -x if x < 0 else 0)
    out["estado"] = out.diferencia.apply(
        lambda x: "🔴 Disminuyó" if x < 0 else ("🔵 Aumentó" if x > 0 else "🟢 Sin cambio")
    )
    return out.sort_values("diferencia")

def get_alerts(df, previous, current, loss_threshold, pct_threshold):
    comp = compare_periods(df, previous, current)
    if comp.empty: return {}
    worker = affected_workers(df, previous, current)
    decreases = worker[worker.diferencia < 0].copy()
    increases = worker[worker.diferencia > 0].copy()

    detail = comp[comp.diferencia != 0].copy()
    detail["pct"] = detail.apply(
        lambda r: ((r["diferencia"] / r[previous]) * 100) if r[previous] else None, axis=1
    )

    # Concepts missing in current period after existing in previous.
    missing_concepts = detail[
        (detail[previous] != 0) & (detail[current] == 0)
    ].copy()

    # New concepts in current.
    new_concepts = detail[
        (detail[previous] == 0) & (detail[current] != 0)
    ].copy()

    big_losses = decreases[
        decreases["perdida"] >= loss_threshold
    ].copy()

    return {
        "workers": worker,
        "decreases": decreases,
        "increases": increases,
        "big_losses": big_losses,
        "missing_concepts": missing_concepts,
        "new_concepts": new_concepts,
        "detail": detail,
    }

def worker_explanation(df, clave, previous, current):
    comp = compare_periods(df[df.clave == clave], previous, current)
    if comp.empty: return None
    row = comp.groupby("concepto", as_index=False)[[previous,current,"diferencia"]].sum()
    row["resultado"] = row.diferencia.apply(
        lambda x: "Aumentó" if x > 0 else ("Disminuyó" if x < 0 else "Sin cambio")
    )
    return row.sort_values("diferencia")

def worker_history(df, clave):
    return df[df.clave == clave].copy()

def set_config(key, value):
    c=get_conn()
    c.execute("INSERT OR REPLACE INTO config(clave,valor) VALUES(?,?)",(key,str(value)))
    c.commit(); c.close()

def get_config(key, default):
    c=get_conn()
    r=c.execute("SELECT valor FROM config WHERE clave=?",(key,)).fetchone()
    c.close()
    return r[0] if r else default

init_db()
inject_css()

st.markdown("""
<div class="lipu-hero">
    <h1>📊 Auditoría de Nómina V4</h1>
    <p class="lipu-sub">Histórico acumulativo · Auditoría automática · Comparativos · Alertas · Altas/Bajas · Rotación</p>
    <div class="lipu-route"></div>
</div>
""", unsafe_allow_html=True)

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("📥 Cargar Excel")
    uploaded = st.file_uploader("Selecciona el Excel de la semana", type=["xlsx","xls"])

    if uploaded is not None:
        try:
            current_file_bytes = uploaded.getvalue()
            incoming = normalize(pd.read_excel(BytesIO(current_file_bytes), header=0))
            periods_in_file = ", ".join(sorted(incoming.periodo.unique(), key=period_key))
            st.success(f"Periodo detectado: {periods_in_file}")
            st.caption(f"{len(incoming):,} registros")
            if st.button("➕ Agregar al histórico", type="primary"):
                # Backup before changing the database.
                if os.path.exists(DB_FILE):
                    make_backup()
                ins, dup = add_history(incoming)
                st.success(f"Agregados: {ins:,}")
                st.info(f"Duplicados ignorados: {dup:,}")
                st.rerun()
        except Exception as e:
            st.error(f"Error al leer el Excel: {e}")

    st.divider()
    st.header("⚙️ Reglas de alerta")
    loss_threshold = st.number_input(
        "Alertar pérdida desde $", min_value=0.0,
        value=float(get_config("loss_threshold","100")), step=50.0
    )
    pct_threshold = st.number_input(
        "Alertar reducción desde %", min_value=0.0,
        value=float(get_config("pct_threshold","20")), step=5.0
    )
    if st.button("Guardar reglas"):
        set_config("loss_threshold", loss_threshold)
        set_config("pct_threshold", pct_threshold)
        st.success("Reglas guardadas.")

    st.divider()
    st.header("💾 Seguridad")
    if st.button("Crear respaldo ahora"):
        backup = make_backup()
        st.success(f"Respaldo: {backup}") if backup else st.info("No hay base para respaldar.")

hist = get_history()

if hist.empty:
    st.info("Carga el primer Excel desde el panel izquierdo para iniciar el histórico.")
    st.stop()

periods = ordered_periods(hist)

# ---------- DASHBOARD ----------
st.markdown('<span class="lipu-section-tag">Panel gerencial</span>', unsafe_allow_html=True)
st.subheader("📌 Centro de control")
latest = periods[-1]
previous = periods[-2] if len(periods) >= 2 else None

total_workers = hist[hist.periodo == latest].clave.nunique()
total_amount = hist[hist.periodo == latest].importe.sum()

if previous:
    alerts = get_alerts(hist, previous, latest, loss_threshold, pct_threshold)
    dec = alerts["decreases"]
    inc = alerts["increases"]
    loss = dec.perdida.sum()
    affected_count = len(alerts["workers"])
else:
    alerts = {}
    dec = pd.DataFrame(); inc = pd.DataFrame(); loss = 0; affected_count = 0

a,b,c,d,e = st.columns(5)
a.metric("Trabajadores actuales", f"{total_workers:,}")
b.metric("Importe actual", f"${total_amount:,.2f}")
c.metric("Afectados", f"{affected_count:,}")
d.metric("Disminuyeron", f"{len(dec):,}")
e.metric("Pérdida detectada", f"${loss:,.2f}")

if previous:
    st.info(f"Comparación automática: **{previous} → {latest}**")

# ---------- TABS ----------
t1,t2,t3,t4,t5,t6,t7 = st.tabs([
    "🔎 Buscar nómina",
    "🔄 Cambios",
    "🚨 Centro de alertas",
    "👥 Altas y bajas",
    "📈 Rotación",
    "📊 Histórico",
    "🗃️ Base"
])

# SEARCH
with t1:
    st.markdown('<span class="lipu-section-tag">Consulta individual</span>', unsafe_allow_html=True)
    st.subheader("Buscar por número de nómina")
    clave = st.text_input("Número de nómina", placeholder="Ej. 14100713").strip()
    if clave:
        person = worker_history(hist, clave)
        if person.empty:
            st.warning("No se encontró esa nómina.")
        else:
            name = person.nombre_completo.mode().iloc[0] if not person.nombre_completo.mode().empty else person.nombre_completo.iloc[0]
            a,b,c,d = st.columns(4)
            a.metric("Nómina", clave); b.metric("Trabajador", name)
            c.metric("Periodos", person.periodo.nunique()); d.metric("Total histórico", f"${person.importe.sum():,.2f}")

            concept = st.selectbox("Concepto", ["Todos"] + sorted(person.concepto.unique()), key="search_concept")
            detail = person if concept == "Todos" else person[person.concepto == concept]
            pivot = detail.pivot_table(index="concepto", columns="periodo", values="importe", aggfunc="sum", fill_value=0)
            if not pivot.empty:
                pivot["TOTAL"] = pivot.sum(axis=1)
            st.dataframe(pivot.style.format("${:,.2f}"), use_container_width=True)

            if concept != "Todos":
                st.line_chart(detail.groupby("periodo")["importe"].sum())

            st.subheader("📋 Detalle")
            st.dataframe(detail.sort_values(["periodo","concepto"]).style.format({"importe":"${:,.2f}"}), use_container_width=True)

            if previous and latest:
                st.subheader(f"🧾 Explicación {previous} → {latest}")
                explanation = worker_explanation(hist, clave, previous, latest)
                if explanation is not None:
                    st.dataframe(
                        explanation.style.format({previous:"${:,.2f}",latest:"${:,.2f}","diferencia":"${:,.2f}"}),
                        use_container_width=True
                    )
                    st.download_button(
                        "⬇️ Descargar historial de la nómina",
                        detail.to_csv(index=False).encode("utf-8-sig"),
                        f"nomina_{clave}.csv", "text/csv", key="dl_person"
                    )

# CHANGES
with t2:
    st.markdown('<span class="lipu-section-tag">Trazabilidad</span>', unsafe_allow_html=True)
    st.subheader("🔄 Cambios del trabajador")
    clave2 = st.text_input("Número de nómina", placeholder="Ej. 14100713", key="change_key").strip()
    if clave2:
        person = worker_history(hist, clave2)
        if person.empty:
            st.warning("No se encontró esa nómina.")
        else:
            st.subheader("💵 Evolución semanal")
            weekly = person.groupby("periodo", as_index=False).importe.sum()
            weekly["orden"] = weekly.periodo.map(period_key)
            weekly = weekly.sort_values("orden").drop(columns="orden")
            st.dataframe(weekly.style.format({"importe":"${:,.2f}"}), use_container_width=True)
            st.line_chart(weekly.set_index("periodo")["importe"])

            changes=[]
            for concept, g in person.groupby("concepto"):
                x=g.groupby("periodo",as_index=False).importe.sum()
                x["orden"]=x.periodo.map(period_key); x=x.sort_values("orden")
                vals=x[["periodo","importe"]].to_dict("records")
                if vals:
                    changes.append(["Inicio de concepto",concept,vals[0]["periodo"],0,vals[0]["importe"],vals[0]["importe"]])
                for p,curr in zip(vals,vals[1:]):
                    delta=curr["importe"]-p["importe"]
                    if delta:
                        changes.append(["Aumento" if delta>0 else "Disminución",concept,curr["periodo"],p["importe"],curr["importe"],delta])
            ch=pd.DataFrame(changes,columns=["Tipo","Concepto","Periodo","Anterior","Nuevo","Cambio"])
            if not ch.empty:
                st.dataframe(ch.style.format({"Anterior":"${:,.2f}","Nuevo":"${:,.2f}","Cambio":"${:,.2f}"}),use_container_width=True)
                st.download_button("⬇️ Descargar cambios",ch.to_csv(index=False).encode("utf-8-sig"),f"cambios_{clave2}.csv","text/csv",key="dl_changes")

# ALERT CENTER
with t3:
    st.markdown('<span class="lipu-section-tag">Monitoreo</span>', unsafe_allow_html=True)
    st.subheader("🚨 Centro de alertas")
    if not previous:
        st.info("Se requieren al menos dos periodos.")
    else:
        st.write(f"**{previous} → {latest}**")
        big = alerts["big_losses"]
        missing = alerts["missing_concepts"]
        newc = alerts["new_concepts"]

        x1,x2,x3,x4 = st.columns(4)
        x1.metric("🔴 Pérdidas sobre umbral", len(big))
        x2.metric("🟠 Conceptos desaparecidos", len(missing))
        x3.metric("🔵 Conceptos nuevos", len(newc))
        x4.metric("📉 Pérdida total", f"${loss:,.2f}")

        if not big.empty:
            st.subheader("🔴 Trabajadores con pérdida relevante")
            st.dataframe(big[["clave","nombre_completo","importe_anterior","importe_actual","perdida","estado"]]
                         .style.format({"importe_anterior":"${:,.2f}","importe_actual":"${:,.2f}","perdida":"${:,.2f}"}), use_container_width=True)

        if not missing.empty:
            st.subheader("🟠 Conceptos que desaparecieron")
            st.dataframe(missing[["clave","nombre_completo","concepto",previous,latest,"diferencia"]]
                         .style.format({previous:"${:,.2f}",latest:"${:,.2f}","diferencia":"${:,.2f}"}), use_container_width=True)

        if not newc.empty:
            st.subheader("🔵 Conceptos nuevos")
            st.dataframe(newc[["clave","nombre_completo","concepto",previous,latest,"diferencia"]]
                         .style.format({previous:"${:,.2f}",latest:"${:,.2f}","diferencia":"${:,.2f}"}), use_container_width=True)

        if not big.empty:
            st.bar_chart(big.set_index("nombre_completo")["perdida"].head(20))

# HIGH/LOW / NEW / RETURNING
with t4:
    st.markdown('<span class="lipu-section-tag">Movimientos de plantilla</span>', unsafe_allow_html=True)
    st.subheader("👥 Altas, bajas y movimientos")
    if len(periods)<2:
        st.info("Se requieren al menos dos periodos.")
    else:
        prev_set=set(hist[hist.periodo==previous].clave)
        curr_set=set(hist[hist.periodo==latest].clave)
        altas=sorted(curr_set-prev_set)
        bajas=sorted(prev_set-curr_set)
        regresos=[]

        older=set(hist[hist.periodo.isin(periods[:-2])].clave) if len(periods)>2 else set()
        regresos=sorted((curr_set-prev_set)&older)

        q1,q2,q3=st.columns(3)
        q1.metric("🟢 Posibles altas",len(altas))
        q2.metric("🔴 Posibles bajas",len(bajas))
        q3.metric("🔵 Regresos",len(regresos))

        if altas:
            st.subheader("🟢 Posibles altas")
            st.dataframe(hist[hist.clave.isin(altas)&(hist.periodo==latest)][["clave","nombre_completo","agrupador"]].drop_duplicates(),use_container_width=True)
        if bajas:
            st.subheader("🔴 Posibles bajas")
            st.dataframe(hist[hist.clave.isin(bajas)&(hist.periodo==previous)][["clave","nombre_completo","agrupador"]].drop_duplicates(),use_container_width=True)
        if regresos:
            st.subheader("🔵 Trabajadores que regresaron")
            st.dataframe(hist[hist.clave.isin(regresos)&(hist.periodo==latest)][["clave","nombre_completo","agrupador"]].drop_duplicates(),use_container_width=True)

        st.warning("Las altas/bajas son 'posibles' porque se basan en presencia/ausencia en los periodos cargados.")

# ROTATION
with t5:
    st.markdown('<span class="lipu-section-tag">Indicadores de personal</span>', unsafe_allow_html=True)
    st.subheader("📈 Rotación y antigüedad")
    rows=[]
    for i,p in enumerate(periods):
        curr=set(hist[hist.periodo==p].clave)
        if i==0:
            alta=len(curr); baja=0
        else:
            prev_set=set(hist[hist.periodo==periods[i-1]].clave)
            alta=len(curr-prev_set); baja=len(prev_set-curr)
        avg=((len(curr)+(len(set(hist[hist.periodo==periods[i-1]].clave))) if i>0 else len(curr))/2)
        rot=(baja/avg*100) if avg else 0
        rows.append([p,len(curr),alta,baja,rot])
    rot_df=pd.DataFrame(rows,columns=["Periodo","Trabajadores","Altas","Bajas","Rotación %"])
    st.dataframe(rot_df.style.format({"Rotación %":"{:.2f}%"}),use_container_width=True)
    st.subheader("Rotación por periodo")
    st.line_chart(rot_df.set_index("Periodo")["Rotación %"])

    st.subheader("Antigüedad")
    first_period=hist.groupby("clave")["periodo"].agg(lambda s:min(s,key=period_key)).reset_index(name="primer_periodo")
    first_period["orden"]=first_period.primer_periodo.map(period_key)
    first_period["antiguedad_periodos"]=len(periods)-first_period["orden"].map(lambda x:x[1])+first_period["orden"].map(lambda x:x[1]) - first_period["orden"].map(lambda x:x[1])
    # More robust: index in ordered period list.
    idx={p:i for i,p in enumerate(periods)}
    first_period["antiguedad_periodos"]=first_period.primer_periodo.map(lambda p: len(periods)-idx.get(p, len(periods)-1))
    bins=[0,4,8,13,26,52,9999]
    labels=["0-4","5-8","9-13","14-26","27-52","53+"]
    first_period["rango"]=pd.cut(first_period.antiguedad_periodos,bins=bins,labels=labels,include_lowest=True)
    st.dataframe(first_period.groupby("rango",observed=False).size().reset_index(name="trabajadores"),use_container_width=True)

# HISTORICAL
with t6:
    st.markdown('<span class="lipu-section-tag">Serie histórica</span>', unsafe_allow_html=True)
    st.subheader("📊 Histórico")
    summary=hist.groupby("periodo").agg(trabajadores=("clave","nunique"),registros=("clave","size"),importe_total=("importe","sum")).reset_index()
    summary["orden"]=summary.periodo.map(period_key); summary=summary.sort_values("orden").drop(columns="orden")
    st.dataframe(summary.style.format({"importe_total":"${:,.2f}"}),use_container_width=True)
    st.bar_chart(summary.set_index("periodo")["importe_total"])

    st.subheader("🔁 Comparativo")
    if len(periods)>=2:
        p1,p2=st.columns(2)
        aa=p1.selectbox("Anterior",periods[:-1],index=len(periods[:-1])-1,key="hist_prev")
        bb=p2.selectbox("Actual",periods[1:],index=len(periods[1:])-1,key="hist_curr")
        comp=compare_periods(hist,aa,bb)
        st.metric("Variación total",f"${comp[bb].sum()-comp[aa].sum():,.2f}")
        st.dataframe(comp[["clave","nombre_completo","concepto",aa,bb,"diferencia","tipo"]]
                     .style.format({aa:"${:,.2f}",bb:"${:,.2f}","diferencia":"${:,.2f}"}),use_container_width=True)

# DATABASE
with t7:
    st.markdown('<span class="lipu-section-tag">Base de datos</span>', unsafe_allow_html=True)
    st.subheader("🗃️ Base histórica")
    st.dataframe(hist.sort_values(["periodo","clave","concepto"]),use_container_width=True)
    buf=BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as writer:
        hist.to_excel(writer,index=False,sheet_name="Historico")
    buf.seek(0)
    st.download_button("⬇️ Descargar histórico Excel",buf,"historico_nomina.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",key="dl_hist")

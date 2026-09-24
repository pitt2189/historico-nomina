import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
import re

DB_FILE = "historico_nomina.db"

st.set_page_config(page_title="Histórico de Nómina", page_icon="📊", layout="wide")

def check_password():
    """Muestra un campo de contraseña y detiene la app si no coincide con st.secrets['app_password']."""

    def password_entered():
        if st.session_state.get("password_input") == st.secrets.get("app_password"):
            st.session_state["password_correct"] = True
            del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct"):
        return True

    st.text_input(
        "🔒 Contraseña de acceso",
        type="password",
        on_change=password_entered,
        key="password_input",
    )
    if st.session_state.get("password_correct") is False:
        st.error("Contraseña incorrecta.")
    return False

if not check_password():
    st.stop()

ALIASES = {
    "agrupador": ["agrupador", "grupo", "agrupación"],
    "concepto": ["concepto", "conceptos"],
    "clave": ["clave", "nomina", "nómina", "numero de nomina", "número de nómina"],
    "nombre_completo": ["nombre_completo", "nombre completo", "nombre", "trabajador"],
    "importe": ["importe", "monto", "cantidad", "importe total"],
    "periodo": ["periodo", "período", "semana", "period"],
}

def clean_col(c):
    return re.sub(r"\s+", " ", str(c).strip().lower())

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
    found = detect_columns(df)
    missing = [x for x in ALIASES if x not in found]
    if missing:
        raise ValueError(
            "No pude identificar estas columnas: " + ", ".join(missing) +
            ". Columnas encontradas: " + ", ".join(map(str, df.columns))
        )
    out = pd.DataFrame()
    for target, source in found.items():
        out[target] = df[source]
    out["clave"] = out["clave"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    out["nombre_completo"] = out["nombre_completo"].astype(str).str.strip()
    out["concepto"] = out["concepto"].astype(str).str.strip()
    out["periodo"] = out["periodo"].astype(str).str.strip()
    out["agrupador"] = out["agrupador"].astype(str).str.strip()
    out["importe"] = pd.to_numeric(out["importe"], errors="coerce").fillna(0)
    return out[["agrupador","concepto","clave","nombre_completo","importe","periodo"]]

def conn():
    return sqlite3.connect(DB_FILE)

def init_db():
    c = conn()
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
    )
    """)
    c.commit(); c.close()

def add_history(df):
    c = conn()
    inserted = duplicated = 0
    for r in df.itertuples(index=False, name=None):
        cur = c.execute("""
        INSERT OR IGNORE INTO movimientos
        (agrupador, concepto, clave, nombre_completo, importe, periodo)
        VALUES (?,?,?,?,?,?)
        """, r)
        if cur.rowcount: inserted += 1
        else: duplicated += 1
    c.commit(); c.close()
    return inserted, duplicated


def period_key(period):
    m = re.search(r'(\d+)', str(period))
    return (0, int(m.group(1))) if m else (1, str(period))

def ordered_periods(df):
    return sorted(df["periodo"].dropna().astype(str).unique(), key=period_key)

def compare_periods(df, previous, current):
    p = df[df["periodo"].isin([previous, current])].copy()
    if p.empty:
        return pd.DataFrame()
    piv = p.pivot_table(
        index=["clave", "nombre_completo", "concepto"],
        columns="periodo", values="importe", aggfunc="sum", fill_value=0
    ).reset_index()
    for col in (previous, current):
        if col not in piv.columns:
            piv[col] = 0.0
    piv["diferencia"] = piv[current] - piv[previous]
    piv["afectado"] = piv["diferencia"] != 0
    piv["tipo"] = piv["diferencia"].apply(
        lambda x: "Aumento" if x > 0 else ("Disminución" if x < 0 else "Sin cambio")
    )
    return piv

def affected_workers(df, previous, current):
    comp = compare_periods(df, previous, current)
    if comp.empty:
        return pd.DataFrame()
    out = comp.groupby(["clave", "nombre_completo"], as_index=False).agg(
        importe_anterior=(previous, "sum"),
        importe_actual=(current, "sum"),
        diferencia=("diferencia", "sum"),
        conceptos_afectados=("afectado", "sum")
    )
    out["tipo"] = out["diferencia"].apply(
        lambda x: "Aumentó" if x > 0 else ("Disminuyó" if x < 0 else "Sin cambio")
    )
    out["perdida"] = out["diferencia"].apply(lambda x: -x if x < 0 else 0)
    return out.sort_values("diferencia")

def worker_change_detail(df, previous, current):
    comp = compare_periods(df, previous, current)
    return comp[comp["afectado"]].sort_values(["clave", "diferencia"]) if not comp.empty else comp

def make_backup():
    if os.path.exists(DB_FILE):
        os.makedirs("backups_historico", exist_ok=True)
        name = datetime.now().strftime("historico_%Y%m%d_%H%M%S.db")
        path = os.path.join("backups_historico", name)
        shutil.copy2(DB_FILE, path)
        return path
    return None

def get_history():
    c = conn()
    d = pd.read_sql_query("SELECT agrupador, concepto, clave, nombre_completo, importe, periodo FROM movimientos", c)
    c.close()
    return d

init_db()

st.title("📊 Histórico de Nómina")
st.caption("Base de Excel actualizable + histórico acumulativo + consulta por número de nómina")

with st.sidebar:
    st.header("💾 Respaldo")
    if st.button("Crear respaldo ahora"):
        backup = make_backup()
        if backup:
            st.success(f"Respaldo creado: {backup}")
        else:
            st.info("Aún no existe una base histórica para respaldar.")

    st.header("📥 Actualizar histórico")
    file = st.file_uploader("Carga el Excel de la semana", type=["xlsx","xls"])
    if file:
        try:
            incoming = normalize(pd.read_excel(file))
            periods = ", ".join(sorted(incoming.periodo.unique()))
            st.success(f"Periodo detectado: {periods}")
            st.caption(f"{len(incoming):,} registros")
            if st.button("➕ Agregar al histórico", type="primary"):
                ins, dup = add_history(incoming)
                st.success(f"Agregados: {ins:,}")
                st.info(f"Duplicados ignorados: {dup:,}")
                st.rerun()
        except Exception as e:
            st.error(str(e))

hist = get_history()
if hist.empty:
    st.info("Carga tu primer Excel desde el panel izquierdo.")
    st.stop()

c1,c2,c3,c4 = st.columns(4)
c1.metric("Registros", f"{len(hist):,}")
c2.metric("Trabajadores", f"{hist.clave.nunique():,}")
c3.metric("Periodos", f"{hist.periodo.nunique():,}")
c4.metric("Conceptos", f"{hist.concepto.nunique():,}")

t1,t2,t3,t4,t5 = st.tabs(["🔎 Buscar nómina","🔄 Cambios del trabajador","🚨 Afectados","📈 Histórico","🗃️ Base"])

with t1:
    st.subheader("Buscar por número de nómina")
    clave = st.text_input("Número de nómina / clave", placeholder="Ej. 12345").strip()

    if clave:
        persona = hist[hist.clave == clave].copy()
        if persona.empty:
            st.warning("No se encontró esa nómina.")
        else:
            nombre = persona.nombre_completo.mode().iloc[0] if not persona.nombre_completo.mode().empty else persona.nombre_completo.iloc[0]
            a,b,c,d = st.columns(4)
            a.metric("Nómina", clave)
            b.metric("Trabajador", nombre)
            c.metric("Periodos", persona.periodo.nunique())
            d.metric("Total histórico", f"${persona.importe.sum():,.2f}")

            concepto = st.selectbox(
                "Concepto",
                ["Todos"] + sorted(persona.concepto.unique().tolist())
            )
            detalle = persona if concepto == "Todos" else persona[persona.concepto == concepto]

            pivot = detalle.pivot_table(
                index="concepto", columns="periodo", values="importe",
                aggfunc="sum", fill_value=0
            )
            pivot["TOTAL"] = pivot.sum(axis=1)

            st.subheader("💰 Lo que cobró por concepto en cada periodo")
            st.dataframe(pivot.style.format("${:,.2f}"), use_container_width=True)

            if concepto != "Todos":
                serie = detalle.groupby("periodo")["importe"].sum()
                st.subheader(f"📈 Evolución: {concepto}")
                st.line_chart(serie)

            st.subheader("📋 Detalle de movimientos")
            st.dataframe(
                detalle.sort_values(["periodo","concepto"]).style.format({"importe":"${:,.2f}"}),
                use_container_width=True
            )

            st.download_button(
                "⬇️ Descargar consulta",
                detalle.to_csv(index=False).encode("utf-8-sig"),
                f"nomina_{clave}.csv",
                "text/csv"
            )

with t3:
    st.subheader("🚨 Detector de trabajadores afectados")
    st.caption("Compara dos periodos y detecta quién tuvo una disminución o aumento y qué concepto lo provocó.")

    periods = ordered_periods(hist)
    if len(periods) < 2:
        st.info("Necesitas al menos dos periodos históricos para comparar.")
    else:
        ca, cb = st.columns(2)
        previous = ca.selectbox("Periodo anterior", periods[:-1], index=len(periods[:-1])-1, key="affected_previous")
        current = cb.selectbox("Periodo actual", periods[1:], index=len(periods[1:])-1, key="affected_current")

        if previous == current:
            st.warning("Selecciona dos periodos diferentes.")
        else:
            affected = affected_workers(hist, previous, current)
            decreases = affected[affected["diferencia"] < 0].copy() if not affected.empty else pd.DataFrame()
            increases = affected[affected["diferencia"] > 0].copy() if not affected.empty else pd.DataFrame()
            total_loss = decreases["perdida"].sum() if not decreases.empty else 0

            a,b,c,d = st.columns(4)
            a.metric("Trabajadores afectados", f"{len(affected):,}")
            b.metric("Disminuyeron", f"{len(decreases):,}")
            c.metric("Aumentaron", f"{len(increases):,}")
            d.metric("Dinero dejado de percibir", f"${total_loss:,.2f}")

            st.subheader(f"📉 Afectados económicamente: {previous} → {current}")
            if decreases.empty:
                st.success("Ningún trabajador tuvo disminución.")
            else:
                show = decreases[["clave","nombre_completo","importe_anterior","importe_actual","diferencia","conceptos_afectados"]].copy()
                show.columns = ["Nómina","Trabajador",previous,current,"Diferencia","Conceptos afectados"]
                st.dataframe(
                    show.style.format({previous:"${:,.2f}", current:"${:,.2f}", "Diferencia":"${:,.2f}"}),
                    use_container_width=True
                )

                st.subheader("🔎 Conceptos que provocaron la afectación")
                detail = worker_change_detail(hist, previous, current)
                detail = detail[detail["diferencia"] < 0][
                    ["clave","nombre_completo","concepto",previous,current,"diferencia","tipo"]
                ]
                st.dataframe(
                    detail.style.format({previous:"${:,.2f}", current:"${:,.2f}", "diferencia":"${:,.2f}"}),
                    use_container_width=True
                )
                st.download_button(
                    "⬇️ Descargar detalle de afectados",
                    detail.to_csv(index=False).encode("utf-8-sig"),
                    f"afectados_{previous}_vs_{current}.csv",
                    "text/csv",
                    key="download_affected"
                )

                st.subheader("📊 Mayores pérdidas")
                impact = decreases.set_index("nombre_completo")["perdida"].sort_values(ascending=False).head(20)
                st.bar_chart(impact)

with t4:
    st.subheader("Resumen por periodo")
    resumen = hist.groupby("periodo").agg(
        trabajadores=("clave","nunique"),
        registros=("clave","size"),
        importe_total=("importe","sum")
    ).reset_index()
    st.dataframe(resumen.style.format({"importe_total":"${:,.2f}"}), use_container_width=True)
    st.bar_chart(resumen.set_index("periodo")["importe_total"])

with t5:
    st.subheader("Base histórica completa")
    st.dataframe(hist.sort_values(["periodo","clave","concepto"]), use_container_width=True)

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        hist.to_excel(writer, index=False, sheet_name="Historico")
    buf.seek(0)
    st.download_button(
        "⬇️ Descargar histórico completo en Excel",
        buf,
        "historico_nomina.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

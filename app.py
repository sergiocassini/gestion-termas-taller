import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime

# Configuración de página adaptable a teléfonos
st.set_page_config(page_title="Gestión Termas & Taller", page_icon="🏪", layout="wide")

# --- CONTROL DE ACCESO CON PIN / CONTRASEÑA ---
PIN_CORRECTO = "2017"  # 👈 CAMBIÁ ESTA CLAVE POR LA QUE VOS QUIERAS

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

def verificar_pin():
    if st.session_state["input_pin"] == PIN_CORRECTO:
        st.session_state["autenticado"] = True
    else:
        st.error("🔒 PIN / Contraseña incorrecta")

if not st.session_state["autenticado"]:
    st.title("🔒 Acceso Restringido")
    st.subheader("Control de Negocio: Termas & Taller")
    
    st.text_input("Ingresá el PIN de acceso:", type="password", key="input_pin", on_change=verificar_pin)
    st.button("Ingresar", on_click=verificar_pin, use_container_width=True)
    st.stop()  # Detiene la ejecución del resto del programa si no ingresó el PIN correcto

# --- CONEXIÓN A SUPABASE ---
def get_connection():
    return psycopg2.connect(
        host=st.secrets["postgres"]["host"],
        database=st.secrets["postgres"]["database"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"],
        port=st.secrets["postgres"]["port"]
    )

def consulta(query, params=(), fetch=True):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    res = cursor.fetchall() if fetch else None
    conn.close()
    return res

# --- INICIALIZACIÓN DE TABLAS ---
def init_db():
    consulta("""
        CREATE TABLE IF NOT EXISTS productos (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(255) UNIQUE NOT NULL,
            categoria VARCHAR(100) DEFAULT 'General',
            precio NUMERIC DEFAULT 0,
            stock INT DEFAULT 0,
            stock_minimo INT DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS gachapon_premios (
            id SERIAL PRIMARY KEY,
            numero VARCHAR(50),
            nombre VARCHAR(255) UNIQUE NOT NULL,
            impresos INT DEFAULT 0,
            stock_deposito INT DEFAULT 0,
            en_maquina INT DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS ventas (
            id SERIAL PRIMARY KEY,
            origen VARCHAR(50) DEFAULT 'TERMAS',
            item_tipo VARCHAR(50) NOT NULL,
            item_nombre VARCHAR(255) NOT NULL,
            cantidad INT NOT NULL,
            precio_unitario NUMERIC NOT NULL,
            subtotal NUMERIC NOT NULL,
            fecha TIMESTAMP NOT NULL,
            cerrado INT DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS config (
            clave VARCHAR(100) PRIMARY KEY,
            valor VARCHAR(255) NOT NULL
        );
    """, fetch=False)

try:
    init_db()
except Exception as e:
    st.error(f"Conectando con la base de datos... ({e})")

# --- INTERFAZ PRINCIPAL ---
st.title("🏪 Control Termas & Taller")

tab_termas, tab_taller, tab_stock, tab_gachapon, tab_caja = st.tabs([
    "🛒 Ventas Termas", 
    "🛠️ Ventas Taller", 
    "📦 Inventario", 
    "🎰 Gachapon", 
    "💰 Caja"
])

# -----------------------------------------------------------------------------
# 1. VENTAS TERMAS (MOSTRADOR)
# -----------------------------------------------------------------------------
with tab_termas:
    st.header("🛒 Ventas Mostrador Termas")

    # Venta de Fichas Gachapon
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        cant_fichas = st.number_input("Cantidad Fichas Gachapon", min_value=1, value=1, key="f_termas")
    with col_f2:
        st.write("")
        if st.button("🎟️ Vender Fichas Gachapon", use_container_width=True):
            res_p = consulta("SELECT valor FROM config WHERE clave='precio_ficha_gachapon'")
            p_unit = float(res_p[0][0]) if res_p else 2000.0
            subt = cant_fichas * p_unit
            consulta("""
                INSERT INTO ventas (origen, item_tipo, item_nombre, cantidad, precio_unitario, subtotal, fecha) 
                VALUES ('TERMAS', 'FICHA_GACHAPON', 'Ficha Gachapon', %s, %s, %s, %s)
            """, (cant_fichas, p_unit, subt, datetime.now()), fetch=False)
            st.success(f"Venta de {cant_fichas} ficha/s registrada (${subt:,.0f})")

    st.divider()

    # Venta de Productos
    prods = consulta("SELECT nombre, precio, stock FROM productos ORDER BY nombre ASC")
    lista_prod = [p[0] for p in prods] if prods else []

    if lista_prod:
        prod_sel = st.selectbox("Seleccionar Producto", lista_prod, key="p_termas")
        cant_p = st.number_input("Cantidad Producto", min_value=1, value=1, key="c_termas")
        
        info_p = [p for p in prods if p[0] == prod_sel][0]
        st.caption(f"Precio: ${info_p[1]:,.0f} | Stock disponible: {info_p[2]} un.")

        if st.button("✔️ Registrar Venta en Termas", use_container_width=True):
            if cant_p > info_p[2]:
                st.error("No hay suficiente stock disponible.")
            else:
                subt = cant_p * float(info_p[1])
                consulta("UPDATE productos SET stock = stock - %s WHERE nombre = %s", (cant_p, prod_sel), fetch=False)
                consulta("""
                    INSERT INTO ventas (origen, item_tipo, item_nombre, cantidad, precio_unitario, subtotal, fecha) 
                    VALUES ('TERMAS', 'PRODUCTO', %s, %s, %s, %s, %s)
                """, (prod_sel, cant_p, info_p[1], subt, datetime.now()), fetch=False)
                st.success(f"Venta registrada: {prod_sel} x{cant_p} (${subt:,.0f})")
                st.rerun()

# -----------------------------------------------------------------------------
# 2. VENTAS TALLER
# -----------------------------------------------------------------------------
with tab_taller:
    st.header("🛠️ Ventas Taller / Envíos Externos")
    st.info("Registrá ventas fuera del local (encargos a pedido, impresiones 3D, envíos).")

    if lista_prod:
        prod_taller = st.selectbox("Producto o Encargo", lista_prod, key="p_taller")
        cant_taller = st.number_input("Cantidad", min_value=1, value=1, key="c_taller")
        
        info_t = [p for p in prods if p[0] == prod_taller][0]
        precio_custom = st.number_input("Precio Final Cobrado ($)", value=float(info_t[1]), min_value=0.0)

        desc_stock = st.checkbox("¿Descontar del stock general?", value=True)

        if st.button("💾 Registrar Venta Taller", use_container_width=True):
            subt = cant_taller * precio_custom
            if desc_stock:
                consulta("UPDATE productos SET stock = stock - %s WHERE nombre = %s", (cant_taller, prod_taller), fetch=False)

            consulta("""
                INSERT INTO ventas (origen, item_tipo, item_nombre, cantidad, precio_unitario, subtotal, fecha) 
                VALUES ('TALLER', 'PRODUCTO', %s, %s, %s, %s, %s)
            """, (prod_taller, cant_taller, precio_custom, subt, datetime.now()), fetch=False)
            
            st.success(f"Venta Taller asentada: {prod_taller} x{cant_taller} (${subt:,.0f})")
            st.rerun()

# -----------------------------------------------------------------------------
# 3. INVENTARIO
# -----------------------------------------------------------------------------
with tab_stock:
    st.header("📦 Inventario General")
    prods_full = consulta("SELECT nombre, categoria, precio, stock, stock_minimo FROM productos ORDER BY nombre ASC")
    if prods_full:
        df_stock = pd.DataFrame(prods_full, columns=["Producto", "Categoría", "Precio", "Stock", "Stock Mínimo"])
        st.dataframe(df_stock, use_container_width=True)

# -----------------------------------------------------------------------------
# 4. GACHAPON
# -----------------------------------------------------------------------------
with tab_gachapon:
    st.header("🎰 Premios Máquina Gachapon")
    premios = consulta("SELECT id, numero, nombre, stock_deposito, en_maquina FROM gachapon_premios ORDER BY id ASC")
    if premios:
        df_gachapon = pd.DataFrame(premios, columns=["ID", "Nº", "Premio", "En Depósito", "En Máquina"])
        st.dataframe(df_gachapon[["Nº", "Premio", "En Máquina", "En Depósito"]], use_container_width=True)

# -----------------------------------------------------------------------------
# 5. CAJA
# -----------------------------------------------------------------------------
with tab_caja:
    st.header("💰 Estado de Caja")
    
    res_termas = consulta("SELECT SUM(subtotal) FROM ventas WHERE origen='TERMAS' AND cerrado = 0")
    res_taller = consulta("SELECT SUM(subtotal) FROM ventas WHERE origen='TALLER' AND cerrado = 0")
    
    tot_termas = float(res_termas[0][0]) if res_termas and res_termas[0][0] else 0.0
    tot_taller = float(res_taller[0][0]) if res_taller and res_taller[0][0] else 0.0
    tot_general = tot_termas + tot_taller

    c1, c2, c3 = st.columns(3)
    c1.metric("🛒 CAJA TERMAS", f"${tot_termas:,.0f}")
    c2.metric("🛠️ CAJA TALLER", f"${tot_taller:,.0f}")
    c3.metric("💵 TOTAL COMBINADO", f"${tot_general:,.0f}")

import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import base64

# Configuración de página adaptable a teléfonos
st.set_page_config(page_title="Gestión Termas & Taller", page_icon="🏪", layout="wide")

# --- CONTROL DE ACCESO CON PIN ---
PIN_CORRECTO = "2017"  # Clave de acceso actualizada

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
    st.stop()

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

# --- INICIALIZACIÓN Y MIGRACIÓN AUTO-CORRECTIVA ---
def init_db():
    try:
        consulta("ALTER TABLE productos ADD COLUMN IF NOT EXISTS imagen_url TEXT;", fetch=False)
        consulta("ALTER TABLE productos ADD COLUMN IF NOT EXISTS subgrupo VARCHAR(100) DEFAULT 'Varios';", fetch=False)
    except Exception:
        pass

    consulta("""
        CREATE TABLE IF NOT EXISTS productos (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(255) UNIQUE NOT NULL,
            categoria VARCHAR(100) DEFAULT 'General',
            subgrupo VARCHAR(100) DEFAULT 'Varios',
            precio NUMERIC DEFAULT 0,
            stock INT DEFAULT 0,
            stock_minimo INT DEFAULT 1,
            imagen_url TEXT
        );
        CREATE TABLE IF NOT EXISTS gachapon_premios (
            id SERIAL PRIMARY KEY,
            numero VARCHAR(50),
            nombre VARCHAR(255) UNIQUE NOT NULL,
            coleccion VARCHAR(100) DEFAULT 'Zookis',
            impresos INT DEFAULT 0,
            stock_deposito INT DEFAULT 0,
            en_maquina INT DEFAULT 0,
            precio_venta_directa NUMERIC DEFAULT 0,
            imagen_url TEXT
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

# --- APLICACIÓN DE MAPEO AUTOMÁTICO DE CATEGORÍAS/GRUPOS ---
def obtener_grupo(categoria):
    cat = str(categoria).lower()
    if 'llavero' in cat or 'dije' in cat or 'pin' in cat or 'iman' in cat:
        return "🔑 Llaveros, Pines y Dijes"
    elif 'fidget' in cat or 'juguete' in cat or 'articulado' in cat or 'kit' in cat or 'burbujero' in cat:
        return "🧩 Juguetes y Fidgets"
    elif 'figura' in cat or 'funko' in cat or 'colgante' in cat:
        return "🗿 Figuras y Funkos"
    elif 'mate' in cat or 'vaso' in cat or 'maceta' in cat or 'celular' in cat or 'vela' in cat or 'florero' in cat:
        return "🏠 Hogar y Deco"
    else:
        return "📦 Varios y Novedades"

# --- INTERFAZ PRINCIPAL ---
st.title("🏪 Control Termas & Taller")

tab_termas, tab_taller, tab_gachapon, tab_stock, tab_caja = st.tabs([
    "🛒 Ventas Termas", 
    "🛠️ Ventas Taller", 
    "🎰 Gachapon & Colecciones", 
    "📦 Inventario & Fotos", 
    "💰 Caja"
])

# -----------------------------------------------------------------------------
# 1. VENTAS TERMAS (CATÁLOGO VISUAL POR GRUPOS)
# -----------------------------------------------------------------------------
with tab_termas:
    st.header("🛒 Ventas Mostrador Termas")
    
    busqueda = st.text_input("🔍 Buscador rápido de producto (nombre o categoría):", key="busqueda_termas")
    
    prods = consulta("SELECT id, nombre, categoria, precio, stock, imagen_url FROM productos ORDER BY nombre ASC")
    
    if prods:
        df_prods = pd.DataFrame(prods, columns=["id", "nombre", "categoria", "precio", "stock", "imagen_url"])
        df_prods['grupo'] = df_prods['categoria'].apply(obtener_grupo)
        
        if busqueda:
            df_filtrado = df_prods[df_prods['nombre'].str.contains(busqueda, case=False, na=False) | 
                                   df_prods['categoria'].str.contains(busqueda, case=False, na=False)]
            st.subheader(f"Resultados de búsqueda ({len(df_filtrado)})")
            grupos_mostrar = {"🔍 Resultados": df_filtrado}
        else:
            grupos_unicos = ["🔑 Llaveros, Pines y Dijes", "🧩 Juguetes y Fidgets", "🗿 Figuras y Funkos", "🏠 Hogar y Deco", "📦 Varios y Novedades"]
            grupos_mostrar = {g: df_prods[df_prods['grupo'] == g] for g in grupos_unicos if not df_prods[df_prods['grupo'] == g].empty}

        # Renderizado de grupos
        for nombre_grupo, df_g in grupos_mostrar.items():
            with st.expander(f"{nombre_grupo} ({len(df_g)} artículos)", expanded=True if busqueda else False):
                cols = st.columns(3)
                for idx, row in df_g.reset_index().iterrows():
                    col = cols[idx % 3]
                    with col:
                        st.markdown("---")
                        if row['imagen_url']:
                            st.image(row['imagen_url'], use_container_width=True)
                        else:
                            st.caption("📷 *Sin foto miniatura*")
                        
                        st.markdown(f"**{row['nombre']}**")
                        st.caption(f"Categoría: {row['categoria']}")
                        st.subheader(f"${float(row['precio']):,.0f}")
                        st.write(f"Stock: **{row['stock']} un.**")
                        
                        if row['stock'] > 0:
                            if st.button(f"🛒 Vender 1 un.", key=f"btn_v_{row['id']}", use_container_width=True):
                                subt = float(row['precio'])
                                consulta("UPDATE productos SET stock = stock - 1 WHERE id = %s", (row['id'],), fetch=False)
                                consulta("""
                                    INSERT INTO ventas (origen, item_tipo, item_nombre, cantidad, precio_unitario, subtotal, fecha) 
                                    VALUES ('TERMAS', 'PRODUCTO', %s, 1, %s, %s, %s)
                                """, (row['nombre'], row['precio'], subt, datetime.now()), fetch=False)
                                st.success(f"Vendido: {row['nombre']}")
                                st.rerun()
                        else:
                            st.error("Sin Stock")
    else:
        st.info("Aún no hay productos cargados en el inventario.")

# -----------------------------------------------------------------------------
# 2. VENTAS TALLER
# -----------------------------------------------------------------------------
with tab_taller:
    st.header("🛠️ Ventas Taller / Envíos Externos")
    st.info("Registrá encargos personalizados, impresiones 3D a pedido o envíos fuera del local.")

    if prods:
        lista_prod = [p[1] for p in prods]
        prod_taller = st.selectbox("Seleccionar Producto o Encargo", lista_prod, key="p_taller")
        cant_taller = st.number_input("Cantidad", min_value=1, value=1, key="c_taller")
        
        info_t = [p for p in prods if p[1] == prod_taller][0]
        precio_custom = st.number_input("Precio Final Cobrado ($)", value=float(info_t[3]), min_value=0.0)
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
# 3. GACHAPON & COLECCIONES
# -----------------------------------------------------------------------------
with tab_gachapon:
    st.header("🎰 Máquina Gachapon & Colecciones")
    
    st.subheader("🎟️ Venta de Ficha Gachapon")
    c_f1, c_f2 = st.columns([2, 1])
    with c_f1:
        cant_fichas = st.number_input("Cantidad Fichas", min_value=1, value=1, key="f_gachapon")
    with c_f2:
        st.write("")
        if st.button("🎟️ Vender Ficha/s", use_container_width=True):
            res_p = consulta("SELECT valor FROM config WHERE clave='precio_ficha_gachapon'")
            p_unit = float(res_p[0][0]) if res_p else 2000.0
            subt = cant_fichas * p_unit
            consulta("""
                INSERT INTO ventas (origen, item_tipo, item_nombre, cantidad, precio_unitario, subtotal, fecha) 
                VALUES ('TERMAS', 'FICHA_GACHAPON', 'Ficha Gachapon', %s, %s, %s, %s)
            """, (cant_fichas, p_unit, subt, datetime.now()), fetch=False)
            st.success(f"Vendido: {cant_fichas} ficha/s (${subt:,.0f})")

    st.divider()
    st.subheader("📦 Estado de Premios y Muñecos")
    premios = consulta("SELECT id, numero, nombre, stock_deposito, en_maquina FROM gachapon_premios ORDER BY id ASC")
    if premios:
        df_gachapon = pd.DataFrame(premios, columns=["ID", "Nº", "Premio", "En Depósito", "En Máquina"])
        st.dataframe(df_gachapon[["Nº", "Premio", "En Máquina", "En Depósito"]], use_container_width=True)

# -----------------------------------------------------------------------------
# 4. INVENTARIO & SUBIDA DE FOTOS
# -----------------------------------------------------------------------------
with tab_stock:
    st.header("📦 Inventario y Carga de Fotos")
    
    st.subheader("🖼️ Asignar / Cambiar Foto a un Producto")
    if prods:
        prod_foto = st.selectbox("Seleccionar producto para agregarle foto:", [p[1] for p in prods])
        id_prod = [p[0] for p in prods if p[1] == prod_foto][0]
        
        archivo_imagen = st.file_uploader("Cargar imagen (JPG, PNG) desde la PC o tomar foto con el Celular:", type=["jpg", "png", "jpeg"])
        
        if archivo_imagen is not None:
            bytes_data = archivo_imagen.getvalue()
            b64_img = f"data:image/jpeg;base64,{base64.b64encode(bytes_data).decode()}"
            st.image(bytes_data, width=150, caption="Vista previa de miniatura")
            
            if st.button("💾 Guardar Foto del Producto", use_container_width=True):
                consulta("UPDATE productos SET imagen_url = %s WHERE id = %s", (b64_img, id_prod), fetch=False)
                st.success(f"¡Foto guardada correctamente para {prod_foto}!")
                st.rerun()

    st.divider()
    st.subheader("📋 Lista Completa de Stock")
    prods_full = consulta("SELECT id, nombre, categoria, precio, stock, stock_minimo FROM productos ORDER BY nombre ASC")
    if prods_full:
        df_stock = pd.DataFrame(prods_full, columns=["ID", "Producto", "Categoría", "Precio", "Stock", "Stock Mínimo"])
        st.dataframe(df_stock, use_container_width=True)

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

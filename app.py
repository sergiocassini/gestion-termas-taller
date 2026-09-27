import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import base64

# Configuración de página adaptable a teléfonos
st.set_page_config(page_title="Gestión Termas & Taller", page_icon="🏪", layout="wide")

# --- CONTROL DE ACCESO CON PIN ---
PIN_CORRECTO = "2017"

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

def verificar_pin():
    if st.session_state["input_pin"] == PIN_CORRECTO:
        st.session_state["autenticado"] = True
    else:
        st.error("🔒 PIN / Contraseña incorrecta")

if not st.session_state["autenticado"]:
    st.title("🔒 Acceso Restringido")
    st.subheader("Control de Negocio: Termas, Taller & Feria")
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

# --- INICIALIZACIÓN Y AUTO-MIGRACIÓN ---
def init_db():
    try:
        consulta("ALTER TABLE productos ADD COLUMN IF NOT EXISTS imagen_url TEXT;", fetch=False)
        consulta("ALTER TABLE productos ADD COLUMN IF NOT EXISTS grupo VARCHAR(100);", fetch=False)
        consulta("ALTER TABLE productos ADD COLUMN IF NOT EXISTS subgrupo VARCHAR(100) DEFAULT 'Varios';", fetch=False)
        consulta("ALTER TABLE gachapon_premios ADD COLUMN IF NOT EXISTS coleccion VARCHAR(100) DEFAULT 'Zooki';", fetch=False)
        consulta("ALTER TABLE gachapon_premios ADD COLUMN IF NOT EXISTS precio_ficha NUMERIC DEFAULT 2000;", fetch=False)
        consulta("ALTER TABLE ventas ADD COLUMN IF NOT EXISTS nombre_feria VARCHAR(150) DEFAULT 'General';", fetch=False)
    except Exception:
        pass

    consulta("""
        CREATE TABLE IF NOT EXISTS productos (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(255) UNIQUE NOT NULL,
            categoria VARCHAR(100) DEFAULT 'General',
            grupo VARCHAR(100),
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
            coleccion VARCHAR(100) DEFAULT 'Zooki',
            impresos INT DEFAULT 0,
            stock_deposito INT DEFAULT 0,
            en_maquina INT DEFAULT 0,
            precio_ficha NUMERIC DEFAULT 2000,
            imagen_url TEXT
        );
        CREATE TABLE IF NOT EXISTS ventas (
            id SERIAL PRIMARY KEY,
            origen VARCHAR(50) DEFAULT 'TERMAS',
            nombre_feria VARCHAR(150) DEFAULT 'General',
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

# --- MAPEO INTELIGENTE DE GRUPOS ---
def obtener_grupo(categoria, nombre=""):
    text = (str(categoria) + " " + str(nombre)).lower()
    if any(k in text for k in ['llavero', 'dije', 'pin', 'iman', 'dijes', 'set imanes']):
        return "🔑 Llaveros, Pines y Dijes"
    elif any(k in text for k in ['fidget', 'juguete', 'articulado', 'kit cards', 'burbujero']):
        return "🧩 Juguetes y Fidgets"
    elif any(k in text for k in ['figura', 'funko', 'colgante']):
        return "🗿 Figuras y Funkos"
    elif any(k in text for k in ['mate', 'vaso', 'maceta', 'portacelular', 'sahumerios', 'porta velas', 'floreros']):
        return "🏠 Hogar y Deco"
    else:
        return "📦 Varios y Novedades"

# --- RENDERIZADOR DE CATÁLOGO VISUAL ---
def renderizar_catalogo(prods, origen_venta, incluir_gachapon=False, key_prefix="cat", nombre_feria="General"):
    busqueda = st.text_input("🔍 Buscador rápido de producto (nombre o categoría):", key=f"busqueda_{key_prefix}")
    
    if prods:
        df_prods = pd.DataFrame(prods, columns=["id", "nombre", "categoria", "precio", "stock", "imagen_url", "grupo"])
        df_prods['grupo_final'] = df_prods.apply(lambda r: r['grupo'] if (r['grupo'] and r['grupo'] != '📦 Varios y Novedades') else obtener_grupo(r['categoria'], r['nombre']), axis=1)
        
        if busqueda:
            df_filtrado = df_prods[df_prods['nombre'].str.contains(busqueda, case=False, na=False) | 
                                   df_prods['categoria'].str.contains(busqueda, case=False, na=False)]
            st.subheader(f"Resultados de búsqueda ({len(df_filtrado)})")
            grupos_mostrar = {"🔍 Resultados": df_filtrado}
        else:
            grupos_orden = [
                "🔑 Llaveros, Pines y Dijes",
                "🧩 Juguetes y Fidgets",
                "🗿 Figuras y Funkos",
                "🏠 Hogar y Deco",
                "📦 Varios y Novedades"
            ]
            grupos_mostrar = {g: df_prods[df_prods['grupo_final'] == g] for g in grupos_orden if not df_prods[df_prods['grupo_final'] == g].empty}

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
                            if st.button(f"🛒 Vender 1 un.", key=f"btn_{key_prefix}_{row['id']}", use_container_width=True):
                                subt = float(row['precio'])
                                consulta("UPDATE productos SET stock = stock - 1 WHERE id = %s", (row['id'],), fetch=False)
                                consulta("""
                                    INSERT INTO ventas (origen, nombre_feria, item_tipo, item_nombre, cantidad, precio_unitario, subtotal, fecha) 
                                    VALUES (%s, %s, 'PRODUCTO', %s, 1, %s, %s, %s)
                                """, (origen_venta, nombre_feria, row['nombre'], row['precio'], subt, datetime.now()), fetch=False)
                                st.success(f"Vendido en {origen_venta}: {row['nombre']}")
                                st.rerun()
                        else:
                            st.error("Sin Stock")
    else:
        st.info("Aún no hay productos cargados en el inventario.")

    # SECCIÓN GACHAPON
    if incluir_gachapon:
        with st.expander("🎰 Gachapon", expanded=False):
            premios_all = consulta("SELECT id, numero, nombre, coleccion, stock_deposito, en_maquina, precio_ficha FROM gachapon_premios ORDER BY id ASC")
            
            if premios_all:
                df_gach = pd.DataFrame(premios_all, columns=["ID", "Nº", "Premio", "Colección", "En Depósito", "En Máquina", "Precio Ficha"])
                df_gach['Colección'] = df_gach['Colección'].fillna('General')
                colecciones_unicas = sorted(df_gach['Colección'].unique())
                
                st.subheader(f"🎟️ Venta de Ficha Gachapon ({origen_venta})")
                col_sel = st.selectbox("Seleccionar Colección:", colecciones_unicas, key=f"gach_sel_{key_prefix}")
                
                p_ficha = float(df_gach[df_gach['Colección'] == col_sel]['Precio Ficha'].iloc[0])
                st.caption(f"Precio actual por ficha ({col_sel}): **${p_ficha:,.0f}**")
                
                c_f1, c_f2 = st.columns([2, 1])
                with c_f1:
                    cant_fichas = st.number_input("Cantidad de Fichas:", min_value=1, value=1, key=f"cant_f_{key_prefix}")
                with c_f2:
                    st.write("")
                    if st.button("🎟️ Vender Ficha/s", key=f"btn_f_{key_prefix}", use_container_width=True):
                        subt = cant_fichas * p_ficha
                        consulta("""
                            INSERT INTO ventas (origen, nombre_feria, item_tipo, item_nombre, cantidad, precio_unitario, subtotal, fecha) 
                            VALUES (%s, %s, 'FICHA_GACHAPON', %s, %s, %s, %s, %s)
                        """, (origen_venta, nombre_feria, f"Ficha Gachapon ({col_sel})", cant_fichas, p_ficha, subt, datetime.now()), fetch=False)
                        st.success(f"Vendido en {origen_venta}: {cant_fichas} ficha/s {col_sel} (${subt:,.0f})")

                st.divider()
                
                tabs_colec = st.tabs([f"📦 {col}" for col in colecciones_unicas])
                for index, col_nombre in enumerate(colecciones_unicas):
                    with tabs_colec[index]:
                        sub_df = df_gach[df_gach['Colección'] == col_nombre]
                        st.dataframe(sub_df[["Nº", "Premio", "En Máquina", "En Depósito"]], use_container_width=True)
            else:
                st.caption("No hay premios de Gachapon cargados aún.")

# --- INTERFAZ PRINCIPAL ---
st.title("🏪 Control Termas, Taller & Feria")

tab_termas, tab_taller, tab_feria, tab_caja, tab_stock = st.tabs([
    "🛒 Ventas Termas", 
    "🛠️ Ventas Taller", 
    "🎪 Ventas Feria", 
    "💰 Caja", 
    "📦 Inventario"
])

prods_db = consulta("SELECT id, nombre, categoria, precio, stock, imagen_url, grupo FROM productos ORDER BY nombre ASC")

# -----------------------------------------------------------------------------
# 1. VENTAS TERMAS
# -----------------------------------------------------------------------------
with tab_termas:
    st.header("🛒 Ventas Mostrador Termas")
    renderizar_catalogo(prods_db, origen_venta="TERMAS", incluir_gachapon=True, key_prefix="termas")

# -----------------------------------------------------------------------------
# 2. VENTAS TALLER
# -----------------------------------------------------------------------------
with tab_taller:
    st.header("🛠️ Ventas Taller / Envíos Externos")
    renderizar_catalogo(prods_db, origen_venta="TALLER", incluir_gachapon=False, key_prefix="taller")

# -----------------------------------------------------------------------------
# 3. VENTAS FERIA
# -----------------------------------------------------------------------------
with tab_feria:
    st.header("🎪 Ventas Stand / Feria")
    
    col_f_nombre, col_f_cierre = st.columns([3, 2])
    with col_f_nombre:
        nombre_feria_activa = st.text_input("Nombre / Lugar de la Feria Activa:", value="Feria Dolores", key="input_nombre_feria")
    with col_f_cierre:
        st.write("")
        res_feria_act = consulta("SELECT SUM(subtotal) FROM ventas WHERE origen='FERIA' AND nombre_feria = %s AND cerrado = 0", (nombre_feria_activa,))
        tot_feria_act = float(res_feria_act[0][0]) if res_feria_act and res_feria_act[0][0] else 0.0
        
        if st.button(f"🔒 Cerrar Feria '{nombre_feria_activa}' (${tot_feria_act:,.0f})", use_container_width=True):
            if tot_feria_act > 0:
                consulta("UPDATE ventas SET cerrado = 1 WHERE origen='FERIA' AND nombre_feria = %s AND cerrado = 0", (nombre_feria_activa,), fetch=False)
                st.success(f"¡Feria '{nombre_feria_activa}' cerrada exitosamente con un total de ${tot_feria_act:,.0f}!")
                st.rerun()
            else:
                st.info("No hay ventas abiertas para esta feria.")

    st.divider()
    renderizar_catalogo(prods_db, origen_venta="FERIA", incluir_gachapon=True, key_prefix="feria", nombre_feria=nombre_feria_activa)

# -----------------------------------------------------------------------------
# 4. CAJA
# -----------------------------------------------------------------------------
with tab_caja:
    st.header("💰 Estado de Caja")
    
    res_termas = consulta("SELECT SUM(subtotal) FROM ventas WHERE origen='TERMAS' AND cerrado = 0")
    res_taller = consulta("SELECT SUM(subtotal) FROM ventas WHERE origen='TALLER' AND cerrado = 0")
    res_feria = consulta("SELECT SUM(subtotal) FROM ventas WHERE origen='FERIA' AND cerrado = 0")
    
    tot_termas = float(res_termas[0][0]) if res_termas and res_termas[0][0] else 0.0
    tot_taller = float(res_taller[0][0]) if res_taller and res_taller[0][0] else 0.0
    tot_feria = float(res_feria[0][0]) if res_feria and res_feria[0][0] else 0.0
    tot_general = tot_termas + tot_taller + tot_feria

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🛒 CAJA TERMAS", f"${tot_termas:,.0f}")
    c2.metric("🛠️ CAJA TALLER", f"${tot_taller:,.0f}")
    c3.metric("🎪 CAJA FERIA", f"${tot_feria:,.0f}")
    c4.metric("💵 TOTAL COMBINADO", f"${tot_general:,.0f}")

    st.divider()
    st.subheader("📊 Reporte de Stock Vendido por Feria (Guía de Carga / Reposición)")
    
    ferias_lista = consulta("SELECT DISTINCT nombre_feria FROM ventas WHERE origen='FERIA' ORDER BY nombre_feria ASC")
    if ferias_lista:
        feria_sel_reporte = st.selectbox("Seleccionar Feria para ver qué productos se vendieron:", [f[0] for f in ferias_lista])
        
        ventas_feria_prod = consulta("""
            SELECT item_nombre, SUM(cantidad) as unidades_vendidas, SUM(subtotal) as total_recaudado
            FROM ventas 
            WHERE origen='FERIA' AND nombre_feria = %s
            GROUP BY item_nombre
            ORDER BY unidades_vendidas DESC
        """, (feria_sel_reporte,))
        
        if ventas_feria_prod:
            df_v_feria = pd.DataFrame(ventas_feria_prod, columns=["Producto / Ficha", "Unidades Vendidas", "Total Recaudado ($)"])
            st.dataframe(df_v_feria, use_container_width=True)
            st.info("💡 Usá esta lista como referencia para saber qué productos reponer e incluir en el stock para la próxima edición de esta feria.")
        else:
            st.caption("No hay ventas registradas para la feria seleccionada.")
    else:
        st.caption("Aún no se han registrado ventas en ferias.")

# -----------------------------------------------------------------------------
# 5. INVENTARIO
# -----------------------------------------------------------------------------
with tab_stock:
    st.header("📦 Inventario")
    
    # 1. ALTAS DIRECCIONADAS MANUALES CON FOTO
    with st.expander("➕ Dar de Alta Nuevo Producto o Premio Gachapon", expanded=False):
        tipo_alta = st.radio("¿Qué querés registrar?", ["Producto General", "Premio de Gachapon"], horizontal=True)
        
        if tipo_alta == "Producto General":
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                nuevo_nombre = st.text_input("Nombre del Producto:")
                nuevo_grupo = st.selectbox("Grupo:", [
                    "🔑 Llaveros, Pines y Dijes",
                    "🧩 Juguetes y Fidgets",
                    "🗿 Figuras y Funkos",
                    "🏠 Hogar y Deco",
                    "📦 Varios y Novedades"
                ])
                nueva_cat = st.text_input("Categoría o Subgrupo (ej: Clubes, Anti-estrés):", value="General")
            with col_a2:
                nuevo_precio = st.number_input("Precio de Venta ($):", min_value=0.0, value=1000.0, key="alta_precio_prod")
                nuevo_stock = st.number_input("Stock Inicial:", min_value=0, value=1, key="alta_stock_prod")
                archivo_foto_alta = st.file_uploader("📷 Foto de Producto (opcional):", type=["jpg", "png", "jpeg"], key="foto_alta_prod")
            
            b64_img_alta = None
            if archivo_foto_alta is not None:
                bytes_data = archivo_foto_alta.getvalue()
                b64_img_alta = f"data:image/jpeg;base64,{base64.b64encode(bytes_data).decode()}"
                st.image(bytes_data, width=120, caption="Vista previa de miniatura")

            if st.button("💾 Guardar Nuevo Producto", use_container_width=True):
                if nuevo_nombre:
                    try:
                        consulta("""
                            INSERT INTO productos (nombre, grupo, categoria, subgrupo, precio, stock, imagen_url) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (nuevo_nombre, nuevo_grupo, nueva_cat, nueva_cat, nuevo_precio, nuevo_stock, b64_img_alta), fetch=False)
                        st.success(f"¡Producto '{nuevo_nombre}' agregado correctamente con su foto!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Error al guardar: {ex}")
                else:
                    st.warning("Escribí un nombre de producto.")

        else: # Alta Gachapon
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                g_num = st.text_input("Número o Código de Premio:")
                g_nombre = st.text_input("Nombre del Personaje/Premio:")
                
                colec_existentes = consulta("SELECT DISTINCT coleccion FROM gachapon_premios")
                lista_c = [c[0] for c in colec_existentes if c[0]] if colec_existentes else ["Zooki", "Minecraft"]
                
                g_colec_sel = st.selectbox("Seleccionar Colección Existente:", lista_c + ["➕ Crear nueva colección..."])
                if g_colec_sel == "➕ Crear nueva colección...":
                    g_colec = st.text_input("Nombre de la NUEVA Colección (ej: Pokémon):")
                    g_precio_ficha = st.number_input("Precio de la Ficha para esta colección ($):", min_value=0.0, value=2000.0, key="alta_p_ficha")
                else:
                    g_colec = g_colec_sel
                    g_precio_ficha = 2000.0
            with col_g2:
                g_en_maq = st.number_input("Cantidad Inicial en Máquina:", min_value=0, value=1, key="alta_maq_gach")
                g_en_dep = st.number_input("Cantidad Inicial en Depósito:", min_value=0, value=0, key="alta_dep_gach")
                archivo_foto_gach = st.file_uploader("📷 Foto del Personaje (opcional):", type=["jpg", "png", "jpeg"], key="foto_alta_gach")

            b64_img_gach = None
            if archivo_foto_gach is not None:
                bytes_data_g = archivo_foto_gach.getvalue()
                b64_img_gach = f"data:image/jpeg;base64,{base64.b64encode(bytes_data_g).decode()}"
                st.image(bytes_data_g, width=120, caption="Vista previa de miniatura")

            if st.button("💾 Guardar Personaje Gachapon", use_container_width=True):
                if g_nombre and g_colec:
                    try:
                        consulta("""
                            INSERT INTO gachapon_premios (numero, nombre, coleccion, en_maquina, stock_deposito, precio_ficha, imagen_url) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (g_num, g_nombre, g_colec, g_en_maq, g_en_dep, g_precio_ficha, b64_img_gach), fetch=False)
                        st.success(f"¡Personaje '{g_nombre}' guardado en la colección '{g_colec}' con su foto!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Error al guardar: {ex}")
                else:
                    st.warning("Completá el nombre del personaje y la colección.")

    # 2. CAMBIO DE PRECIOS Y STOCK
    with st.expander("✏️ Cambiar Precios y Stock", expanded=False):
        tipo_precio = st.radio("Editar datos de:", ["Producto General", "Ficha/Colección Gachapon"], horizontal=True, key="edit_tipo_radio")
        
        if tipo_precio == "Producto General":
            if prods_db:
                p_edit = st.selectbox("Seleccionar Producto:", [p[1] for p in prods_db], key="edit_sel_producto")
                info_p = [p for p in prods_db if p[1] == p_edit][0]
                val_act = info_p[3]
                stock_act = info_p[4]
                
                cp1, cp2 = st.columns(2)
                with cp1:
                    p_nuevo = st.number_input("Precio de Venta ($):", value=float(val_act), min_value=0.0, key=f"edit_p_{p_edit}")
                with cp2:
                    s_nuevo = st.number_input("Stock Disponible (un.):", value=int(stock_act), min_value=0, key=f"edit_s_{p_edit}")
                    
                if st.button("💾 Actualizar Producto", use_container_width=True, key="btn_actualizar_prod"):
                    consulta("UPDATE productos SET precio = %s, stock = %s WHERE nombre = %s", (p_nuevo, s_nuevo, p_edit), fetch=False)
                    st.success(f"¡Producto '{p_edit}' actualizado! Precio: ${p_nuevo:,.0f} | Stock: {s_nuevo} un.")
                    st.rerun()
        else:
            colec_precios = consulta("SELECT DISTINCT coleccion, precio_ficha FROM gachapon_premios")
            if colec_precios:
                col_e = st.selectbox("Seleccionar Colección:", [c[0] for c in colec_precios], key="edit_sel_coleccion")
                p_f_act = [c[1] for c in colec_precios if c[0] == col_e][0]
                pf_nuevo = st.number_input(f"Nuevo Precio de Ficha para {col_e} ($):", value=float(p_f_act if p_f_act else 2000), min_value=0.0, key=f"edit_pf_{col_e}")
                if st.button("💾 Actualizar Precio de Ficha", use_container_width=True, key="btn_actualizar_ficha"):
                    consulta("UPDATE gachapon_premios SET precio_ficha = %s WHERE coleccion = %s", (pf_nuevo, col_e), fetch=False)
                    st.success(f"¡Precio de ficha para {col_e} actualizado a ${pf_nuevo:,.0f}!")
                    st.rerun()

    # 3. IMPORTADOR MASIVO DESDE EXCEL
    with st.expander("📥 Importar / Actualizar desde Excel (Stock Termas.xlsx)", expanded=False):
        st.write("Subí tu archivo Excel para actualizar automáticamente productos generales y colecciones de Gachapon.")
        archivo_excel = st.file_uploader("Seleccionar planilla (.xlsx o .xls):", type=["xlsx", "xls"], key="excel_uploader")
        
        if archivo_excel is not None:
            if st.button("🚀 Sincronizar Base de Datos con Excel", use_container_width=True):
                try:
                    xls = pd.ExcelFile(archivo_excel)
                    cargados_prods = 0
                    cargados_gach = 0
                    
                    for sheet in xls.sheet_names:
                        df_sheet = pd.read_excel(archivo_excel, sheet_name=sheet)
                        df_sheet.columns = [str(c).strip().lower() for c in df_sheet.columns]
                        
                        is_gachapon = any(k in sheet.lower() for k in ['zooki', 'minecraft', 'gachapon', 'premio']) or \
                                      any('impresos' in c or 'deposito' in c or 'maquina' in c for c in df_sheet.columns)
                        
                        if is_gachapon:
                            col_nom = next((c for c in df_sheet.columns if 'nombre' in c or 'premio' in c or 'personaje' in c), None)
                            col_num = next((c for c in df_sheet.columns if 'numero' in c or 'nº' in c or 'num' in c or 'id' in c), None)
                            col_dep = next((c for c in df_sheet.columns if 'deposito' in c or 'depósito' in c or 'stock' in c), None)
                            col_maq = next((c for c in df_sheet.columns if 'maquina' in c or 'máquina' in c), None)
                            
                            if col_nom:
                                for _, r in df_sheet.dropna(subset=[col_nom]).iterrows():
                                    g_nom = str(r[col_nom]).strip()
                                    g_num = str(r[col_num]).strip() if (col_num and pd.notnull(r[col_num])) else ""
                                    g_dep = int(r[col_dep]) if (col_dep and pd.notnull(r[col_dep])) else 0
                                    g_maq = int(r[col_maq]) if (col_maq and pd.notnull(r[col_maq])) else 0
                                    
                                    consulta("""
                                        INSERT INTO gachapon_premios (numero, nombre, coleccion, stock_deposito, en_maquina)
                                        VALUES (%s, %s, %s, %s, %s)
                                        ON CONFLICT (nombre) DO UPDATE SET
                                            numero = EXCLUDED.numero,
                                            coleccion = EXCLUDED.coleccion,
                                            stock_deposito = EXCLUDED.stock_deposito,
                                            en_maquina = EXCLUDED.en_maquina;
                                    """, (g_num, g_nom, sheet, g_dep, g_maq), fetch=False)
                                    cargados_gach += 1
                        else:
                            col_nombre = next((c for c in df_sheet.columns if 'producto' in c or 'nombre' in c or 'item' in c), None)
                            col_precio = next((c for c in df_sheet.columns if 'precio' in c or 'valor' in c), None)
                            col_stock = next((c for c in df_sheet.columns if 'stock' in c or 'cantidad' in c or 'cant' in c), None)
                            col_cat = next((c for c in df_sheet.columns if 'categoria' in c or 'categoría' in c or 'grupo' in c), None)
                            
                            if col_nombre:
                                for _, r in df_sheet.dropna(subset=[col_nombre]).iterrows():
                                    p_nombre = str(r[col_nombre]).strip()
                                    p_precio = float(r[col_precio]) if (col_precio and pd.notnull(r[col_precio])) else 0.0
                                    p_stock = int(r[col_stock]) if (col_stock and pd.notnull(r[col_stock])) else 0
                                    p_cat = str(r[col_cat]).strip() if (col_cat and pd.notnull(r[col_cat])) else "General"
                                    p_grupo = obtener_grupo(p_cat, p_nombre)
                                    
                                    consulta("""
                                        INSERT INTO productos (nombre, categoria, grupo, precio, stock)
                                        VALUES (%s, %s, %s, %s, %s)
                                        ON CONFLICT (nombre) DO UPDATE SET
                                            precio = EXCLUDED.precio,
                                            stock = EXCLUDED.stock,
                                            categoria = EXCLUDED.categoria,
                                            grupo = EXCLUDED.grupo;
                                    """, (p_nombre, p_cat, p_grupo, p_precio, p_stock), fetch=False)
                                    cargados_prods += 1
                                
                    st.success(f"¡Éxito! Se actualizaron {cargados_prods} productos generales y {cargados_gach} premios/personajes de Gachapon.")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error al procesar el archivo Excel: {ex}")

    # 4. ARQUEO DE MAQUINA GACHAPON
    with st.expander("🔍 Arqueo y Recompuesto de Máquina Gachapon", expanded=False):
        premios_arq = consulta("SELECT id, numero, nombre, coleccion, en_maquina, stock_deposito FROM gachapon_premios ORDER BY coleccion, numero ASC")
        if premios_arq:
            df_arq = pd.DataFrame(premios_arq, columns=["id", "numero", "nombre", "coleccion", "en_maquina", "stock_deposito"])
            col_arq_sel = st.selectbox("Seleccionar Colección para Auditar/Arquear:", df_arq['coleccion'].unique(), key="arq_col")
            
            df_col_arq = df_arq[df_arq['coleccion'] == col_arq_sel]
            st.write("Ajustá la **Cantidad Real Actual en Máquina** observada al abrir la máquina:")
            
            for index, row in df_col_arq.iterrows():
                ca1, ca2 = st.columns([3, 2])
                with ca1:
                    st.write(f"**Nº {row['numero']} - {row['nombre']}** (En dep: {row['stock_deposito']})")
                with ca2:
                    n_cant_maq = st.number_input(f"En Máquina:", min_value=0, value=int(row['en_maquina']), key=f"arq_n_{row['id']}")
                    if n_cant_maq != int(row['en_maquina']):
                        consulta("UPDATE gachapon_premios SET en_maquina = %s WHERE id = %s", (n_cant_maq, row['id']), fetch=False)
            st.caption("Los cambios de stock se guardan en tiempo real al modificar los números.")

    st.divider()

    # 5. MÓDULO PARA CARGAR / CAMBIAR FOTO
    st.subheader("🖼️ Asignar / Cambiar Foto a un Producto Existente")
    if prods_db:
        prod_foto = st.selectbox("Seleccionar producto para agregarle foto:", [p[1] for p in prods_db])
        id_prod = [p[0] for p in prods_db if p[1] == prod_foto][0]
        
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
    st.subheader("📋 Lista Completa de Stock General")
    prods_full = consulta("SELECT id, nombre, grupo, categoria, precio, stock FROM productos ORDER BY nombre ASC")
    if prods_full:
        df_stock = pd.DataFrame(prods_full, columns=["ID", "Producto", "Grupo", "Categoría", "Precio Venta", "Stock"])
        st.dataframe(df_stock, use_container_width=True)

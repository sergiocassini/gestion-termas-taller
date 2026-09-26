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

# --- INICIALIZACIÓN Y AUTO-MIGRACIÓN ---
def init_db():
    try:
        consulta("ALTER TABLE productos ADD COLUMN IF NOT EXISTS imagen_url TEXT;", fetch=False)
        consulta("ALTER TABLE productos ADD COLUMN IF NOT EXISTS grupo VARCHAR(100) DEFAULT '📦 Varios y Novedades';", fetch=False)
        consulta("ALTER TABLE productos ADD COLUMN IF NOT EXISTS subgrupo VARCHAR(100) DEFAULT 'Varios';", fetch=False)
        consulta("ALTER TABLE gachapon_premios ADD COLUMN IF NOT EXISTS coleccion VARCHAR(100) DEFAULT 'Zooki';", fetch=False)
        consulta("ALTER TABLE gachapon_premios ADD COLUMN IF NOT EXISTS precio_ficha NUMERIC DEFAULT 2000;", fetch=False)
    except Exception:
        pass

    consulta("""
        CREATE TABLE IF NOT EXISTS productos (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(255) UNIQUE NOT NULL,
            categoria VARCHAR(100) DEFAULT 'General',
            grupo VARCHAR(100) DEFAULT '📦 Varios y Novedades',
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

# --- MAPEO DE GRUPOS ---
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

tab_termas, tab_taller, tab_stock, tab_caja = st.tabs([
    "🛒 Ventas Termas", 
    "🛠️ Ventas Taller", 
    "📦 Inventario", 
    "💰 Caja"
])

# -----------------------------------------------------------------------------
# 1. VENTAS TERMAS
# -----------------------------------------------------------------------------
with tab_termas:
    st.header("🛒 Ventas Mostrador Termas")
    
    busqueda = st.text_input("🔍 Buscador rápido de producto (nombre o categoría):", key="busqueda_termas")
    
    prods = consulta("SELECT id, nombre, categoria, precio, stock, imagen_url, grupo FROM productos ORDER BY nombre ASC")
    
    if prods:
        df_prods = pd.DataFrame(prods, columns=["id", "nombre", "categoria", "precio", "stock", "imagen_url", "grupo"])
        df_prods['grupo_final'] = df_prods.apply(lambda r: r['grupo'] if r['grupo'] else obtener_grupo(r['categoria']), axis=1)
        
        if busqueda:
            df_filtrado = df_prods[df_prods['nombre'].str.contains(busqueda, case=False, na=False) | 
                                   df_prods['categoria'].str.contains(busqueda, case=False, na=False)]
            st.subheader(f"Resultados de búsqueda ({len(df_filtrado)})")
            grupos_mostrar = {"🔍 Resultados": df_filtrado}
        else:
            grupos_unicos = df_prods['grupo_final'].unique()
            grupos_mostrar = {g: df_prods[df_prods['grupo_final'] == g] for g in grupos_unicos if not df_prods[df_prods['grupo_final'] == g].empty}

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

    # MÓDULO GACHAPON
    with st.expander("🎰 Gachapon", expanded=False):
        premios_all = consulta("SELECT id, numero, nombre, coleccion, stock_deposito, en_maquina, precio_ficha FROM gachapon_premios ORDER BY id ASC")
        
        if premios_all:
            df_gach = pd.DataFrame(premios_all, columns=["ID", "Nº", "Premio", "Colección", "En Depósito", "En Máquina", "Precio Ficha"])
            df_gach['Colección'] = df_gach['Colección'].fillna('General')
            colecciones_unicas = sorted(df_gach['Colección'].unique())
            
            st.subheader("🎟️ Venta de Ficha Gachapon")
            col_sel = st.selectbox("Seleccionar Colección:", colecciones_unicas)
            
            p_ficha = float(df_gach[df_gach['Colección'] == col_sel]['Precio Ficha'].iloc[0])
            st.caption(f"Precio actual por ficha ({col_sel}): **${p_ficha:,.0f}**")
            
            c_f1, c_f2 = st.columns([2, 1])
            with c_f1:
                cant_fichas = st.number_input("Cantidad de Fichas:", min_value=1, value=1, key="cant_f_v")
            with c_f2:
                st.write("")
                if st.button("🎟️ Vender Ficha/s", use_container_width=True):
                    subt = cant_fichas * p_ficha
                    consulta("""
                        INSERT INTO ventas (origen, item_tipo, item_nombre, cantidad, precio_unitario, subtotal, fecha) 
                        VALUES ('TERMAS', 'FICHA_GACHAPON', %s, %s, %s, %s, %s)
                    """, (f"Ficha Gachapon ({col_sel})", cant_fichas, p_ficha, subt, datetime.now()), fetch=False)
                    st.success(f"Vendido: {cant_fichas} ficha/s {col_sel} (${subt:,.0f})")

            st.divider()
            
            tabs_colec = st.tabs([f"📦 {col}" for col in colecciones_unicas])
            for index, col_nombre in enumerate(colecciones_unicas):
                with tabs_colec[index]:
                    sub_df = df_gach[df_gach['Colección'] == col_nombre]
                    st.dataframe(sub_df[["Nº", "Premio", "En Máquina", "En Depósito"]], use_container_width=True)
        else:
            st.caption("No hay premios de Gachapon cargados aún.")

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
# 3. INVENTARIO (ALTAS, EDICIÓN DE PRECIOS Y ARQUEOS)
# -----------------------------------------------------------------------------
with tab_stock:
    st.header("📦 Inventario")
    
    # 1. ALTAS DIRECCIONADAS
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
                nuevo_precio = st.number_input("Precio ($):", min_value=0.0, value=1000.0)
                nuevo_stock = st.number_input("Stock Inicial:", min_value=0, value=1)
            
            if st.button("💾 Guardar Nuevo Producto", use_container_width=True):
                if nuevo_nombre:
                    try:
                        consulta("""
                            INSERT INTO productos (nombre, grupo, categoria, subgrupo, precio, stock) 
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (nuevo_nombre, nuevo_grupo, nueva_cat, nueva_cat, nuevo_precio, nuevo_stock), fetch=False)
                        st.success(f"¡Producto '{nuevo_nombre}' agregado correctamente!")
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
                    g_precio_ficha = st.number_input("Precio de la Ficha para esta colección ($):", min_value=0.0, value=2000.0)
                else:
                    g_colec = g_colec_sel
                    g_precio_ficha = 2000.0
            with col_g2:
                g_en_maq = st.number_input("Cantidad Inicial en Máquina:", min_value=0, value=1)
                g_en_dep = st.number_input("Cantidad Inicial en Depósito:", min_value=0, value=0)
            
            if st.button("💾 Guardar Personaje Gachapon", use_container_width=True):
                if g_nombre and g_colec:
                    try:
                        consulta("""
                            INSERT INTO gachapon_premios (numero, nombre, coleccion, en_maquina, stock_deposito, precio_ficha) 
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (g_num, g_nombre, g_colec, g_en_maq, g_en_dep, g_precio_ficha), fetch=False)
                        st.success(f"¡Personaje '{g_nombre}' guardado en la colección '{g_colec}'!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Error al guardar: {ex}")
                else:
                    st.warning("Completá el nombre del personaje y la colección.")

    # 2. CAMBIO DE PRECIOS
    with st.expander("✏️ Cambiar Precios (Productos o Fichas Gachapon)", expanded=False):
        tipo_precio = st.radio("Editar precio de:", ["Producto General", "Ficha de Colección Gachapon"], horizontal=True)
        
        if tipo_precio == "Producto General":
            if prods:
                p_edit = st.selectbox("Seleccionar Producto:", [p[1] for p in prods], key="sel_p_e")
                val_act = [p[3] for p in prods if p[1] == p_edit][0]
                p_nuevo = st.number_input(f"Nuevo Precio para {p_edit} ($):", value=float(val_act), min_value=0.0)
                if st.button("💾 Actualizar Precio Producto", use_container_width=True):
                    consulta("UPDATE productos SET precio = %s WHERE nombre = %s", (p_nuevo, p_edit), fetch=False)
                    st.success(f"¡Precio de {p_edit} actualizado a ${p_nuevo:,.0f}!")
                    st.rerun()
        else:
            colec_precios = consulta("SELECT DISTINCT coleccion, precio_ficha FROM gachapon_premios")
            if colec_precios:
                col_e = st.selectbox("Seleccionar Colección:", [c[0] for c in colec_precios], key="sel_c_e")
                p_f_act = [c[1] for c in colec_precios if c[0] == col_e][0]
                pf_nuevo = st.number_input(f"Nuevo Precio de Ficha para {col_e} ($):", value=float(p_f_act if p_f_act else 2000), min_value=0.0)
                if st.button("💾 Actualizar Precio de Ficha", use_container_width=True):
                    consulta("UPDATE gachapon_premios SET precio_ficha = %s WHERE coleccion = %s", (pf_nuevo, col_e), fetch=False)
                    st.success(f"¡Precio de ficha para {col_e} actualizado a ${pf_nuevo:,.0f}!")
                    st.rerun()

    # 3. ARQUEO DE MAQUINA GACHAPON
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

    # 4. MÓDULO PARA CARGAR FOTO
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
    prods_full = consulta("SELECT id, nombre, grupo, categoria, precio, stock FROM productos ORDER BY nombre ASC")
    if prods_full:
        df_stock = pd.DataFrame(prods_full, columns=["ID", "Producto", "Grupo", "Categoría", "Precio", "Stock"])
        st.dataframe(df_stock, use_container_width=True)

# -----------------------------------------------------------------------------
# 4. CAJA
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

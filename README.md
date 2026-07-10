# SAUDA – Dashboard Forecast Semanal (Streamlit)

Versión Streamlit del dashboard de forecast, pensada para desplegarse como
app web con login y lectura de datos desde el Lakehouse de Microsoft Fabric.
Incluye únicamente las vistas de **Gráfico** y **Tabla** (sin Historial ni
Mapa de Calor).

## Estructura

```
app.py               Entrypoint de Streamlit (filtros, métricas, tabs)
auth.py              Login usuario/contraseña (streamlit-authenticator)
data_source.py       Origen de datos: OneLake (Fabric) o parquet local
logic.py             Transformación de datos, filtros y métricas
charts.py            Gráfico interactivo (Plotly)
config.yaml          Usuarios y contraseñas (hasheadas) del login
scripts/generar_hash_password.py   Utilidad para hashear contraseñas
.streamlit/secrets.toml.example    Plantilla de configuración de OneLake
```

## 1. Instalación

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## 2. Configurar el login

1. Elegí un usuario y contraseña, y generá el hash:
   ```bash
   python scripts/generar_hash_password.py "la_contraseña_elegida"
   ```
2. Copiá el usuario, nombre, email y hash en `config.yaml`.
3. Cambiá `cookie.key` por una cadena aleatoria propia (invalida sesiones si se cambia).

`config.yaml` está en `.gitignore`: no debe subirse al repositorio con
contraseñas reales. Al desplegar en Streamlit Community Cloud, pegar el
contenido completo como un secret adicional (ver paso 4) en vez de subir el archivo.

## 3. Configurar el origen de datos

Copiá `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` y completá:

- **Modo desarrollo (sin Lakehouse):** dejar `DATA_SOURCE = "parquet"` y copiar
  el archivo `forecast_final_semanal.parquet` que genera el pipeline dentro de
  `Data/`.
- **Modo producción (OneLake / Lakehouse de Fabric):** poner `DATA_SOURCE = "onelake"`
  y completar:
  - `ONELAKE_WORKSPACE` / `ONELAKE_LAKEHOUSE`: nombre del workspace y del
    Lakehouse en Fabric (se ven en la URL al abrir el Lakehouse en
    `app.fabric.microsoft.com`).
  - `ONELAKE_TABLA_FORECAST`: nombre de la tabla Delta dentro del Lakehouse.
  - `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET`: credenciales
    de un **Service Principal** (App registration en Microsoft Entra ID) al
    que se le otorga acceso de lectura al workspace de Fabric (rol *Viewer*).
    Es la identidad con la que la app lee los datos — no se usan las
    credenciales del usuario que abre el dashboard.

## 4. Desplegar en Streamlit Community Cloud

1. Subir este proyecto a un repositorio (GitHub/GitLab/Bitbucket) — **sin**
   `config.yaml` ni `.streamlit/secrets.toml` reales (quedan afuera por
   `.gitignore`).
2. En [share.streamlit.io](https://share.streamlit.io), crear la app apuntando
   a `app.py`.
3. En *App settings → Secrets*, pegar en formato TOML:
   - Todo el contenido de `.streamlit/secrets.toml` (con `DATA_SOURCE = "onelake"`
     y los datos reales del Service Principal), **y además** el contenido de
     `config.yaml` bajo una clave propia, por ejemplo:
     ```toml
     DATA_SOURCE = "onelake"
     ONELAKE_WORKSPACE = "..."
     # ... resto de secrets.toml ...

     [auth_config]
     # contenido de config.yaml pegado acá si se prefiere no subir el archivo
     ```
     (Si se sube `config.yaml` directamente al repo privado en cambio, no
     hace falta duplicarlo en Secrets — pero entonces las contraseñas quedan
     en el repositorio, aunque sea privado.)

### Por qué OneLake y no el SQL Analytics Endpoint

Streamlit Community Cloud corre en un contenedor Linux sobre el que **no se
puede instalar el ODBC Driver de Microsoft** (el mecanismo de `packages.txt`
solo instala paquetes de los repos estándar de Debian; no hay forma soportada
de agregar el repositorio de Microsoft que provee `msodbcsql18`). Por eso
`data_source.py` lee la tabla Delta **directo de OneLake** con el paquete
`deltalake` (Python puro, sin drivers de sistema) en vez de conectarse por el
SQL Analytics Endpoint vía `pyodbc`.

Si en algún momento se despliega en infraestructura propia (VM, Azure App
Service, contenedor Docker propio) donde sí se puede instalar el driver ODBC,
se puede volver a la variante SQL Analytics Endpoint sin tocar el resto de la
app — alcanza con reescribir `cargar_forecast_raw()` en `data_source.py`.

**Importante:** la conexión a OneLake vía `deltalake` no se pudo probar contra
un Lakehouse real durante el desarrollo (no había credenciales de un tenant de
Fabric disponibles). Las claves de `storage_options` usadas
(`azure_tenant_id`, `azure_client_id`, `azure_client_secret`,
`use_fabric_endpoint`) se verificaron como reconocidas por la librería, pero
conviene probar la conexión con las credenciales reales antes de dar por
cerrado el despliegue — si falla, el mensaje de error de `deltalake` suele
indicar bastante bien si el problema es de autenticación (revisar el rol del
Service Principal en el workspace) o de la ruta (revisar
`ONELAKE_WORKSPACE`/`ONELAKE_LAKEHOUSE`/nombre de tabla).

## 5. Ejecutar en local

```bash
streamlit run app.py
```

## Notas sobre la conexión a OneLake

- OneLake es de **solo lectura** desde la app y se actualiza automáticamente a
  medida que el pipeline escribe nuevas versiones de la tabla Delta — no
  requiere ningún paso adicional en el pipeline.
- Las consultas se cachean 10 minutos (`st.cache_data` para el origen de
  datos, `st.cache_resource` para el DataFrame ya transformado) para no
  pegarle a OneLake en cada interacción de filtro; el botón "🔄 Recargar
  datos" limpia el caché a demanda.

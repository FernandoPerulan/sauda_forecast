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
runtime.txt          Fija la versión de Python en Streamlit Cloud
scripts/generar_hash_password.py   Utilidad para hashear contraseñas
scripts/probar_onelake.py          Prueba standalone de la conexión a OneLake
.streamlit/secrets.toml.example    Plantilla de configuración (login + OneLake)
```

Usuarios, contraseñas (hasheadas) y credenciales del Lakehouse viven **todas
en `st.secrets`** (`.streamlit/secrets.toml` en local, "Secrets" de la app en
Streamlit Community Cloud) — no hay ningún archivo de credenciales que se
suba al repositorio.

## 1. Instalación

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## 2. Configurar el login

Copiá `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` (si no lo
hiciste ya en el paso siguiente) y completá la sección `[auth]`:

1. Elegí un usuario y contraseña, y generá el hash:
   ```bash
   python scripts/generar_hash_password.py "la_contraseña_elegida"
   ```
2. Agregá un bloque `[auth.credentials.usernames.<usuario>]` con `name`,
   `email` y el hash generado como `password` (ver el ejemplo ya incluido
   en el `.example`).
3. Cambiá `auth.cookie_key` por una cadena aleatoria propia (invalida
   sesiones activas si se cambia).

`.streamlit/secrets.toml` está en `.gitignore`: nunca se sube al repositorio
con contraseñas reales. Al desplegar en Streamlit Community Cloud, este mismo
contenido se pega en *App settings → Secrets* (ver paso 4).

## 3. Configurar el origen de datos

**Modo desarrollo (sin Lakehouse):** en `.streamlit/secrets.toml` dejar
`DATA_SOURCE = "parquet"` y copiar el archivo `forecast_final_semanal.parquet`
que genera el pipeline dentro de `Data/`. Para producción, seguir el tutorial
de abajo.

### 3.1 Tutorial paso a paso: configurar OneLake / Lakehouse de Fabric

**Paso 1 — Crear el Service Principal (App registration) en Microsoft Entra ID**

1. Entrar a [portal.azure.com](https://portal.azure.com) → buscar
   **Microsoft Entra ID** → **Registros de aplicaciones** (*App registrations*)
   → **Nuevo registro**.
2. Nombre: algo identificable, ej. `sauda-forecast-streamlit`.
3. Tipo de cuenta admitida: *"Cuentas solo en este directorio organizativo"*
   (single tenant). No hace falta URI de redirección.
4. Clic en **Registrar**.
5. En la página *Overview* de la app recién creada, copiar:
   - **Id. de aplicación (cliente)** → va en `AZURE_CLIENT_ID`.
   - **Id. de directorio (inquilino)** → va en `AZURE_TENANT_ID`.

**Paso 2 — Generar el Client Secret**

1. Dentro de la misma app registrada, ir a **Certificados y secretos**
   (*Certificates & secrets*) → **Nuevo secreto de cliente**.
2. Poner una descripción y una expiración (ej. 12 o 24 meses — al vencer, hay
   que generar uno nuevo y actualizar el secret en Streamlit).
3. Copiar el **Valor** del secreto apenas se genera — Azure solo lo muestra
   una vez. Va en `AZURE_CLIENT_SECRET`.

**Paso 3 — Habilitar Service Principals en el tenant de Fabric (una sola vez)**

Este paso lo hace un administrador del tenant de Fabric/Power BI, y suele
pasarse por alto:

1. En [app.fabric.microsoft.com](https://app.fabric.microsoft.com), ícono de
   engranaje → **Configuración de administración** (*Admin portal*) →
   **Configuración del inquilino** (*Tenant settings*).
2. Buscar la sección **Configuración de desarrollador** y habilitar
   **"Los service principals pueden usar las API de Fabric"** (*Service
   principals can use Fabric APIs*) — como mínimo para el grupo de seguridad
   al que pertenece el Service Principal creado en el Paso 1.
3. Sin este paso, el Service Principal no puede autenticarse contra
   Fabric/OneLake aunque tenga permisos en el workspace — es la causa más
   común de errores de autenticación "silenciosos".

**Paso 4 — Dar acceso del Service Principal al workspace**

1. En Fabric, abrir el workspace donde está el Lakehouse.
2. Ícono de personas / **Gestionar acceso** (*Manage access*) → **Agregar
   personas o grupos**.
3. Buscar por el **nombre** de la app registrada en el Paso 1 (Fabric la
   encuentra como si fuera un usuario más).
4. Asignar el rol **Viewer** (alcanza para lectura; no hace falta más).

**Paso 5 — Identificar el workspace, el Lakehouse y la tabla**

1. Abrir el Lakehouse en Fabric y mirar la URL del navegador:
   ```
   https://app.fabric.microsoft.com/groups/<WORKSPACE>/lakehouses/<lakehouse-id>
   ```
   `<WORKSPACE>` (nombre o GUID) va en `ONELAKE_WORKSPACE`.
2. El nombre del Lakehouse (sin la palabra "Lakehouse", tal como aparece en
   el panel izquierdo de Fabric) va en `ONELAKE_LAKEHOUSE`.
3. Dentro del Lakehouse, en el panel **Tables**, revisar si las tablas están
   agrupadas dentro de una carpeta de esquema (ej. `dbo`) — eso pasa cuando el
   Lakehouse tiene *esquemas* habilitados. Si es así, ese nombre (`dbo`) va en
   `ONELAKE_SCHEMA`; si las tablas aparecen sueltas directamente bajo
   **Tables** (sin carpeta intermedia), dejar `ONELAKE_SCHEMA` vacío.
4. Confirmar el nombre exacto de la tabla del forecast (debe ser una tabla
   administrada/Delta, no un archivo suelto en *Files*) → va en
   `ONELAKE_TABLA_FORECAST`.

**Paso 6 — Completar `.streamlit/secrets.toml`**

```toml
DATA_SOURCE = "onelake"

ONELAKE_WORKSPACE = "mi-workspace"
ONELAKE_LAKEHOUSE = "MiLakehouse"
ONELAKE_SCHEMA = "dbo"                 # vacío ("") si el Lakehouse no tiene esquemas
ONELAKE_TABLA_FORECAST = "forecast_final_semanal"

AZURE_TENANT_ID = "<Id. de directorio del Paso 1>"
AZURE_CLIENT_ID = "<Id. de aplicación del Paso 1>"
AZURE_CLIENT_SECRET = "<Valor del secreto del Paso 2>"
```

**Paso 7 — Probar la conexión antes de desplegar**

Correr el script de prueba standalone (no necesita levantar Streamlit):

```bash
python scripts/probar_onelake.py
```

Si imprime la cantidad de filas y las columnas, la conexión funciona y se
puede pasar a desplegar. Si falla, ver la sección de errores comunes abajo.

**Errores comunes**

| Síntoma | Causa probable |
|---|---|
| Error de autenticación / tenant inválido | `AZURE_TENANT_ID`/`AZURE_CLIENT_ID` mal copiados (revisar que sean GUIDs completos) |
| `403` / `Forbidden` / permission denied | Falta el Paso 3 (Service principals habilitados en el tenant) o el Paso 4 (rol Viewer en el workspace) |
| `404` / *path not found* | `ONELAKE_WORKSPACE`, `ONELAKE_LAKEHOUSE` o el nombre de tabla no coinciden exactamente (mayúsculas/minúsculas incluidas) con lo que muestra Fabric |
| El secreto dejó de funcionar de un día para otro | El Client Secret venció (ver fecha de expiración elegida en el Paso 2) — generar uno nuevo |

## 4. Desplegar en Streamlit Community Cloud

1. Subir este proyecto a un repositorio (GitHub/GitLab/Bitbucket) — **sin**
   `.streamlit/secrets.toml` real (queda afuera por `.gitignore`).
2. En [share.streamlit.io](https://share.streamlit.io), crear la app apuntando
   a `app.py`.
3. En *App settings → Secrets*, pegar tal cual el contenido completo de tu
   `.streamlit/secrets.toml` local (con `DATA_SOURCE = "onelake"`, los datos
   reales del Service Principal, y la sección `[auth]` con tus usuarios).

### Versión de Python (`runtime.txt`)

`runtime.txt` fija `python-3.12`. Sin este archivo, Streamlit Cloud puede
asignar una versión de Python muy nueva para la que paquetes como `pandas` o
`numpy` todavía no tienen instaladores (`wheels`) precompilados — obliga a
compilarlos desde el código fuente en cada build, lo que puede tardar
decenas de minutos y hacer que el build se corte a la mitad (dependencias
instaladas parcialmente). Si en el futuro se actualizan las versiones de
`requirements.txt`, conviene revisar que `runtime.txt` siga apuntando a una
versión de Python con buena cobertura de wheels para esas versiones.

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

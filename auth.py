"""
Login usuario/contraseña con streamlit-authenticator.

Usuarios, hashes de contraseña y clave de cookie viven en st.secrets bajo la
sección [auth] (.streamlit/secrets.toml en local, "Secrets" de la app en
Streamlit Community Cloud) — nunca en un archivo commiteado al repositorio.
"""

import streamlit as st
import streamlit_authenticator as stauth

authenticator: stauth.Authenticate | None = None


def _a_dict_plano(valor):
    if hasattr(valor, "to_dict"):
        valor = valor.to_dict()
    if isinstance(valor, dict):
        return {k: _a_dict_plano(v) for k, v in valor.items()}
    return valor


def require_login() -> str:
    """Muestra el formulario de login y detiene la app hasta que el usuario ingrese.

    Devuelve el nombre del usuario autenticado.
    """
    global authenticator

    # Authenticate() inicializa varias claves de st.session_state (entre
    # ellas "logout") la primera vez que se instancia. Si se construyera una
    # sola vez a nivel de módulo, Python cachea el import y esa
    # inicialización correría solo para la primera sesión del proceso —
    # cualquier otra sesión posterior en el mismo proceso (otro usuario, u
    # otra pestaña) rompería con KeyError al leer la cookie. Por eso se
    # reconstruye en cada rerun, dentro de esta función.
    auth_cfg = st.secrets["auth"]
    credentials = _a_dict_plano(auth_cfg["credentials"])
    authenticator = stauth.Authenticate(
        credentials,
        auth_cfg["cookie_name"],
        auth_cfg["cookie_key"],
        int(auth_cfg.get("cookie_expiry_days", 7)),
    )

    authenticator.login()

    estado = st.session_state.get("authentication_status")

    if estado is False:
        st.error("Usuario o contraseña incorrectos.")
        st.stop()
    elif estado is None:
        st.info("Ingresá tus credenciales para acceder al dashboard.")
        st.stop()

    return st.session_state["name"]

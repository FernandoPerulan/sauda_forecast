"""
Login usuario/contraseña con streamlit-authenticator.

Credenciales y clave de cookie en config.yaml (ver ese archivo para agregar usuarios).
"""

from pathlib import Path

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"

with open(_CONFIG_PATH, encoding="utf-8") as f:
    _config = yaml.load(f, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    _config["credentials"],
    _config["cookie"]["name"],
    _config["cookie"]["key"],
    _config["cookie"]["expiry_days"],
)


def require_login() -> str:
    """Muestra el formulario de login y detiene la app hasta que el usuario ingrese.

    Devuelve el nombre del usuario autenticado.
    """
    authenticator.login()

    estado = st.session_state.get("authentication_status")

    if estado is False:
        st.error("Usuario o contraseña incorrectos.")
        st.stop()
    elif estado is None:
        st.info("Ingresá tus credenciales para acceder al dashboard.")
        st.stop()

    return st.session_state["name"]

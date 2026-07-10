"""
Genera el hash bcrypt de una contraseña para pegarlo en config.yaml.

Uso:
    python scripts/generar_hash_password.py "mi_contraseña"
"""

import sys

import streamlit_authenticator as stauth


def main():
    if len(sys.argv) != 2:
        print('Uso: python scripts/generar_hash_password.py "mi_contraseña"')
        sys.exit(1)

    password = sys.argv[1]
    print(stauth.Hasher.hash(password))


if __name__ == "__main__":
    main()

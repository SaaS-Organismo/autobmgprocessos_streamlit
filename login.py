import streamlit as st
from decouple import config

# Carregar credenciais do .env
LOGIN = config("LOGIN")
PASSWORD = config("PASSWORD")


def run():
    st.title("AutoBMG Processos")

    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        if username == LOGIN and password == PASSWORD:
            st.success("Login realizado com sucesso!")
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos!")
            
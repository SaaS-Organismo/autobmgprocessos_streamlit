import streamlit as st

# Import pages
import login
import upload_form
import list_files

# Gerenciar estado de autenticação
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Create a multi-page application
PAGES = {
    "Login": login,
    "Upload Form": upload_form,
    "List Files": list_files,
}

# Verificar autenticação
if not st.session_state.authenticated:
    # Forçar exibição da página de login
    page = PAGES["Login"]
else:
    page = PAGES["Upload Form"]

with st.spinner(f"Loading  ..."):
    page.run()


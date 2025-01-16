import streamlit as st

import list_files
import login
import upload_form

# Initialize the session state variable at the very beginning.
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

import streamlit as st

# Import pages
import upload_form
import list_files

# Create a multi-page application
PAGES = {
    "Upload Form": upload_form,
    "List Files": list_files,
}


page = PAGES["Upload Form"]


with st.spinner(f"Loading  ..."):
    page.run()

import streamlit as st

st.set_page_config(page_title="Truetone")

page = st.sidebar.radio("Navigation", ["Déposer", "Vérifier"])

st.title(page)

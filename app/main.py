"""Точка входа Streamlit: разделы через st.navigation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

st.set_page_config(
    page_title="Галерея",
    page_icon="🗂️",
    layout="wide",
)

navigation = st.navigation(
    [
        st.Page("ui/gallery.py", title="Галерея", icon="🗂️", default=True, url_path="gallery"),
        st.Page("ui/notepad.py", title="Блокнот", icon="📝", url_path="notepad"),
        st.Page("ui/constructor.py", title="Конструктор", icon="✏️", url_path="constructor"),
        st.Page("ui/history.py", title="История", icon="🕘", url_path="history"),
        st.Page("ui/showcase.py", title="Витрина", icon="📊", url_path="showcase"),
    ]
)

navigation.run()

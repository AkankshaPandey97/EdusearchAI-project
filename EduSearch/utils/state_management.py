import streamlit as st
from typing import Dict, Any

class StateManager:
    @staticmethod
    def initialize_session_state():
        if "error" not in st.session_state:
            st.session_state.error = None
        if "playlists" not in st.session_state:
            st.session_state.playlists = None
        if "selected_playlist" not in st.session_state:
            st.session_state.selected_playlist = None
        if "playlist_data" not in st.session_state:
            st.session_state.playlist_data = None

    @staticmethod
    def handle_error(error: str):
        st.session_state.error = error
        st.error(error) 
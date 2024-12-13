import os
from dotenv import load_dotenv
import streamlit as st
from pages.dashboard import show_dashboard
from pages.playlist_page import show_playlist_page
from utils.state_management import StateManager
from config.api_config import ENDPOINTS
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set the environment variable for Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
# Initialize session state
StateManager.initialize_session_state()

# Set page config
st.set_page_config(
    page_title="EduSearch AI",
    page_icon="📚",
    layout="wide"
)

# Initialize session state variables
if "active_page" not in st.session_state:
    st.session_state.active_page = "Dashboard"
if "selected_playlist" not in st.session_state:
    st.session_state.selected_playlist = None

def set_active_page(page_name: str):
    st.session_state.active_page = page_name

# Display current page
if st.session_state.active_page == "Dashboard":
    show_dashboard(set_active_page)
elif st.session_state.active_page == "Playlist Page":
    show_playlist_page(set_active_page)

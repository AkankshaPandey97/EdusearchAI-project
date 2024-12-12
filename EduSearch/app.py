import os
from dotenv import load_dotenv
import streamlit as st
from pages.dashboard import show_dashboard
from pages.playlist_page import show_playlist_page

# Load environment variables from the .env file
load_dotenv()

# Set the environment variable for Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Set up the page configuration
st.set_page_config(page_title="EduSearch AI", layout="wide")

# Initialize session state variables
if "active_page" not in st.session_state:
    st.session_state.active_page = "Dashboard"
if "selected_playlist" not in st.session_state:
    st.session_state.selected_playlist = None

# Helper function to switch pages
def set_active_page(page_name):
    st.session_state.active_page = page_name

# Render the UI based on the active page
if st.session_state.active_page == "Dashboard":
    show_dashboard(set_active_page)

elif st.session_state.active_page == "Playlist Page":
    show_playlist_page(set_active_page)

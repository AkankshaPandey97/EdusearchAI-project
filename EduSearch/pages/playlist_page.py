import streamlit as st
from utils.api_client import APIClient
import asyncio
import requests

async def load_playlist_data(playlist_id: str):
    return await APIClient.get_playlist_details(playlist_id)

def fetch_course_summary(course_title: str) -> str:
    try:
        response = requests.get(f"http://127.0.0.1:8000/api/v1/summarize/{course_title}")
        response.raise_for_status()
        data = response.json()
        return data.get("summary", "No summary available.")
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching course summary: {str(e)}")
        return "An error occurred while fetching the course summary."

def show_playlist_page(set_active_page):
    """
    Renders the playlist page with interactive tools.
    Args:
        set_active_page (function): Function to set the active page for navigation.
    """
    # Get the selected playlist details from session state
    selected_playlist_title = st.session_state.get("selected_playlist_title", "Unknown Playlist")
    selected_playlist_id = st.session_state.get("selected_playlist", "Unknown Playlist ID")

    # Page Title and Subtitle
    st.title(f"Playlist: {selected_playlist_title}")
    st.subheader(f"Playlist ID: {selected_playlist_id}")

    # Load playlist data if not in session state
    if "playlist_data" not in st.session_state:
        with st.spinner("Loading playlist data..."):
            st.session_state.playlist_data = asyncio.run(
                load_playlist_data(selected_playlist_id)
            )
    
    playlist_data = st.session_state.playlist_data

    # Create a container for tools
    tools_container = st.container()
    
    # Create 4 columns for different tools
    with tools_container:
        tools_col1, tools_col2, tools_col3, tools_col4 = st.columns(4)

        with tools_col1:
            if st.button("Generate Summary"):
                with st.spinner("Generating summary..."):
                    try:
                        # URL encode the title to handle spaces and special characters
                        encoded_title = requests.utils.quote(selected_playlist_title)
                        response = requests.get(f"http://127.0.0.1:8000/api/v1/summarize/{encoded_title}")
                        response.raise_for_status()
                        data = response.json()
                        if data.get("summary"):
                            st.write("Summary:", data["summary"])
                        else:
                            st.warning("No summary available for this course.")
                    except requests.exceptions.RequestException as e:
                        st.error(f"Error generating summary: {str(e)}")
                        if hasattr(e.response, 'json'):
                            st.error(f"Server error: {e.response.json().get('detail', 'Unknown error')}")

        with tools_col2:
            st.subheader("Topic Segmentation")
            if st.button("Segment Topics"):
                with st.spinner("Segmenting topics..."):
                    try:
                        response = requests.post(
                            "http://localhost:8000/api/v1/segments",
                            json={
                                "course_title": selected_playlist_title
                            }
                        )
                        if response.status_code == 200:
                            data = response.json()
                            if data["success"] and data["segments"]:
                                st.write("Course Segments:")
                                # Create an expander for segments
                                with st.expander("View All Segments", expanded=True):
                                    for segment in data["segments"]:
                                        # Create a card-like display for each segment
                                        st.markdown(f"""
                                        ---
                                        #### Segment {segment['segment_number']}
                                        **{segment['formatted_title']}**
                                        <details>
                                        <summary>Original Title</summary>
                                        <small>{segment['title']}</small>
                                        </details>
                                        """, unsafe_allow_html=True)
                            else:
                                st.info("No segments found for this course.")
                        else:
                            st.error("Failed to fetch segments")
                    except Exception as e:
                        st.error(f"Error fetching segments: {str(e)}")

        with tools_col3:
            st.subheader("Research Notes")
            if st.button("Display Research Notes"):
                with st.spinner("Loading research notes..."):
                    notes = asyncio.run(
                        APIClient.get_research_notes(selected_playlist_id)
                    )
                    st.write(notes)

        with tools_col4:
            st.subheader("Citations")
            if st.button("Generate Citation"):
                with st.spinner("Generating citations..."):
                    try:
                        response = requests.post(
                            "http://localhost:8000/api/v1/citation/generate",
                            json={
                                "content": selected_playlist_title,
                                "style": "APA"
                            }
                        )
                        if response.status_code == 200:
                            data = response.json()
                            if data["success"] and data["citations"]:
                                st.write("References:")
                                for citation in data["citations"]:
                                    st.write(f"- [{citation['source']}]({citation['url']})")
                            else:
                                st.info("No citations found for this course.")
                        else:
                            st.error("Failed to generate citations")
                    except Exception as e:
                        st.error(f"Error generating citations: {str(e)}")

    # Q&A Section
    st.markdown("---")
    st.subheader("Ask Questions")
    question = st.text_input("Enter your question about the course content:")
    if question and st.button("Ask"):
        with st.spinner("Processing your question..."):
            try:
                response = requests.post(
                    "http://localhost:8000/api/v1/qa",  # Updated endpoint URL
                    json={
                        "question": question,
                        "course_title": selected_playlist_title
                    },
                    headers={
                        "Content-Type": "application/json"
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        st.write("Answer:", data["data"]["answer"])
                    else:
                        st.error(data.get("message", "Failed to get answer"))
                else:
                    st.error(f"Server error: {response.status_code}")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

    # Example: Display course summary for a selected course
    #course_title = st.selectbox("Select a course", ["Course 1", "Course 2", "Course 3"])
    #if course_title:
    #    summary = fetch_course_summary(course_title)
    #    st.write("Course Summary:")
    #    st.write(summary)

    # Navigation Back to Dashboard
    st.markdown("---")
    if st.button("Back to Dashboard"):
        # Clear playlist-specific session state
        if "playlist_data" in st.session_state:
            del st.session_state.playlist_data
        set_active_page("Dashboard")

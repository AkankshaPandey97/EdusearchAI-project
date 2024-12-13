import streamlit as st
from google.cloud import bigquery
from utils.api_client import APIClient
import asyncio
import requests
from googleapiclient.discovery import build
import os
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# YouTube API setup with error handling
def get_youtube_client():
    try:
        # Get API key from .env file
        api_key = os.getenv('YOUTUBE_API_KEY')
        
        if not api_key:
            st.error("YouTube API key not found in .env file")
            return None
            
        return build('youtube', 'v3', developerKey=api_key)
    except Exception as e:
        st.error(f"Failed to initialize YouTube client: {str(e)}")
        return None

async def load_playlist_data(playlist_id: str):
    return await APIClient.get_playlist_details(playlist_id)

def fetch_playlist_details(playlist_id):
    """
    Fetches detailed information for a specific playlist using its playlist_id.
    """
    try:
        client = bigquery.Client()
        query = f"""
        SELECT
            playlist_id,
            title,
            description,
            instructors,
            ARRAY_AGG(DISTINCT t.topic) AS topics,
            ARRAY_AGG(DISTINCT subtopic) AS subtopics
        FROM `finalproject-442400.coursesdata.Courses`,
        UNNEST(topics) AS t,
        UNNEST(t.subtopics) AS subtopic
        WHERE playlist_id = '{playlist_id}'
        GROUP BY playlist_id, title, description, instructors
        LIMIT 1
        """
        query_job = client.query(query)
        results = query_job.result()

        for row in results:
            topics = ", ".join(row.topics) if row.topics else "N/A"
            subtopics = ", ".join(row.subtopics) if row.subtopics else "N/A"
            topic_details = f"{topics} ({subtopics})" if subtopics != "N/A" else topics

            return {
                "playlist_id": row.playlist_id,
                "title": row.title,
                "description": row.description or "No description available.",
                "instructors": row.instructors or "No instructors available.",
                "topics": topic_details or "No topics available.",
            }
    except Exception as e:
        st.error(f"Error fetching playlist details: {e}")
        return None

def get_playlist_videos(playlist_id):
    """Fetch videos from YouTube playlist with better error handling"""
    try:
        youtube = get_youtube_client()
        if not youtube:
            return []

        videos = []
        request = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50
        )
        
        try:
            response = request.execute()
            
            for item in response.get('items', []):
                snippet = item.get('snippet', {})
                video_id = snippet.get('resourceId', {}).get('videoId')
                title = snippet.get('title', 'Untitled Video')
                if video_id:
                    videos.append({
                        'id': video_id,
                        'title': title
                    })
            return videos
            
        except HttpError as e:
            if e.resp.status == 403:
                st.error("API quota exceeded or authentication error. Please check your API key.")
            elif e.resp.status == 404:
                st.error("Playlist not found or is private.")
            else:
                st.error(f"YouTube API error: {str(e)}")
            return []
            
    except Exception as e:
        st.error(f"Error fetching YouTube videos: {str(e)}")
        return []

def show_playlist_page(set_active_page):
    """
    Renders the playlist page with interactive tools and dynamic content.
    """
    # Get the selected playlist details from session state
    selected_playlist_title = st.session_state.get("selected_playlist_title", "Unknown Playlist")
    selected_playlist_id = st.session_state.get("selected_playlist", "Unknown Playlist ID")

    if not selected_playlist_id:
        st.error("No playlist selected. Please go back to the dashboard and select a playlist.")
        return

    # Load playlist data if not in session state
    if "playlist_data" not in st.session_state:
        with st.spinner("Loading playlist data..."):
            st.session_state.playlist_data = asyncio.run(
                load_playlist_data(selected_playlist_id)
            )
    
    playlist_data = st.session_state.playlist_data

    # Apply custom CSS with dark theme
    st.markdown(
        """
        <style>
        .main-container {
            background-color: #1a1a1a;
            color: #ffffff;
            padding: 20px;
            border-radius: 10px;
        }
        .title {
            background-color: #FFD700;
            color: black;
            text-align: center;
            font-size: 24px;
            font-weight: bold;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .video-section {
            background-color: #2d2d2d;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .qa-section {
            background-color: #2d2d2d;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .tool-button {
            background-color: #4a4a4a;
            color: white;
            border: none;
            padding: 10px;
            border-radius: 5px;
            margin: 5px;
            cursor: pointer;
        }
        .tool-button:hover {
            background-color: #666666;
        }
        </style>
        """, unsafe_allow_html=True
    )

    # Main container
    with st.container():
        st.markdown("<div class='main-container'>", unsafe_allow_html=True)

        # Title
        st.markdown(f"<div class='title'>{selected_playlist_title}</div>", unsafe_allow_html=True)

        # Two-column layout for Video and Q&A
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("<div class='video-section'>", unsafe_allow_html=True)
            st.markdown("### 🎥 Video Section")
            
            # Add a loading indicator
            with st.spinner("Loading playlist videos..."):
                videos = get_playlist_videos(selected_playlist_id)
                
            if videos:
                selected_video = st.selectbox(
                    "Select Video",
                    options=videos,
                    format_func=lambda x: x['title']
                )
                if selected_video:
                    try:
                        video_url = f"https://youtu.be/{selected_video['id']}"
                        st.video(video_url)
                    except Exception as e:
                        st.error(f"Error playing video: {str(e)}")
            else:
                st.info("No videos available in this playlist")
            st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            st.markdown("<div class='qa-section'>", unsafe_allow_html=True)
            st.markdown("### 💬 Q&A Section")
            question = st.text_input("Ask a question:", placeholder="Type your question here...")
            if st.button("Get Answer"):
                if question:
                    with st.spinner("Processing your question..."):
                        try:
                            response = requests.post(
                                "http://localhost:8000/api/v1/qa",
                                json={
                                    "question": question,
                                    "course_title": selected_playlist_title
                                },
                                headers={"Content-Type": "application/json"}
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
            st.markdown("</div>", unsafe_allow_html=True)

        # Tools Section
        st.markdown("### 🛠️ Additional Tools")
        tool_cols = st.columns(4)

        # Tool buttons with consistent styling
        with tool_cols[0]:
            if st.button("📜 Summarize", key="summarize", help="Generate course summary"):
                with st.spinner("Generating summary..."):
                    try:
                        encoded_title = requests.utils.quote(selected_playlist_title)
                        response = requests.get(f"http://127.0.0.1:8000/api/v1/summarize/{encoded_title}")
                        response.raise_for_status()
                        data = response.json()
                        if data.get("summary"):
                            with st.expander("Course Summary", expanded=True):
                                st.write(data["summary"])
                        else:
                            st.warning("No summary available for this course.")
                    except requests.exceptions.RequestException as e:
                        st.error(f"Error generating summary: {str(e)}")
                        if hasattr(e.response, 'json'):
                            st.error(f"Server error: {e.response.json().get('detail', 'Unknown error')}")

        with tool_cols[1]:
            if st.button("📑 Segment Topics", key="segment", help="View course segments"):
                with st.spinner("Segmenting topics..."):
                    try:
                        response = requests.post(
                            "http://localhost:8000/api/v1/segments",
                            json={"course_title": selected_playlist_title}
                        )
                        if response.status_code == 200:
                            data = response.json()
                            if data["success"] and data["segments"]:
                                with st.expander("Course Segments", expanded=True):
                                    for segment in data["segments"]:
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

       # with tool_cols[2]:
            #if st.button("📝 Display Notes", key="notes", help="View course notes"):
             #   st.info("Notes feature coming soon!")

        with tool_cols[2]:
            if st.button("🔗 Notes & Citation", key="citation", help="Notes & citations"):
                with st.spinner("Generating Notes & Citations..."):
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
                                with st.expander("References", expanded=True):
                                    for citation in data["citations"]:
                                        st.markdown(f"- [{citation['source']}]({citation['url']})")
                            else:
                                st.info("No citations found for this course.")
                        else:
                            st.error("Failed to generate citations")
                    except Exception as e:
                        st.error(f"Error generating citations: {str(e)}")

        # Navigation
        st.markdown("---")
        if st.button("🔙 Back to Dashboard", use_container_width=True):
            if "playlist_data" in st.session_state:
                del st.session_state.playlist_data
            set_active_page("Dashboard")

        st.markdown("</div>", unsafe_allow_html=True)
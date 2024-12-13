import streamlit as st
from google.cloud import bigquery
 
def fetch_playlist_details(playlist_id):
    """
    Fetches detailed information for a specific playlist using its playlist_id.
    Args:
        playlist_id (str): The ID of the playlist to fetch.
    Returns:
        dict: A dictionary with playlist details or None if not found.
    """
    try:
        # Initialize BigQuery client
        client = bigquery.Client()
 
        # Query to fetch playlist details
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
        query_job = client.query(query)  # Execute the query
        results = query_job.result()    # Get the query results
 
        # Extract and return the playlist details
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
 
def show_playlist_page(set_active_page):
    """
    Renders the playlist page with interactive tools and dynamically fetched playlist details.
    Args:
        set_active_page (function): Function to set the active page for navigation.
    """
    # Fetch the selected playlist_id from session state
    playlist_id = st.session_state.get("selected_playlist")
    if not playlist_id:
        st.error("No playlist selected. Please go back to the dashboard and select a playlist.")
        return
 
    # Fetch playlist details dynamically
    with st.spinner("Fetching playlist details..."):
        playlist_details = fetch_playlist_details(playlist_id)
 
    if not playlist_details:
        st.error("Unable to fetch playlist details. Please try again later.")
        return
 
    # Apply custom CSS for consistent button sizes, details styling, and light grey background
    st.markdown(
        """
        <style>
        /* Main container styling */
        .main-container {
            background-color: #f9f9f9;
            padding: 0;
            border-radius: 2px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }
        /* Title styling with rounded corners */
        .title {
            background-color: #FFEB3B;  /* Yellow background */
            color: black;
            text-align: center;
            font-size: 32px;
            font-weight: bold;
            padding: 15px;
            border-radius: 15px;  /* Rounded corners */
            margin-bottom: 10px;
            box-shadow: 0px 3px 6px rgba(0, 0, 0, 0.1); /* Subtle shadow */
        }
        /* Playlist ID styling */
        .playlist-id {
            color: #6c757d;  /* Grey color */
            text-align: center;
            font-size: 14px;
            font-style: italic;
            font-weight: bold;
            margin-bottom: 30px;
        }
        /* Details styling for description, instructors, and topics */
        .details {
            text-align: left;  /* Left-aligned text */
            font-size: 16px;  /* Smaller font size */
            color: #f9f9f9;  /* light grey text color */
            margin: 10px auto;
            line-height: 1.6;  /* Slightly increased line height for readability */
            max-width: 90%;  /* Limit width for better readability */
        }
        /* Divider styling */
        .divider {
            margin: 40px 0; /* Spacing above and below the divider */
            border: none;    /* No visible border */
            height: 1px;     /* Thickness of the divider line */
            background-color: rgba(128, 128, 128, 0.2); /* Dark gray with 20% opacity */
        }
        /* Q&A Section title styling */
        .qa-title {
            background-color: rgba(255, 235, 59, 0.8); /* Light yellow with 40% opacity */
            color: black;
            padding: 10px 15px;
            border-radius: 8px;
            display: inline-block;
            font-size: 18px;
            font-weight: bold;
        }
        /* Uniform button styling for Additional Tools */
        .tool-button {
            width: 220px;  /* Set uniform width */
            height: 120px;  /* Enforce uniform height */
            background-color: #f5f5f5;  /* Light grey fill color */
            color: black;  /* Button text color */
            font-weight: bold;  /* Bold text */
            border: 2px solid #cccccc;  /* Border color */
            border-radius: 10px;  /* Rounded corners */
            display: inline-flex;  /* Flex layout for vertical and horizontal alignment */
            justify-content: center;  /* Center content horizontally */
            align-items: center;  /* Center content vertically */
            text-align: center;  /* Align text center */
            white-space: normal;  /* Allow text wrapping within the button */
            overflow: hidden;  /* Hide overflow if text exceeds button bounds */
            padding: 0;  /* Remove extra padding */
            margin: 5px; /* Add some spacing between buttons */
            cursor: pointer; /* Pointer cursor for interactivity */
            transition: background-color 0.2s ease; /* Smooth hover transition */
        }
 
        /* Hover effect to make buttons more interactive */
        .tool-button:hover {
            background-color: #e0e0e0;  /* Slightly darker grey on hover */
        }
        </style>
        """, unsafe_allow_html=True
    )
 
    # Main container for page content
    with st.container():
        st.markdown("<div class='main-container'>", unsafe_allow_html=True)
 
        # Title with rounded yellow highlight
        st.markdown(
            f"<div class='title'>{playlist_details['title']}</div>",
            unsafe_allow_html=True
        )
 
        # Playlist ID styled in italics and grey
        st.markdown(
            f"<div class='playlist-id'>Playlist ID: {playlist_details['playlist_id']}</div>",
            unsafe_allow_html=True
        )
 
        # Add description, instructors, and topics below Playlist ID
        st.markdown(
            f"""
    <div class='details'>
        <p><b>Instructors:</b> {playlist_details['instructors']}</p>
    </div>
            """,
            unsafe_allow_html=True
        )
 
        # Divider before Video Section
        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
 
        # Layout for Video and Q&A Section
        col1, col2 = st.columns([2, 3], gap="large")  # Smaller video, larger Q&A
 
        with col1:
            # YouTube Video Placeholder
            st.markdown("### 🎥 Video Section")
            st.image("https://via.placeholder.com/300x200?text=Video+Player", caption="Video Placeholder", use_container_width=True)
 
        with col2:
            # Q&A Section with Highlight
            st.markdown("<div class='qa-title'>💬 Q&A Section</div>", unsafe_allow_html=True)
            user_question = st.text_input("Enter your question here:", placeholder="Type your question...", key="question_input")
            if st.button("Get Answer"):
                if user_question:
                    st.success(f"**Answer:** This is a placeholder for the response to: '{user_question}'")
                else:
                    st.error("Please enter a question to get an answer!")
 
        # Divider above Additional Tools
        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
 
        # Additional Tools Section
        st.markdown("### 🛠️ Additional Tools")
        tool_cols = st.columns(4, gap="large")
 
        # Handle button clicks for each tool
        for i, (icon, label, key) in enumerate([
            ("📜", "Summarize", "summary"),
            ("📑", "Segment Topics", "topics"),
            ("📝", "Display Notes", "notes"),
            ("🔗", "Generate Citation", "citation"),
        ]):
            with tool_cols[i]:
                if st.button(f"{icon} {label}", key=f"tool_{key}"):
                    st.info(f"Placeholder: You clicked on '{label}'.")
 
        # Divider for navigation
        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
 
        # Navigation Back to Dashboard
        if st.button("🔙 Back to Dashboard", use_container_width=True):
            set_active_page("Dashboard")
 
        st.markdown("</div>", unsafe_allow_html=True)
 
import streamlit as st
from google.cloud import bigquery


def fetch_playlists():
    """
    Fetches playlist details (playlist_id, title, description, instructors, topics, subtopics) 
    from the Courses table in BigQuery.
    Returns:
        list of dict: A list of dictionaries with course details.
    """
    try:
        # Initialize BigQuery client
        client = bigquery.Client()
        
        # Query to fetch course details
        query = """
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
        GROUP BY playlist_id, title, description, instructors
        LIMIT 1000
        """
        query_job = client.query(query)  # Execute the query
        results = query_job.result()    # Get the query results
        
        # Extract course details into a list of dictionaries
        playlists = []
        for row in results:
            # Handle hierarchical topics and subtopics
            topics = ", ".join(row.topics) if row.topics else "N/A"
            subtopics = ", ".join(row.subtopics) if row.subtopics else "N/A"
            topic_details = f"{topics} ({subtopics})" if subtopics != "N/A" else topics

            # Append course details
            playlists.append({
                "playlist_id": row.playlist_id,
                "title": row.title,
                "description": row.description or "N/A",
                "instructors": row.instructors or "N/A",
                "topics": topic_details,
            })
        return playlists
    except Exception as e:
        st.error(f"Error fetching playlists: {e}")
        return []


def paginate_list(items, page_size):
    """
    Divides a list into pages of a given size.
    Args:
        items (list): The list of items to paginate.
        page_size (int): The number of items per page.
    Returns:
        list of lists: Paginated lists.
    """
    return [items[i:i + page_size] for i in range(0, len(items), page_size)]


def show_dashboard(set_active_page):
    """
    Renders the dashboard page with course details displayed in card format.
    Args:
        set_active_page (function): Function to set the active page for navigation.
    """
    # Page Title and Subtitle
    st.markdown("<h1 style='text-align: center; color: #4CAF50;'>Welcome to EduSearch AI</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #9E9E9E;'>Turning YouTube Playlists into Interactive Learning Tools</h3>", unsafe_allow_html=True)

    # Introduction Text
    st.markdown(
        """
        <p style='text-align: center; font-size: 18px; color: #757575;'>
        Welcome to <b>EduSearch AI</b>, your interactive learning platform. 
        Select a course below to start exploring engaging content.
        </p>
        """, unsafe_allow_html=True
    )

    # Divider for visual separation
    st.markdown("<hr style='border: 1px solid #E0E0E0;'>", unsafe_allow_html=True)

    # Fetch playlists dynamically from BigQuery
    with st.spinner("Fetching courses..."):
        playlists = fetch_playlists()

    # Check if playlists are available
    if not playlists:
        st.warning("No courses available at the moment. Please check back later.")
        return

    # Implement pagination if the number of courses exceeds the limit
    page_size = 6  # Number of cards per page
    paginated_playlists = paginate_list(playlists, page_size)

    # Select a page
    total_pages = len(paginated_playlists)
    if total_pages > 1:
        page_number = st.sidebar.number_input(
            "Page Number",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1
        ) - 1
    else:
        page_number = 0

    current_page = paginated_playlists[page_number]

    # Display each course in a grid layout (2 columns)
    cols = st.columns(2)  # 2 cards per row
    for idx, playlist in enumerate(current_page):
        with cols[idx % 2]:
            st.markdown(
                f"""
                <div style='border: 1px solid #E0E0E0; border-radius: 10px; padding: 15px; margin-bottom: 15px; box-shadow: 2px 2px 8px rgba(0,0,0,0.1);'>
                    <h3 style='color: #4CAF50;'>{playlist['title']}</h3>
                    <p style='font-size: 14px; color: #757575;'><b>Description:</b> {playlist['description']}</p>
                    <p style='font-size: 14px; color: #757575;'><b>Instructors:</b> {playlist['instructors']}</p>
                    <p style='font-size: 14px; color: #757575;'><b>Topics:</b> {playlist['topics']}</p>
                    <button style='background-color: #4CAF50; color: white; border: none; border-radius: 5px; padding: 10px 15px; cursor: pointer;'>Select</button>
                </div>
                """, unsafe_allow_html=True
            )
            if st.button(f"Select '{playlist['title']}'", key=f"select_{playlist['playlist_id']}"):
                # Store the selected playlist_id and title in session state
                st.session_state.selected_playlist = playlist["playlist_id"]
                st.session_state.selected_playlist_title = playlist["title"]
                # Navigate to the Playlist Page
                set_active_page("Playlist Page")

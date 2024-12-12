import streamlit as st

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

    # Layout for Video and Q&A Section
    col1, col2 = st.columns([2, 3])  # Smaller video, larger Q&A

    with col1:
        # YouTube Video Placeholder (reduced size)
        st.markdown("### Video")
       # st.video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")  # Replace with a dynamic video link if needed

    with col2:
        # Q&A Section
        st.markdown("### Q&A Section")
        st.markdown(
            """
            **Ask a question about this video, and we'll provide an answer below.**
            """
        )
        # Question input
        user_question = st.text_input("Enter your question here:")

        # "Get Answer" button and answer display
        if st.button("Get Answer"):
            if user_question:
                # Placeholder answer logic
                st.markdown(f"**Answer:** This is a response to your question: '{user_question}'")
            else:
                st.error("Please enter a question.")

    # Additional Tools Section
    st.markdown("---")  # Horizontal divider
    st.markdown("### Additional Tools")
    tools_col1, tools_col2, tools_col3, tools_col4 = st.columns(4)

    with tools_col1:
        if st.button("Generate Summary"):
            st.write("Summary generation functionality coming soon!")

    with tools_col2:
        if st.button("Segment Topics"):
            st.write("Topic segmentation functionality coming soon!")

    with tools_col3:
        if st.button("Display Research Notes"):
            st.write("Research notes functionality coming soon!")

    with tools_col4:
        if st.button("Generate Citation"):
            st.write("Citation generator functionality coming soon!")

    # Navigation Back to Dashboard
    st.markdown("---")  # Horizontal divider
    if st.button("Back to Dashboard"):
        set_active_page("Dashboard")

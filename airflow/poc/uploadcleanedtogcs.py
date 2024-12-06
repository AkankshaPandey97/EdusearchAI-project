import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import logging
import re
from google.cloud import storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

# Base URL and Course URLs
base_url = "https://ocw.mit.edu"
course_data_urls = {
    "6-041-probabilistic-systems-analysis-and-applied-probability-fall-2010": {
        "course_url": f"{base_url}/courses/6-041-probabilistic-systems-analysis-and-applied-probability-fall-2010/",
        "video_gallery_url": f"{base_url}/courses/6-041-probabilistic-systems-analysis-and-applied-probability-fall-2010/video_galleries/video-lectures/",
        "playlist_id": "PLUl4u3cNGP62uI_DWNdWoIMsgPcLGOx-V"

    },
    "res-ll-005-mathematics-of-big-data-and-machine-learning-january-iap-2020": {
        "course_url": f"{base_url}/courses/res-ll-005-mathematics-of-big-data-and-machine-learning-january-iap-2020/",
        "video_gallery_url": f"{base_url}/courses/res-ll-005-mathematics-of-big-data-and-machine-learning-january-iap-2020/video_galleries/class-videos/",
        "playlist_id": "PLUl4u3cNGP61MdtwGTqZA0MreSaDybji8"
    },
    "15-s21-nuts-and-bolts-of-business-plans-january-iap-2014": {
        "course_url": f"{base_url}/courses/15-s21-nuts-and-bolts-of-business-plans-january-iap-2014/",
        "video_gallery_url": f"{base_url}/courses/15-s21-nuts-and-bolts-of-business-plans-january-iap-2014/video_galleries/lecture-videos/",
        "playlist_id": "PLUl4u3cNGP61x5b_88idmqeRdPULQjGnv"
    },
    "15-s50-how-to-win-at-texas-holdem-poker-january-iap-2016": {
        "course_url": f"{base_url}/courses/15-s50-how-to-win-at-texas-holdem-poker-january-iap-2016/",
        "video_gallery_url": f"{base_url}/courses/15-s50-how-to-win-at-texas-holdem-poker-january-iap-2016/video_galleries/video-lectures/",
        "playlist_id": "PLUl4u3cNGP6083Y-NElqTRAgKtXQxgD3g"
    },
     "6-858-computer-systems-security-fall-2014": {
        "course_url": f"{base_url}/courses/6-858-computer-systems-security-fall-2014/",
        "video_gallery_url": f"{base_url}/courses/6-858-computer-systems-security-fall-2014/video_galleries/video-lectures/",
        "playlist_id": "PLUl4u3cNGP62K2DjQLRxDNRi0z2IRWnNh"
     }
}

def fetch_html(url):
    """Fetch HTML content for a given URL."""
    try:
        logging.info(f"Fetching URL: {url}")
        response = requests.get(url)
        response.raise_for_status()
        return BeautifulSoup(response.content, "html.parser")
    except Exception as e:
        logging.error(f"Failed to fetch URL: {url}, Error: {e}")
        return None

def parse_course_metadata(soup, course_data):
    """Parse course metadata."""
    try:
        # Title and Course Number
        banner = soup.find("div", id="course-banner")
        if banner:
            title = banner.find("h1")
            course_number_term = banner.find("span", class_="course-number-term-detail")
            course_data["metadata"]["title"] = title.get_text(strip=True) if title else "N/A"
            course_data["metadata"]["course_number_term"] = course_number_term.get_text(strip=True) if course_number_term else "N/A"

        # Description
        description = soup.find("div", id="collapsed-description")
        if description:
            course_data["metadata"]["description"] = description.get_text(strip=True).replace("Show more", "")

        # Topics and Subtopics
        topics_section = soup.find("ul", class_="list-unstyled pb-2 m-0")
        if topics_section:
            topics_list = topics_section.find_all("li", recursive=False)
            for topic in topics_list:
                topic_name = topic.find("a", class_="course-info-topic").get_text(strip=True)
                subtopics = []
                subtopic_container = topic.find("ul", class_="subtopic-container")
                if subtopic_container:
                    subtopic_links = subtopic_container.find_all("a", class_="course-info-topic")
                    subtopics = [link.get_text(strip=True) for link in subtopic_links]
                course_data["metadata"]["topics"].append({
                    "topic": topic_name,
                    "subtopics": subtopics
                })

        # Instructors
        instructors_section = soup.find("div", class_="course-info-content")
        if instructors_section:
            instructors = instructors_section.find_all("a", class_="course-info-instructor")
            for instructor in instructors:
                course_data["metadata"]["instructors"].append(instructor.get_text(strip=True))

        logging.info("Successfully extracted course metadata.")
    except Exception as e:
        logging.error(f"Error extracting metadata: {e}")

    # Add Playlist ID
        course_data["metadata"]["playlist_id"] = playlist_id

        logging.info("Successfully extracted course metadata.")
    except Exception as e:
        logging.error(f"Error extracting metadata: {e}")

def parse_lecture_notes(soup, course_data):
    """Parse lecture notes from various structures in the course pages."""
    try:
        logging.info("Extracting lecture notes...")
        lecture_notes_links = []
        processed_urls = set()

        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "/resources/" in href:
                resource_page_url = urljoin(base_url, href)
                resource_soup = fetch_html(resource_page_url)

                if resource_soup:
                    for pdf_link in resource_soup.find_all("a", href=True):
                        pdf_href = pdf_link["href"]
                        if pdf_href.endswith(".pdf") and pdf_href not in processed_urls:
                            processed_urls.add(pdf_href)

                            parent_tag = pdf_link.find_parent()
                            note_title = parent_tag.get_text(strip=True) if parent_tag else None

                            if not note_title or re.match(r'^\s*(pdf|download|file|[\d\s]*kb|mb|gb)\s*$', note_title, re.I):
                                note_title = pdf_link.get("title") or pdf_link.get_text(strip=True)
                            if not note_title or re.match(r'^\s*(pdf|download|file|[\d\s]*kb|mb|gb)\s*$', note_title, re.I):
                                note_title = os.path.splitext(os.path.basename(pdf_href))[0].replace("_", " ")

                            # Normalize the title
                            note_title = normalize_lecture_note_title(note_title, course_data["metadata"]["title"])

                            pdf_url = urljoin(base_url, pdf_href)
                            lecture_notes_links.append({
                                "title": note_title,
                                "url": pdf_url
                            })

        course_data["lecture_notes"].extend(lecture_notes_links)
        logging.info(f"Successfully extracted {len(course_data['lecture_notes'])} lecture notes.")
    except Exception as e:
        logging.error(f"Error extracting lecture notes: {e}")

def normalize_lecture_note_title(title, course_title):
    """Normalize lecture note titles."""
    # Extract lecture number or provide a generic title
    match = re.search(r"(Lecture\s+\d+)", title, flags=re.IGNORECASE)
    lecture_number = match.group(0) if match else "General"
    # Remove file size and reformat title
    cleaned_title = f"{lecture_number}: {title.split(lecture_number)[-1].strip()} - {course_title}" if lecture_number != "General" else title
    return re.sub(r"\s+", " ", cleaned_title).strip()


def download_lecture_notes(course_title, lecture_notes):
    """Download lecture notes to local storage."""
    formatted_course_title = course_title.replace(" ", "_").replace(":", "_").replace("/", "_")
    lecture_notes_dir = os.path.join(formatted_course_title, f"{formatted_course_title}_Lecture_Notes")
    os.makedirs(lecture_notes_dir, exist_ok=True)

    for note in lecture_notes:
        try:
            file_name = f"{formatted_course_title}_{note['title'].replace(' ', '_').replace(':', '_').replace('/', '_')}.pdf"
            file_path = os.path.join(lecture_notes_dir, file_name)
            logging.info(f"Downloading: {note['url']}")
            response = requests.get(note["url"], stream=True)
            response.raise_for_status()

            # Ensure valid PDF content
            if 'application/pdf' in response.headers.get('Content-Type', ''):
                with open(file_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                logging.info(f"Saved to: {file_path}")
            else:
                logging.error(f"Invalid content type for: {note['url']}. Expected PDF.")
        except Exception as e:
            logging.error(f"Failed to download: {note['url']}, Error: {e}")

def download_transcripts(course_title, video_gallery_url, course_data):
    """Download transcripts from all subpages of the video gallery and update metadata."""
    try:
        formatted_course_title = course_title.replace(" ", "_").replace(":", "_").replace("/", "_")
        transcript_dir = os.path.join(formatted_course_title, f"{formatted_course_title}_transcripts")
        os.makedirs(transcript_dir, exist_ok=True)

        def get_video_pages(page_url):
            """Find all links to individual video pages."""
            soup = fetch_html(page_url)
            if not soup:
                return []
            video_links = soup.find_all('a', href=True)
            return list(set(
                urljoin(page_url, link['href']) for link in video_links
                if 'courses/' in link['href'] and 'video_galleries' not in link['href']
            ))

        def get_transcripts_from_page(page_url):
            """Fetch and download transcripts from a specific video page."""
            soup = fetch_html(page_url)
            if not soup:
                return
            transcript_links = soup.find_all('a', string='Download transcript')
            for link in transcript_links:
                transcript_url = urljoin(page_url, link['href'])
                transcript_name = os.path.basename(transcript_url)
                transcript_filename = f"{formatted_course_title}_{transcript_name}"
                transcript_filepath = os.path.join(transcript_dir, transcript_filename)

                # Download transcript
                logging.info(f"Downloading transcript: {transcript_url}")
                response = requests.get(transcript_url)
                if response.status_code == 200:
                    with open(transcript_filepath, "wb") as file:
                        file.write(response.content)
                    logging.info(f"Saved transcript to: {transcript_filepath}")
                    # Add transcript metadata
                    course_data["transcripts"].append({
                        "title": transcript_name,
                        "url": transcript_url,
                        "path": transcript_filepath
                    })
                else:
                    logging.error(f"Failed to download transcript: {transcript_url}")

        # Main transcript downloading workflow
        video_pages = get_video_pages(video_gallery_url)
        logging.info(f"Found {len(video_pages)} video pages for transcripts.")
        for video_page in video_pages:
            get_transcripts_from_page(video_page)

    except Exception as e:
        logging.error(f"Error downloading transcripts for course {course_title}: {e}")

def normalize_transcript_title(transcript_name, lecture_notes):
    """Generate descriptive transcript titles by mapping to lecture notes."""
    # Attempt to match transcript to a lecture note
    for note in lecture_notes:
        if transcript_name in note["url"]:
            return f"{note['title']} - Transcript"
    return f"Transcript - {transcript_name}"  # Fallback if no match

def upload_folder_to_gcs(local_folder_path, bucket_name, gcs_base_path=""):
    """
    Upload a local folder and its contents to GCS, preserving the folder structure.
    Excludes unnecessary files like .DS_Store.
    
    :param local_folder_path: Path to the local folder to upload.
    :param bucket_name: Name of the GCS bucket.
    :param gcs_base_path: Base path in the GCS bucket where files will be uploaded.
    """
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)

        for root, _, files in os.walk(local_folder_path):
            for file in files:
                # Skip .DS_Store and other unnecessary system files
                if file == ".DS_Store":
                    logging.info(f"Skipping system file: {file}")
                    continue

                local_file_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_file_path, local_folder_path)
                gcs_blob_path = os.path.join(gcs_base_path, relative_path).replace("\\", "/")  # Ensure correct GCS path
                blob = bucket.blob(gcs_blob_path)
                blob.upload_from_filename(local_file_path)
                logging.info(f"Uploaded {local_file_path} to GCS as {gcs_blob_path}.")
    except Exception as e:
        logging.error(f"Error uploading folder to GCS: {e}")


def clean_metadata(metadata):
    """
    Cleans metadata fields to remove unwanted characters like escape sequences.
    """
    cleaned_metadata = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            # Remove escape sequences and clean extra whitespace
            cleaned_metadata[key] = value.encode('ascii', 'ignore').decode().replace("\u2026", "...").strip()
        elif isinstance(value, list):
            # Recursively clean lists
            cleaned_metadata[key] = [clean_metadata(item) if isinstance(item, dict) else item for item in value]
        elif isinstance(value, dict):
            # Recursively clean nested dictionaries
            cleaned_metadata[key] = clean_metadata(value)
        else:
            # Keep other types as-is
            cleaned_metadata[key] = value
    return cleaned_metadata

# Update the course metadata saving section
# Process each course
for course_key, urls in course_data_urls.items():
    course_url = urls["course_url"]
    video_gallery_url = urls["video_gallery_url"]
    playlist_id = urls["playlist_id"]  # Get Playlist ID

    logging.info(f"Processing course: {course_url}")

    # Initialize course data structure
    course_data = {
        "metadata": {
            "title": "",
            "course_number_term": "",
            "instructors": [],
            "topics": [],
            "description": "",
            "playlist_id": playlist_id
        },
        "lecture_notes": [],
        "transcripts": []
    }

    # Fetch and parse metadata
    course_soup = fetch_html(course_url)
    if course_soup:
        parse_course_metadata(course_soup, course_data)

    # Clean metadata
    course_data["metadata"] = clean_metadata(course_data["metadata"])

    course_title = course_data["metadata"]["title"]
    if not course_title:
        logging.error(f"Could not determine course title for URL: {course_url}")
        continue

    # Download transcripts
    download_transcripts(course_title, video_gallery_url, course_data)

    # Download lecture notes
    lecture_notes_url = f"{course_url}pages/lecture-notes/"
    lecture_notes_soup = fetch_html(lecture_notes_url)
    if lecture_notes_soup:
        parse_lecture_notes(lecture_notes_soup, course_data)
        download_lecture_notes(course_title, course_data["lecture_notes"])

    # Save metadata to JSON
    try:
        formatted_course_title = course_title.replace(" ", "_")
        metadata_path = os.path.join(formatted_course_title, f"{formatted_course_title}_metadata.json")
        os.makedirs(formatted_course_title, exist_ok=True)

        # Save cleaned metadata
        with open(metadata_path, "w") as metadata_file:
            json.dump(course_data, metadata_file, indent=4)
        logging.info(f"Metadata saved to {metadata_path}")
    except Exception as e:
        logging.error(f"Failed to save metadata: {e}")

    # Upload the course folder to GCS
    try:
        upload_folder_to_gcs(
            local_folder_path=formatted_course_title,
            bucket_name="mit_scraped_courses",
            gcs_base_path=formatted_course_title
        )
    except Exception as e:
        logging.error(f"Failed to upload folder {formatted_course_title} to GCS: {e}")

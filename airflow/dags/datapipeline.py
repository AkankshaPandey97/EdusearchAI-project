import os
import requests
from urllib.parse import urljoin
import json
import logging
import time
import re
import threading
from pathlib import Path
import pandas as pd
from google.cloud import bigquery
from google.cloud import storage
import psutil
from dotenv import load_dotenv
import unicodedata
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import timedelta
from datetime import datetime
from google.oauth2 import service_account
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep
from airflow.exceptions import AirflowException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

# Load environment variables
load_dotenv()

# Get the path to the credentials file from environment variable
credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Create credentials and client
if credentials_path:
    credentials = service_account.Credentials.from_service_account_file(credentials_path)
    client = storage.Client(credentials=credentials)
else:
    raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")

# Initialize clients
bq_client = bigquery.Client(project=os.getenv('GCP_PROJECT_ID'))
gcs_client = storage.Client(project=os.getenv('GCP_PROJECT_ID'))

# Get environment variables
bucket_name = os.getenv('GCS_BUCKET_NAME')
dataset_id = os.getenv('BQ_DATASET_ID')


EXCLUDED_DIRS = {'logs', 'dags', 'plugins', 'parsed_content', 'config'}
BATCH_SIZE = 1


# Configure logging
logging.basicConfig(level=logging.INFO)
_log = logging.getLogger(__name__)

# Base directory for courses (current directory)
base_dir = Path(".")  # Use the current directory directly
output_dir = Path("parsed_content")  # Base output directory for parsed content
output_dir.mkdir(parents=True, exist_ok=True)

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
    from bs4 import BeautifulSoup
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

def process_course_metadata(course_data_urls, bucket_name="mit_scraped_courses"):
    """
    Process courses to fetch metadata, download lecture notes and transcripts, 
    and upload results to Google Cloud Storage.

    :param course_data_urls: Dictionary containing course data URLs and metadata.
    :param bucket_name: GCS bucket name where data will be uploaded.
    """
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
                bucket_name=bucket_name,
                gcs_base_path=formatted_course_title
            )
        except Exception as e:
            logging.error(f"Failed to upload folder {formatted_course_title} to GCS: {e}")

# Helper function to list JSON files in GCS
def list_json_files(bucket_name):
    bucket = gcs_client.bucket(bucket_name)
    blobs = bucket.list_blobs()
    return [blob.name for blob in blobs if blob.name.endswith('_metadata.json')]

# Extract course metadata
def extract_course_metadata(json_data):
    course_id = json_data["metadata"]["title"].replace(" ", "_")
    metadata = {
        "course_id": course_id,
        "title": json_data["metadata"].get("title"),
        "description": json_data["metadata"].get("description"),
        "playlist_id": json_data["metadata"].get("playlist_id"),
        "instructors": json_data["metadata"].get("instructors", []),
        "topics": json_data["metadata"].get("topics", []),
    }
    return metadata

# Extract lecture notes
def extract_lecture_notes(json_data, course_id):
    return [
        {
            "course_id": course_id,
            "lecture_id": f"{course_id}_L{idx+1}",
            "title": note.get("title"),
            "url": note.get("url"),
        }
        for idx, note in enumerate(json_data.get("lecture_notes", []))
    ]

# Extract transcripts
def extract_transcripts(json_data, course_id):
    return [
        {
            "course_id": course_id,
            "transcript_id": f"{course_id}_T{idx+1}",
            "title": transcript.get("title"),
            "url": transcript.get("url"),
            "path": transcript.get("path"),
        }
        for idx, transcript in enumerate(json_data.get("transcripts", []))
    ]

# Load JSON files into DataFrames
def load_json_to_dataframes(bucket_name, json_files):
    courses = []
    lecture_notes = []
    transcripts = []
    
    for file_name in json_files:
        blob = gcs_client.bucket(bucket_name).blob(file_name)
        json_data = json.loads(blob.download_as_text())
        course_metadata = extract_course_metadata(json_data)
        courses.append(course_metadata)
        lecture_notes.extend(extract_lecture_notes(json_data, course_metadata["course_id"]))
        transcripts.extend(extract_transcripts(json_data, course_metadata["course_id"]))
    
    return pd.DataFrame(courses), pd.DataFrame(lecture_notes), pd.DataFrame(transcripts)

# Helper function to load DataFrame into BigQuery
def load_table_to_bq(df, table_name, schema):
    table_id = f"{os.getenv('GCP_PROJECT_ID')}.{dataset_id}.{table_name}"
    job_config = bigquery.LoadJobConfig(schema=schema, write_disposition="WRITE_TRUNCATE")
    load_job = bq_client.load_table_from_dataframe(df, table_id, job_config=job_config)
    load_job.result()
    print(f"Loaded {load_job.output_rows} rows into {table_id}.")

# Main function
def load_data_into_bigquery():
    print("Listing JSON files...")
    json_files = list_json_files(bucket_name)
    print(f"Found {len(json_files)} JSON files.")

    if not json_files:
        print("No JSON files found.")
        return

    print("Loading JSON data into DataFrames...")
    courses_df, lecture_notes_df, transcripts_df = load_json_to_dataframes(bucket_name, json_files)

    # Print DataFrame structures
    print("Courses DataFrame:")
    print(courses_df.head())
    print("Lecture Notes DataFrame:")
    print(lecture_notes_df.head())
    print("Transcripts DataFrame:")
    print(transcripts_df.head())

    # Define BigQuery schemas
    courses_schema = [
        bigquery.SchemaField("course_id", "STRING"),
        bigquery.SchemaField("title", "STRING"),
        bigquery.SchemaField("description", "STRING"),
        bigquery.SchemaField("playlist_id", "STRING"),
        bigquery.SchemaField("instructors", "STRING", mode="REPEATED"),
        bigquery.SchemaField("topics", "RECORD", mode="REPEATED", fields=[
            bigquery.SchemaField("topic", "STRING"),
            bigquery.SchemaField("subtopics", "STRING", mode="REPEATED"),
        ]),
    ]

    lecture_notes_schema = [
        bigquery.SchemaField("course_id", "STRING"),
        bigquery.SchemaField("lecture_id", "STRING"),
        bigquery.SchemaField("title", "STRING"),
        bigquery.SchemaField("url", "STRING"),
    ]

    transcripts_schema = [
        bigquery.SchemaField("course_id", "STRING"),
        bigquery.SchemaField("transcript_id", "STRING"),
        bigquery.SchemaField("title", "STRING"),
        bigquery.SchemaField("url", "STRING"),
        bigquery.SchemaField("path", "STRING"),
    ]

    # Load data into BigQuery tables
    print("Loading Courses data into BigQuery...")
    load_table_to_bq(courses_df, "Courses", courses_schema)
    
    print("Loading Lecture Notes data into BigQuery...")
    load_table_to_bq(lecture_notes_df, "LectureNotes", lecture_notes_schema)
    
    print("Loading Transcripts data into BigQuery...")
    load_table_to_bq(transcripts_df, "Transcripts", transcripts_schema)

from easyocr import Reader
import os
import logging

def setup_easyocr_environment():
    """
    Set up EasyOCR environment to avoid runtime downloads and ensure availability.
    """
    easyocr_dir = os.path.expanduser("~/.EasyOCR")
    os.makedirs(easyocr_dir, exist_ok=True)
    os.environ["EASYOCR_DIR"] = easyocr_dir

    try:
        # Initialize EasyOCR Reader
        reader = Reader(['en'], gpu=True, model_storage_directory=easyocr_dir)
        logging.info("EasyOCR setup completed with GPU support.")
    except Exception as e:
        logging.warning(f"GPU not available for EasyOCR. Falling back to CPU: {e}")
        reader = Reader(['en'], gpu=False, model_storage_directory=easyocr_dir)
    logging.info(f"EasyOCR models are stored in: {easyocr_dir}")
    return reader


def clean_text(text):
    """
    Clean up text by normalizing Unicode characters, removing GLYPH artifacts,
    and stripping unnecessary whitespace.
    """
    try:
        text = unicodedata.normalize("NFKD", text)
        text = re.sub(r"GLYPH<[^>]+>", "", text)
        text = re.sub(r"[\x00-\x1F\x7F]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception as e:
        _log.error(f"Failed to clean text: {e}")
        return None
def wait_for_resources(memory_threshold=75, cpu_threshold=90, check_interval=5):
    """
    Pause processing if memory or CPU usage is high.

    :param memory_threshold: Percentage of memory usage above which the function will pause (default: 75%).
    :param cpu_threshold: Percentage of CPU usage above which the function will pause (default: 90%).
    :param check_interval: Time interval (in seconds) between usage checks (default: 5 seconds).
    """
    import psutil
    import time
    import logging

    while psutil.virtual_memory().percent > memory_threshold or psutil.cpu_percent(interval=1) > cpu_threshold:
        logging.warning(
            f"High resource usage detected. Memory: {psutil.virtual_memory().percent}%, "
            f"CPU: {psutil.cpu_percent(interval=1)}%. Retrying in {check_interval} seconds..."
        )
        time.sleep(check_interval)


def process_pdf(file_path, course_name, content_type):
    """
    Process a single PDF for parsing and chunking.
    Includes saving tables, images, and text chunks.
    
    :param file_path: Path to the PDF file.
    :param course_name: Name of the course.
    :param content_type: Content type (e.g., lecture_notes, transcripts).
    """
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import PictureItem, TableItem
    from docling_core.transforms.chunker import HierarchicalChunker

    # Configuration constants
    IMAGE_RESOLUTION_SCALE = 2.0
    CHUNK_LENGTH_MIN = 500
    CHUNK_LENGTH_MAX = 1500
    CHUNK_OVERLAP = 50

    # Ensure resources are available before processing
    wait_for_resources()

    try:
        logging.info(f"Processing file: {file_path}")
        # Configure pipeline options for Docling
        pipeline_options = PdfPipelineOptions(
            images_scale=IMAGE_RESOLUTION_SCALE,
            generate_page_images=True,
            generate_table_images=True,
            generate_picture_images=True
        )
        doc_converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )

        # Convert the PDF
        conv_res = doc_converter.convert(file_path)
        doc_filename = Path(file_path).stem
        course_output_dir = output_dir / course_name / content_type
        course_output_dir.mkdir(parents=True, exist_ok=True)

        # Save tables
        table_counter = 0
        for element, _ in conv_res.document.iterate_items():
            if isinstance(element, TableItem):
                table_counter += 1
                table_csv_filename = course_output_dir / f"{doc_filename}-table-{table_counter}.csv"
                pd.DataFrame(element.export_to_dataframe()).to_csv(table_csv_filename, index=False)
                logging.info(f"Saved table to {table_csv_filename}")

        # Save images
        picture_counter = 0
        for element, _ in conv_res.document.iterate_items():
            if isinstance(element, PictureItem):
                picture_counter += 1
                picture_image_filename = course_output_dir / f"{doc_filename}-picture-{picture_counter}.png"
                with picture_image_filename.open("wb") as fp:
                    element.image.pil_image.save(fp, "PNG")
                logging.info(f"Saved picture to {picture_image_filename}")

        # Chunk text content
        chunks = list(HierarchicalChunker(
            min_chunk_length=CHUNK_LENGTH_MIN,
            max_chunk_length=CHUNK_LENGTH_MAX,
            split_by="paragraph",
            overlap=CHUNK_OVERLAP
        ).chunk(conv_res.document))

        chunk_data = []
        for i, chunk in enumerate(chunks):
            cleaned_text = unicodedata.normalize("NFKD", chunk.text.strip())
            if cleaned_text:
                chunk_data.append({
                    "course": course_name,
                    "content_type": content_type,
                    "document": doc_filename,
                    "chunk_id": i,
                    "text": cleaned_text
                })

        # Save text chunks to JSON
        chunks_json_filename = course_output_dir / f"{doc_filename}_chunks.json"
        with chunks_json_filename.open("w") as json_fp:
            json.dump(chunk_data, json_fp, indent=4, ensure_ascii=False)
        logging.info(f"Chunks saved to {chunks_json_filename}")

        logging.info(f"Processing completed for file: {file_path}")

    except Exception as e:
        logging.error(f"Error processing {file_path}: {e}")

        # Chunk text content
        chunks = list(HierarchicalChunker(
            min_chunk_length=CHUNK_LENGTH_MIN,
            max_chunk_length=CHUNK_LENGTH_MAX,
            split_by="paragraph",
            overlap=CHUNK_OVERLAP
        ).chunk(conv_res.document))
        
        chunk_data = []
        for i, chunk in enumerate(chunks):
            cleaned_text = clean_text(chunk.text)
            if cleaned_text:
                chunk_data.append({
                    "course": course_name,
                    "content_type": content_type,
                    "document": doc_filename,
                    "chunk_id": i,
                    "text": cleaned_text
                })

        # Save text chunks to JSON
        chunks_json_filename = course_output_dir / f"{doc_filename}_chunks.json"
        with chunks_json_filename.open("w") as json_fp:
            json.dump(chunk_data, json_fp, indent=4, ensure_ascii=False)
        _log.info(f"Chunks saved to {chunks_json_filename}")
        
        _log.info(f"Processed {file_path} in {time.time() - start_time:.2f} seconds.")
    except Exception as e:
        _log.error(f"Error processing {file_path}: {e}")

def process_courses(base_dir):
    """
    Process all courses and their PDFs in the base directory.
    """
    if not base_dir.exists() not in EXCLUDED_DIRS:
        _log.error(f"Base directory {base_dir} does not exist.")
        return

    for course_dir in base_dir.iterdir():
        if course_dir.is_dir():
            course_name = course_dir.name
            _log.info(f"Processing course: {course_name}")
            
            # Process Lecture Notes
            lecture_notes_dir = course_dir / f"{course_name}_Lecture_Notes"
            if lecture_notes_dir.exists():
                for pdf_file in lecture_notes_dir.glob("*.pdf"):
                    process_pdf(pdf_file, course_name, "lecture_notes")
            
            # Process Transcripts
            transcripts_dir = course_dir / f"{course_name}_transcripts"
            if transcripts_dir.exists():
                for pdf_file in transcripts_dir.glob("*.pdf"):
                    process_pdf(pdf_file, course_name, "transcripts")


def run_processing_pipeline(base_dir):
    setup_easyocr_environment()  # Ensure EasyOCR setup before processing
    process_courses(base_dir)
    BASE_DIR = Path(".") 

def embedandpineconeupload():
    """
    Run the pipeline for embedding and uploading parsed content to Pinecone.
    """
    import os
    import json
    import glob
    import logging
    import pandas as pd
    from dotenv import load_dotenv
    from pathlib import Path
    from pinecone import Pinecone, ServerlessSpec
    from sentence_transformers import SentenceTransformer
    from transformers import CLIPProcessor, CLIPModel
    from PIL import Image
    import torch
    import torch.multiprocessing as mp  # Add this import

    # Set the multiprocessing start method to "spawn"
    mp.set_start_method("spawn", force=True)
    

    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # Load environment variables
    load_dotenv()

    # Pinecone configuration
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    pinecone_env = os.getenv("PINECONE_ENV", "us-east-1")
    index_name = os.getenv("PINECONE_INDEX_NAME", "edu-parsed-content-index")

    # Initialize Pinecone
    pc = Pinecone(api_key=pinecone_api_key)

    # Embedding models
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    embedding_dimension = embedding_model.get_sentence_embedding_dimension()

    clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

    # Create Pinecone index if not exists
    if index_name not in pc.list_indexes().names():
        logging.info(f"Creating Pinecone index: {index_name}")
        pc.create_index(
            name=index_name,
            dimension=embedding_dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region=pinecone_env),
        )

    # Connect to the index
    index = pc.Index(index_name)
    logging.info(f"Connected to Pinecone index: {index_name}")

    # Directory containing parsed content
    parsed_content_dir = "parsed_content"

    # Helper Functions
    def chunk_text(text, max_length=512):
        """Chunks text into smaller parts for embedding."""
        return [text[i : i + max_length] for i in range(0, len(text), max_length)]

    def validate_and_log_metadata(metadata):
        """Logs metadata and validates it."""
        if not metadata:
            logging.warning("Empty metadata. Skipping...")
            return False
        logging.debug(f"Metadata: {json.dumps(metadata, indent=2)}")
        return True

    # Summary Stats
    upload_stats = {"text_chunks": 0, "tables": 0, "images": 0}

    # Process Text Chunks
    for json_file in glob.glob(os.path.join(parsed_content_dir, "**", "*_chunks.json"), recursive=True):
        logging.info(f"Processing text chunks from: {json_file}")
        try:
            with open(json_file, "r") as f:
                chunks = json.load(f)
                for chunk in chunks:
                    text = chunk.get("text", "").strip()
                    document = chunk.get("document", "unknown")
                    chunk_id = chunk.get("chunk_id", "unknown")
                    if not text:
                        logging.warning(f"Skipping empty text chunk in {json_file}")
                        continue
                    for text_chunk in chunk_text(text):
                        embedding = embedding_model.encode(text_chunk).tolist()
                        metadata = {"document": document, "chunk_id": chunk_id, "type": "text_chunk"}
                        if validate_and_log_metadata(metadata):
                            index.upsert([(f"{document}_{chunk_id}", embedding, metadata)])
                            upload_stats["text_chunks"] += 1
        except Exception as e:
            logging.error(f"Error processing text chunks in {json_file}: {e}")

    # Process Tables
    for table_file in glob.glob(os.path.join(parsed_content_dir, "**", "*-table-*.csv"), recursive=True):
        logging.info(f"Processing table: {table_file}")
        try:
            table_data = pd.read_csv(table_file).to_string()
            if not table_data.strip():
                logging.warning(f"Skipping empty table file: {table_file}")
                continue
            doc_name = Path(table_file).stem.split("-table")[0]
            embedding = embedding_model.encode(table_data).tolist()
            metadata = {"document": doc_name, "type": "table", "filename": os.path.basename(table_file)}
            if validate_and_log_metadata(metadata):
                index.upsert([(f"{doc_name}_table", embedding, metadata)])
                upload_stats["tables"] += 1
        except Exception as e:
            logging.error(f"Error processing table {table_file}: {e}")

    # Process Images
    for img_file in glob.glob(os.path.join(parsed_content_dir, "**", "*.png"), recursive=True):
        logging.info(f"Processing image: {img_file}")
        try:
            doc_name = Path(img_file).stem.split("-")[0]
            image = Image.open(img_file)
            inputs = clip_processor(images=image, return_tensors="pt")
            with torch.no_grad():
                image_embedding = clip_model.get_image_features(**inputs).squeeze().tolist()
            metadata = {"document": doc_name, "type": "image", "filename": os.path.basename(img_file)}
            if validate_and_log_metadata(metadata):
                index.upsert([(f"{doc_name}_{Path(img_file).stem}", image_embedding[:embedding_dimension], metadata)])
                upload_stats["images"] += 1
        except Exception as e:
            logging.error(f"Error processing image {img_file}: {e}")

    # Summary
    logging.info(f"Data upload completed. Summary: {upload_stats}")


# Define the DAG
with DAG(
    dag_id='scraping_and_pinecone_upload',
    schedule_interval='@daily',  # Set the desired schedule interval
    start_date=datetime(2024, 12, 8),  # Change to your desired start date
    catchup=False,
    tags=['webscraping', 'parsing', 'pineconeupload']
) as dag:

    # Task to scrape course data and process metadata
    Webscrape_course_data = PythonOperator(
        task_id='Webscrape_course_data',
        python_callable=process_course_metadata,
        op_kwargs={
            'course_data_urls': course_data_urls,
            'bucket_name': 'mit_scraped_courses',  # Replace with your GCS bucket name
        },
        execution_timeout=timedelta(hours=1)  # Add timeout for this task
    )

    # Task to load data into BigQuery
    bigquery_tables_task = PythonOperator(
        task_id='bigquery_tables_task',
        python_callable=load_data_into_bigquery,
        execution_timeout=timedelta(hours=1)  # Add timeout for this task
    )

    # Task to parse and chunk course data
    coursedata_parsing_and_chunking = PythonOperator(
        task_id='coursedata_parsing_and_chunking',
        python_callable=run_processing_pipeline,  # Wrapper function as the callable
        op_kwargs={
            'base_dir': Path("."),  # Pass BASE_DIR as an argument
        },
        execution_timeout=timedelta(hours=6),  # Ensure sufficient timeout for the task
        retries=3,  # Retry on failure
        retry_delay=timedelta(minutes=10)  # Delay between retries
    )


    # Task to embed and upload data to Pinecone
    embedd_and_pinecone_upload = PythonOperator(
        task_id='embedd_and_pinecone_upload',
        python_callable=embedandpineconeupload,
        execution_timeout=timedelta(hours=2)  # Add timeout for this task
    )

    # Set task dependencies
    Webscrape_course_data >> bigquery_tables_task >> coursedata_parsing_and_chunking >> embedd_and_pinecone_upload
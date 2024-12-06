import logging
import time
from pathlib import Path
import pandas as pd
import json
import unicodedata
import re
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ImageRefMode, PictureItem, TableItem
from docling_core.transforms.chunker import HierarchicalChunker

# Configure logging
logging.basicConfig(level=logging.INFO)
_log = logging.getLogger(__name__)

# Define the resolution scale for images
IMAGE_RESOLUTION_SCALE = 2.0

# Base directory for courses (current directory)
base_dir = Path(".")  # Use the current directory directly
output_dir = Path("parsed_content")  # Base output directory for parsed content
output_dir.mkdir(parents=True, exist_ok=True)

def clean_text(text):
    """
    Clean up text by normalizing Unicode characters, removing GLYPH artifacts,
    and stripping unnecessary whitespace.
    """
    try:
        # Normalize Unicode text
        text = unicodedata.normalize("NFKD", text)
        # Remove unwanted GLYPH placeholders or similar artifacts
        text = re.sub(r"GLYPH<[^>]+>", "", text)
        # Remove other unwanted control characters
        text = re.sub(r"[\x00-\x1F\x7F]", "", text)
        # Normalize spaces
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception as e:
        _log.error(f"Failed to clean text: {e}")
        return None

# Function to process PDF files
def process_pdf(file_path, course_name, content_type):
    pipeline_options = PdfPipelineOptions()
    pipeline_options.images_scale = IMAGE_RESOLUTION_SCALE
    pipeline_options.generate_page_images = True
    pipeline_options.generate_table_images = True
    pipeline_options.generate_picture_images = True

    doc_converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    start_time = time.time()
    conv_res = doc_converter.convert(file_path)
    doc_filename = Path(file_path).stem

    # Output directory for the current course and content type
    course_output_dir = output_dir / course_name / content_type
    course_output_dir.mkdir(parents=True, exist_ok=True)

    # Save images, tables, and figures
    table_counter = 0
    picture_counter = 0

    for element, _level in conv_res.document.iterate_items():
        if isinstance(element, TableItem):
            table_counter += 1
            table_csv_filename = course_output_dir / f"{doc_filename}-table-{table_counter}.csv"
            table_df: pd.DataFrame = element.export_to_dataframe()
            table_df.to_csv(table_csv_filename, index=False)
            _log.info(f"Saved table CSV: {table_csv_filename}")

        if isinstance(element, PictureItem):
            picture_counter += 1
            picture_image_filename = course_output_dir / f"{doc_filename}-picture-{picture_counter}.png"
            with picture_image_filename.open("wb") as fp:
                element.image.pil_image.save(fp, "PNG")
            _log.info(f"Saved picture image: {picture_image_filename}")

    # Chunk text content
    chunks = list(HierarchicalChunker(min_chunk_length=500, max_chunk_length=1500, split_by='paragraph', overlap=50).chunk(conv_res.document))
    chunk_data = []

    for i, chunk in enumerate(chunks):
        text_content = chunk.text
        cleaned_text = clean_text(text_content)  # Clean text
        if not cleaned_text:
            _log.warning(f"Skipped chunk {i} in {doc_filename} due to cleanup failure.")
            continue

        chunk_metadata = {
            "course": course_name,
            "content_type": content_type,
            "document": doc_filename,
            "chunk_id": i,
            "text": cleaned_text,
        }
        chunk_data.append(chunk_metadata)

    # Save chunks to JSON
    chunks_json_filename = course_output_dir / f"{doc_filename}_chunks.json"
    with chunks_json_filename.open("w") as json_fp:
        json.dump(chunk_data, json_fp, indent=4, ensure_ascii=False)  # Save Unicode properly
    _log.info(f"Chunks saved to JSON file: {chunks_json_filename}")

    end_time = time.time() - start_time
    _log.info(f"{doc_filename} processed in {end_time:.2f} seconds.")

# Function to traverse course directories
def process_courses(base_dir):
    if not base_dir.exists():
        _log.error(f"Base directory {base_dir} does not exist.")
        return

    for course_dir in base_dir.iterdir():
        if course_dir.is_dir():
            course_name = course_dir.name
            _log.info(f"Processing course: {course_name}")

            # Process Lecture Notes
            lecture_notes_dir = course_dir / f"{course_name}_Lecture_Notes"
            if lecture_notes_dir.exists():
                _log.info(f"Processing lecture notes in {lecture_notes_dir}")
                for pdf_file in lecture_notes_dir.glob("*.pdf"):
                    process_pdf(pdf_file, course_name, "lecture_notes")

            # Process Transcripts
            transcripts_dir = course_dir / f"{course_name}_transcripts"
            if transcripts_dir.exists():
                _log.info(f"Processing transcripts in {transcripts_dir}")
                for pdf_file in transcripts_dir.glob("*.pdf"):
                    process_pdf(pdf_file, course_name, "transcripts")

# Run the processing pipeline
process_courses(base_dir)

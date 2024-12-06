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

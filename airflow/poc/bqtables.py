import os
import json
import pandas as pd
from google.cloud import bigquery
from google.cloud import storage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize clients
bq_client = bigquery.Client(project=os.getenv('GCP_PROJECT_ID'))
gcs_client = storage.Client(project=os.getenv('GCP_PROJECT_ID'))

# Get environment variables
bucket_name = os.getenv('GCS_BUCKET_NAME')
dataset_id = os.getenv('BQ_DATASET_ID')

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

if __name__ == "__main__":
    load_data_into_bigquery()

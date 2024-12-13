from dotenv import load_dotenv
import os

def get_bigquery_settings():
    # Load environment variables from .env file
    load_dotenv()
    
    return {
        "GOOGLE_APPLICATION_CREDENTIALS": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        "BIGQUERY_PROJECT_ID": os.getenv("BIGQUERY_PROJECT_ID"),
        "BIGQUERY_DATASET": os.getenv("BIGQUERY_DATASET"),
        "BIGQUERY_TABLE": os.getenv("BIGQUERY_TABLE")
    } 
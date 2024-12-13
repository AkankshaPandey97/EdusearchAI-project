import os

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")

ENDPOINTS = {
    "playlists": f"{API_BASE_URL}/playlists",
    "qa": f"{API_BASE_URL}/qa",
    "search": f"{API_BASE_URL}/search",
    "notes": f"{API_BASE_URL}/notes",
    "citations": f"{API_BASE_URL}/citations"
}
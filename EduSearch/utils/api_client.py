# EduSearch/utils/api_client.py
import requests
import aiohttp
from typing import Dict, Any
from config.api_config import ENDPOINTS

class APIClient:
    @staticmethod
    async def get_playlist_details(playlist_id: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ENDPOINTS['playlists']}/{playlist_id}") as response:
                return await response.json()
    
    @staticmethod
    async def get_research_notes(playlist_id: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ENDPOINTS['notes']}/{playlist_id}") as response:
                return await response.json()
    
    @staticmethod
    async def ask_question(question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ENDPOINTS['qa'], 
                json={"question": question, "context": context}
            ) as response:
                return await response.json()
    
    @classmethod
    async def get_topic_segments(cls, course_title: str):
        """Fetch topic segments for a course"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{cls.base_url}/segments",
                json={"course_title": course_title}
            ) as response:
                return await response.json()
    
    @staticmethod
    async def get_citations(playlist_id: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ENDPOINTS['citations']}/{playlist_id}") as response:
                return await response.json()
    
    @staticmethod
    async def process_playlist(playlist_id: str) -> Dict[str, Any]:
        """
        Triggers processing for a playlist on the backend.
        Args:
            playlist_id (str): The ID of the playlist to process
        Returns:
            Dict[str, Any]: Processing status and metadata
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ENDPOINTS['playlists']}/process",
                json={"playlist_id": playlist_id}
            ) as response:
                return await response.json()
    
    @staticmethod
    async def get_playlist_status(playlist_id: str) -> Dict[str, Any]:
        """
        Gets the processing status of a playlist.
        Args:
            playlist_id (str): The ID of the playlist to check
        Returns:
            Dict[str, Any]: Status information
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ENDPOINTS['playlists']}/{playlist_id}/status") as response:
                return await response.json()
            
    
    async def get_segments(self, playlist_id: str):
        """Get segments for a playlist"""
        response = await self._make_request(
            "GET", 
            f"/api/v1/playlists/{playlist_id}/segments"
        )
        return response
    
    async def create_segments(self, playlist_id: str, transcript: str):
        """Create segments for a playlist"""
        response = await self._make_request(
            "POST", 
            f"/api/v1/playlists/{playlist_id}/segments",
            json={"transcript": transcript}
        )
        return response

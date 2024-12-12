from typing import AsyncGenerator
from fastapi import Depends
from functools import lru_cache
from backend.utils.vectorDb.pinecone_client import PineconeClient

class DependencyContainer:
    def __init__(self):
        self._services = {}
        
    def register(self, service_class: type, *args, **kwargs):
        self._services[service_class] = lambda: service_class(*args, **kwargs)
        
    def get(self, service_class: type):
        if service_class not in self._services:
            raise KeyError(f"Service {service_class.__name__} not registered")
        return self._services[service_class]()

container = DependencyContainer()

# Register PineconeClient
container.register(PineconeClient)

@lru_cache()
def get_container() -> DependencyContainer:
    return container

def get_service(service_class: type):
    def _get_service(container: DependencyContainer = Depends(get_container)):
        return container.get(service_class)
    return _get_service

# Create specific dependency for PineconeClient
get_pinecone_index = get_service(PineconeClient)
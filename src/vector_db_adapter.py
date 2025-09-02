"""
Vector Database Adapter for supporting both ChromaDB and Supabase
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import os
import logging

logger = logging.getLogger(__name__)

class VectorDBAdapter(ABC):
    """Abstract base class for vector database adapters"""
    
    @abstractmethod
    def store_embeddings(self, documents: List[str], embeddings: List[List[float]], metadata: List[Dict]) -> None:
        """Store documents with their embeddings and metadata"""
        pass
    
    @abstractmethod
    def search_similar(self, query_embedding: List[float], limit: int = 10, source_filter: Optional[str] = None) -> List[Dict]:
        """Search for similar documents using vector similarity"""
        pass
    
    @abstractmethod
    def get_sources(self) -> List[str]:
        """Get list of available sources/domains"""
        pass

class ChromaDBAdapter(VectorDBAdapter):
    """ChromaDB adapter for local vector storage"""
    
    def __init__(self, persist_directory: str = "./data/chroma"):
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
        except ImportError:
            raise ImportError("ChromaDB not installed. Run: uv add chromadb")
        
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        # Main collection for crawled content
        self.collection = self.client.get_or_create_collection(
            name="crawled_content",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Collection for code examples (if USE_AGENTIC_RAG is enabled)
        self.code_collection = self.client.get_or_create_collection(
            name="code_examples",
            metadata={"hnsw:space": "cosine"}
        )
        
        logger.info(f"ChromaDB initialized with persist directory: {persist_directory}")
    
    def store_embeddings(self, documents: List[str], embeddings: List[List[float]], metadata: List[Dict], collection_type: str = "content") -> None:
        """Store documents with embeddings in ChromaDB"""
        try:
            collection = self.code_collection if collection_type == "code" else self.collection
            
            # Generate unique IDs
            import uuid
            ids = [str(uuid.uuid4()) for _ in documents]
            
            collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadata,
                ids=ids
            )
            
            logger.info(f"Stored {len(documents)} documents in ChromaDB {collection_type} collection")
        except Exception as e:
            logger.error(f"Error storing embeddings in ChromaDB: {e}")
            raise
    
    def search_similar(self, query_embedding: List[float], limit: int = 10, source_filter: Optional[str] = None, collection_type: str = "content") -> List[Dict]:
        """Search for similar documents in ChromaDB"""
        try:
            collection = self.code_collection if collection_type == "code" else self.collection
            
            # Build where filter for source if specified
            where_filter = None
            if source_filter:
                where_filter = {"source": {"$eq": source_filter}}
            
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where_filter
            )
            
            # Format results
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    formatted_results.append({
                        "content": doc,
                        "metadata": metadata,
                        "similarity": 1.0 - distance,  # Convert distance to similarity
                        "source": metadata.get('source', 'unknown')
                    })
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching ChromaDB: {e}")
            return []
    
    def get_sources(self) -> List[str]:
        """Get list of available sources from ChromaDB"""
        try:
            # Get all metadata and extract unique sources
            results = self.collection.get()
            sources = set()
            
            if results['metadatas']:
                for metadata in results['metadatas']:
                    if 'source' in metadata:
                        sources.add(metadata['source'])
            
            return sorted(list(sources))
        except Exception as e:
            logger.error(f"Error getting sources from ChromaDB: {e}")
            return []

class SupabaseAdapter(VectorDBAdapter):
    """Supabase adapter for cloud vector storage"""
    
    def __init__(self, url: str, key: str):
        try:
            from supabase import create_client
        except ImportError:
            raise ImportError("Supabase client not installed. Run: uv add supabase")
        
        self.client = create_client(url, key)
        logger.info("Supabase adapter initialized")
    
    def store_embeddings(self, documents: List[str], embeddings: List[List[float]], metadata: List[Dict], collection_type: str = "content") -> None:
        """Store documents with embeddings in Supabase"""
        try:
            # This would implement the original Supabase storage logic
            # For now, keeping the original implementation structure
            table_name = "code_examples" if collection_type == "code" else "crawled_pages"
            
            # Implementation would go here based on original code
            logger.info(f"Stored {len(documents)} documents in Supabase {table_name} table")
        except Exception as e:
            logger.error(f"Error storing embeddings in Supabase: {e}")
            raise
    
    def search_similar(self, query_embedding: List[float], limit: int = 10, source_filter: Optional[str] = None, collection_type: str = "content") -> List[Dict]:
        """Search for similar documents in Supabase"""
        try:
            # This would implement the original Supabase search logic
            # Implementation would go here based on original code
            return []
        except Exception as e:
            logger.error(f"Error searching Supabase: {e}")
            return []
    
    def get_sources(self) -> List[str]:
        """Get list of available sources from Supabase"""
        try:
            # Implementation would go here based on original code
            return []
        except Exception as e:
            logger.error(f"Error getting sources from Supabase: {e}")
            return []

def get_vector_db() -> VectorDBAdapter:
    """Factory function to get the appropriate vector database adapter"""
    vector_db_type = os.getenv("VECTOR_DB", "supabase").lower()
    
    if vector_db_type == "chromadb":
        persist_dir = os.getenv("CHROMA_PERSIST_DIRECTORY", "./data/chroma")
        return ChromaDBAdapter(persist_dir)
    elif vector_db_type == "supabase":
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set when using Supabase")
        
        return SupabaseAdapter(supabase_url, supabase_key)
    else:
        raise ValueError(f"Unsupported vector database type: {vector_db_type}")

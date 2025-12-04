"""Text chunking and processing for GraphRAG."""

import logging
import json
from typing import List, Dict, Any
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import graphrag_config

logger = logging.getLogger(__name__)


class ChunkProcessor:
    """Processes text into chunks for knowledge graph ingestion."""
    
    def __init__(self):
        """Initialize chunk processor."""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=graphrag_config.CHUNK_SIZE,
            chunk_overlap=graphrag_config.CHUNK_OVERLAP,
            separators=graphrag_config.CHUNK_SEPARATORS
        )
    
    def split_text(self, text: str) -> List[str]:
        """Split text into chunks.
        
        Args:
            text: Text to split
            
        Returns:
            List of text chunks
        """
        try:
            chunks = self.text_splitter.split_text(text)
            logger.info(f"Split text into {len(chunks)} chunks")
            return chunks
        except Exception as e:
            logger.error(f"Failed to split text: {e}")
            raise
    
    def extract_text_from_json(self, json_data: Dict[str, Any]) -> str:
        """Recursively extract all text content from JSON structure.
        
        Args:
            json_data: JSON data structure
            
        Returns:
            Extracted text concatenated with newlines
        """
        texts = []
        
        def extract_recursive(obj: Any):
            """Recursively extract text from nested structures."""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    # Extract text from known text fields
                    if key in ['content_text', 'text', 'description', 'title', 'content']:
                        if isinstance(value, str) and value.strip():
                            texts.append(value.strip())
                    # Recurse into nested structures
                    elif isinstance(value, (dict, list)):
                        extract_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_recursive(item)
        
        extract_recursive(json_data)
        return "\n\n".join(texts)
    
    def load_json_file(self, file_path: str) -> Dict[str, Any]:
        """Load and parse a JSON file.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Parsed JSON data
            
        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Loaded JSON file: {file_path}")
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in file {file_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load JSON file {file_path}: {e}")
            raise
    
    def process_json_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Process a JSON file into chunks with metadata.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        try:
            # Load JSON data
            json_data = self.load_json_file(file_path)
            
            # Extract text
            text = self.extract_text_from_json(json_data)
            
            if not text:
                logger.warning(f"No text content found in {file_path}")
                return []
            
            # Split into chunks
            chunk_texts = self.split_text(text)
            
            # Create chunk objects with metadata
            chunks = []
            file_name = Path(file_path).name
            
            for idx, chunk_text in enumerate(chunk_texts):
                chunks.append({
                    "text": chunk_text,
                    "source": file_name,
                    "chunk_id": f"{file_name}_chunk_{idx}",
                    "chunk_index": idx,
                    "total_chunks": len(chunk_texts)
                })
            
            logger.info(f"Processed {file_path} into {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to process JSON file {file_path}: {e}")
            raise
    
    def get_files_in_directory(self, directory: str, pattern: str = "*.json") -> List[Path]:
        """Get all JSON files in a directory.
        
        Args:
            directory: Directory path
            pattern: File pattern to match (default: *.json)
            
        Returns:
            List of file paths
            
        Raises:
            FileNotFoundError: If directory doesn't exist
        """
        try:
            dir_path = Path(directory)
            if not dir_path.exists():
                raise FileNotFoundError(f"Directory not found: {directory}")
            
            if not dir_path.is_dir():
                raise ValueError(f"Not a directory: {directory}")
            
            files = list(dir_path.glob(pattern))
            logger.info(f"Found {len(files)} files matching {pattern} in {directory}")
            return files
            
        except Exception as e:
            logger.error(f"Failed to get files from directory {directory}: {e}")
            raise

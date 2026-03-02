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
    
    def extract_pages_with_urls(self, json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract pages with their URLs and content.
        
        Args:
            json_data: JSON data structure
            
        Returns:
            List of pages with URL and text content
        """
        pages_data = []
        
        # Handle nested data structure
        if 'data' in json_data and isinstance(json_data['data'], list):
            for data_item in json_data['data']:
                if 'pages' in data_item and isinstance(data_item['pages'], list):
                    for page in data_item['pages']:
                        if isinstance(page, dict):
                            url = page.get('url', '')
                            
                            # Extract text from this page
                            text_parts = []
                            
                            # Get title
                            if 'title' in page and page['title']:
                                text_parts.append(page['title'])
                            
                            # Get content_text
                            if 'content_text' in page and page['content_text']:
                                text_parts.append(page['content_text'])
                            
                            # Get content_html as fallback
                            elif 'content_html' in page and page['content_html']:
                                text_parts.append(page['content_html'])
                            
                            # Extract from sections
                            if 'sections' in page and isinstance(page['sections'], list):
                                for section in page['sections']:
                                    if isinstance(section, dict):
                                        if 'heading' in section and section['heading']:
                                            text_parts.append(section['heading'])
                                        
                                        # Extract content from section
                                        if 'content' in section and isinstance(section['content'], list):
                                            for content_item in section['content']:
                                                if isinstance(content_item, dict) and 'text' in content_item:
                                                    if content_item['text']:
                                                        text_parts.append(content_item['text'])
                            
                            if text_parts:
                                pages_data.append({
                                    'url': url,
                                    'text': '\n\n'.join(text_parts),
                                    'page_id': page.get('page_id', ''),
                                    'title': page.get('title', '')
                                })
        
        # Fallback: if no pages structure found, try direct pages array
        elif 'pages' in json_data and isinstance(json_data['pages'], list):
            for page in json_data['pages']:
                if isinstance(page, dict):
                    url = page.get('url', '')
                    text = self.extract_text_from_json(page)
                    if text:
                        pages_data.append({
                            'url': url,
                            'text': text,
                            'page_id': page.get('page_id', ''),
                            'title': page.get('title', '')
                        })
        
        return pages_data
    
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
        """Process a JSON file into chunks with metadata including URLs.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            List of chunk dictionaries with text, URL, and metadata
        """
        try:
            # Load JSON data
            json_data = self.load_json_file(file_path)
            file_name = Path(file_path).name
            
            # Extract pages with URLs
            pages = self.extract_pages_with_urls(json_data)
            
            if not pages:
                # Fallback to old method if no pages found
                logger.warning(f"No pages with URLs found in {file_path}, using fallback extraction")
                text = self.extract_text_from_json(json_data)
                
                if not text:
                    logger.warning(f"No text content found in {file_path}")
                    return []
                
                # Split into chunks without URLs
                chunk_texts = self.split_text(text)
                chunks = []
                
                for idx, chunk_text in enumerate(chunk_texts):
                    chunks.append({
                        "text": chunk_text,
                        "source": file_name,
                        "url": "",  # No URL available
                        "chunk_id": f"{file_name}_chunk_{idx}",
                        "chunk_index": idx,
                        "total_chunks": len(chunk_texts)
                    })
                
                logger.info(f"Processed {file_path} into {len(chunks)} chunks (no URLs)")
                return chunks
            
            # Process each page separately to preserve URL associations
            all_chunks = []
            chunk_counter = 0
            
            for page in pages:
                page_text = page['text']
                page_url = page['url']
                page_title = page.get('title', '')
                
                if not page_text:
                    continue
                
                # Split page text into chunks
                chunk_texts = self.split_text(page_text)
                
                # Create chunk objects with URL preserved
                for idx, chunk_text in enumerate(chunk_texts):
                    all_chunks.append({
                        "text": chunk_text,
                        "source": file_name,
                        "url": page_url,  # Source URL for this chunk
                        "page_title": page_title,
                        "chunk_id": f"{file_name}_chunk_{chunk_counter}",
                        "chunk_index": chunk_counter,
                        "page_chunk_index": idx,  # Index within this page
                    })
                    chunk_counter += 1
            
            # Add total chunks count to all chunks
            for chunk in all_chunks:
                chunk["total_chunks"] = len(all_chunks)
            
            logger.info(f"Processed {file_path} into {len(all_chunks)} chunks from {len(pages)} pages")
            return all_chunks
            
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

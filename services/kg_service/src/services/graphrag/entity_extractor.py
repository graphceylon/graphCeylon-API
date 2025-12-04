"""Entity extraction using LLM for knowledge graph construction."""

import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from ...models.graphrag import GraphExtraction, GraphNode, GraphRelationship
from .config import graphrag_config

logger = logging.getLogger(__name__)


class EntityExtractor:
    """Extracts entities and relationships from text using LLM."""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize entity extractor.
        
        Args:
            openai_api_key: OpenAI API key for LLM access
        """
        self.openai_api_key = openai_api_key
        self.llm = None
        
        if openai_api_key:
            try:
                self.llm = ChatOpenAI(
                    model=graphrag_config.LLM_MODEL,
                    temperature=graphrag_config.LLM_TEMPERATURE,
                    api_key=openai_api_key
                )
                logger.info("Entity extractor LLM initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize LLM: {e}")
                self.llm = None
        else:
            logger.warning("No OpenAI API key provided. Entity extraction will be unavailable.")
    
    def extract_entities(self, text: str) -> GraphExtraction:
        """Extract entities and relationships from text.
        
        Args:
            text: Text to extract entities from
            
        Returns:
            GraphExtraction with nodes and relationships
            
        Raises:
            ValueError: If LLM is not initialized
        """
        if not self.llm:
            raise ValueError("LLM not initialized. Provide OpenAI API key.")
        
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", self._get_system_prompt()),
                ("user", "Extract entities and relationships from this text:\n\n{text}")
            ])
            
            # Use structured output for reliable extraction
            extraction_llm = self.llm.with_structured_output(GraphExtraction)
            chain = prompt | extraction_llm
            
            result = chain.invoke({"text": text})
            
            # Filter entities and relationships based on allowed types
            filtered_nodes = [
                node for node in result.nodes 
                if node.type in graphrag_config.ALLOWED_NODES
            ]
            
            filtered_relationships = [
                rel for rel in result.relationships 
                if rel.type in graphrag_config.ALLOWED_RELATIONSHIPS
            ]
            
            logger.info(f"Extracted {len(filtered_nodes)} nodes and {len(filtered_relationships)} relationships")
            
            return GraphExtraction(
                nodes=filtered_nodes,
                relationships=filtered_relationships
            )
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            raise
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for entity extraction.
        
        Returns:
            System prompt string
        """
        return f"""You are an expert Knowledge Graph extractor for Sri Lankan immigration and policy data.
Extract entities and relationships from the text focusing on Economic & Policy domain.

Allowed Node Types: {', '.join(graphrag_config.ALLOWED_NODES)}
Allowed Relationship Types: {', '.join(graphrag_config.ALLOWED_RELATIONSHIPS)}

Focus on extracting:
- Policies and regulations
- Visa types and requirements
- Required documents
- Fees and costs (with amounts and currency)
- Procedures and steps
- Government authorities and locations
- Time frames and deadlines

Guidelines:
1. Create unique IDs for each entity (e.g., 'policy_dual_citizenship', 'doc_birth_cert')
2. Extract all important properties (name, amount, duration, etc.)
3. Link related entities with appropriate relationships
4. Be specific and concrete - avoid vague entities
5. Preserve important details like amounts, dates, and requirements

Return a structured extraction with nodes and relationships."""
    
    def is_available(self) -> bool:
        """Check if entity extraction is available.
        
        Returns:
            True if LLM is initialized, False otherwise
        """
        return self.llm is not None

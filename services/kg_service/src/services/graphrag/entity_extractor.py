"""Entity extraction using LLM for knowledge graph construction."""

import logging
from typing import Optional

from models.ai.graphrag import GraphExtraction, GraphNode, GraphRelationship
from services.graphrag.config import graphrag_config
from services.llm import LLMFactory
from core.config import settings

logger = logging.getLogger(__name__)


class EntityExtractor:
    """Extracts entities and relationships from text using LLM."""
    
    def __init__(self):
        """Initialize entity extractor with configured ingestion LLM."""
        self.llm = None
        
        # Get API key based on configured provider
        api_key = None
        if settings.ingestion_llm_provider == "openai":
            api_key = settings.openai_api_key
        elif settings.ingestion_llm_provider == "groq":
            api_key = settings.groq_api_key
        
        if api_key:
            try:
                # Create provider using factory
                provider = LLMFactory.create_from_config(
                    settings.ingestion_llm_provider,
                    api_key
                )
                
                if provider:
                    self.llm = provider.get_chat_model(
                        model=settings.ingestion_llm_model,
                        temperature=settings.llm_temperature
                    )
                    logger.info(f"Entity extractor initialized with {settings.ingestion_llm_provider} ({settings.ingestion_llm_model})")
                else:
                    logger.error(f"Failed to create provider: {settings.ingestion_llm_provider}")
            except Exception as e:
                logger.error(f"Failed to initialize LLM: {e}")
                self.llm = None
        else:
            logger.warning(f"No API key provided for {settings.ingestion_llm_provider}. Entity extraction will be unavailable.")
    
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
            from langchain_core.prompts import ChatPromptTemplate
            prompt = ChatPromptTemplate.from_messages([
                ("system", self._get_system_prompt()),
                ("user", "Extract entities and relationships from this text:\n\n{text}")
            ])
            
            # Use function calling for reliable extraction (more compatible with nested schemas)
            extraction_llm = self.llm.with_structured_output(GraphExtraction, method="function_calling")
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

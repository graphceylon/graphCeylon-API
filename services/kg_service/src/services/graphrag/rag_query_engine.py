"""RAG query engine for answering questions using knowledge graph."""

import logging
from typing import List, Dict, Any, Optional
from neo4j import Driver

from core.config import settings
from services.embeddings import embedding_service
from services.graphrag.config import graphrag_config
from services.llm import LLMFactory

logger = logging.getLogger(__name__)


class RAGQueryEngine:
    """Executes RAG queries against the knowledge graph."""
    
    def __init__(self, driver: Driver):
        """Initialize RAG query engine with configured query LLM.
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
        self.llm = None
        
        # Get API key based on configured provider
        api_key = None
        if settings.query_llm_provider == "openai":
            api_key = settings.openai_api_key
        elif settings.query_llm_provider == "groq":
            api_key = settings.groq_api_key
        
        # Initialize LLM if API key provided
        if api_key:
            try:
                # Create provider using factory
                provider = LLMFactory.create_from_config(
                    settings.query_llm_provider,
                    api_key
                )
                
                if provider:
                    self.llm = provider.get_chat_model(
                        model=settings.query_llm_model,
                        temperature=settings.llm_temperature
                    )
                    logger.info(f"RAG query engine initialized with {settings.query_llm_provider} ({settings.query_llm_model})")
                else:
                    logger.error(f"Failed to create provider: {settings.query_llm_provider}")
            except Exception as e:
                logger.error(f"Failed to initialize LLM: {e}")
                self.llm = None
        else:
            logger.warning(f"No API key provided for {settings.query_llm_provider}. RAG queries will be unavailable.")
    
    def query(
        self, 
        question: str, 
        domain_name: str = "Economic & Policy", 
        top_k: int = 5
    ) -> Dict[str, Any]:
        """Execute a RAG query.
        
        Args:
            question: Question to answer
            domain_name: Domain to search within
            top_k: Number of similar chunks to retrieve
            
        Returns:
            Dictionary with answer, context, and metadata
            
        Raises:
            ValueError: If LLM is not initialized
        """
        if not self.llm:
            raise ValueError(f"LLM not initialized. Provide API key for {settings.query_llm_provider}.")
        
        try:
            # 1. Generate query embedding
            query_embedding = self._generate_embedding(question)
            
            # 2. Retrieve similar chunks
            similar_chunks = self._retrieve_similar_chunks(
                query_embedding, 
                domain_name, 
                top_k
            )
            
            if not similar_chunks:
                return {
                    "answer": "I couldn't find relevant information to answer this question.",
                    "context": [],
                    "metadata": {
                        "question": question,
                        "domain": domain_name,
                        "chunks_found": 0
                    }
                }
            
            # 3. Generate answer using LLM
            answer = self._generate_answer(question, similar_chunks)
            
            # 4. Format response
            return {
                "answer": answer,
                "context": similar_chunks,
                "metadata": {
                    "question": question,
                    "domain": domain_name,
                    "chunks_found": len(similar_chunks),
                    "top_k": top_k
                }
            }
            
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            raise
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using the centralized embedding service."""
        embedding = embedding_service.generate_embedding(text)
        if not embedding:
            raise ValueError("Failed to generate embedding for query text")
        return embedding
    
    def _retrieve_similar_chunks(
        self, 
        query_embedding: List[float], 
        domain_name: str, 
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Retrieve similar chunks using vector similarity.
        
        Args:
            query_embedding: Query embedding vector
            domain_name: Domain to filter by
            top_k: Number of results to return
            
        Returns:
            List of similar chunks with metadata
        """
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (c:Chunk)-[:BELONGS_TO]->(d:Domain {name: $domain_name})
                    WHERE c.embedding IS NOT NULL
                    WITH c, 
                         vector.similarity.cosine(c.embedding, $query_embedding) AS score
                    WHERE score > 0.5
                    RETURN c.text AS text,
                           c.source AS source,
                           c.url AS url,
                           c.chunk_id AS chunk_id,
                           score
                    ORDER BY score DESC
                    LIMIT $top_k
                """, {
                    "query_embedding": query_embedding,
                    "domain_name": domain_name,
                    "top_k": top_k
                })
                
                chunks = []
                for record in result:
                    chunks.append({
                        "text": record["text"],
                        "source": record["source"],
                        "url": record.get("url", ""),
                        "chunk_id": record["chunk_id"],
                        "relevance_score": record["score"]
                    })
                
                logger.info(f"Retrieved {len(chunks)} similar chunks")
                return chunks
                
        except Exception as e:
            logger.error(f"Failed to retrieve similar chunks: {e}")
            raise
    
    def _generate_answer(self, question: str, context_chunks: List[Dict[str, Any]]) -> str:
        """Generate answer using LLM based on retrieved context.
        
        Args:
            question: User question
            context_chunks: Retrieved context chunks
            
        Returns:
            Generated answer
        """
        try:
            # Format context with URLs
            context_parts = []
            for chunk in context_chunks:
                url = chunk.get('url', '')
                source = chunk['source']
                score = chunk['relevance_score']
                text = chunk['text']
                
                context_part = f"Source: {source}\nRelevance: {score:.2f}"
                if url:
                    context_part += f"\nURL: {url}"
                context_part += f"\n{text}"
                
                context_parts.append(context_part)
            
            context_text = "\n\n---\n\n".join(context_parts)
            
            # Create prompt
            from langchain_core.prompts import ChatPromptTemplate
            prompt = ChatPromptTemplate.from_messages([
                ("system", self._get_system_prompt()),
                ("user", "Context:\n{context}\n\nQuestion: {question}")
            ])
            
            # Generate answer
            chain = prompt | self.llm
            response = chain.invoke({
                "context": context_text,
                "question": question
            })
            
            answer = response.content
            logger.info(f"Generated answer of length {len(answer)}")
            return answer
            
        except Exception as e:
            logger.error(f"Failed to generate answer: {e}")
            raise
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for answer generation.
        
        Returns:
            System prompt string
        """
        return """You are an expert assistant for Sri Lankan immigration and policy questions.

Your task is to answer questions based on the provided context about policies, visas, citizenship, passports, and related services.

Guidelines:
1. Answer based ONLY on the provided context - don't make up information
2. If the context doesn't contain enough information, say so clearly
3. Be specific and cite details like fees, requirements, and procedures
4. Use clear, professional language
5. Structure your answer with bullet points or numbered lists when appropriate
6. If multiple options exist (e.g., different visa types), explain them clearly
7. ALWAYS include relevant source URLs in your answer when they are provided in the context
8. Format URLs as clickable links at the end of relevant information or in a "References" section

When URLs are available, include them like:
- "For more information, visit: [URL]"
- Or include a "References:" section at the end with all relevant URLs

If you're unsure or the context is insufficient, respond with:
"Based on the available information, I cannot provide a complete answer to this question. Please consult official immigration authorities for accurate details." """
    
    def is_available(self) -> bool:
        """Check if RAG queries are available.
        
        Returns:
            True if LLM is initialized, False otherwise
        """
        return self.llm is not None
    
    def retrieve_relevant_chunks(
        self,
        query_text: str,
        domain_name: str = "Economic & Policy",
        top_k: int = 10,
        min_score: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks without LLM answer generation.
        
        This method performs only the retrieval step of RAG, suitable for
        when another service handles the answer generation.
        
        Args:
            query_text: Text to search for
            domain_name: Domain to search within
            top_k: Number of similar chunks to retrieve
            min_score: Minimum similarity score threshold (0-1)
            
        Returns:
            List of relevant chunks with metadata and relevance scores
        """
        try:
            # 1. Generate query embedding
            query_embedding = self._generate_embedding(query_text)
            
            # 2. Retrieve similar chunks
            similar_chunks = self._retrieve_similar_chunks_with_threshold(
                query_embedding,
                domain_name,
                top_k,
                min_score
            )
            
            logger.info(f"Retrieved {len(similar_chunks)} chunks for query: {query_text[:50]}...")
            return similar_chunks
            
        except Exception as e:
            logger.error(f"Chunk retrieval failed: {e}")
            raise
    
    def _retrieve_similar_chunks_with_threshold(
        self,
        query_embedding: List[float],
        domain_name: str,
        top_k: int,
        min_score: float
    ) -> List[Dict[str, Any]]:
        """Retrieve similar chunks with custom threshold.
        
        Args:
            query_embedding: Query embedding vector
            domain_name: Domain to filter by
            top_k: Number of results to return
            min_score: Minimum similarity score
            
        Returns:
            List of similar chunks with metadata
        """
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (c:Chunk)-[:BELONGS_TO]->(d:Domain {name: $domain_name})
                    WHERE c.embedding IS NOT NULL
                    WITH c, 
                         vector.similarity.cosine(c.embedding, $query_embedding) AS score
                    WHERE score > $min_score
                    
                    // Get entities mentioned in chunk
                    OPTIONAL MATCH (c)-[:MENTIONS]->(entity)
                    WHERE NOT entity:Domain AND NOT entity:Chunk
                    
                    WITH c, score, 
                         collect(DISTINCT {
                             id: entity.id,
                             type: labels(entity)[0],
                             properties: properties(entity)
                         }) AS entities
                    
                    RETURN c.text AS text,
                           c.source AS source,
                           c.url AS url,
                           c.id AS chunk_id,
                           score,
                           entities
                    ORDER BY score DESC
                    LIMIT $top_k
                """, {
                    "query_embedding": query_embedding,
                    "domain_name": domain_name,
                    "top_k": top_k,
                    "min_score": min_score
                })
                
                chunks = []
                for record in result:
                    chunks.append({
                        "text": record["text"],
                        "source": record["source"],
                        "url": record.get("url", ""),
                        "chunk_id": record["chunk_id"],
                        "relevance_score": record["score"],
                        "entities": record["entities"] or []
                    })
                
                logger.info(f"Retrieved {len(chunks)} similar chunks with threshold {min_score}")
                return chunks
                
        except Exception as e:
            logger.error(f"Failed to retrieve similar chunks: {e}")
            raise

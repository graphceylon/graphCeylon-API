"""RAG query engine for answering questions using knowledge graph."""

import logging
from typing import List, Dict, Any, Optional
from neo4j import Driver
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from sentence_transformers import SentenceTransformer

from ...core.config import settings
from .config import graphrag_config

logger = logging.getLogger(__name__)


class RAGQueryEngine:
    """Executes RAG queries against the knowledge graph."""
    
    def __init__(self, driver: Driver, openai_api_key: Optional[str] = None):
        """Initialize RAG query engine.
        
        Args:
            driver: Neo4j driver instance
            openai_api_key: OpenAI API key for LLM access
        """
        self.driver = driver
        self.openai_api_key = openai_api_key
        self.llm = None
        
        # Initialize embedding model
        try:
            self.embedding_model = SentenceTransformer(settings.embedding_model)
            logger.info(f"Embedding model '{settings.embedding_model}' initialized")
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {e}")
            raise
        
        # Initialize LLM if API key provided
        if openai_api_key:
            try:
                self.llm = ChatOpenAI(
                    model=graphrag_config.LLM_MODEL,
                    temperature=graphrag_config.LLM_TEMPERATURE,
                    api_key=openai_api_key
                )
                logger.info("RAG query LLM initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize LLM: {e}")
                self.llm = None
        else:
            logger.warning("No OpenAI API key provided. RAG queries will be unavailable.")
    
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
            raise ValueError("LLM not initialized. Provide OpenAI API key.")
        
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
        """Generate embedding for text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        try:
            embedding = self.embedding_model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
    
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
            # Format context
            context_text = "\n\n---\n\n".join([
                f"Source: {chunk['source']}\nRelevance: {chunk['relevance_score']:.2f}\n{chunk['text']}"
                for chunk in context_chunks
            ])
            
            # Create prompt
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

If you're unsure or the context is insufficient, respond with:
"Based on the available information, I cannot provide a complete answer to this question. Please consult official immigration authorities for accurate details." """
    
    def is_available(self) -> bool:
        """Check if RAG queries are available.
        
        Returns:
            True if LLM is initialized, False otherwise
        """
        return self.llm is not None

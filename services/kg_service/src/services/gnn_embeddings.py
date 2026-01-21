"""
Graph Neural Network embeddings for knowledge graph entities.

This module implements Graph Attention Networks (GAT) for learning entity embeddings
from the Neo4j knowledge graph structure, enabling:
- Link prediction
- Entity similarity search
- Knowledge graph completion
- Hybrid reasoning with symbolic queries
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.data import Data
from torch_geometric.nn import GATConv, global_mean_pool
from torch_geometric.utils import negative_sampling
from neo4j import Driver
from neo4j.time import DateTime, Date, Time

logger = logging.getLogger(__name__)


def sanitize_neo4j_types(obj: Any) -> Any:
    """
    Convert Neo4j-specific types to Python-native types for JSON serialization.
    
    Args:
        obj: Any object that might contain Neo4j types
        
    Returns:
        Object with Neo4j types converted to Python native types
    """
    if isinstance(obj, (DateTime, Date, Time)):
        return obj.iso_format()
    elif isinstance(obj, dict):
        return {k: sanitize_neo4j_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_neo4j_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitize_neo4j_types(item) for item in obj)
    else:
        return obj


class TourismKGEmbedder(nn.Module):
    """
    Graph Attention Network for tourism knowledge graph embeddings.
    
    Architecture:
    - 3-layer GAT with multi-head attention
    - Learns node embeddings that capture both:
      * Structural patterns (graph topology)
      * Semantic relationships (edge types, attributes)
    """
    
    def __init__(
        self,
        in_channels: int = 128,
        hidden_channels: int = 64,
        out_channels: int = 32,
        num_heads: int = 4,
        dropout: float = 0.3
    ):
        super(TourismKGEmbedder, self).__init__()
        
        self.in_channels = in_channels
        self.hidden_channels = hidden_channels
        self.out_channels = out_channels
        
        # First GAT layer with multi-head attention
        self.conv1 = GATConv(
            in_channels=in_channels,
            out_channels=hidden_channels,
            heads=num_heads,
            dropout=dropout,
            add_self_loops=True
        )
        
        # Second GAT layer
        self.conv2 = GATConv(
            in_channels=hidden_channels * num_heads,
            out_channels=hidden_channels // 2,
            heads=num_heads,
            dropout=dropout,
            add_self_loops=True
        )
        
        # Final layer (single head)
        self.conv3 = GATConv(
            in_channels=(hidden_channels // 2) * num_heads,
            out_channels=out_channels,
            heads=1,
            concat=False,
            dropout=dropout
        )
        
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through GAT layers.
        
        Args:
            x: Node feature matrix [num_nodes, in_channels]
            edge_index: Graph connectivity [2, num_edges]
            
        Returns:
            Node embeddings [num_nodes, out_channels]
        """
        # Layer 1
        x = self.conv1(x, edge_index)
        x = F.elu(x)
        x = self.dropout(x)
        
        # Layer 2
        x = self.conv2(x, edge_index)
        x = F.elu(x)
        x = self.dropout(x)
        
        # Layer 3 (output)
        x = self.conv3(x, edge_index)
        
        return x


class LinkPredictor(nn.Module):
    """
    Link prediction module for knowledge graph completion.
    
    Predicts probability of relationship between two entities.
    """
    
    def __init__(self, embedding_dim: int = 32, hidden_dim: int = 64):
        super(LinkPredictor, self).__init__()
        
        self.fc1 = nn.Linear(embedding_dim * 2, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.fc3 = nn.Linear(hidden_dim // 2, 1)
        self.dropout = nn.Dropout(0.3)
        
    def forward(self, emb1: torch.Tensor, emb2: torch.Tensor) -> torch.Tensor:
        """
        Predict link between two nodes.
        
        Args:
            emb1: Embedding of first entity [batch, embedding_dim]
            emb2: Embedding of second entity [batch, embedding_dim]
            
        Returns:
            Link probability [batch, 1]
        """
        # Concatenate embeddings
        x = torch.cat([emb1, emb2], dim=-1)
        
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = F.relu(self.fc2(x))
        x = self.dropout(x)
        x = torch.sigmoid(self.fc3(x))
        
        return x


class GNNEmbeddingService:
    """
    Service for managing GNN embeddings in the tourism knowledge graph.
    
    Responsibilities:
    - Extract graph structure from Neo4j
    - Train GNN embeddings
    - Perform link prediction
    - Compute entity similarities
    - Integrate with hybrid reasoning
    """
    
    def __init__(
        self,
        driver: Driver,
        embedding_dim: int = 32,
        device: Optional[str] = None
    ):
        self.driver = driver
        self.embedding_dim = embedding_dim
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Models
        self.embedder: Optional[TourismKGEmbedder] = None
        self.link_predictor: Optional[LinkPredictor] = None
        
        # Cached data
        self.node_embeddings: Optional[torch.Tensor] = None
        self.node_id_map: Optional[Dict[str, int]] = None
        self.reverse_node_map: Optional[Dict[int, str]] = None
        self.edge_index: Optional[torch.Tensor] = None
        self.node_types: Optional[List[str]] = None  # NEW: Track node types
        
        logger.info(f"GNN Embedding Service initialized on device: {self.device}")
    
    def _extract_heterogeneous_features(
        self,
        node_type: str,
        props: Dict[str, Any],
        all_types: List[str]
    ) -> List[float]:
        """
        Extract type-aware features for heterogeneous graph.
        
        Args:
            node_type: Primary label of the node
            props: Node properties dictionary
            all_types: List of all possible node types
            
        Returns:
            128-dimensional feature vector
        """
        features = []
        
        # 1. Node type one-hot encoding (first 27 dimensions)
        type_embedding = [1.0 if t == node_type else 0.0 for t in all_types[:27]]
        features.extend(type_embedding)
        
        # 2. Type-specific features (next ~20 dimensions)
        if node_type == 'Attraction':
            features.extend([
                float(props.get('rating', 0)) / 5.0,
                float(props.get('latitude', 0)) / 90.0,
                float(props.get('longitude', 0)) / 180.0,
                float(np.log1p(props.get('userRatingsTotal', 0))) / 10.0,
                float(len(str(props.get('description', '')))) / 1000.0,
            ])
        elif node_type == 'Policy':
            # Policy-specific features
            features.extend([
                1.0,  # Is policy
                float(len(str(props.get('id', '')))),
                0.0, 0.0, 0.0
            ])
        elif node_type == 'Chunk':
            # Chunk-specific features (text embeddings if available)
            embedding = props.get('embedding', [])
            if embedding and len(embedding) > 0:
                # Use first 5 dimensions of text embedding
                features.extend([float(embedding[i]) if i < len(embedding) else 0.0 for i in range(5)])
            else:
                features.extend([
                    float(len(str(props.get('text', '')))) / 1000.0,
                    1.0,  # Has text
                    0.0, 0.0, 0.0
                ])
        elif node_type in ['District', 'Province', 'Location']:
            # Geographic features
            features.extend([
                1.0,  # Is geographic
                float(len(str(props.get('name', '')))),
                0.0, 0.0, 0.0
            ])
        elif node_type == 'Holiday':
            # Holiday-specific features
            features.extend([
                1.0 if props.get('isPublicHoliday') else 0.0,
                float(props.get('duration_days', 1)),
                float(props.get('month', 0)) / 12.0,
                float(props.get('day', 0)) / 31.0,
                0.0
            ])
        elif node_type in ['Month', 'Year']:
            # Temporal features
            features.extend([
                float(props.get('year', 2025)) / 2100.0,
                float(props.get('month', 1)) / 12.0,
                1.0,  # Is temporal
                0.0, 0.0
            ])
        elif node_type == 'Domain':
            # Domain features
            features.extend([
                float(props.get('order', 0)) / 20.0,
                1.0,  # Is domain
                0.0, 0.0, 0.0
            ])
        else:
            # Generic features for other types
            features.extend([
                1.0 if props.get('name') else 0.0,
                1.0 if props.get('id') else 0.0,
                float(len(props)) / 10.0,  # Property count
                0.0, 0.0
            ])
        
        # 3. Pad to exactly 128 dimensions
        while len(features) < 128:
            features.append(0.0)
        
        return features[:128]
        
        # Cached data
        self.node_embeddings: Optional[torch.Tensor] = None
        self.node_id_map: Optional[Dict[str, int]] = None
        self.reverse_node_map: Optional[Dict[int, str]] = None
        self.edge_index: Optional[torch.Tensor] = None
        
        logger.info(f"GNN Embedding Service initialized on device: {self.device}")
    
    def extract_graph_from_neo4j(
        self,
        node_labels: Optional[List[str]] = None,
        relationship_types: Optional[List[str]] = None,
        limit: int = 10000
    ) -> Tuple[Data, Dict[str, int]]:
        """
        Extract graph structure from Neo4j and convert to PyTorch Geometric format.
        
        Args:
            node_labels: Specific node labels to include (None = all)
            relationship_types: Specific relationships to include (None = all)
            limit: Maximum number of nodes to extract
            
        Returns:
            Tuple of (PyG Data object, node_id_mapping)
        """
        logger.info("Extracting graph structure from Neo4j...")
        
        # Build node query with proper OR logic
        if node_labels:
            label_conditions = " OR ".join([f"'{label}' IN labels(n)" for label in node_labels])
            where_clause = f"WHERE {label_conditions}"
        else:
            where_clause = ""
        
        # Extract nodes with ALL properties for heterogeneous graph (using elementId())
        node_query = f"""
        MATCH (n)
        {where_clause}
        RETURN 
            elementId(n) AS neo4j_id,
            labels(n) AS labels,
            properties(n) AS props
        LIMIT {limit}
        """
        
        with self.driver.session() as session:
            node_results = session.run(node_query)
            nodes = [dict(record) for record in node_results]
        
        # Create node ID mapping
        node_id_map = {node['neo4j_id']: idx for idx, node in enumerate(nodes)}
        reverse_node_map = {idx: node['neo4j_id'] for idx, node in enumerate(nodes)}
        
        # Extract edges (using elementId())
        if relationship_types:
            rel_filter = "|".join(relationship_types)
            rel_match = f"-[r:{rel_filter}]->"
        else:
            rel_match = "-[r]->"
        
        edge_query = f"""
        MATCH (a){rel_match}(b)
        WHERE elementId(a) IN $node_ids AND elementId(b) IN $node_ids
        RETURN 
            elementId(a) AS source,
            elementId(b) AS target,
            type(r) AS rel_type
        """
        
        with self.driver.session() as session:
            edge_results = session.run(edge_query, node_ids=list(node_id_map.keys()))
            edges = [dict(record) for record in edge_results]
        
        # Convert to edge index
        edge_sources = [node_id_map[e['source']] for e in edges if e['source'] in node_id_map]
        edge_targets = [node_id_map[e['target']] for e in edges if e['target'] in node_id_map]
        
        edge_index = torch.tensor([edge_sources, edge_targets], dtype=torch.long)
        
        # Create heterogeneous node features (type-aware)
        num_nodes = len(nodes)
        node_features = []
        node_type_names = []
        
        # Define all possible node types (29 types from analysis)
        ALL_NODE_TYPES = [
            'Attraction', 'Policy', 'Chunk', 'District', 'Location', 'Authority',
            'Domain', 'Month', 'Year', 'Province', 'Holiday', 'TimeFrame',
            'NewsArticle', 'TourismProject', 'Procedure', 'SHACLShape', 'SHACLProperty',
            'NewsCategory', 'VisaType', 'Document', 'CitizenshipService', 'VisaPolicy',
            'Country', 'Evidence', 'Fee', 'Warning', 'ImmigrationService'
        ]
        
        for node in nodes:
            primary_label = node['labels'][0] if node['labels'] else 'Unknown'
            node_type_names.append(primary_label)
            props = node.get('props', {})
            
            features = self._extract_heterogeneous_features(primary_label, props, ALL_NODE_TYPES)
            node_features.append(features)
        
        node_features = torch.tensor(node_features, dtype=torch.float32)
        
        # Store node types for analysis
        self.node_types = node_type_names
        
        # Create PyG Data object
        data = Data(
            x=node_features,
            edge_index=edge_index,
            num_nodes=num_nodes
        )
        
        self.node_id_map = node_id_map
        self.reverse_node_map = reverse_node_map
        self.edge_index = edge_index
        
        logger.info(f"Extracted {num_nodes} nodes and {len(edges)} edges with {node_features.shape[1]} features")
        
        return data, node_id_map
    
    def train_embeddings(
        self,
        data: Data,
        epochs: int = 100,
        lr: float = 0.001,
        weight_decay: float = 5e-4
    ) -> Dict[str, Any]:
        """
        Train GNN embeddings using link prediction as training objective.
        
        Args:
            data: PyG Data object with graph structure
            epochs: Number of training epochs
            lr: Learning rate
            weight_decay: Weight decay for regularization
            
        Returns:
            Training statistics
        """
        logger.info(f"Training GNN embeddings for {epochs} epochs...")
        
        # Initialize models
        self.embedder = TourismKGEmbedder(
            in_channels=data.x.size(1),
            out_channels=self.embedding_dim
        ).to(self.device)
        
        self.link_predictor = LinkPredictor(
            embedding_dim=self.embedding_dim
        ).to(self.device)
        
        # Move data to device
        data = data.to(self.device)
        
        # Optimizer
        optimizer = torch.optim.Adam(
            list(self.embedder.parameters()) + list(self.link_predictor.parameters()),
            lr=lr,
            weight_decay=weight_decay
        )
        
        # Training loop
        self.embedder.train()
        self.link_predictor.train()
        
        loss_history = []
        
        for epoch in range(epochs):
            optimizer.zero_grad()
            
            # Forward pass: generate embeddings
            embeddings = self.embedder(data.x, data.edge_index)
            
            # Positive edges (actual edges in graph)
            pos_edge_index = data.edge_index
            pos_src = embeddings[pos_edge_index[0]]
            pos_dst = embeddings[pos_edge_index[1]]
            pos_pred = self.link_predictor(pos_src, pos_dst).squeeze()
            
            # Negative edges (sample non-existent edges)
            neg_edge_index = negative_sampling(
                edge_index=data.edge_index,
                num_nodes=data.num_nodes,
                num_neg_samples=pos_edge_index.size(1)
            )
            neg_src = embeddings[neg_edge_index[0]]
            neg_dst = embeddings[neg_edge_index[1]]
            neg_pred = self.link_predictor(neg_src, neg_dst).squeeze()
            
            # Binary cross-entropy loss
            pos_loss = F.binary_cross_entropy(pos_pred, torch.ones_like(pos_pred))
            neg_loss = F.binary_cross_entropy(neg_pred, torch.zeros_like(neg_pred))
            loss = pos_loss + neg_loss
            
            loss.backward()
            optimizer.step()
            
            loss_history.append(loss.item())
            
            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}")
        
        # Cache embeddings
        self.embedder.eval()
        with torch.no_grad():
            self.node_embeddings = self.embedder(data.x, data.edge_index)
        
        logger.info("Training completed!")
        
        return {
            "epochs": epochs,
            "final_loss": loss_history[-1],
            "avg_loss": np.mean(loss_history),
            "loss_history": loss_history,  # Include full history for plotting
            "num_nodes": data.num_nodes,
            "num_edges": data.edge_index.size(1),
            "embedding_dim": self.embedding_dim
        }
    
    def _find_entity_by_name(self, entity_name: str) -> Optional[str]:
        """
        Find Neo4j entity ID by name.
        Prioritizes Attraction nodes and searches title, name, and id properties.
        
        Args:
            entity_name: Entity name to search for
            
        Returns:
            Neo4j element ID if found, None otherwise
        """
        # Try multiple search strategies, prioritizing Attraction nodes
        queries = [
            # Priority 1: Exact match on Attraction.title
            """
            MATCH (n:Attraction)
            WHERE toLower(n.title) = toLower($name)
            RETURN elementId(n) AS neo4j_id, n.title AS found_name, labels(n) AS labels
            LIMIT 1
            """,
            # Priority 2: Exact match on any node's name/title/id
            """
            MATCH (n)
            WHERE toLower(n.name) = toLower($name) 
               OR toLower(n.title) = toLower($name)
               OR toLower(n.id) = toLower($name)
            RETURN elementId(n) AS neo4j_id, coalesce(n.title, n.name, n.id) AS found_name, labels(n) AS labels
            LIMIT 1
            """,
            # Priority 3: Contains match on Attraction.title
            """
            MATCH (n:Attraction)
            WHERE toLower(n.title) CONTAINS toLower($name)
            RETURN elementId(n) AS neo4j_id, n.title AS found_name, labels(n) AS labels
            LIMIT 1
            """,
            # Priority 4: Contains match on any property
            """
            MATCH (n)
            WHERE toLower(n.name) CONTAINS toLower($name)
               OR toLower(n.title) CONTAINS toLower($name)
               OR toLower(n.id) CONTAINS toLower($name)
            RETURN elementId(n) AS neo4j_id, coalesce(n.title, n.name, n.id) AS found_name, labels(n) AS labels
            LIMIT 1
            """
        ]
        
        with self.driver.session() as session:
            for i, query in enumerate(queries, 1):
                result = session.run(query, name=entity_name)
                record = result.single()
                if record:
                    logger.info(f"Found entity '{entity_name}' as '{record['found_name']}' ({record['labels']}) using strategy {i}")
                    return record["neo4j_id"]
            
            # If still not found, log available Attraction entities
            logger.warning(f"Entity '{entity_name}' not found in Neo4j.")
            sample_query = """
            MATCH (n:Attraction)
            RETURN n.title AS title
            LIMIT 10
            """
            sample_result = session.run(sample_query)
            sample_names = [r["title"] for r in sample_result if r["title"]]
            logger.warning(f"Sample Attraction titles: {sample_names}")
            
            return None
    
    def predict_link(
        self,
        entity1: str,
        entity2: str
    ) -> Dict[str, Any]:
        """
        Predict whether a link exists between two entities.
        
        Args:
            entity1: Entity name or Neo4j ID
            entity2: Entity name or Neo4j ID
            
        Returns:
            Prediction result with confidence score
        """
        if self.embedder is None or self.link_predictor is None:
            raise ValueError("Models not trained. Call train_embeddings() first.")
        
        # Try to find entities by name
        entity1_id = self._find_entity_by_name(entity1)
        entity2_id = self._find_entity_by_name(entity2)
        
        if not entity1_id:
            logger.warning(f"Entity not found: {entity1}")
            return {
                "exists": False,
                "confidence": 0.0,
                "reason": f"Entity '{entity1}' not found in graph"
            }
        
        if not entity2_id:
            logger.warning(f"Entity not found: {entity2}")
            return {
                "exists": False,
                "confidence": 0.0,
                "reason": f"Entity '{entity2}' not found in graph"
            }
        
        # Check if entities are in the trained model
        if entity1_id not in self.node_id_map or entity2_id not in self.node_id_map:
            return {
                "exists": False,
                "confidence": 0.0,
                "reason": "Entity not in trained model (may have been added after training)"
            }
        
        idx1 = self.node_id_map[entity1_id]
        idx2 = self.node_id_map[entity2_id]
        
        self.link_predictor.eval()
        with torch.no_grad():
            emb1 = self.node_embeddings[idx1].unsqueeze(0)
            emb2 = self.node_embeddings[idx2].unsqueeze(0)
            score = self.link_predictor(emb1, emb2).item()
        
        return {
            "exists": score > 0.5,
            "confidence": float(score),
            "method": "gnn_link_prediction"
        }
    
    def find_similar_entities(
        self,
        entity_neo4j_id: int,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find most similar entities based on embedding similarity.
        
        Args:
            entity_neo4j_id: Neo4j internal ID
            top_k: Number of similar entities to return
            
        Returns:
            List of similar entities with similarity scores
        """
        if self.node_embeddings is None:
            raise ValueError("Embeddings not computed. Call train_embeddings() first.")
        
        if entity_neo4j_id not in self.node_id_map:
            return []
        
        idx = self.node_id_map[entity_neo4j_id]
        entity_emb = self.node_embeddings[idx]
        
        # Compute cosine similarity
        similarities = F.cosine_similarity(
            entity_emb.unsqueeze(0),
            self.node_embeddings,
            dim=1
        )
        
        # Get top-k (excluding self)
        top_scores, top_indices = torch.topk(similarities, k=top_k + 1)
        
        results = []
        for score, idx in zip(top_scores.tolist(), top_indices.tolist()):
            if idx != idx:  # Skip self
                neo4j_id = self.reverse_node_map[idx]
                results.append({
                    "neo4j_id": neo4j_id,
                    "similarity": score,
                    "method": "gnn_cosine_similarity"
                })
        
        return results[:top_k]
    
    def predict_cross_type_links(
        self,
        source_entity: str,
        target_type: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Predict relationships between a source entity and entities of a different type.
        
        Args:
            source_entity: Name of the source entity
            target_type: Node label of target type (e.g., 'District', 'Policy')
            top_k: Number of top predictions to return
            
        Returns:
            List of predicted entities with confidence scores
            
        Example:
            # Find which District an Attraction might belong to
            results = gnn.predict_cross_type_links("Sigiriya", "District", top_k=3)
            # Results: [{"name": "Matale", "confidence": 0.85, ...}, ...]
        """
        if self.node_embeddings is None:
            raise ValueError("Embeddings not computed. Call train_embeddings() first.")
        
        # Find source entity
        source_id = self._find_entity_by_name(source_entity)
        if not source_id:
            logger.warning(f"Source entity not found: {source_entity}")
            return []
        
        if source_id not in self.node_id_map:
            logger.warning(f"Source entity not in trained model: {source_entity}")
            return []
        
        # Get source embedding
        source_idx = self.node_id_map[source_id]
        source_emb = self.node_embeddings[source_idx]
        
        # Filter node_types for target type and compute similarities
        target_indices = []
        target_neo4j_ids = []
        
        for idx, node_type in enumerate(self.node_types):
            if node_type == target_type:
                neo4j_id = self.reverse_node_map[idx]
                
                # CRITICAL FIX #3: Filter out self-matches
                # Skip if this is the same entity as source
                if neo4j_id != source_id:
                    target_indices.append(idx)
                    target_neo4j_ids.append(neo4j_id)
        
        if not target_indices:
            logger.warning(f"No entities of type '{target_type}' in trained model (or all are self-matches)")
            return []
        
        # Compute similarities only for target type
        target_embeddings = self.node_embeddings[target_indices]
        similarities = F.cosine_similarity(
            source_emb.unsqueeze(0),
            target_embeddings,
            dim=1
        )
        
        # CRITICAL FIX #2: Normalize cosine similarity from [-1, 1] to [0, 1]
        # This fixes negative confidence scores
        similarities = (similarities + 1.0) / 2.0
        
        # Get top-k
        top_scores, top_local_indices = torch.topk(similarities, k=min(top_k, len(target_indices)))
        
        # Fetch entity details from Neo4j
        results = []
        with self.driver.session() as session:
            for score, local_idx in zip(top_scores.tolist(), top_local_indices.tolist()):
                neo4j_id = target_neo4j_ids[local_idx]
                
                # Get entity details
                result = session.run(
                    """
                    MATCH (n)
                    WHERE elementId(n) = $id
                    RETURN coalesce(n.title, n.name, n.id) AS name,
                           labels(n) AS labels,
                           properties(n) AS props
                    """,
                    id=neo4j_id
                )
                record = result.single()
                
                if record:
                    # Sanitize Neo4j types (DateTime, Date, etc.) for JSON serialization
                    sanitized_props = sanitize_neo4j_types(dict(record["props"]))
                    
                    results.append({
                        "name": record["name"],
                        "type": target_type,
                        "confidence": float(score),
                        "labels": record["labels"],
                        "properties": sanitized_props,
                        "method": "gnn_cross_type_similarity"
                    })
        
        return results
    
        if self.node_embeddings is None:
            return None
        
        if entity_neo4j_id not in self.node_id_map:
            return None
        
        idx = self.node_id_map[entity_neo4j_id]
        return self.node_embeddings[idx].cpu().numpy()

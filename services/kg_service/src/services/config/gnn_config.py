"""
Configuration for GNN (Graph Neural Network) module.

Centralized configuration for heterogeneous GNN training and inference.
"""

from typing import List, ClassVar
from dataclasses import dataclass


@dataclass
class GNNConfig:
    """Configuration for GNN model architecture and training."""
    
    # ========================================================================
    # MODEL ARCHITECTURE
    # ========================================================================
    
    # Embedding dimensions
    EMBEDDING_DIM: int = 64  # Output embedding size
    HIDDEN_DIM: int = 64     # Hidden layer size
    INPUT_DIM: int = 128     # Input feature dimension (type-aware features)
    
    # Graph Attention Network (GAT) parameters
    NUM_HEADS: int = 4       # Multi-head attention heads
    NUM_LAYERS: int = 3      # Number of GAT layers
    DROPOUT: float = 0.2     # Dropout rate for regularization
    
    # Device
    DEVICE: str = 'cpu'      # 'cpu' or 'cuda'
    
    # ========================================================================
    # TRAINING PARAMETERS
    # ========================================================================
    
    # Optimization
    DEFAULT_EPOCHS: int = 200
    DEFAULT_LR: float = 0.001
    DEFAULT_WEIGHT_DECAY: float = 5e-4
    
    # Training constraints
    MIN_EPOCHS: int = 10
    MAX_EPOCHS: int = 1000
    MIN_LR: float = 0.0001
    MAX_LR: float = 0.1
    
    # Data limits
    DEFAULT_NODE_LIMIT: int = 1000  # Max nodes to extract from Neo4j
    MIN_NODE_LIMIT: int = 100
    MAX_NODE_LIMIT: int = 10000
    
    # ========================================================================
    # HETEROGENEOUS GNN - NODE TYPES
    # ========================================================================
    
    # GNN-suitable node types (avg degree > 2, count > 10)
    # Using ClassVar so it's accessible as class attribute
    MULTI_TYPE_LABELS: ClassVar[List[str]] = [
        'Attraction',    # 39 nodes  - Tourism attractions
        'Policy',        # 47 nodes  - Immigration/visa policies
        'Chunk',         # 73 nodes  - RAG text chunks
        'District',      # 25 nodes  - Geographic districts
        'Location',      # 27 nodes  - Specific locations
        'Authority',     # 16 nodes  - Governing bodies
        'Domain',        # 13 nodes  - Policy domains
        'Month',         # 132 nodes - Temporal (months)
        'Year'           # 11 nodes  - Temporal (years)
    ]
    
    # Total expected nodes across all types
    EXPECTED_TOTAL_NODES: int = 383
    EXPECTED_TOTAL_EDGES: int = 759
    
    # ========================================================================
    # TYPE-SPECIFIC FEATURE DIMENSIONS
    # ========================================================================
    
    # One-hot encoding for node types
    TYPE_ENCODING_DIM: int = 27      # Support up to 27 node types (extensible)
    TYPE_SPECIFIC_DIM: int = 5       # Type-specific features per node
    PADDING_DIM: int = 96            # Padding for 128-dim consistency
    
    # Verify: TYPE_ENCODING_DIM + TYPE_SPECIFIC_DIM + PADDING_DIM = INPUT_DIM
    assert TYPE_ENCODING_DIM + TYPE_SPECIFIC_DIM + PADDING_DIM == INPUT_DIM
    
    # ========================================================================
    # PREDICTION PARAMETERS
    # ========================================================================
    
    # Link prediction
    LINK_THRESHOLD: float = 0.5      # Confidence threshold for link existence
    
    # Cross-type prediction
    DEFAULT_TOP_K: int = 5           # Default number of predictions to return
    MIN_TOP_K: int = 1
    MAX_TOP_K: int = 20
    
    # Similarity metrics
    SIMILARITY_METHOD: str = 'cosine'  # 'cosine', 'euclidean', 'dot'
    
    # ========================================================================
    # CACHING & PERFORMANCE
    # ========================================================================
    
    # Cache settings
    CACHE_EMBEDDINGS: bool = True    # Cache embeddings in memory
    CACHE_NODE_MAP: bool = True      # Cache node ID mappings
    
    # Performance
    BATCH_SIZE: int = 32             # Batch size for training
    NUM_WORKERS: int = 0             # DataLoader workers (0 = main process)
    
    # ========================================================================
    # LOGGING & MONITORING
    # ========================================================================
    
    # Training logging
    LOG_INTERVAL: int = 20           # Log every N epochs
    VERBOSE_TRAINING: bool = True    # Print training progress
    
    # Model checkpointing
    SAVE_CHECKPOINTS: bool = False   # Save model checkpoints
    CHECKPOINT_DIR: str = "models/kg_service/gnn_checkpoints"
    
    # ========================================================================
    # VALIDATION
    # ========================================================================
    
    @classmethod
    def validate_training_params(cls, epochs: int, lr: float, node_limit: int) -> dict:
        """
        Validate training parameters and return sanitized values.
        
        Args:
            epochs: Number of training epochs
            lr: Learning rate
            node_limit: Maximum nodes to extract
            
        Returns:
            Dict with validated parameters
            
        Raises:
            ValueError: If parameters out of bounds
        """
        errors = []
        
        # Validate epochs
        if epochs < cls.MIN_EPOCHS:
            errors.append(f"epochs must be >= {cls.MIN_EPOCHS}, got {epochs}")
        if epochs > cls.MAX_EPOCHS:
            errors.append(f"epochs must be <= {cls.MAX_EPOCHS}, got {epochs}")
        
        # Validate learning rate
        if lr < cls.MIN_LR:
            errors.append(f"learning_rate must be >= {cls.MIN_LR}, got {lr}")
        if lr > cls.MAX_LR:
            errors.append(f"learning_rate must be <= {cls.MAX_LR}, got {lr}")
        
        # Validate node limit
        if node_limit < cls.MIN_NODE_LIMIT:
            errors.append(f"node_limit must be >= {cls.MIN_NODE_LIMIT}, got {node_limit}")
        if node_limit > cls.MAX_NODE_LIMIT:
            errors.append(f"node_limit must be <= {cls.MAX_NODE_LIMIT}, got {node_limit}")
        
        if errors:
            raise ValueError("; ".join(errors))
        
        return {
            "epochs": epochs,
            "lr": lr,
            "node_limit": node_limit,
            "weight_decay": cls.DEFAULT_WEIGHT_DECAY
        }
    
    @classmethod
    def validate_prediction_params(cls, top_k: int) -> int:
        """
        Validate prediction parameters.
        
        Args:
            top_k: Number of predictions to return
            
        Returns:
            Validated top_k value
            
        Raises:
            ValueError: If top_k out of bounds
        """
        if top_k < cls.MIN_TOP_K:
            raise ValueError(f"top_k must be >= {cls.MIN_TOP_K}, got {top_k}")
        if top_k > cls.MAX_TOP_K:
            raise ValueError(f"top_k must be <= {cls.MAX_TOP_K}, got {top_k}")
        
        return top_k
    
    @classmethod
    def get_type_index(cls, node_type: str) -> int:
        """
        Get index of node type in one-hot encoding.
        
        Args:
            node_type: Node label (e.g., 'Attraction')
            
        Returns:
            Index in MULTI_TYPE_LABELS (0-8)
            
        Raises:
            ValueError: If node_type not supported
        """
        try:
            return cls.MULTI_TYPE_LABELS.index(node_type)
        except ValueError:
            raise ValueError(
                f"Unsupported node type: {node_type}. "
                f"Supported types: {', '.join(cls.MULTI_TYPE_LABELS)}"
            )
    
    @classmethod
    def is_supported_type(cls, node_type: str) -> bool:
        """Check if node type is supported."""
        return node_type in cls.MULTI_TYPE_LABELS
    
    @classmethod
    def get_model_info(cls) -> dict:
        """Get model architecture information."""
        return {
            "model_type": "Heterogeneous Graph Attention Network (GAT)",
            "architecture": {
                "input_dim": cls.INPUT_DIM,
                "hidden_dim": cls.HIDDEN_DIM,
                "embedding_dim": cls.EMBEDDING_DIM,
                "num_layers": cls.NUM_LAYERS,
                "num_heads": cls.NUM_HEADS,
                "dropout": cls.DROPOUT
            },
            "node_types": cls.MULTI_TYPE_LABELS,
            "num_types": len(cls.MULTI_TYPE_LABELS),
            "feature_composition": {
                "type_encoding": f"{cls.TYPE_ENCODING_DIM} dims (one-hot)",
                "type_specific": f"{cls.TYPE_SPECIFIC_DIM} dims (rating, geo, etc.)",
                "padding": f"{cls.PADDING_DIM} dims",
                "total": f"{cls.INPUT_DIM} dims"
            },
            "training": {
                "default_epochs": cls.DEFAULT_EPOCHS,
                "default_lr": cls.DEFAULT_LR,
                "weight_decay": cls.DEFAULT_WEIGHT_DECAY
            }
        }


# Singleton instance
gnn_config = GNNConfig()

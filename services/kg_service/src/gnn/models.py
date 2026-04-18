"""
GraphCeylon - GNN Models for Tourism Knowledge Graph

This module contains Graph Neural Network models for:
1. Hotel Recommendation (link prediction)
2. Route Optimization (path ranking)
3. Tourist Itinerary Generation (sequence prediction)

Requires: torch, torch-geometric
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass


# Check for PyTorch Geometric availability
try:
    from torch_geometric.nn import (
        HGTConv, 
        HeteroConv, 
        SAGEConv, 
        GATConv,
        GCNConv,
        Linear,
        to_hetero,
        global_mean_pool,
        global_max_pool,
    )
    from torch_geometric.data import HeteroData
    HAS_PYG = True
except ImportError:
    HAS_PYG = False
    print("⚠️ PyTorch Geometric not installed. Install with: pip install torch-geometric")


@dataclass
class ModelConfig:
    """Configuration for GNN models"""
    hidden_channels: int = 64
    out_channels: int = 32
    num_heads: int = 4
    num_layers: int = 3
    dropout: float = 0.2
    use_batch_norm: bool = True


class HeterogeneousGNN(nn.Module):
    """
    Base Heterogeneous Graph Neural Network.
    
    Uses separate GNN per edge type with message aggregation.
    """
    
    def __init__(
        self,
        metadata: Tuple[List[str], List[Tuple[str, str, str]]],
        in_channels_dict: Dict[str, int],
        config: ModelConfig = ModelConfig(),
    ):
        super().__init__()
        
        if not HAS_PYG:
            raise ImportError("PyTorch Geometric required")
        
        self.config = config
        self.node_types = list(metadata[0])
        self.edge_types = list(metadata[1])
        
        # Input projections
        self.input_projections = nn.ModuleDict()
        for node_type in self.node_types:
            in_dim = in_channels_dict.get(node_type, 1)
            self.input_projections[node_type] = nn.Sequential(
                nn.Linear(in_dim, config.hidden_channels),
                nn.ReLU(),
                nn.Dropout(config.dropout),
            )
        
        # Single hidden projection per node type (self-loops)
        self.self_loops = nn.ModuleDict()
        for node_type in self.node_types:
            self.self_loops[node_type] = nn.Linear(
                config.hidden_channels, config.hidden_channels
            )
        
        # Edge-type specific message passing
        self.edge_linears = nn.ModuleDict()
        for src, rel, dst in self.edge_types:
            key = f"{src}__{rel}__{dst}"
            self.edge_linears[key] = nn.Linear(
                config.hidden_channels, config.hidden_channels
            )
        
        # Layer norms
        self.layer_norms = nn.ModuleDict()
        for node_type in self.node_types:
            self.layer_norms[node_type] = nn.LayerNorm(config.hidden_channels)
        
        # Output projection
        self.output_projection = nn.Linear(config.hidden_channels, config.out_channels)
    
    def forward(
        self, 
        x_dict: Dict[str, torch.Tensor], 
        edge_index_dict: Dict
    ) -> Dict[str, torch.Tensor]:
        """Forward pass with skip connections to prevent over-smoothing"""
        # Project inputs
        h_dict = {}
        for node_type in self.node_types:
            if node_type in x_dict and x_dict[node_type] is not None:
                h_dict[node_type] = self.input_projections[node_type](x_dict[node_type])
        
        # Save initial projected features for skip connection
        h_init = {nt: h.clone() for nt, h in h_dict.items()}
        
        # Message passing
        for _ in range(self.config.num_layers):
            h_dict = self._message_passing_layer(h_dict, edge_index_dict)
        
        # Skip connection: combine initial features with GNN output
        # This preserves node-specific information lost through over-smoothing
        for node_type in h_dict:
            if node_type in h_init:
                h_dict[node_type] = h_dict[node_type] + h_init[node_type]
        
        # Output projection
        out_dict = {}
        for node_type, h in h_dict.items():
            out_dict[node_type] = self.output_projection(h)
        
        return out_dict
    
    def _message_passing_layer(
        self, 
        h_dict: Dict[str, torch.Tensor],
        edge_index_dict: Dict
    ) -> Dict[str, torch.Tensor]:
        """Single message passing layer"""
        # Accumulate messages for each node type
        out_dict = {}
        msg_counts = {nt: 0 for nt in self.node_types}
        
        # Initialize with self-loop (keeps original info)
        for node_type, h in h_dict.items():
            out_dict[node_type] = F.relu(self.self_loops[node_type](h))
            msg_counts[node_type] = 1
        
        # Process each edge type
        for edge_type, edge_index in edge_index_dict.items():
            if edge_index is None or edge_index.numel() == 0:
                continue
            
            if isinstance(edge_type, tuple):
                src_type, rel, dst_type = edge_type
            else:
                continue
            
            if src_type not in h_dict:
                continue
            
            key = f"{src_type}__{rel}__{dst_type}"
            if key not in self.edge_linears:
                continue
            
            src_h = h_dict[src_type]
            src_idx = edge_index[0]
            dst_idx = edge_index[1]
            
            # Get source features
            src_features = src_h[src_idx]  # [num_edges, hidden]
            
            # Transform
            msg = self.edge_linears[key](src_features)  # [num_edges, hidden]
            
            # Aggregate to destination nodes
            if dst_type not in out_dict:
                num_dst = max(dst_idx.max().item() + 1, 1)
                out_dict[dst_type] = torch.zeros(
                    num_dst, self.config.hidden_channels, 
                    device=src_h.device
                )
            
            # Scatter add
            out_dict[dst_type] = out_dict[dst_type].scatter_add(
                0, 
                dst_idx.unsqueeze(-1).expand(-1, self.config.hidden_channels),
                msg
            )
            msg_counts[dst_type] += 1
        
        # Normalize and apply non-linearity
        for node_type in out_dict:
            if msg_counts[node_type] > 1:
                out_dict[node_type] = out_dict[node_type] / msg_counts[node_type]
            out_dict[node_type] = self.layer_norms[node_type](out_dict[node_type])
            out_dict[node_type] = F.relu(out_dict[node_type])
            out_dict[node_type] = F.dropout(
                out_dict[node_type], 
                p=self.config.dropout, 
                training=self.training
            )
        
        return out_dict


class HotelRecommenderGNN(nn.Module):
    """
    GNN-based Hotel Recommendation Model.
    
    Uses heterogeneous graph structure to learn hotel embeddings that capture:
    - Amenity offerings
    - Nearby points of interest
    - Geographic location
    - Attraction proximity
    
    Tasks:
    - Link prediction (user-hotel interaction)
    - Hotel similarity ranking
    - Personalized recommendation
    """
    
    def __init__(
        self,
        metadata: Tuple[List[str], List[Tuple[str, str, str]]],
        in_channels_dict: Dict[str, int],
        config: ModelConfig = ModelConfig(),
    ):
        super().__init__()
        
        if not HAS_PYG:
            raise ImportError("PyTorch Geometric required")
        
        self.encoder = HeterogeneousGNN(metadata, in_channels_dict, config)
        self.config = config
        
        # Learnable per-hotel node embeddings to prevent over-smoothing
        # Hotels sharing the same neighborhood get unique identity features
        num_hotels = 200  # Upper bound, will be sliced at runtime
        self.hotel_node_emb = nn.Embedding(num_hotels, config.out_channels)
        nn.init.normal_(self.hotel_node_emb.weight, std=0.5)
        
        # Hotel-specific layers — takes GNN output + node identity
        self.hotel_mlp = nn.Sequential(
            nn.Linear(config.out_channels * 2, config.out_channels),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.out_channels, config.out_channels),
        )
        
        # Scoring head for link prediction
        self.link_predictor = nn.Sequential(
            nn.Linear(config.out_channels * 2, config.out_channels),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.out_channels, 1),
        )
        
        # Rating prediction head
        self.rating_predictor = nn.Sequential(
            nn.Linear(config.out_channels, config.out_channels // 2),
            nn.ReLU(),
            nn.Linear(config.out_channels // 2, 1),
            nn.Sigmoid(),  # Output 0-1, scale to rating range
        )
    
    def encode(self, data: 'HeteroData') -> Dict[str, torch.Tensor]:
        """Encode all nodes to embeddings"""
        x_dict = {}
        for k in data.node_types:
            if hasattr(data[k], 'x') and data[k].x is not None:
                x_dict[k] = data[k].x
        
        edge_index_dict = {}
        for k in data.edge_types:
            if hasattr(data[k], 'edge_index') and data[k].edge_index is not None:
                edge_index_dict[k] = data[k].edge_index
        
        embeddings = self.encoder(x_dict, edge_index_dict)
        
        # Apply hotel-specific transformation with node identity
        if 'Hotel' in embeddings:
            num_hotels = embeddings['Hotel'].shape[0]
            node_ids = torch.arange(num_hotels, device=embeddings['Hotel'].device)
            # Clamp to embedding table size
            node_ids = node_ids.clamp(max=self.hotel_node_emb.num_embeddings - 1)
            identity = self.hotel_node_emb(node_ids)
            # Concatenate GNN output with unique node identity
            combined = torch.cat([embeddings['Hotel'], identity], dim=-1)
            embeddings['Hotel'] = self.hotel_mlp(combined)
        
        return embeddings
    
    def predict_link(
        self, 
        hotel_emb: torch.Tensor, 
        target_emb: torch.Tensor
    ) -> torch.Tensor:
        """
        Predict link probability between hotels and target nodes.
        
        Args:
            hotel_emb: Hotel embeddings [batch_size, out_channels]
            target_emb: Target node embeddings [batch_size, out_channels]
        
        Returns:
            Link probabilities [batch_size]
        """
        combined = torch.cat([hotel_emb, target_emb], dim=-1)
        return torch.sigmoid(self.link_predictor(combined)).squeeze(-1)
    
    def predict_rating(self, hotel_emb: torch.Tensor) -> torch.Tensor:
        """
        Predict hotel rating from embedding.
        
        Args:
            hotel_emb: Hotel embeddings [batch_size, out_channels]
        
        Returns:
            Predicted ratings [batch_size] (scaled 0-5)
        """
        return self.rating_predictor(hotel_emb).squeeze(-1) * 5.0
    
    def get_similar_hotels(
        self, 
        hotel_idx: int, 
        embeddings: Dict[str, torch.Tensor], 
        top_k: int = 10
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Find most similar hotels to a given hotel.
        
        Args:
            hotel_idx: Index of query hotel
            embeddings: Encoded node embeddings
            top_k: Number of similar hotels to return
        
        Returns:
            (indices, similarities) of top-k similar hotels
        """
        hotel_emb = embeddings['Hotel']
        query = hotel_emb[hotel_idx].unsqueeze(0)
        
        # Cosine similarity
        similarities = F.cosine_similarity(query, hotel_emb, dim=-1)
        
        # Exclude self
        similarities[hotel_idx] = -1
        
        # Top-k
        top_similarities, top_indices = torch.topk(similarities, top_k)
        
        return top_indices, top_similarities
    
    def forward(
        self, 
        data: 'HeteroData',
        hotel_indices: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Full forward pass.
        
        Args:
            data: HeteroData graph
            hotel_indices: Optional specific hotel indices to process
        
        Returns:
            Dictionary with embeddings and predictions
        """
        embeddings = self.encode(data)
        
        results = {'embeddings': embeddings}
        
        if 'Hotel' in embeddings:
            hotel_emb = embeddings['Hotel']
            if hotel_indices is not None:
                hotel_emb = hotel_emb[hotel_indices]
            
            results['predicted_ratings'] = self.predict_rating(hotel_emb)
        
        return results


class RouteOptimizerGNN(nn.Module):
    """
    GNN-based Route Optimization Model for Train Schedules.
    
    Learns to rank and optimize routes based on:
    - Station connectivity
    - Schedule timing
    - Route duration and distance
    - Transfer efficiency
    
    Tasks:
    - Route scoring/ranking
    - Next station prediction
    - Journey time estimation
    """
    
    def __init__(
        self,
        metadata: Tuple[List[str], List[Tuple[str, str, str]]],
        in_channels_dict: Dict[str, int],
        config: ModelConfig = ModelConfig(),
    ):
        super().__init__()
        
        if not HAS_PYG:
            raise ImportError("PyTorch Geometric required")
        
        self.encoder = HeterogeneousGNN(metadata, in_channels_dict, config)
        self.config = config
        
        # Station embedding refinement
        self.station_mlp = nn.Sequential(
            nn.Linear(config.out_channels, config.out_channels),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.out_channels, config.out_channels),
        )
        
        # Route scoring head (for pair of stations)
        self.route_scorer = nn.Sequential(
            nn.Linear(config.out_channels * 3, config.out_channels),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.out_channels, 1),
        )
        
        # Journey time predictor
        self.time_predictor = nn.Sequential(
            nn.Linear(config.out_channels * 2, config.out_channels),
            nn.ReLU(),
            nn.Linear(config.out_channels, 1),
            nn.ReLU(),  # Time is positive
        )
        
        # Next station predictor (for sequence generation)
        self.next_station_predictor = nn.Linear(config.out_channels, config.out_channels)
    
    def encode(self, data: 'HeteroData') -> Dict[str, torch.Tensor]:
        """Encode all nodes"""
        x_dict = {}
        for k in data.node_types:
            if hasattr(data[k], 'x') and data[k].x is not None:
                x_dict[k] = data[k].x
        
        edge_index_dict = {}
        for k in data.edge_types:
            if hasattr(data[k], 'edge_index') and data[k].edge_index is not None:
                edge_index_dict[k] = data[k].edge_index
        
        embeddings = self.encoder(x_dict, edge_index_dict)
        
        # Refine station embeddings
        if 'RailwayStation' in embeddings:
            embeddings['RailwayStation'] = self.station_mlp(embeddings['RailwayStation'])
        
        return embeddings
    
    def score_route(
        self,
        src_emb: torch.Tensor,
        dst_emb: torch.Tensor,
        schedule_emb: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Score a route between two stations.
        
        Args:
            src_emb: Source station embedding [batch_size, out_channels]
            dst_emb: Destination station embedding [batch_size, out_channels]
            schedule_emb: Optional schedule embedding [batch_size, out_channels]
        
        Returns:
            Route scores [batch_size]
        """
        if schedule_emb is None:
            # Use difference as proxy for schedule info
            schedule_emb = dst_emb - src_emb
        
        combined = torch.cat([src_emb, dst_emb, schedule_emb], dim=-1)
        return self.route_scorer(combined).squeeze(-1)
    
    def predict_journey_time(
        self,
        src_emb: torch.Tensor,
        dst_emb: torch.Tensor,
    ) -> torch.Tensor:
        """
        Predict journey time between stations.
        
        Args:
            src_emb: Source station embedding
            dst_emb: Destination station embedding
        
        Returns:
            Predicted time in minutes
        """
        combined = torch.cat([src_emb, dst_emb], dim=-1)
        return self.time_predictor(combined).squeeze(-1)
    
    def predict_next_station(
        self,
        current_emb: torch.Tensor,
        all_station_emb: torch.Tensor,
    ) -> torch.Tensor:
        """
        Predict probability distribution over next stations.
        
        Args:
            current_emb: Current station embedding [batch_size, out_channels]
            all_station_emb: All station embeddings [num_stations, out_channels]
        
        Returns:
            Probability distribution [batch_size, num_stations]
        """
        query = self.next_station_predictor(current_emb)
        scores = torch.matmul(query, all_station_emb.t())
        return F.softmax(scores, dim=-1)
    
    def rank_routes(
        self,
        embeddings: Dict[str, torch.Tensor],
        src_idx: int,
        dst_idx: int,
        candidate_paths: List[List[int]],
    ) -> Tuple[List[int], torch.Tensor]:
        """
        Rank multiple candidate routes between source and destination.
        
        Args:
            embeddings: Node embeddings
            src_idx: Source station index
            dst_idx: Destination station index
            candidate_paths: List of paths, each path is list of station indices
        
        Returns:
            Sorted path indices and their scores
        """
        station_emb = embeddings['RailwayStation']
        
        scores = []
        for path in candidate_paths:
            # Score is sum of consecutive pair scores
            path_score = 0.0
            for i in range(len(path) - 1):
                pair_score = self.score_route(
                    station_emb[path[i]].unsqueeze(0),
                    station_emb[path[i + 1]].unsqueeze(0),
                )
                path_score += pair_score.item()
            
            # Normalize by path length
            scores.append(path_score / len(path))
        
        scores = torch.tensor(scores)
        sorted_indices = torch.argsort(scores, descending=True)
        
        return sorted_indices.tolist(), scores[sorted_indices]
    
    def forward(
        self,
        data: 'HeteroData',
        src_indices: Optional[torch.Tensor] = None,
        dst_indices: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Full forward pass.
        
        Args:
            data: HeteroData graph
            src_indices: Source station indices for route scoring
            dst_indices: Destination station indices for route scoring
        
        Returns:
            Dictionary with embeddings and predictions
        """
        embeddings = self.encode(data)
        
        results = {'embeddings': embeddings}
        
        if src_indices is not None and dst_indices is not None:
            station_emb = embeddings.get('RailwayStation')
            if station_emb is not None:
                src_emb = station_emb[src_indices]
                dst_emb = station_emb[dst_indices]
                
                results['route_scores'] = self.score_route(src_emb, dst_emb)
                results['journey_times'] = self.predict_journey_time(src_emb, dst_emb)
        
        return results


class GraphCeylonGNN(nn.Module):
    """
    Unified GNN model for GraphCeylon knowledge graph.
    
    Combines hotel recommendation and route optimization capabilities
    into a single model for multi-task learning.
    """
    
    def __init__(
        self,
        metadata: Tuple[List[str], List[Tuple[str, str, str]]],
        in_channels_dict: Dict[str, int],
        config: ModelConfig = ModelConfig(),
    ):
        super().__init__()
        
        if not HAS_PYG:
            raise ImportError("PyTorch Geometric required")
        
        # Shared encoder
        self.encoder = HeterogeneousGNN(metadata, in_channels_dict, config)
        
        # Task-specific heads
        self.hotel_head = nn.Sequential(
            nn.Linear(config.out_channels, config.out_channels),
            nn.ReLU(),
            nn.Linear(config.out_channels, config.out_channels),
        )
        
        self.route_head = nn.Sequential(
            nn.Linear(config.out_channels, config.out_channels),
            nn.ReLU(),
            nn.Linear(config.out_channels, config.out_channels),
        )
        
        # Multi-task outputs
        self.hotel_rating_predictor = nn.Linear(config.out_channels, 1)
        self.route_scorer = nn.Linear(config.out_channels * 2, 1)
    
    def encode(self, data: 'HeteroData') -> Dict[str, torch.Tensor]:
        """Get shared embeddings"""
        x_dict = {}
        for k in data.node_types:
            if hasattr(data[k], 'x') and data[k].x is not None:
                x_dict[k] = data[k].x
        
        edge_index_dict = {}
        for k in data.edge_types:
            if hasattr(data[k], 'edge_index') and data[k].edge_index is not None:
                edge_index_dict[k] = data[k].edge_index
        
        return self.encoder(x_dict, edge_index_dict)
    
    def forward(
        self,
        data: 'HeteroData',
        task: str = 'all',
    ) -> Dict[str, torch.Tensor]:
        """
        Multi-task forward pass.
        
        Args:
            data: HeteroData graph
            task: 'hotel', 'route', or 'all'
        """
        embeddings = self.encode(data)
        results = {'embeddings': embeddings}
        
        if task in ['hotel', 'all'] and 'Hotel' in embeddings:
            hotel_emb = self.hotel_head(embeddings['Hotel'])
            results['hotel_embeddings'] = hotel_emb
            results['hotel_ratings'] = torch.sigmoid(
                self.hotel_rating_predictor(hotel_emb)
            ).squeeze(-1) * 5.0
        
        if task in ['route', 'all'] and 'RailwayStation' in embeddings:
            station_emb = self.route_head(embeddings['RailwayStation'])
            results['station_embeddings'] = station_emb
        
        return results


# Loss functions for training

class HotelRecommendationLoss(nn.Module):
    """Combined loss for hotel recommendation"""
    
    def __init__(self, rating_weight: float = 1.0, link_weight: float = 1.0):
        super().__init__()
        self.rating_weight = rating_weight
        self.link_weight = link_weight
        self.mse_loss = nn.MSELoss()
        self.bce_loss = nn.BCELoss()
    
    def forward(
        self,
        pred_ratings: torch.Tensor,
        true_ratings: torch.Tensor,
        pred_links: Optional[torch.Tensor] = None,
        true_links: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        loss = self.rating_weight * self.mse_loss(pred_ratings, true_ratings)
        
        if pred_links is not None and true_links is not None:
            loss += self.link_weight * self.bce_loss(pred_links, true_links)
        
        return loss


class RouteOptimizationLoss(nn.Module):
    """Combined loss for route optimization"""
    
    def __init__(self, time_weight: float = 1.0, rank_weight: float = 1.0):
        super().__init__()
        self.time_weight = time_weight
        self.rank_weight = rank_weight
        self.mse_loss = nn.MSELoss()
        self.margin_loss = nn.MarginRankingLoss(margin=0.1)
    
    def forward(
        self,
        pred_times: torch.Tensor,
        true_times: torch.Tensor,
        better_route_scores: Optional[torch.Tensor] = None,
        worse_route_scores: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        loss = self.time_weight * self.mse_loss(pred_times, true_times)
        
        if better_route_scores is not None and worse_route_scores is not None:
            target = torch.ones_like(better_route_scores)
            loss += self.rank_weight * self.margin_loss(
                better_route_scores, worse_route_scores, target
            )
        
        return loss


if __name__ == "__main__":
    print("GraphCeylon GNN Models")
    print("=" * 50)
    
    if HAS_PYG:
        print("✅ PyTorch Geometric available")
        print("\nAvailable models:")
        print("  - HeterogeneousGNN: Base heterogeneous encoder")
        print("  - HotelRecommenderGNN: Hotel recommendation")
        print("  - RouteOptimizerGNN: Route optimization")
        print("  - GraphCeylonGNN: Multi-task unified model")
    else:
        print("❌ PyTorch Geometric not installed")
        print("Install with: pip install torch-geometric")

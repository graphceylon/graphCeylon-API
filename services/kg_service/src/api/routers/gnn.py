"""
GNN API Router

RESTful endpoints for Graph Neural Network inference:
- Hotel recommendations using learned embeddings
- Route optimization using station embeddings
- Similarity search
- Model information and statistics
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import torch
import torch.nn.functional as F
from pathlib import Path
import time
from datetime import datetime

# GNN imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from gnn.export_graph import GraphExporter
from gnn.models import HotelRecommenderGNN, RouteOptimizerGNN, ModelConfig


router = APIRouter(
    prefix="/gnn",
    tags=["GNN - Graph Neural Networks"],
    responses={404: {"description": "Not found"}}
)


# ========== Configuration ==========

_ROUTER_FILE = Path(__file__).resolve()
_KG_SERVICE_ROOT = _ROUTER_FILE.parent.parent.parent.parent
GNN_DATA_DIR = _KG_SERVICE_ROOT / "data" / "gnn"
CHECKPOINT_DIR = _KG_SERVICE_ROOT / "checkpoints"

print(f"[GNN API] Data dir: {GNN_DATA_DIR} (exists: {GNN_DATA_DIR.exists()})")
print(f"[GNN API] Checkpoint dir: {CHECKPOINT_DIR} (exists: {CHECKPOINT_DIR.exists()})")

# Global model cache
_model_cache = {
    'hotel': None,
    'route': None,
    'hotel_data': None,
    'route_data': None,
    'hotel_mappings': None,
    'route_mappings': None,
}


# ========== Pydantic Models ==========

class HotelRecommendationRequest(BaseModel):
    hotel_id: Optional[str] = Field(None, description="Neo4j hotel ID for similar hotels")
    hotel_name: Optional[str] = Field(None, description="Hotel name to find similar hotels")
    top_k: int = Field(5, ge=1, le=50, description="Number of recommendations")
    min_similarity: float = Field(0.0, ge=0.0, le=1.0, description="Minimum similarity threshold")


class HotelRecommendationResponse(BaseModel):
    query_hotel: Optional[Dict[str, Any]] = None
    recommendations: List[Dict[str, Any]]
    model_info: Dict[str, Any]
    inference_time_ms: float


class RouteScoreRequest(BaseModel):
    source_station: str = Field(..., description="Source station name or ID")
    destination_station: str = Field(..., description="Destination station name or ID")


class RouteScoreResponse(BaseModel):
    source: Dict[str, Any]
    destination: Dict[str, Any]
    connectivity_score: float
    embedding_similarity: float
    model_info: Dict[str, Any]
    inference_time_ms: float


class StationSimilarityResponse(BaseModel):
    query_station: Dict[str, Any]
    similar_stations: List[Dict[str, Any]]
    model_info: Dict[str, Any]
    inference_time_ms: float


class ModelInfoResponse(BaseModel):
    model_name: str
    model_type: str
    parameters: int
    hidden_channels: int
    output_channels: int
    num_layers: int
    node_types: List[str]
    edge_types: int
    checkpoint_path: Optional[str]
    last_trained: Optional[str]
    training_loss: Optional[float]


class EmbeddingResponse(BaseModel):
    node_type: str
    node_id: str
    embedding: List[float]
    embedding_dim: int


# ========== Helper Functions ==========

def load_hotel_model():
    """Load hotel recommender model (cached)"""
    if _model_cache['hotel'] is None:
        data_path = GNN_DATA_DIR / "graphceylon_hotels.pt"
        if not data_path.exists():
            raise HTTPException(status_code=503, detail=f"Hotel data not found. Run 'python run_gnn.py export' first.")
        
        data, node_mappings, cat_encodings = GraphExporter.load(str(data_path))
        _model_cache['hotel_data'] = data
        _model_cache['hotel_mappings'] = node_mappings
        
        metadata = (list(data.node_types), list(data.edge_types))
        in_channels_dict = {}
        for node_type in data.node_types:
            if hasattr(data[node_type], 'x'):
                in_channels_dict[node_type] = data[node_type].x.shape[1]
            else:
                in_channels_dict[node_type] = 1
        
        config = ModelConfig(hidden_channels=64, out_channels=32, num_layers=2)
        model = HotelRecommenderGNN(metadata, in_channels_dict, config)
        
        checkpoint_path = CHECKPOINT_DIR / "hotel_recommender_best.pt"
        if checkpoint_path.exists():
            checkpoint = torch.load(checkpoint_path, weights_only=False)
            model.load_state_dict(checkpoint['model_state_dict'])
            model._checkpoint_info = checkpoint
        
        model.eval()
        _model_cache['hotel'] = model
    
    return _model_cache['hotel'], _model_cache['hotel_data'], _model_cache['hotel_mappings']


def load_route_model():
    """Load route optimizer model (cached)"""
    if _model_cache['route'] is None:
        data_path = GNN_DATA_DIR / "graphceylon_trains.pt"
        if not data_path.exists():
            raise HTTPException(status_code=503, detail=f"Train data not found. Run 'python run_gnn.py export' first.")
        
        data, node_mappings, cat_encodings = GraphExporter.load(str(data_path))
        _model_cache['route_data'] = data
        _model_cache['route_mappings'] = node_mappings
        
        metadata = (list(data.node_types), list(data.edge_types))
        in_channels_dict = {}
        for node_type in data.node_types:
            if hasattr(data[node_type], 'x'):
                in_channels_dict[node_type] = data[node_type].x.shape[1]
            else:
                in_channels_dict[node_type] = 1
        
        config = ModelConfig(hidden_channels=64, out_channels=32, num_layers=2)
        model = RouteOptimizerGNN(metadata, in_channels_dict, config)
        
        checkpoint_path = CHECKPOINT_DIR / "route_optimizer_best.pt"
        if checkpoint_path.exists():
            checkpoint = torch.load(checkpoint_path, weights_only=False)
            model.load_state_dict(checkpoint['model_state_dict'])
            model._checkpoint_info = checkpoint
        
        model.eval()
        _model_cache['route'] = model
    
    return _model_cache['route'], _model_cache['route_data'], _model_cache['route_mappings']


def find_node_index(node_type: str, identifier: str, mappings: dict, data) -> Optional[int]:
    """Find node index by ID or name"""
    if node_type in mappings:
        type_mapping = mappings[node_type]
        # NodeMapping is a dataclass with neo4j_to_idx dict
        id_to_idx = type_mapping.neo4j_to_idx if hasattr(type_mapping, 'neo4j_to_idx') else type_mapping
        
        if identifier in id_to_idx:
            return id_to_idx[identifier]
        # Fuzzy match
        for node_id, idx in id_to_idx.items():
            if identifier.lower() in str(node_id).lower():
                return idx
    return None


def get_node_info(node_type: str, idx: int, mappings: dict, data) -> Dict[str, Any]:
    """Get node information from index"""
    node_id = f"node_{idx}"
    if node_type in mappings:
        type_mapping = mappings[node_type]
        # NodeMapping is a dataclass with idx_to_neo4j dict
        idx_to_id = type_mapping.idx_to_neo4j if hasattr(type_mapping, 'idx_to_neo4j') else {v: k for k, v in type_mapping.items()}
        node_id = idx_to_id.get(idx, f"node_{idx}")
    
    info = {'id': node_id, 'index': idx, 'type': node_type}
    if hasattr(data[node_type], 'x'):
        info['features'] = data[node_type].x[idx].tolist()
    return info


# ========== API Endpoints ==========

@router.get("/status", summary="GNN Service Status")
async def get_gnn_status():
    """Get the status of GNN models and data availability."""
    hotel_data_path = GNN_DATA_DIR / "graphceylon_hotels.pt"
    hotel_checkpoint = CHECKPOINT_DIR / "hotel_recommender_best.pt"
    route_data_path = GNN_DATA_DIR / "graphceylon_trains.pt"
    route_checkpoint = CHECKPOINT_DIR / "route_optimizer_best.pt"
    
    return {
        'service': 'GraphCeylon GNN API',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat(),
        'models': {
            'hotel_recommender': {
                'data_available': hotel_data_path.exists(),
                'checkpoint_available': hotel_checkpoint.exists(),
                'loaded': _model_cache['hotel'] is not None,
            },
            'route_optimizer': {
                'data_available': route_data_path.exists(),
                'checkpoint_available': route_checkpoint.exists(),
                'loaded': _model_cache['route'] is not None,
            }
        },
        'data': {
            'hotel_graph': hotel_data_path.exists(),
            'route_graph': route_data_path.exists(),
        }
    }


@router.get("/models/hotel", response_model=ModelInfoResponse, summary="Hotel Model Info")
async def get_hotel_model_info():
    """Get information about the Hotel Recommender GNN model."""
    try:
        model, data, mappings = load_hotel_model()
        checkpoint_info = getattr(model, '_checkpoint_info', {})
        config = model.config
        
        return ModelInfoResponse(
            model_name="Hotel Recommender GNN",
            model_type=model.__class__.__name__,
            parameters=sum(p.numel() for p in model.parameters()),
            hidden_channels=config.hidden_channels,
            output_channels=config.out_channels,
            num_layers=config.num_layers,
            node_types=list(data.node_types),
            edge_types=len(data.edge_types),
            checkpoint_path=str(CHECKPOINT_DIR / "hotel_recommender_best.pt"),
            last_trained=str(checkpoint_info.get('epoch')),
            training_loss=checkpoint_info.get('loss'),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/route", response_model=ModelInfoResponse, summary="Route Model Info")
async def get_route_model_info():
    """Get information about the Route Optimizer GNN model."""
    try:
        model, data, mappings = load_route_model()
        checkpoint_info = getattr(model, '_checkpoint_info', {})
        config = model.config
        
        return ModelInfoResponse(
            model_name="Route Optimizer GNN",
            model_type=model.__class__.__name__,
            parameters=sum(p.numel() for p in model.parameters()),
            hidden_channels=config.hidden_channels,
            output_channels=config.out_channels,
            num_layers=config.num_layers,
            node_types=list(data.node_types),
            edge_types=len(data.edge_types),
            checkpoint_path=str(CHECKPOINT_DIR / "route_optimizer_best.pt"),
            last_trained=str(checkpoint_info.get('epoch')),
            training_loss=checkpoint_info.get('loss'),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hotels/recommend", response_model=HotelRecommendationResponse, summary="Get Hotel Recommendations")
async def get_hotel_recommendations(request: HotelRecommendationRequest):
    """
    Get hotel recommendations based on GNN embeddings.
    
    - Provide hotel_id or hotel_name to find similar hotels
    - Leave both empty to get top-rated hotels by predicted ratings
    """
    start_time = time.time()
    
    try:
        model, data, mappings = load_hotel_model()
        
        with torch.no_grad():
            embeddings = model.encode(data)
        
        hotel_emb = embeddings.get('Hotel')
        if hotel_emb is None:
            raise HTTPException(status_code=500, detail="Failed to compute hotel embeddings")
        
        hotel_emb_norm = F.normalize(hotel_emb, dim=1)
        
        query_hotel = None
        recommendations = []
        
        if request.hotel_id or request.hotel_name:
            identifier = request.hotel_id or request.hotel_name
            query_idx = find_node_index('Hotel', identifier, mappings, data)
            
            if query_idx is None:
                raise HTTPException(status_code=404, detail=f"Hotel not found: {identifier}")
            
            query_hotel = get_node_info('Hotel', query_idx, mappings, data)
            
            query_emb = hotel_emb_norm[query_idx].unsqueeze(0)
            similarities = torch.mm(query_emb, hotel_emb_norm.t()).squeeze(0)
            similarities[query_idx] = -1
            
            top_k_indices = similarities.argsort(descending=True)[:request.top_k]
            
            for idx in top_k_indices:
                idx = idx.item()
                sim = similarities[idx].item()
                if sim >= request.min_similarity:
                    hotel_info = get_node_info('Hotel', idx, mappings, data)
                    hotel_info['similarity_score'] = round(sim, 4)
                    recommendations.append(hotel_info)
        else:
            # Get predicted ratings for all hotels
            with torch.no_grad():
                predicted_ratings = model.predict_rating(hotel_emb)
            
            top_k_indices = predicted_ratings.argsort(descending=True)[:request.top_k]
            
            for idx in top_k_indices:
                idx = idx.item()
                rating = predicted_ratings[idx].item()
                hotel_info = get_node_info('Hotel', idx, mappings, data)
                hotel_info['predicted_rating'] = round(rating, 2)
                recommendations.append(hotel_info)
        
        inference_time = (time.time() - start_time) * 1000
        
        return HotelRecommendationResponse(
            query_hotel=query_hotel,
            recommendations=recommendations,
            model_info={
                'model_name': 'Hotel Recommender GNN',
                'embedding_dim': hotel_emb.shape[1],
                'total_hotels': hotel_emb.shape[0],
            },
            inference_time_ms=round(inference_time, 2),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hotels/similar/{hotel_name}", summary="Find Similar Hotels")
async def find_similar_hotels(
    hotel_name: str,
    top_k: int = Query(5, ge=1, le=50),
    min_similarity: float = Query(0.0, ge=0.0, le=1.0),
):
    """Find hotels similar to the specified hotel using GNN embeddings."""
    request = HotelRecommendationRequest(
        hotel_name=hotel_name,
        top_k=top_k,
        min_similarity=min_similarity,
    )
    return await get_hotel_recommendations(request)


@router.post("/routes/score", response_model=RouteScoreResponse, summary="Score a Route")
async def score_route(request: RouteScoreRequest):
    """Score the connectivity between two railway stations using GNN embeddings."""
    start_time = time.time()
    
    try:
        model, data, mappings = load_route_model()
        
        with torch.no_grad():
            embeddings = model.encode(data)
        
        station_emb = embeddings.get('RailwayStation')
        if station_emb is None:
            raise HTTPException(status_code=500, detail="Failed to compute station embeddings")
        
        src_idx = find_node_index('RailwayStation', request.source_station, mappings, data)
        dst_idx = find_node_index('RailwayStation', request.destination_station, mappings, data)
        
        if src_idx is None:
            raise HTTPException(status_code=404, detail=f"Source station not found: {request.source_station}")
        if dst_idx is None:
            raise HTTPException(status_code=404, detail=f"Destination station not found: {request.destination_station}")
        
        src_info = get_node_info('RailwayStation', src_idx, mappings, data)
        dst_info = get_node_info('RailwayStation', dst_idx, mappings, data)
        
        src_emb = station_emb[src_idx].unsqueeze(0)
        dst_emb = station_emb[dst_idx].unsqueeze(0)
        
        with torch.no_grad():
            route_score = model.score_route(src_emb, dst_emb).item()
        
        emb_similarity = F.cosine_similarity(src_emb, dst_emb).item()
        
        inference_time = (time.time() - start_time) * 1000
        
        return RouteScoreResponse(
            source=src_info,
            destination=dst_info,
            connectivity_score=round(route_score, 4),
            embedding_similarity=round(emb_similarity, 4),
            model_info={
                'model_name': 'Route Optimizer GNN',
                'embedding_dim': station_emb.shape[1],
                'total_stations': station_emb.shape[0],
            },
            inference_time_ms=round(inference_time, 2),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stations/similar/{station_name}", response_model=StationSimilarityResponse, summary="Find Similar Stations")
async def find_similar_stations(
    station_name: str,
    top_k: int = Query(5, ge=1, le=50),
):
    """Find railway stations similar to the specified station using GNN embeddings."""
    start_time = time.time()
    
    try:
        model, data, mappings = load_route_model()
        
        with torch.no_grad():
            embeddings = model.encode(data)
        
        station_emb = embeddings.get('RailwayStation')
        if station_emb is None:
            raise HTTPException(status_code=500, detail="Failed to compute station embeddings")
        
        query_idx = find_node_index('RailwayStation', station_name, mappings, data)
        if query_idx is None:
            raise HTTPException(status_code=404, detail=f"Station not found: {station_name}")
        
        query_info = get_node_info('RailwayStation', query_idx, mappings, data)
        
        station_emb_norm = F.normalize(station_emb, dim=1)
        query_emb = station_emb_norm[query_idx].unsqueeze(0)
        
        similarities = torch.mm(query_emb, station_emb_norm.t()).squeeze(0)
        similarities[query_idx] = -1
        
        top_k_indices = similarities.argsort(descending=True)[:top_k]
        
        similar_stations = []
        for idx in top_k_indices:
            idx = idx.item()
            sim = similarities[idx].item()
            station_info = get_node_info('RailwayStation', idx, mappings, data)
            station_info['similarity_score'] = round(sim, 4)
            similar_stations.append(station_info)
        
        inference_time = (time.time() - start_time) * 1000
        
        return StationSimilarityResponse(
            query_station=query_info,
            similar_stations=similar_stations,
            model_info={
                'model_name': 'Route Optimizer GNN',
                'embedding_dim': station_emb.shape[1],
                'total_stations': station_emb.shape[0],
            },
            inference_time_ms=round(inference_time, 2),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/embeddings/{node_type}/{node_id}", response_model=EmbeddingResponse, summary="Get Node Embedding")
async def get_node_embedding(node_type: str, node_id: str):
    """Get the GNN embedding for a specific node."""
    try:
        hotel_types = {'Hotel', 'PointOfInterest', 'Attraction', 'Amenity', 'Province', 'District'}
        route_types = {'RailwayStation', 'TrainSchedule', 'District'}
        
        if node_type in hotel_types:
            model, data, mappings = load_hotel_model()
            with torch.no_grad():
                embeddings = model.encode(data)
        elif node_type in route_types:
            model, data, mappings = load_route_model()
            with torch.no_grad():
                embeddings = model.encode(data)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown node type: {node_type}")
        
        if node_type not in embeddings:
            raise HTTPException(status_code=404, detail=f"No embeddings for node type: {node_type}")
        
        idx = find_node_index(node_type, node_id, mappings, data)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"Node not found: {node_type}/{node_id}")
        
        embedding = embeddings[node_type][idx].tolist()
        
        return EmbeddingResponse(
            node_type=node_type,
            node_id=node_id,
            embedding=embedding,
            embedding_dim=len(embedding),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hotels/top-rated", summary="Get Top Rated Hotels by GNN")
async def get_top_rated_hotels(top_k: int = Query(10, ge=1, le=50)):
    """Get hotels with highest predicted ratings from the GNN model."""
    request = HotelRecommendationRequest(top_k=top_k)
    return await get_hotel_recommendations(request)


@router.post("/reload-models", summary="Reload GNN Models")
async def reload_models():
    """Reload all GNN models from checkpoints."""
    global _model_cache
    _model_cache = {
        'hotel': None, 'route': None,
        'hotel_data': None, 'route_data': None,
        'hotel_mappings': None, 'route_mappings': None,
    }
    return {'status': 'success', 'message': 'Model cache cleared. Models will be reloaded on next request.'}

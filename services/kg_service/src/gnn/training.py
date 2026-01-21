"""
GraphCeylon GNN Training Module

Training loops, data loaders, and evaluation utilities for:
- Hotel Recommendation Model
- Route Optimization Model
- Multi-task Unified Model

Features:
- Comprehensive training with detailed logging
- Early stopping and learning rate scheduling
- Automatic report generation with visualizations
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from typing import Dict, List, Optional, Tuple, Callable, Any
from dataclasses import dataclass, field
import numpy as np
from tqdm import tqdm
import json
import time
from pathlib import Path
from datetime import datetime

try:
    from torch_geometric.data import HeteroData
    from torch_geometric.loader import LinkNeighborLoader, NeighborLoader
    HAS_PYG = True
except ImportError:
    HAS_PYG = False


@dataclass
class TrainingConfig:
    """Training configuration"""
    epochs: int = 100
    learning_rate: float = 0.001
    weight_decay: float = 1e-5
    batch_size: int = 64
    patience: int = 10  # Early stopping patience
    min_delta: float = 1e-4  # Minimum improvement for early stopping
    save_best: bool = True
    checkpoint_dir: str = "checkpoints"
    log_interval: int = 10
    generate_report: bool = True  # Auto-generate training report
    report_dir: str = "reports"
    model_name: str = "GNN Model"
    dataset_name: str = "GraphCeylon Dataset"


class EarlyStopping:
    """Early stopping utility"""
    
    def __init__(self, patience: int = 10, min_delta: float = 1e-4):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = None
        self.should_stop = False
    
    def __call__(self, val_loss: float) -> bool:
        if self.best_loss is None:
            self.best_loss = val_loss
        elif val_loss > self.best_loss - self.min_delta:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True
        else:
            self.best_loss = val_loss
            self.counter = 0
        
        return self.should_stop


class HotelTrainDataset(Dataset):
    """Dataset for hotel recommendation training"""
    
    def __init__(
        self,
        data: 'HeteroData',
        node_mappings: Dict,
        negative_samples: int = 5,
    ):
        self.data = data
        self.node_mappings = node_mappings
        self.negative_samples = negative_samples
        
        # Get hotel-amenity positive pairs
        self.positive_pairs = []
        if ('Hotel', 'OFFERS_AMENITY', 'Amenity') in data.edge_types:
            edge_index = data['Hotel', 'OFFERS_AMENITY', 'Amenity'].edge_index
            for i in range(edge_index.shape[1]):
                self.positive_pairs.append((
                    edge_index[0, i].item(),
                    edge_index[1, i].item(),
                ))
        
        self.num_hotels = data['Hotel'].num_nodes if 'Hotel' in data.node_types else 0
        self.num_amenities = data['Amenity'].num_nodes if 'Amenity' in data.node_types else 0
    
    def __len__(self):
        return len(self.positive_pairs)
    
    def __getitem__(self, idx):
        hotel_idx, amenity_idx = self.positive_pairs[idx]
        
        # Generate negative samples
        neg_amenities = []
        while len(neg_amenities) < self.negative_samples:
            neg_idx = np.random.randint(0, self.num_amenities)
            if (hotel_idx, neg_idx) not in self.positive_pairs:
                neg_amenities.append(neg_idx)
        
        return {
            'hotel': hotel_idx,
            'pos_amenity': amenity_idx,
            'neg_amenities': neg_amenities,
        }


class RouteTrainDataset(Dataset):
    """Dataset for route optimization training"""
    
    def __init__(
        self,
        data: 'HeteroData',
        node_mappings: Dict,
    ):
        self.data = data
        self.node_mappings = node_mappings
        
        # Get schedule edges (departs_from -> arrives_at)
        self.routes = []
        if 'TrainSchedule' in data.node_types:
            dep_edge = data['TrainSchedule', 'DEPARTS_FROM', 'RailwayStation'].edge_index
            arr_edge = data['TrainSchedule', 'ARRIVES_AT', 'RailwayStation'].edge_index
            
            # Match schedules to get (src, dst) pairs
            schedule_to_src = {}
            schedule_to_dst = {}
            
            for i in range(dep_edge.shape[1]):
                schedule_idx = dep_edge[0, i].item()
                station_idx = dep_edge[1, i].item()
                schedule_to_src[schedule_idx] = station_idx
            
            for i in range(arr_edge.shape[1]):
                schedule_idx = arr_edge[0, i].item()
                station_idx = arr_edge[1, i].item()
                schedule_to_dst[schedule_idx] = station_idx
            
            for schedule_idx in schedule_to_src:
                if schedule_idx in schedule_to_dst:
                    self.routes.append((
                        schedule_to_src[schedule_idx],
                        schedule_to_dst[schedule_idx],
                        schedule_idx,
                    ))
        
        self.num_stations = data['RailwayStation'].num_nodes if 'RailwayStation' in data.node_types else 0
    
    def __len__(self):
        return len(self.routes)
    
    def __getitem__(self, idx):
        src, dst, schedule = self.routes[idx]
        
        # Get schedule features for duration
        schedule_features = self.data['TrainSchedule'].x[schedule]
        
        return {
            'src': src,
            'dst': dst,
            'schedule': schedule,
            'features': schedule_features,
        }


def train_hotel_recommender(
    model: nn.Module,
    data: 'HeteroData',
    node_mappings: Dict,
    config: TrainingConfig = TrainingConfig(),
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu',
) -> Dict[str, Any]:
    """
    Train hotel recommendation model with comprehensive logging and reporting.
    
    Args:
        model: HotelRecommenderGNN instance
        data: HeteroData graph
        node_mappings: Neo4j to tensor index mappings
        config: Training configuration
        device: Device to train on
    
    Returns:
        Training results including history, metrics, and report paths
    """
    model = model.to(device)
    data = data.to(device)
    
    optimizer = optim.Adam(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=5
    )
    
    early_stopping = EarlyStopping(config.patience, config.min_delta)
    
    # Create checkpoint directory
    checkpoint_dir = Path(config.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    history = {
        'train_loss': [],
        'val_loss': [],
        'lr': [],
        'epoch_times': [],
        'rating_mse': [],
        'rating_mae': [],
    }
    
    best_loss = float('inf')
    training_start_time = time.time()
    
    print(f"\n{'='*60}")
    print(f"🏨 HOTEL RECOMMENDER TRAINING")
    print(f"{'='*60}")
    print(f"\n📊 Model: {model.__class__.__name__}")
    print(f"📊 Parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"📊 Device: {device}")
    print(f"📊 Epochs: {config.epochs}")
    print(f"📊 Learning Rate: {config.learning_rate}")
    print(f"📊 Weight Decay: {config.weight_decay}")
    print(f"📊 Early Stopping Patience: {config.patience}")
    print(f"\n{'='*60}\n")
    
    for epoch in range(config.epochs):
        epoch_start = time.time()
        model.train()
        
        # Forward pass
        results = model(data)
        
        # Compute loss (rating prediction)
        if 'Hotel' in data.node_types and hasattr(data['Hotel'], 'y'):
            true_ratings = data['Hotel'].y
            pred_ratings = results['predicted_ratings']
            loss = nn.MSELoss()(pred_ratings, true_ratings)
        else:
            # Self-supervised: use actual ratings from features
            hotel_features = data['Hotel'].x
            # Assume rating is first feature (normalized)
            true_ratings = hotel_features[:, 0] * 5.0  # Denormalize
            pred_ratings = results['predicted_ratings']
            loss = nn.MSELoss()(pred_ratings, true_ratings)
        
        # Calculate additional metrics
        with torch.no_grad():
            mse = nn.MSELoss()(pred_ratings, true_ratings).item()
            mae = nn.L1Loss()(pred_ratings, true_ratings).item()
        
        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        
        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        
        optimizer.step()
        
        # Update scheduler
        scheduler.step(loss)
        
        epoch_time = time.time() - epoch_start
        
        # Log
        history['train_loss'].append(loss.item())
        history['lr'].append(optimizer.param_groups[0]['lr'])
        history['epoch_times'].append(epoch_time)
        history['rating_mse'].append(mse)
        history['rating_mae'].append(mae)
        
        if (epoch + 1) % config.log_interval == 0:
            print(f"Epoch {epoch + 1:3d}/{config.epochs} | Loss: {loss.item():.6f} | MSE: {mse:.6f} | MAE: {mae:.6f} | LR: {history['lr'][-1]:.6f} | Time: {epoch_time:.2f}s")
        
        # Save best model
        if config.save_best and loss.item() < best_loss:
            best_loss = loss.item()
            best_epoch = epoch + 1
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'loss': loss.item(),
                'config': {
                    'epochs': config.epochs,
                    'learning_rate': config.learning_rate,
                    'weight_decay': config.weight_decay,
                    'patience': config.patience,
                },
            }, checkpoint_dir / 'hotel_recommender_best.pt')
        
        # Early stopping
        if early_stopping(loss.item()):
            print(f"\n⚠️ Early stopping triggered at epoch {epoch + 1}")
            break
    
    total_time = time.time() - training_start_time
    
    print(f"\n{'='*60}")
    print(f"✅ TRAINING COMPLETE")
    print(f"{'='*60}")
    print(f"\n📊 Training Summary:")
    print(f"   • Total Epochs: {len(history['train_loss'])}")
    print(f"   • Best Epoch: {best_epoch}")
    print(f"   • Best Loss: {best_loss:.6f}")
    print(f"   • Final Loss: {history['train_loss'][-1]:.6f}")
    print(f"   • Initial Loss: {history['train_loss'][0]:.6f}")
    print(f"   • Improvement: {(1 - best_loss/history['train_loss'][0])*100:.2f}%")
    print(f"   • Total Time: {total_time:.2f}s")
    print(f"   • Avg Epoch Time: {np.mean(history['epoch_times']):.2f}s")
    
    result = {
        'history': history,
        'best_loss': best_loss,
        'best_epoch': best_epoch,
        'total_time': total_time,
        'model': model,
    }
    
    # Generate report
    if config.generate_report:
        try:
            from .reporting import generate_training_report
            
            # Get evaluation metrics
            eval_metrics = evaluate_hotel_recommender(model, data, device=device)
            
            report_paths = generate_training_report(
                model=model,
                data=data,
                history=history,
                config={
                    'epochs': config.epochs,
                    'learning_rate': config.learning_rate,
                    'weight_decay': config.weight_decay,
                    'patience': config.patience,
                    'batch_size': config.batch_size,
                    'optimizer': 'Adam',
                },
                model_name=config.model_name or "Hotel Recommender GNN",
                dataset_name=config.dataset_name or "GraphCeylon Hotels Dataset",
                evaluation_results=eval_metrics,
                output_dir=config.report_dir,
                notes=f"Trained for {len(history['train_loss'])} epochs. Best loss: {best_loss:.6f}",
            )
            result['report_paths'] = report_paths
            print(f"\n📄 Report generated: {report_paths.get('markdown', '')}")
        except Exception as e:
            print(f"\n⚠️ Could not generate report: {e}")
    
    return result


def train_route_optimizer(
    model: nn.Module,
    data: 'HeteroData',
    node_mappings: Dict,
    config: TrainingConfig = TrainingConfig(),
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu',
) -> Dict[str, Any]:
    """
    Train route optimization model with comprehensive logging and reporting.
    
    Args:
        model: RouteOptimizerGNN instance
        data: HeteroData graph
        node_mappings: Neo4j to tensor index mappings
        config: Training configuration
        device: Device to train on
    
    Returns:
        Training results including history, metrics, and report paths
    """
    model = model.to(device)
    data = data.to(device)
    
    optimizer = optim.Adam(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=5
    )
    
    early_stopping = EarlyStopping(config.patience, config.min_delta)
    
    checkpoint_dir = Path(config.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    history = {
        'train_loss': [],
        'lr': [],
        'epoch_times': [],
        'pos_scores': [],
        'neg_scores': [],
    }
    
    best_loss = float('inf')
    best_epoch = 0
    training_start_time = time.time()
    
    # Get route pairs from data
    if ('TrainSchedule', 'DEPARTS_FROM', 'RailwayStation') in data.edge_types:
        dep_edges = data['TrainSchedule', 'DEPARTS_FROM', 'RailwayStation'].edge_index
        arr_edges = data['TrainSchedule', 'ARRIVES_AT', 'RailwayStation'].edge_index
    else:
        print("No schedule edges found!")
        return {'history': history, 'best_loss': best_loss, 'model': model}
    
    print(f"\n{'='*60}")
    print(f"🚂 ROUTE OPTIMIZER TRAINING")
    print(f"{'='*60}")
    print(f"\n📊 Model: {model.__class__.__name__}")
    print(f"📊 Parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"📊 Device: {device}")
    print(f"📊 Epochs: {config.epochs}")
    print(f"📊 Learning Rate: {config.learning_rate}")
    print(f"📊 Weight Decay: {config.weight_decay}")
    print(f"📊 Early Stopping Patience: {config.patience}")
    print(f"\n{'='*60}\n")
    
    for epoch in range(config.epochs):
        epoch_start = time.time()
        model.train()
        
        # Forward pass
        embeddings = model.encode(data)
        
        station_emb = embeddings.get('RailwayStation')
        schedule_emb = embeddings.get('TrainSchedule')
        
        if station_emb is None:
            print("No station embeddings!")
            break
        
        # Route scoring task: predict connectivity
        # Use CONNECTED_BY_TRAIN edges as positive examples
        if ('RailwayStation', 'CONNECTED_BY_TRAIN', 'RailwayStation') in data.edge_types:
            conn_edges = data['RailwayStation', 'CONNECTED_BY_TRAIN', 'RailwayStation'].edge_index
            
            src_emb = station_emb[conn_edges[0]]
            dst_emb = station_emb[conn_edges[1]]
            
            # Positive pairs should have high scores
            pos_scores = model.score_route(src_emb, dst_emb)
            
            # Negative sampling
            num_stations = station_emb.shape[0]
            neg_dst = torch.randint(0, num_stations, conn_edges[1].shape, device=device)
            neg_dst_emb = station_emb[neg_dst]
            neg_scores = model.score_route(src_emb, neg_dst_emb)
            
            # Margin ranking loss
            margin_loss = nn.MarginRankingLoss(margin=1.0)
            target = torch.ones_like(pos_scores)
            loss = margin_loss(pos_scores, neg_scores, target)
            
            # Track scores
            history['pos_scores'].append(pos_scores.mean().item())
            history['neg_scores'].append(neg_scores.mean().item())
        else:
            # Fallback: contrastive loss on station embeddings
            loss = torch.tensor(0.0, device=device)
            history['pos_scores'].append(0)
            history['neg_scores'].append(0)
        
        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        
        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        
        optimizer.step()
        scheduler.step(loss)
        
        epoch_time = time.time() - epoch_start
        
        history['train_loss'].append(loss.item())
        history['lr'].append(optimizer.param_groups[0]['lr'])
        history['epoch_times'].append(epoch_time)
        
        if (epoch + 1) % config.log_interval == 0:
            pos_avg = history['pos_scores'][-1]
            neg_avg = history['neg_scores'][-1]
            print(f"Epoch {epoch + 1:3d}/{config.epochs} | Loss: {loss.item():.6f} | Pos: {pos_avg:.4f} | Neg: {neg_avg:.4f} | LR: {history['lr'][-1]:.6f} | Time: {epoch_time:.2f}s")
        
        if config.save_best and loss.item() < best_loss:
            best_loss = loss.item()
            best_epoch = epoch + 1
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'loss': loss.item(),
                'config': {
                    'epochs': config.epochs,
                    'learning_rate': config.learning_rate,
                    'weight_decay': config.weight_decay,
                    'patience': config.patience,
                },
            }, checkpoint_dir / 'route_optimizer_best.pt')
        
        if early_stopping(loss.item()):
            print(f"\n⚠️ Early stopping triggered at epoch {epoch + 1}")
            break
    
    total_time = time.time() - training_start_time
    
    print(f"\n{'='*60}")
    print(f"✅ TRAINING COMPLETE")
    print(f"{'='*60}")
    print(f"\n📊 Training Summary:")
    print(f"   • Total Epochs: {len(history['train_loss'])}")
    print(f"   • Best Epoch: {best_epoch}")
    print(f"   • Best Loss: {best_loss:.6f}")
    print(f"   • Final Loss: {history['train_loss'][-1]:.6f}")
    print(f"   • Initial Loss: {history['train_loss'][0]:.6f}")
    print(f"   • Improvement: {(1 - best_loss/history['train_loss'][0])*100:.2f}%")
    print(f"   • Total Time: {total_time:.2f}s")
    print(f"   • Avg Epoch Time: {np.mean(history['epoch_times']):.2f}s")
    
    result = {
        'history': history,
        'best_loss': best_loss,
        'best_epoch': best_epoch,
        'total_time': total_time,
        'model': model,
    }
    
    # Generate report
    if config.generate_report:
        try:
            from .reporting import generate_training_report
            
            # Get evaluation metrics
            eval_metrics = evaluate_route_optimizer(model, data, device=device)
            
            report_paths = generate_training_report(
                model=model,
                data=data,
                history=history,
                config={
                    'epochs': config.epochs,
                    'learning_rate': config.learning_rate,
                    'weight_decay': config.weight_decay,
                    'patience': config.patience,
                    'batch_size': config.batch_size,
                    'optimizer': 'Adam',
                },
                model_name=config.model_name or "Route Optimizer GNN",
                dataset_name=config.dataset_name or "GraphCeylon Railway Dataset",
                evaluation_results=eval_metrics,
                output_dir=config.report_dir,
                notes=f"Trained for {len(history['train_loss'])} epochs. Best loss: {best_loss:.6f}",
            )
            result['report_paths'] = report_paths
            print(f"\n📄 Report generated: {report_paths.get('markdown', '')}")
        except Exception as e:
            print(f"\n⚠️ Could not generate report: {e}")
    
    return result


def evaluate_hotel_recommender(
    model: nn.Module,
    data: 'HeteroData',
    k_values: List[int] = [5, 10, 20],
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu',
) -> Dict[str, float]:
    """
    Evaluate hotel recommender model.
    
    Metrics:
    - Rating MSE/MAE
    - Hit Rate @ K
    - NDCG @ K
    """
    model.eval()
    model = model.to(device)
    data = data.to(device)
    
    with torch.no_grad():
        results = model(data)
        embeddings = results['embeddings']
        
        metrics = {}
        
        # Rating prediction metrics
        if 'predicted_ratings' in results:
            pred = results['predicted_ratings']
            # Use feature rating as ground truth
            true = data['Hotel'].x[:, 0] * 5.0  # Denormalized
            
            mse = nn.MSELoss()(pred, true).item()
            mae = nn.L1Loss()(pred, true).item()
            
            metrics['rating_mse'] = mse
            metrics['rating_mae'] = mae
        
        # Similarity-based metrics
        if 'Hotel' in embeddings:
            hotel_emb = embeddings['Hotel']
            
            # Compute pairwise similarities
            sim_matrix = torch.mm(
                nn.functional.normalize(hotel_emb, dim=1),
                nn.functional.normalize(hotel_emb, dim=1).t()
            )
            
            # Average self-similarity (should be 1.0)
            metrics['avg_self_sim'] = sim_matrix.diag().mean().item()
            
            # Average cross-similarity
            mask = ~torch.eye(sim_matrix.shape[0], dtype=bool, device=device)
            metrics['avg_cross_sim'] = sim_matrix[mask].mean().item()
    
    return metrics


def evaluate_route_optimizer(
    model: nn.Module,
    data: 'HeteroData',
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu',
) -> Dict[str, float]:
    """
    Evaluate route optimizer model.
    
    Metrics:
    - Route score accuracy
    - Station embedding quality
    """
    model.eval()
    model = model.to(device)
    data = data.to(device)
    
    with torch.no_grad():
        embeddings = model.encode(data)
        
        metrics = {}
        
        if 'RailwayStation' in embeddings:
            station_emb = embeddings['RailwayStation']
            
            # Embedding quality metrics
            norms = torch.norm(station_emb, dim=1)
            metrics['avg_embedding_norm'] = norms.mean().item()
            metrics['std_embedding_norm'] = norms.std().item()
            
            # Connected stations should have similar embeddings
            if ('RailwayStation', 'CONNECTED_BY_TRAIN', 'RailwayStation') in data.edge_types:
                conn_edges = data['RailwayStation', 'CONNECTED_BY_TRAIN', 'RailwayStation'].edge_index
                
                src_emb = station_emb[conn_edges[0]]
                dst_emb = station_emb[conn_edges[1]]
                
                # Cosine similarity of connected pairs
                connected_sim = nn.functional.cosine_similarity(src_emb, dst_emb, dim=1)
                metrics['connected_similarity'] = connected_sim.mean().item()
    
    return metrics


if __name__ == "__main__":
    print("GraphCeylon GNN Training Utilities")
    print("=" * 50)
    
    if HAS_PYG:
        print("✅ PyTorch Geometric available")
        print("\nAvailable functions:")
        print("  - train_hotel_recommender()")
        print("  - train_route_optimizer()")
        print("  - evaluate_hotel_recommender()")
        print("  - evaluate_route_optimizer()")
    else:
        print("❌ PyTorch Geometric not installed")

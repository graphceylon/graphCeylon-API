#!/usr/bin/env python
"""
GraphCeylon GNN - Main Script

Export Neo4j graph to PyTorch Geometric and train GNN models.

Usage:
    python run_gnn.py export          # Export graph to PyG format
    python run_gnn.py train hotel     # Train hotel recommender
    python run_gnn.py train route     # Train route optimizer
    python run_gnn.py eval hotel      # Evaluate hotel model
    python run_gnn.py eval route      # Evaluate route model
    python run_gnn.py all             # Run full pipeline
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def check_dependencies():
    """Check required dependencies"""
    missing = []
    
    try:
        import torch
        print(f"✅ PyTorch {torch.__version__}")
    except ImportError:
        missing.append("torch")
    
    try:
        import torch_geometric
        print(f"✅ PyTorch Geometric {torch_geometric.__version__}")
    except ImportError:
        missing.append("torch-geometric")
    
    try:
        from neo4j import GraphDatabase
        print("✅ Neo4j Driver")
    except ImportError:
        missing.append("neo4j")
    
    if missing:
        print(f"\n❌ Missing dependencies: {', '.join(missing)}")
        print("\nInstall with:")
        print("  pip install torch torch-geometric neo4j")
        return False
    
    return True


def export_graph(output_dir: str = "data/gnn"):
    """Export Neo4j graph to PyTorch Geometric format"""
    from gnn.export_graph import (
        GraphExporter, TrainScheduleGraphExporter, HotelGraphExporter,
        TransportGraphExporter, EventGraphExporter
    )
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "=" * 60)
    print("📊 EXPORTING GRAPH TO PYTORCH GEOMETRIC")
    print("=" * 60)
    
    # Full graph export
    print("\n[1/5] Exporting full graph...")
    with GraphExporter() as exporter:
        data = exporter.export()
        exporter.save(data, str(output_path / "graphceylon_full.pt"))
    
    # Train schedule subgraph (backward compat)
    print("\n[2/5] Exporting train schedule subgraph...")
    with TrainScheduleGraphExporter() as exporter:
        train_data = exporter.export_with_temporal_features()
        exporter.save(train_data, str(output_path / "graphceylon_trains.pt"))
    
    # Hotel subgraph (now includes SubAttraction edges)
    print("\n[3/5] Exporting hotel subgraph...")
    with HotelGraphExporter() as exporter:
        hotel_data = exporter.export()
        exporter.save(hotel_data, str(output_path / "graphceylon_hotels.pt"))
    
    # Transport subgraph (trains + buses)
    print("\n[4/5] Exporting transport subgraph...")
    with TransportGraphExporter() as exporter:
        transport_data = exporter.export_with_temporal_features()
        exporter.save(transport_data, str(output_path / "graphceylon_transport.pt"))
    
    # Event subgraph
    print("\n[5/5] Exporting event subgraph...")
    with EventGraphExporter() as exporter:
        event_data = exporter.export()
        exporter.save(event_data, str(output_path / "graphceylon_events.pt"))
    
    print("\n✅ Export complete!")
    print(f"   Files saved to: {output_path}")
    
    return data


def train_hotel(data_path: str = "data/gnn/graphceylon_hotels.pt"):
    """Train hotel recommendation model with comprehensive reporting"""
    import torch
    from gnn.export_graph import GraphExporter
    from gnn.models import HotelRecommenderGNN, ModelConfig
    from gnn.training import train_hotel_recommender, TrainingConfig
    
    print("\n" + "=" * 60)
    print("🏨 TRAINING HOTEL RECOMMENDER")
    print("=" * 60)
    
    # Load data
    print(f"\nLoading data from {data_path}...")
    data, node_mappings, cat_encodings, name_mappings = GraphExporter.load(data_path)
    
    # Get metadata
    metadata = (list(data.node_types), list(data.edge_types))
    
    # Get input dimensions
    in_channels_dict = {}
    for node_type in data.node_types:
        if hasattr(data[node_type], 'x'):
            in_channels_dict[node_type] = data[node_type].x.shape[1]
        else:
            in_channels_dict[node_type] = 1
    
    print(f"Node types: {list(data.node_types)}")
    print(f"Edge types: {len(data.edge_types)}")
    print(f"Input dimensions: {in_channels_dict}")
    
    # Create model
    config = ModelConfig(
        hidden_channels=64,
        out_channels=32,
        num_heads=4,
        num_layers=3,
        dropout=0.2,
    )
    
    model = HotelRecommenderGNN(metadata, in_channels_dict, config)
    print(f"\nModel parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Train with reporting enabled
    train_config = TrainingConfig(
        epochs=150,
        learning_rate=0.001,
        patience=20,
        log_interval=5,
        generate_report=True,
        report_dir="reports",
        model_name="Hotel Recommender GNN",
        dataset_name="GraphCeylon Hotels Dataset",
    )
    
    result = train_hotel_recommender(model, data, node_mappings, train_config)
    
    return result.get('model'), result.get('history')


def train_route(data_path: str = "data/gnn/graphceylon_trains.pt"):
    """Train route optimization model with comprehensive reporting"""
    import torch
    from gnn.export_graph import GraphExporter
    from gnn.models import RouteOptimizerGNN, ModelConfig
    from gnn.training import train_route_optimizer, TrainingConfig
    
    print("\n" + "=" * 60)
    print("🚂 TRAINING ROUTE OPTIMIZER")
    print("=" * 60)
    
    # Load data
    print(f"\nLoading data from {data_path}...")
    data, node_mappings, cat_encodings, name_mappings = GraphExporter.load(data_path)
    
    metadata = (list(data.node_types), list(data.edge_types))
    
    in_channels_dict = {}
    for node_type in data.node_types:
        if hasattr(data[node_type], 'x'):
            in_channels_dict[node_type] = data[node_type].x.shape[1]
        else:
            in_channels_dict[node_type] = 1
    
    print(f"Node types: {list(data.node_types)}")
    print(f"Edge types: {len(data.edge_types)}")
    
    config = ModelConfig(
        hidden_channels=64,
        out_channels=32,
        num_heads=4,
        num_layers=3,
        dropout=0.2,
    )
    
    model = RouteOptimizerGNN(metadata, in_channels_dict, config)
    print(f"\nModel parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Train with reporting enabled
    train_config = TrainingConfig(
        epochs=50,
        learning_rate=0.001,
        patience=10,
        log_interval=5,
        generate_report=True,
        report_dir="reports",
        model_name="Route Optimizer GNN",
        dataset_name="GraphCeylon Railway Dataset",
    )
    
    result = train_route_optimizer(model, data, node_mappings, train_config)
    
    return result.get('model'), result.get('history')


def evaluate_hotel(
    model_path: str = "checkpoints/hotel_recommender_best.pt",
    data_path: str = "data/gnn/graphceylon_hotels.pt",
):
    """Evaluate hotel model"""
    import torch
    from gnn.export_graph import GraphExporter
    from gnn.models import HotelRecommenderGNN, ModelConfig
    from gnn.training import evaluate_hotel_recommender
    
    print("\n" + "=" * 60)
    print("📊 EVALUATING HOTEL RECOMMENDER")
    print("=" * 60)
    
    # Load data and model
    data, node_mappings, cat_encodings, name_mappings = GraphExporter.load(data_path)
    metadata = (list(data.node_types), list(data.edge_types))
    
    in_channels_dict = {}
    for node_type in data.node_types:
        if hasattr(data[node_type], 'x'):
            in_channels_dict[node_type] = data[node_type].x.shape[1]
        else:
            in_channels_dict[node_type] = 1
    
    config = ModelConfig()
    model = HotelRecommenderGNN(metadata, in_channels_dict, config)
    
    # Load weights
    checkpoint = torch.load(model_path)
    model.load_state_dict(checkpoint['model_state_dict'])
    print(f"Loaded model from epoch {checkpoint['epoch']}")
    
    # Evaluate
    metrics = evaluate_hotel_recommender(model, data)
    
    print("\n📈 Evaluation Results:")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")
    
    return metrics


def evaluate_route(
    model_path: str = "checkpoints/route_optimizer_best.pt",
    data_path: str = "data/gnn/graphceylon_trains.pt",
):
    """Evaluate route model"""
    import torch
    from gnn.export_graph import GraphExporter
    from gnn.models import RouteOptimizerGNN, ModelConfig
    from gnn.training import evaluate_route_optimizer
    
    print("\n" + "=" * 60)
    print("📊 EVALUATING ROUTE OPTIMIZER")
    print("=" * 60)
    
    data, node_mappings, cat_encodings, name_mappings = GraphExporter.load(data_path)
    metadata = (list(data.node_types), list(data.edge_types))
    
    in_channels_dict = {}
    for node_type in data.node_types:
        if hasattr(data[node_type], 'x'):
            in_channels_dict[node_type] = data[node_type].x.shape[1]
        else:
            in_channels_dict[node_type] = 1
    
    config = ModelConfig()
    model = RouteOptimizerGNN(metadata, in_channels_dict, config)
    
    checkpoint = torch.load(model_path)
    model.load_state_dict(checkpoint['model_state_dict'])
    print(f"Loaded model from epoch {checkpoint['epoch']}")
    
    metrics = evaluate_route_optimizer(model, data)
    
    print("\n📈 Evaluation Results:")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")
    
    return metrics


def run_full_pipeline():
    """Run complete pipeline: export, train, evaluate"""
    print("\n" + "=" * 60)
    print("🚀 GRAPHCEYLON GNN - FULL PIPELINE")
    print("=" * 60)
    
    # Step 1: Export
    export_graph()
    
    # Step 2: Train models
    train_hotel()
    train_route()
    
    # Step 3: Evaluate
    evaluate_hotel()
    evaluate_route()
    
    print("\n" + "=" * 60)
    print("✅ PIPELINE COMPLETE!")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="GraphCeylon GNN Training Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export graph to PyG format')
    export_parser.add_argument('--output', '-o', default='data/gnn', help='Output directory')
    
    # Train command
    train_parser = subparsers.add_parser('train', help='Train a model')
    train_parser.add_argument('model', choices=['hotel', 'route', 'all'], help='Model to train')
    train_parser.add_argument('--data', '-d', help='Path to data file')
    
    # Eval command
    eval_parser = subparsers.add_parser('eval', help='Evaluate a model')
    eval_parser.add_argument('model', choices=['hotel', 'route'], help='Model to evaluate')
    eval_parser.add_argument('--weights', '-w', help='Path to model weights')
    eval_parser.add_argument('--data', '-d', help='Path to data file')
    
    # All command
    subparsers.add_parser('all', help='Run full pipeline')
    
    args = parser.parse_args()
    
    print("\n🌴 GraphCeylon GNN")
    print("Tourism Knowledge Graph Neural Networks")
    print("-" * 40)
    
    if not check_dependencies():
        return 1
    
    if args.command == 'export':
        export_graph(args.output)
    
    elif args.command == 'train':
        if args.model == 'hotel':
            train_hotel(args.data or 'data/gnn/graphceylon_hotels.pt')
        elif args.model == 'route':
            train_route(args.data or 'data/gnn/graphceylon_trains.pt')
        elif args.model == 'all':
            train_hotel()
            train_route()
    
    elif args.command == 'eval':
        if args.model == 'hotel':
            evaluate_hotel(
                args.weights or 'checkpoints/hotel_recommender_best.pt',
                args.data or 'data/gnn/graphceylon_hotels.pt',
            )
        elif args.model == 'route':
            evaluate_route(
                args.weights or 'checkpoints/route_optimizer_best.pt',
                args.data or 'data/gnn/graphceylon_trains.pt',
            )
    
    elif args.command == 'all':
        run_full_pipeline()
    
    else:
        parser.print_help()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

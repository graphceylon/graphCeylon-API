"""
GraphCeylon GNN Reporting Module

Comprehensive training reports with:
- Training curves and visualizations
- Model architecture analysis
- Performance metrics and statistics
- Detailed documentation for academic reports
"""

import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
import json
import math

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.ticker import MaxNLocator
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("⚠️ matplotlib not installed. Install with: pip install matplotlib")

try:
    from torch_geometric.data import HeteroData
    HAS_PYG = True
except ImportError:
    HAS_PYG = False


@dataclass
class ModelArchitectureInfo:
    """Detailed model architecture information"""
    model_name: str
    model_type: str
    total_parameters: int
    trainable_parameters: int
    non_trainable_parameters: int
    hidden_channels: int
    output_channels: int
    num_layers: int
    node_types: List[str]
    edge_types: List[str]
    input_dimensions: Dict[str, int]
    layer_details: List[Dict[str, Any]]
    activation_function: str = "ReLU"
    normalization: str = "LayerNorm"
    dropout_rate: float = 0.0
    aggregation_method: str = "scatter_add"


@dataclass
class DatasetInfo:
    """Dataset statistics and information"""
    dataset_name: str
    total_nodes: int
    total_edges: int
    node_type_counts: Dict[str, int]
    edge_type_counts: Dict[str, int]
    feature_dimensions: Dict[str, int]
    graph_density: float
    avg_degree: float
    node_features_summary: Dict[str, Dict[str, float]]
    edge_features_summary: Dict[str, Dict[str, float]]
    split_info: Optional[Dict[str, int]] = None


@dataclass
class TrainingMetrics:
    """Training metrics and statistics"""
    total_epochs: int
    best_epoch: int
    initial_loss: float
    final_loss: float
    best_loss: float
    loss_improvement: float
    loss_improvement_percent: float
    avg_epoch_time: float = 0.0
    total_training_time: float = 0.0
    early_stopped: bool = False
    early_stop_epoch: Optional[int] = None
    convergence_epoch: Optional[int] = None  # When loss stabilized
    learning_rate_initial: float = 0.001
    learning_rate_final: float = 0.001
    optimizer: str = "Adam"
    weight_decay: float = 1e-5


@dataclass
class EvaluationMetrics:
    """Evaluation metrics for different tasks"""
    task_name: str
    primary_metric: str
    primary_value: float
    all_metrics: Dict[str, float]
    confusion_matrix: Optional[np.ndarray] = None
    per_class_metrics: Optional[Dict[str, Dict[str, float]]] = None


@dataclass
class TrainingHistory:
    """Complete training history"""
    train_losses: List[float]
    val_losses: Optional[List[float]] = None
    learning_rates: List[float] = field(default_factory=list)
    epoch_times: List[float] = field(default_factory=list)
    gradient_norms: List[float] = field(default_factory=list)
    custom_metrics: Dict[str, List[float]] = field(default_factory=dict)


@dataclass
class GNNTrainingReport:
    """Complete GNN training report"""
    report_id: str
    timestamp: str
    model_info: ModelArchitectureInfo
    dataset_info: DatasetInfo
    training_config: Dict[str, Any]
    training_metrics: TrainingMetrics
    training_history: TrainingHistory
    evaluation_metrics: Optional[EvaluationMetrics] = None
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    hardware_info: Dict[str, str] = field(default_factory=dict)
    notes: str = ""


class GNNReporter:
    """
    Comprehensive GNN Training Reporter
    
    Generates detailed reports with:
    - Training visualizations
    - Performance metrics
    - Model analysis
    - Export to various formats
    """
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.report: Optional[GNNTrainingReport] = None
        self.figures: Dict[str, plt.Figure] = {}
        
    def analyze_model(
        self,
        model: nn.Module,
        data: 'HeteroData',
        model_name: str = "GNN Model"
    ) -> ModelArchitectureInfo:
        """Analyze model architecture in detail"""
        
        # Count parameters
        total_params = sum(p.numel() for p in model.parameters())
        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        non_trainable_params = total_params - trainable_params
        
        # Get model attributes
        hidden_channels = getattr(model, 'hidden_channels', 64)
        out_channels = getattr(model, 'out_channels', 32)
        num_layers = getattr(model, 'num_layers', 2)
        
        # Analyze layers
        layer_details = []
        for name, module in model.named_modules():
            if name:  # Skip root module
                layer_info = {
                    'name': name,
                    'type': module.__class__.__name__,
                    'parameters': sum(p.numel() for p in module.parameters()),
                }
                
                # Add layer-specific info
                if hasattr(module, 'in_features'):
                    layer_info['in_features'] = module.in_features
                if hasattr(module, 'out_features'):
                    layer_info['out_features'] = module.out_features
                if hasattr(module, 'in_channels'):
                    layer_info['in_channels'] = module.in_channels
                if hasattr(module, 'out_channels'):
                    layer_info['out_channels'] = module.out_channels
                    
                layer_details.append(layer_info)
        
        # Get graph info
        node_types = list(data.node_types) if hasattr(data, 'node_types') else []
        edge_types = [str(et) for et in data.edge_types] if hasattr(data, 'edge_types') else []
        
        # Input dimensions per node type
        input_dims = {}
        for nt in node_types:
            if hasattr(data[nt], 'x') and data[nt].x is not None:
                input_dims[nt] = data[nt].x.shape[1]
            else:
                input_dims[nt] = 0
        
        return ModelArchitectureInfo(
            model_name=model_name,
            model_type=model.__class__.__name__,
            total_parameters=total_params,
            trainable_parameters=trainable_params,
            non_trainable_parameters=non_trainable_params,
            hidden_channels=hidden_channels,
            output_channels=out_channels,
            num_layers=num_layers,
            node_types=node_types,
            edge_types=edge_types,
            input_dimensions=input_dims,
            layer_details=layer_details,
        )
    
    def analyze_dataset(
        self,
        data: 'HeteroData',
        dataset_name: str = "GraphCeylon Dataset"
    ) -> DatasetInfo:
        """Analyze dataset statistics"""
        
        # Count nodes and edges
        node_counts = {}
        edge_counts = {}
        feature_dims = {}
        node_feature_stats = {}
        edge_feature_stats = {}
        
        total_nodes = 0
        total_edges = 0
        
        for nt in data.node_types:
            count = data[nt].num_nodes
            node_counts[nt] = count
            total_nodes += count
            
            if hasattr(data[nt], 'x') and data[nt].x is not None:
                x = data[nt].x
                feature_dims[nt] = x.shape[1]
                
                # Feature statistics
                node_feature_stats[nt] = {
                    'mean': float(x.mean()),
                    'std': float(x.std()),
                    'min': float(x.min()),
                    'max': float(x.max()),
                    'sparsity': float((x == 0).sum()) / x.numel(),
                }
        
        for et in data.edge_types:
            count = data[et].edge_index.shape[1]
            edge_counts[str(et)] = count
            total_edges += count
            
            if hasattr(data[et], 'edge_attr') and data[et].edge_attr is not None:
                attr = data[et].edge_attr
                edge_feature_stats[str(et)] = {
                    'mean': float(attr.mean()),
                    'std': float(attr.std()),
                    'min': float(attr.min()),
                    'max': float(attr.max()),
                }
        
        # Graph density
        max_edges = total_nodes * (total_nodes - 1)
        density = total_edges / max_edges if max_edges > 0 else 0
        
        # Average degree
        avg_degree = (2 * total_edges) / total_nodes if total_nodes > 0 else 0
        
        return DatasetInfo(
            dataset_name=dataset_name,
            total_nodes=total_nodes,
            total_edges=total_edges,
            node_type_counts=node_counts,
            edge_type_counts=edge_counts,
            feature_dimensions=feature_dims,
            graph_density=density,
            avg_degree=avg_degree,
            node_features_summary=node_feature_stats,
            edge_features_summary=edge_feature_stats,
        )
    
    def analyze_training(
        self,
        history: Dict[str, List[float]],
        config: Dict[str, Any],
        epoch_times: Optional[List[float]] = None,
    ) -> Tuple[TrainingMetrics, TrainingHistory]:
        """Analyze training results"""
        
        train_losses = history.get('train_loss', [])
        val_losses = history.get('val_loss', None)
        learning_rates = history.get('lr', [])
        
        if not train_losses:
            raise ValueError("No training losses found in history")
        
        # Calculate metrics
        initial_loss = train_losses[0]
        final_loss = train_losses[-1]
        best_loss = min(train_losses)
        best_epoch = train_losses.index(best_loss) + 1
        
        improvement = initial_loss - best_loss
        improvement_pct = (improvement / initial_loss * 100) if initial_loss > 0 else 0
        
        # Detect convergence (when loss stops improving significantly)
        convergence_epoch = None
        threshold = 0.001  # 0.1% change
        window = 5
        for i in range(window, len(train_losses)):
            recent_change = abs(train_losses[i] - train_losses[i-window]) / (train_losses[i-window] + 1e-8)
            if recent_change < threshold:
                convergence_epoch = i
                break
        
        # Early stopping detection
        total_epochs = len(train_losses)
        early_stopped = total_epochs < config.get('epochs', 100)
        
        metrics = TrainingMetrics(
            total_epochs=total_epochs,
            best_epoch=best_epoch,
            initial_loss=initial_loss,
            final_loss=final_loss,
            best_loss=best_loss,
            loss_improvement=improvement,
            loss_improvement_percent=improvement_pct,
            early_stopped=early_stopped,
            early_stop_epoch=total_epochs if early_stopped else None,
            convergence_epoch=convergence_epoch,
            learning_rate_initial=learning_rates[0] if learning_rates else config.get('learning_rate', 0.001),
            learning_rate_final=learning_rates[-1] if learning_rates else config.get('learning_rate', 0.001),
            optimizer=config.get('optimizer', 'Adam'),
            weight_decay=config.get('weight_decay', 1e-5),
            avg_epoch_time=np.mean(epoch_times) if epoch_times else 0,
            total_training_time=sum(epoch_times) if epoch_times else 0,
        )
        
        history_obj = TrainingHistory(
            train_losses=train_losses,
            val_losses=val_losses,
            learning_rates=learning_rates,
            epoch_times=epoch_times or [],
        )
        
        return metrics, history_obj
    
    def create_report(
        self,
        model: nn.Module,
        data: 'HeteroData',
        history: Dict[str, List[float]],
        config: Dict[str, Any],
        model_name: str = "GNN Model",
        dataset_name: str = "GraphCeylon Dataset",
        evaluation_results: Optional[Dict[str, float]] = None,
        notes: str = "",
    ) -> GNNTrainingReport:
        """Create a comprehensive training report"""
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_id = f"{model_name.replace(' ', '_')}_{timestamp}"
        
        # Analyze components
        model_info = self.analyze_model(model, data, model_name)
        dataset_info = self.analyze_dataset(data, dataset_name)
        training_metrics, training_history = self.analyze_training(history, config)
        
        # Evaluation metrics
        eval_metrics = None
        if evaluation_results:
            primary_metric = list(evaluation_results.keys())[0]
            eval_metrics = EvaluationMetrics(
                task_name=model_name,
                primary_metric=primary_metric,
                primary_value=evaluation_results[primary_metric],
                all_metrics=evaluation_results,
            )
        
        # Hardware info
        hardware_info = {
            'device': 'CUDA' if torch.cuda.is_available() else 'CPU',
            'pytorch_version': torch.__version__,
        }
        if torch.cuda.is_available():
            hardware_info['gpu_name'] = torch.cuda.get_device_name(0)
            hardware_info['gpu_memory'] = f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB"
        
        self.report = GNNTrainingReport(
            report_id=report_id,
            timestamp=timestamp,
            model_info=model_info,
            dataset_info=dataset_info,
            training_config=config,
            training_metrics=training_metrics,
            training_history=training_history,
            evaluation_metrics=eval_metrics,
            hyperparameters=config,
            hardware_info=hardware_info,
            notes=notes,
        )
        
        return self.report
    
    def plot_training_curves(self, save: bool = True) -> Optional[plt.Figure]:
        """Generate training loss curves"""
        if not HAS_MATPLOTLIB or self.report is None:
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'{self.report.model_info.model_name} Training Report', fontsize=16, fontweight='bold')
        
        history = self.report.training_history
        epochs = range(1, len(history.train_losses) + 1)
        
        # 1. Loss Curve
        ax1 = axes[0, 0]
        ax1.plot(epochs, history.train_losses, 'b-', linewidth=2, label='Training Loss', marker='o', markersize=3)
        if history.val_losses:
            ax1.plot(epochs, history.val_losses, 'r-', linewidth=2, label='Validation Loss', marker='s', markersize=3)
        
        # Mark best epoch
        best_epoch = self.report.training_metrics.best_epoch
        best_loss = self.report.training_metrics.best_loss
        ax1.axvline(x=best_epoch, color='g', linestyle='--', alpha=0.7, label=f'Best Epoch ({best_epoch})')
        ax1.scatter([best_epoch], [best_loss], color='g', s=100, zorder=5, marker='*')
        
        ax1.set_xlabel('Epoch', fontsize=12)
        ax1.set_ylabel('Loss', fontsize=12)
        ax1.set_title('Training Loss Curve', fontsize=14)
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_locator(MaxNLocator(integer=True))
        
        # 2. Log-scale Loss
        ax2 = axes[0, 1]
        ax2.semilogy(epochs, history.train_losses, 'b-', linewidth=2, label='Training Loss')
        ax2.axhline(y=best_loss, color='g', linestyle='--', alpha=0.7, label=f'Best: {best_loss:.6f}')
        ax2.set_xlabel('Epoch', fontsize=12)
        ax2.set_ylabel('Loss (log scale)', fontsize=12)
        ax2.set_title('Training Loss (Log Scale)', fontsize=14)
        ax2.legend(loc='upper right')
        ax2.grid(True, alpha=0.3, which='both')
        ax2.xaxis.set_major_locator(MaxNLocator(integer=True))
        
        # 3. Learning Rate Schedule
        ax3 = axes[1, 0]
        if history.learning_rates:
            ax3.plot(epochs, history.learning_rates, 'g-', linewidth=2, marker='o', markersize=3)
            ax3.set_xlabel('Epoch', fontsize=12)
            ax3.set_ylabel('Learning Rate', fontsize=12)
            ax3.set_title('Learning Rate Schedule', fontsize=14)
            ax3.grid(True, alpha=0.3)
            ax3.xaxis.set_major_locator(MaxNLocator(integer=True))
        else:
            ax3.text(0.5, 0.5, 'Learning Rate data not available', ha='center', va='center', fontsize=12)
            ax3.set_title('Learning Rate Schedule', fontsize=14)
        
        # 4. Loss Improvement
        ax4 = axes[1, 1]
        loss_change = [0] + [history.train_losses[i] - history.train_losses[i-1] for i in range(1, len(history.train_losses))]
        colors = ['green' if x < 0 else 'red' for x in loss_change]
        ax4.bar(epochs, loss_change, color=colors, alpha=0.7)
        ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax4.set_xlabel('Epoch', fontsize=12)
        ax4.set_ylabel('Loss Change', fontsize=12)
        ax4.set_title('Epoch-wise Loss Change', fontsize=14)
        ax4.grid(True, alpha=0.3, axis='y')
        ax4.xaxis.set_major_locator(MaxNLocator(integer=True))
        
        plt.tight_layout()
        
        if save:
            filepath = self.output_dir / f"{self.report.report_id}_training_curves.png"
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
            print(f"📊 Saved training curves: {filepath}")
        
        self.figures['training_curves'] = fig
        return fig
    
    def plot_model_architecture(self, save: bool = True) -> Optional[plt.Figure]:
        """Visualize model architecture"""
        if not HAS_MATPLOTLIB or self.report is None:
            return None
        
        model_info = self.report.model_info
        
        fig, axes = plt.subplots(1, 3, figsize=(16, 6))
        fig.suptitle(f'{model_info.model_name} Architecture Analysis', fontsize=16, fontweight='bold')
        
        # 1. Parameter Distribution by Layer Type
        ax1 = axes[0]
        layer_types = {}
        for layer in model_info.layer_details:
            ltype = layer['type']
            params = layer['parameters']
            layer_types[ltype] = layer_types.get(ltype, 0) + params
        
        if layer_types:
            labels = list(layer_types.keys())
            sizes = list(layer_types.values())
            colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
            
            wedges, texts, autotexts = ax1.pie(sizes, labels=labels, autopct='%1.1f%%', 
                                                colors=colors, startangle=90)
            ax1.set_title('Parameters by Layer Type', fontsize=14)
        
        # 2. Input Dimensions per Node Type
        ax2 = axes[1]
        node_types = list(model_info.input_dimensions.keys())
        dims = list(model_info.input_dimensions.values())
        colors = plt.cm.Paired(np.linspace(0, 1, len(node_types)))
        
        bars = ax2.bar(range(len(node_types)), dims, color=colors)
        ax2.set_xticks(range(len(node_types)))
        ax2.set_xticklabels(node_types, rotation=45, ha='right')
        ax2.set_xlabel('Node Type', fontsize=12)
        ax2.set_ylabel('Input Dimension', fontsize=12)
        ax2.set_title('Input Dimensions per Node Type', fontsize=14)
        
        # Add value labels
        for bar, dim in zip(bars, dims):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                    str(dim), ha='center', va='bottom', fontsize=10)
        
        # 3. Model Summary Table
        ax3 = axes[2]
        ax3.axis('off')
        
        summary_data = [
            ['Model Type', model_info.model_type],
            ['Total Parameters', f'{model_info.total_parameters:,}'],
            ['Trainable Parameters', f'{model_info.trainable_parameters:,}'],
            ['Hidden Channels', str(model_info.hidden_channels)],
            ['Output Channels', str(model_info.output_channels)],
            ['Number of Layers', str(model_info.num_layers)],
            ['Node Types', str(len(model_info.node_types))],
            ['Edge Types', str(len(model_info.edge_types))],
            ['Activation', model_info.activation_function],
            ['Normalization', model_info.normalization],
            ['Aggregation', model_info.aggregation_method],
        ]
        
        table = ax3.table(
            cellText=summary_data,
            colLabels=['Property', 'Value'],
            loc='center',
            cellLoc='left',
            colWidths=[0.5, 0.5],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1.2, 1.5)
        
        # Style header
        for i in range(2):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(color='white', fontweight='bold')
        
        ax3.set_title('Model Summary', fontsize=14, pad=20)
        
        plt.tight_layout()
        
        if save:
            filepath = self.output_dir / f"{self.report.report_id}_architecture.png"
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
            print(f"📊 Saved architecture analysis: {filepath}")
        
        self.figures['architecture'] = fig
        return fig
    
    def plot_dataset_analysis(self, save: bool = True) -> Optional[plt.Figure]:
        """Visualize dataset statistics"""
        if not HAS_MATPLOTLIB or self.report is None:
            return None
        
        dataset_info = self.report.dataset_info
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'{dataset_info.dataset_name} Analysis', fontsize=16, fontweight='bold')
        
        # 1. Node Type Distribution
        ax1 = axes[0, 0]
        node_types = list(dataset_info.node_type_counts.keys())
        node_counts = list(dataset_info.node_type_counts.values())
        colors = plt.cm.tab20(np.linspace(0, 1, len(node_types)))
        
        bars = ax1.barh(range(len(node_types)), node_counts, color=colors)
        ax1.set_yticks(range(len(node_types)))
        ax1.set_yticklabels(node_types)
        ax1.set_xlabel('Count', fontsize=12)
        ax1.set_title('Node Type Distribution', fontsize=14)
        
        for bar, count in zip(bars, node_counts):
            ax1.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                    f'{count:,}', ha='left', va='center', fontsize=9)
        
        # 2. Edge Type Distribution (Top 10)
        ax2 = axes[0, 1]
        edge_items = sorted(dataset_info.edge_type_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        edge_types = [e[0].split("'")[3] if "'" in e[0] else e[0] for e in edge_items]  # Extract relationship name
        edge_counts = [e[1] for e in edge_items]
        colors = plt.cm.Set2(np.linspace(0, 1, len(edge_types)))
        
        bars = ax2.barh(range(len(edge_types)), edge_counts, color=colors)
        ax2.set_yticks(range(len(edge_types)))
        ax2.set_yticklabels(edge_types, fontsize=9)
        ax2.set_xlabel('Count', fontsize=12)
        ax2.set_title('Top 10 Edge Types', fontsize=14)
        
        for bar, count in zip(bars, edge_counts):
            ax2.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                    f'{count:,}', ha='left', va='center', fontsize=9)
        
        # 3. Feature Statistics
        ax3 = axes[1, 0]
        if dataset_info.node_features_summary:
            node_types_with_features = list(dataset_info.node_features_summary.keys())
            means = [dataset_info.node_features_summary[nt]['mean'] for nt in node_types_with_features]
            stds = [dataset_info.node_features_summary[nt]['std'] for nt in node_types_with_features]
            
            x = range(len(node_types_with_features))
            ax3.bar(x, means, yerr=stds, capsize=5, color='steelblue', alpha=0.8)
            ax3.set_xticks(x)
            ax3.set_xticklabels(node_types_with_features, rotation=45, ha='right')
            ax3.set_xlabel('Node Type', fontsize=12)
            ax3.set_ylabel('Feature Mean ± Std', fontsize=12)
            ax3.set_title('Node Feature Statistics', fontsize=14)
        else:
            ax3.text(0.5, 0.5, 'No feature statistics available', ha='center', va='center')
        
        # 4. Dataset Summary Table
        ax4 = axes[1, 1]
        ax4.axis('off')
        
        summary_data = [
            ['Total Nodes', f'{dataset_info.total_nodes:,}'],
            ['Total Edges', f'{dataset_info.total_edges:,}'],
            ['Node Types', str(len(dataset_info.node_type_counts))],
            ['Edge Types', str(len(dataset_info.edge_type_counts))],
            ['Graph Density', f'{dataset_info.graph_density:.6f}'],
            ['Average Degree', f'{dataset_info.avg_degree:.2f}'],
        ]
        
        table = ax4.table(
            cellText=summary_data,
            colLabels=['Metric', 'Value'],
            loc='center',
            cellLoc='left',
            colWidths=[0.5, 0.5],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.2, 1.5)
        
        for i in range(2):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(color='white', fontweight='bold')
        
        ax4.set_title('Dataset Summary', fontsize=14, pad=20)
        
        plt.tight_layout()
        
        if save:
            filepath = self.output_dir / f"{self.report.report_id}_dataset.png"
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
            print(f"📊 Saved dataset analysis: {filepath}")
        
        self.figures['dataset'] = fig
        return fig
    
    def plot_evaluation_results(self, save: bool = True) -> Optional[plt.Figure]:
        """Visualize evaluation metrics"""
        if not HAS_MATPLOTLIB or self.report is None or self.report.evaluation_metrics is None:
            return None
        
        eval_metrics = self.report.evaluation_metrics
        
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle(f'{eval_metrics.task_name} Evaluation Results', fontsize=16, fontweight='bold')
        
        # 1. Metrics Bar Chart
        ax1 = axes[0]
        metrics = eval_metrics.all_metrics
        names = list(metrics.keys())
        values = list(metrics.values())
        colors = plt.cm.RdYlGn(np.linspace(0.3, 0.9, len(names)))
        
        bars = ax1.bar(range(len(names)), values, color=colors)
        ax1.set_xticks(range(len(names)))
        ax1.set_xticklabels(names, rotation=45, ha='right')
        ax1.set_ylabel('Value', fontsize=12)
        ax1.set_title('Evaluation Metrics', fontsize=14)
        
        for bar, val in zip(bars, values):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01, 
                    f'{val:.4f}', ha='center', va='bottom', fontsize=10)
        
        # 2. Metrics Table
        ax2 = axes[1]
        ax2.axis('off')
        
        table_data = [[name, f'{value:.6f}'] for name, value in metrics.items()]
        
        table = ax2.table(
            cellText=table_data,
            colLabels=['Metric', 'Value'],
            loc='center',
            cellLoc='left',
            colWidths=[0.6, 0.4],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1.2, 1.5)
        
        for i in range(2):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(color='white', fontweight='bold')
        
        # Highlight primary metric
        primary_idx = names.index(eval_metrics.primary_metric) + 1
        table[(primary_idx, 0)].set_facecolor('#90EE90')
        table[(primary_idx, 1)].set_facecolor('#90EE90')
        
        ax2.set_title('Detailed Metrics', fontsize=14, pad=20)
        
        plt.tight_layout()
        
        if save:
            filepath = self.output_dir / f"{self.report.report_id}_evaluation.png"
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
            print(f"📊 Saved evaluation results: {filepath}")
        
        self.figures['evaluation'] = fig
        return fig
    
    def generate_all_plots(self, save: bool = True) -> Dict[str, plt.Figure]:
        """Generate all visualization plots"""
        self.plot_training_curves(save)
        self.plot_model_architecture(save)
        self.plot_dataset_analysis(save)
        self.plot_evaluation_results(save)
        return self.figures
    
    def export_json(self) -> str:
        """Export report as JSON"""
        if self.report is None:
            return "{}"
        
        # Convert dataclasses to dict
        report_dict = {
            'report_id': self.report.report_id,
            'timestamp': self.report.timestamp,
            'model_info': asdict(self.report.model_info),
            'dataset_info': asdict(self.report.dataset_info),
            'training_config': self.report.training_config,
            'training_metrics': asdict(self.report.training_metrics),
            'training_history': {
                'train_losses': self.report.training_history.train_losses,
                'val_losses': self.report.training_history.val_losses,
                'learning_rates': self.report.training_history.learning_rates,
            },
            'hyperparameters': self.report.hyperparameters,
            'hardware_info': self.report.hardware_info,
            'notes': self.report.notes,
        }
        
        if self.report.evaluation_metrics:
            report_dict['evaluation_metrics'] = asdict(self.report.evaluation_metrics)
        
        filepath = self.output_dir / f"{self.report.report_id}.json"
        with open(filepath, 'w') as f:
            json.dump(report_dict, f, indent=2, default=str)
        
        print(f"📄 Saved JSON report: {filepath}")
        return str(filepath)
    
    def generate_markdown_report(self) -> str:
        """Generate comprehensive markdown report"""
        if self.report is None:
            return ""
        
        r = self.report
        
        md = f"""# GNN Training Report: {r.model_info.model_name}

**Report ID:** {r.report_id}  
**Generated:** {r.timestamp}

---

## Executive Summary

This report documents the training and evaluation of the **{r.model_info.model_name}** Graph Neural Network model on the **{r.dataset_info.dataset_name}** dataset. The model achieved a **best loss of {r.training_metrics.best_loss:.6f}** after **{r.training_metrics.total_epochs} epochs** of training.

### Key Highlights

| Metric | Value |
|--------|-------|
| Model Type | {r.model_info.model_type} |
| Total Parameters | {r.model_info.total_parameters:,} |
| Training Epochs | {r.training_metrics.total_epochs} |
| Best Loss | {r.training_metrics.best_loss:.6f} |
| Loss Improvement | {r.training_metrics.loss_improvement_percent:.2f}% |
| Early Stopped | {'Yes (Epoch ' + str(r.training_metrics.early_stop_epoch) + ')' if r.training_metrics.early_stopped else 'No'} |

---

## 1. Model Architecture

### 1.1 Overview

The **{r.model_info.model_type}** is a heterogeneous Graph Neural Network designed to process graphs with multiple node and edge types. It uses a custom message passing mechanism with scatter-add aggregation to propagate information across the graph structure.

### 1.2 Architecture Details

| Property | Value |
|----------|-------|
| Model Name | {r.model_info.model_name} |
| Model Type | {r.model_info.model_type} |
| Hidden Channels | {r.model_info.hidden_channels} |
| Output Channels | {r.model_info.output_channels} |
| Number of Layers | {r.model_info.num_layers} |
| Activation Function | {r.model_info.activation_function} |
| Normalization | {r.model_info.normalization} |
| Aggregation Method | {r.model_info.aggregation_method} |

### 1.3 Parameters

| Parameter Type | Count |
|----------------|-------|
| **Total Parameters** | {r.model_info.total_parameters:,} |
| Trainable Parameters | {r.model_info.trainable_parameters:,} |
| Non-trainable Parameters | {r.model_info.non_trainable_parameters:,} |

### 1.4 Input Dimensions per Node Type

| Node Type | Input Dimension |
|-----------|-----------------|
"""
        for nt, dim in r.model_info.input_dimensions.items():
            md += f"| {nt} | {dim} |\n"
        
        md += f"""
### 1.5 Supported Node Types ({len(r.model_info.node_types)})

"""
        for nt in r.model_info.node_types:
            md += f"- `{nt}`\n"
        
        md += f"""
### 1.6 Supported Edge Types ({len(r.model_info.edge_types)})

"""
        for et in r.model_info.edge_types[:15]:  # Limit to 15
            md += f"- `{et}`\n"
        if len(r.model_info.edge_types) > 15:
            md += f"- ... and {len(r.model_info.edge_types) - 15} more\n"
        
        md += f"""
### 1.7 Layer Details

| Layer Name | Type | Parameters |
|------------|------|------------|
"""
        for layer in r.model_info.layer_details[:20]:  # Limit to 20
            md += f"| {layer['name']} | {layer['type']} | {layer['parameters']:,} |\n"
        
        md += f"""

---

## 2. Dataset Analysis

### 2.1 Overview

| Metric | Value |
|--------|-------|
| Dataset Name | {r.dataset_info.dataset_name} |
| Total Nodes | {r.dataset_info.total_nodes:,} |
| Total Edges | {r.dataset_info.total_edges:,} |
| Node Types | {len(r.dataset_info.node_type_counts)} |
| Edge Types | {len(r.dataset_info.edge_type_counts)} |
| Graph Density | {r.dataset_info.graph_density:.6f} |
| Average Degree | {r.dataset_info.avg_degree:.2f} |

### 2.2 Node Type Distribution

| Node Type | Count | Percentage |
|-----------|-------|------------|
"""
        for nt, count in sorted(r.dataset_info.node_type_counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / r.dataset_info.total_nodes * 100
            md += f"| {nt} | {count:,} | {pct:.2f}% |\n"
        
        md += f"""
### 2.3 Edge Type Distribution

| Edge Type | Count | Percentage |
|-----------|-------|------------|
"""
        sorted_edges = sorted(r.dataset_info.edge_type_counts.items(), key=lambda x: x[1], reverse=True)
        for et, count in sorted_edges[:15]:
            pct = count / r.dataset_info.total_edges * 100
            # Extract just the relationship name
            rel_name = et.split("'")[3] if "'" in et else et
            md += f"| {rel_name} | {count:,} | {pct:.2f}% |\n"
        
        md += f"""
### 2.4 Feature Dimensions

| Node Type | Feature Dimension |
|-----------|-------------------|
"""
        for nt, dim in r.dataset_info.feature_dimensions.items():
            md += f"| {nt} | {dim} |\n"
        
        if r.dataset_info.node_features_summary:
            md += f"""
### 2.5 Feature Statistics

| Node Type | Mean | Std | Min | Max | Sparsity |
|-----------|------|-----|-----|-----|----------|
"""
            for nt, stats in r.dataset_info.node_features_summary.items():
                md += f"| {nt} | {stats['mean']:.4f} | {stats['std']:.4f} | {stats['min']:.4f} | {stats['max']:.4f} | {stats['sparsity']:.2%} |\n"
        
        md += f"""

---

## 3. Training Configuration

### 3.1 Hyperparameters

| Parameter | Value |
|-----------|-------|
| Epochs | {r.training_config.get('epochs', 'N/A')} |
| Learning Rate | {r.training_metrics.learning_rate_initial} |
| Weight Decay | {r.training_metrics.weight_decay} |
| Optimizer | {r.training_metrics.optimizer} |
| Batch Size | {r.training_config.get('batch_size', 'Full batch')} |
| Early Stopping Patience | {r.training_config.get('patience', 10)} |

### 3.2 Hardware Information

| Property | Value |
|----------|-------|
"""
        for key, value in r.hardware_info.items():
            md += f"| {key.replace('_', ' ').title()} | {value} |\n"
        
        md += f"""

---

## 4. Training Results

### 4.1 Training Metrics

| Metric | Value |
|--------|-------|
| Total Epochs Trained | {r.training_metrics.total_epochs} |
| Best Epoch | {r.training_metrics.best_epoch} |
| Initial Loss | {r.training_metrics.initial_loss:.6f} |
| Final Loss | {r.training_metrics.final_loss:.6f} |
| **Best Loss** | **{r.training_metrics.best_loss:.6f}** |
| Loss Improvement | {r.training_metrics.loss_improvement:.6f} |
| Improvement Percentage | {r.training_metrics.loss_improvement_percent:.2f}% |
| Learning Rate (final) | {r.training_metrics.learning_rate_final:.6f} |
| Early Stopped | {'Yes' if r.training_metrics.early_stopped else 'No'} |
| Convergence Epoch | {r.training_metrics.convergence_epoch or 'N/A'} |

### 4.2 Loss Progression (Sample)

| Epoch | Loss | Learning Rate |
|-------|------|---------------|
"""
        # Sample every N epochs
        total = len(r.training_history.train_losses)
        step = max(1, total // 10)
        for i in range(0, total, step):
            loss = r.training_history.train_losses[i]
            lr = r.training_history.learning_rates[i] if r.training_history.learning_rates else 'N/A'
            md += f"| {i+1} | {loss:.6f} | {lr if isinstance(lr, str) else f'{lr:.6f}'} |\n"
        
        # Always include last epoch
        if total > 1 and (total - 1) % step != 0:
            loss = r.training_history.train_losses[-1]
            lr = r.training_history.learning_rates[-1] if r.training_history.learning_rates else 'N/A'
            md += f"| {total} | {loss:.6f} | {lr if isinstance(lr, str) else f'{lr:.6f}'} |\n"
        
        md += """
### 4.3 Training Visualization

![Training Curves](""" + f"{r.report_id}_training_curves.png" + """)

---

## 5. Evaluation Results

"""
        if r.evaluation_metrics:
            md += f"""### 5.1 Task: {r.evaluation_metrics.task_name}

**Primary Metric:** {r.evaluation_metrics.primary_metric} = **{r.evaluation_metrics.primary_value:.6f}**

### 5.2 All Metrics

| Metric | Value |
|--------|-------|
"""
            for name, value in r.evaluation_metrics.all_metrics.items():
                md += f"| {name} | {value:.6f} |\n"
            
            md += """
### 5.3 Evaluation Visualization

![Evaluation Results](""" + f"{r.report_id}_evaluation.png" + """)
"""
        else:
            md += "*No evaluation metrics available.*\n"
        
        md += f"""

---

## 6. Visualizations

### 6.1 Model Architecture Analysis

![Model Architecture](""" + f"{r.report_id}_architecture.png" + """)

### 6.2 Dataset Analysis

![Dataset Analysis](""" + f"{r.report_id}_dataset.png" + """)

---

## 7. Conclusions and Observations

### 7.1 Training Performance

"""
        # Auto-generate observations
        if r.training_metrics.loss_improvement_percent > 90:
            md += "- ✅ **Excellent convergence**: The model achieved >90% loss improvement from initial to best loss.\n"
        elif r.training_metrics.loss_improvement_percent > 50:
            md += "- ✅ **Good convergence**: The model achieved significant loss improvement during training.\n"
        else:
            md += "- ⚠️ **Limited convergence**: The model may benefit from longer training or hyperparameter tuning.\n"
        
        if r.training_metrics.early_stopped:
            md += f"- ℹ️ **Early stopping triggered** at epoch {r.training_metrics.early_stop_epoch}, indicating convergence.\n"
        
        if r.training_metrics.convergence_epoch:
            md += f"- 📈 **Convergence detected** around epoch {r.training_metrics.convergence_epoch}.\n"
        
        md += f"""
### 7.2 Model Characteristics

- The model has **{r.model_info.total_parameters:,} parameters**, making it {'lightweight' if r.model_info.total_parameters < 100000 else 'moderately sized' if r.model_info.total_parameters < 1000000 else 'large'}.
- Processes **{len(r.model_info.node_types)} node types** and **{len(r.model_info.edge_types)} edge types**.
- Uses **{r.model_info.num_layers} message passing layers** with {r.model_info.hidden_channels} hidden channels.

### 7.3 Dataset Characteristics

- The dataset is **{'sparse' if r.dataset_info.graph_density < 0.001 else 'moderately connected' if r.dataset_info.graph_density < 0.01 else 'dense'}** with density {r.dataset_info.graph_density:.6f}.
- Average node degree is **{r.dataset_info.avg_degree:.2f}**.

---

## 8. Technical Details

### 8.1 GNN Architecture Explanation

The heterogeneous GNN uses the following key components:

1. **Input Projection Layers**: Linear transformations that project each node type's features to a common hidden dimension ({r.model_info.hidden_channels}).

2. **Message Passing Layers**: Custom implementation using scatter-add aggregation:
   - For each edge type $(s, r, t)$, messages are computed as: $m_{{r,t}} = W_r \\cdot h_s$
   - Messages are aggregated: $h'_t = \\sum_{{r \\in R}} \\text{{scatter\\_add}}(m_{{r,t}})$
   - Self-loops ensure all nodes receive updates: $h'_t = h'_t + W_{{self}} \\cdot h_t$

3. **Layer Normalization**: Applied after each message passing layer for training stability.

4. **Task-Specific Decoders**: Output heads for rating prediction and embedding generation.

### 8.2 Loss Function

- **Rating Prediction**: Mean Squared Error (MSE) loss
- **Route Optimization**: Margin Ranking Loss with margin=1.0

### 8.3 Optimization

- **Optimizer**: {r.training_metrics.optimizer} with learning rate {r.training_metrics.learning_rate_initial}
- **Weight Decay**: {r.training_metrics.weight_decay}
- **LR Scheduler**: ReduceLROnPlateau (factor=0.5, patience=5)

---

## Appendix

### A. Full Training History

<details>
<summary>Click to expand full training history</summary>

| Epoch | Loss |
|-------|------|
"""
        for i, loss in enumerate(r.training_history.train_losses):
            md += f"| {i+1} | {loss:.6f} |\n"
        
        md += """
</details>

### B. Report Metadata

"""
        md += f"""- **Report ID**: {r.report_id}
- **Generation Timestamp**: {r.timestamp}
- **PyTorch Version**: {r.hardware_info.get('pytorch_version', 'N/A')}
- **Device**: {r.hardware_info.get('device', 'N/A')}
"""
        
        if r.notes:
            md += f"""
### C. Notes

{r.notes}
"""
        
        md += f"""

---

*This report was automatically generated by the GraphCeylon GNN Reporting Module.*
"""
        
        # Save the report
        filepath = self.output_dir / f"{r.report_id}_report.md"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md)
        
        print(f"📝 Saved Markdown report: {filepath}")
        return str(filepath)
    
    def generate_full_report(self) -> Dict[str, str]:
        """Generate all report artifacts"""
        if self.report is None:
            raise ValueError("No report created. Call create_report() first.")
        
        results = {}
        
        # Generate all plots
        print("\n" + "=" * 60)
        print("📊 GENERATING GNN TRAINING REPORT")
        print("=" * 60)
        
        self.generate_all_plots()
        
        # Export JSON
        results['json'] = self.export_json()
        
        # Generate Markdown
        results['markdown'] = self.generate_markdown_report()
        
        # List all generated files
        results['figures'] = [str(self.output_dir / f"{self.report.report_id}_{name}.png") 
                            for name in self.figures.keys()]
        
        print("\n" + "=" * 60)
        print("✅ REPORT GENERATION COMPLETE")
        print("=" * 60)
        print(f"\n📁 Output Directory: {self.output_dir}")
        print(f"\n📄 Generated Files:")
        for key, path in results.items():
            if isinstance(path, list):
                for p in path:
                    print(f"   - {Path(p).name}")
            else:
                print(f"   - {Path(path).name}")
        
        return results


def generate_training_report(
    model: nn.Module,
    data: 'HeteroData',
    history: Dict[str, List[float]],
    config: Dict[str, Any],
    model_name: str = "GNN Model",
    dataset_name: str = "GraphCeylon Dataset",
    evaluation_results: Optional[Dict[str, float]] = None,
    output_dir: str = "reports",
    notes: str = "",
) -> Dict[str, str]:
    """
    Convenience function to generate a complete training report.
    
    Args:
        model: Trained PyTorch model
        data: HeteroData graph
        history: Training history dict with 'train_loss', 'lr', etc.
        config: Training configuration dict
        model_name: Name for the model
        dataset_name: Name for the dataset
        evaluation_results: Optional evaluation metrics dict
        output_dir: Directory to save reports
        notes: Additional notes for the report
    
    Returns:
        Dictionary with paths to generated files
    """
    reporter = GNNReporter(output_dir)
    reporter.create_report(
        model=model,
        data=data,
        history=history,
        config=config,
        model_name=model_name,
        dataset_name=dataset_name,
        evaluation_results=evaluation_results,
        notes=notes,
    )
    return reporter.generate_full_report()


if __name__ == "__main__":
    print("GraphCeylon GNN Reporting Module")
    print("=" * 50)
    print("\nUsage:")
    print("  from src.gnn.reporting import generate_training_report")
    print("  generate_training_report(model, data, history, config)")

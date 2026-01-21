"""
Visualization Generator for Research Thesis

Creates publication-quality figures for:
1. Graph structure visualization
2. t-SNE embeddings projection
3. Training loss curves
4. Link prediction performance
5. Confidence score distributions
6. Ablation study comparisons
7. Performance benchmarks

All figures saved in high resolution for thesis inclusion.
"""

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
import networkx as nx
from typing import Dict, List, Any, Tuple
import torch
from pathlib import Path
import pandas as pd

# Set publication style
plt.style.use('seaborn-v0_8-paper')
sns.set_context("paper", font_scale=1.5)
sns.set_palette("husl")

# High DPI for thesis quality
DPI = 300


class ThesisVisualizer:
    """Generate all visualizations for research thesis."""
    
    def __init__(self, self.output_dir: str = "thesis_visualizations"):
        self.colors = sns.color_palette("husl", 8)
        self.self.output_dir = Path(self.output_dir)
        self.self.output_dir.mkdir(exist_ok=True)
        
    def plot_graph_structure(
        self,
        edge_index: torch.Tensor,
        node_labels: Dict[int, str],
        node_types: Dict[int, str],
        title: str = "Tourism Knowledge Graph Structure"
    ):
        """
        Visualize the graph structure with colored node types.
        
        Args:
            edge_index: PyTorch Geometric edge index [2, num_edges]
            node_labels: Mapping of node idx to name
            node_types: Mapping of node idx to type (District/Province/Attraction)
        """
        G = nx.Graph()
        
        # Add nodes with attributes
        for idx, label in node_labels.items():
            G.add_node(idx, label=label, type=node_types.get(idx, "Unknown"))
        
        # Add edges
        edges = edge_index.t().numpy()
        G.add_edges_from(edges)
        
        # Layout
        pos = nx.spring_layout(G, k=0.5, iterations=50, seed=42)
        
        # Color by type
        type_colors = {
            "Province": self.colors[0],
            "District": self.colors[1],
            "Attraction": self.colors[2]
        }
        
        node_colors = [type_colors.get(node_types.get(n, "Unknown"), "gray") for n in G.nodes()]
        
        # Plot
        fig, ax = plt.subplots(figsize=(14, 10))
        
        nx.draw_networkx_nodes(
            G, pos, node_color=node_colors, node_size=500, alpha=0.8, ax=ax
        )
        nx.draw_networkx_edges(G, pos, alpha=0.3, width=1.5, ax=ax)
        
        # Labels for major nodes only (to avoid clutter)
        if len(G.nodes()) < 50:
            labels = {n: node_labels.get(n, str(n))[:15] for n in G.nodes()}
            nx.draw_networkx_labels(G, pos, labels, font_size=8, ax=ax)
        
        # Legend
        legend_elements = [
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=type_colors[t], 
                      markersize=10, label=t)
            for t in type_colors.keys()
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
        
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.axis('off')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "graph_structure.png", dpi=DPI, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Graph structure saved: {self.output_dir / 'graph_structure.png'}")
    
    def plot_embeddings_tsne(
        self,
        embeddings: np.ndarray,
        labels: List[str],
        types: List[str],
        title: str = "GNN Embeddings (t-SNE Projection)"
    ):
        """
        Visualize embeddings in 2D using t-SNE.
        
        Args:
            embeddings: Node embeddings [num_nodes, embedding_dim]
            labels: Node names
            types: Node types
        """
        print("Computing t-SNE projection...")
        tsne = TSNE(n_components=2, random_state=42, perplexity=min(30, len(embeddings)-1))
        embeddings_2d = tsne.fit_transform(embeddings)
        
        # Create DataFrame for easier plotting
        df = pd.DataFrame({
            'x': embeddings_2d[:, 0],
            'y': embeddings_2d[:, 1],
            'label': labels,
            'type': types
        })
        
        # Plot
        fig, ax = plt.subplots(figsize=(12, 9))
        
        for node_type in df['type'].unique():
            mask = df['type'] == node_type
            ax.scatter(
                df[mask]['x'], df[mask]['y'],
                label=node_type, s=100, alpha=0.7, edgecolors='w', linewidth=0.5
            )
        
        ax.set_xlabel('t-SNE Component 1', fontsize=14)
        ax.set_ylabel('t-SNE Component 2', fontsize=14)
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.legend(fontsize=12, loc='best')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "embeddings_tsne.png", dpi=DPI, bbox_inches='tight')
        plt.close()
        
        print(f"✓ t-SNE embeddings saved: {self.output_dir / 'embeddings_tsne.png'}")
    
    def plot_training_loss(
        self,
        losses: List[float],
        title: str = "GNN Training Loss Curve"
    ):
        """Plot training loss over epochs."""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        epochs = range(1, len(losses) + 1)
        ax.plot(epochs, losses, linewidth=2.5, color=self.colors[0], marker='o', markersize=4)
        
        # Add trend line
        z = np.polyfit(epochs, losses, 3)
        p = np.poly1d(z)
        ax.plot(epochs, p(epochs), "--", linewidth=2, color=self.colors[1], alpha=0.7, label='Trend')
        
        ax.set_xlabel('Epoch', fontsize=14)
        ax.set_ylabel('Loss', fontsize=14)
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.legend(fontsize=12)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "training_loss.png", dpi=DPI, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Training loss saved: {self.output_dir / 'training_loss.png'}")
    
    def plot_link_prediction_performance(
        self,
        predictions: List[Dict[str, Any]],
        threshold: float = 0.5
    ):
        """
        Plot link prediction results.
        
        Args:
            predictions: List of {exists: bool, confidence: float}
        """
        confidences = [p['confidence'] for p in predictions]
        exists = [p['exists'] for p in predictions]
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # Confidence distribution
        axes[0].hist(confidences, bins=20, alpha=0.7, edgecolor='black', color=self.colors[0])
        axes[0].axvline(threshold, color='red', linestyle='--', linewidth=2, label=f'Threshold ({threshold})')
        axes[0].set_xlabel('Confidence Score', fontsize=12)
        axes[0].set_ylabel('Frequency', fontsize=12)
        axes[0].set_title('Link Prediction Confidence Distribution', fontsize=14, fontweight='bold')
        axes[0].legend(fontsize=10)
        axes[0].grid(True, alpha=0.3, axis='y')
        
        # Binary classification
        predicted_exists = [conf >= threshold for conf in confidences]
        correct = sum([p == e for p, e in zip(predicted_exists, exists)])
        accuracy = correct / len(predictions) if predictions else 0
        
        labels = ['Correct', 'Incorrect']
        sizes = [correct, len(predictions) - correct]
        colors_pie = [self.colors[2], self.colors[3]]
        explode = (0.1, 0)
        
        axes[1].pie(sizes, explode=explode, labels=labels, colors=colors_pie,
                   autopct='%1.1f%%', shadow=True, startangle=90, textprops={'fontsize': 12})
        axes[1].set_title(f'Prediction Accuracy: {accuracy:.1%}', fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "link_prediction_performance.png", dpi=DPI, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Link prediction performance saved: {self.output_dir / 'link_prediction_performance.png'}")
    
    def plot_ablation_study(
        self,
        results: Dict[str, Dict[str, float]]
    ):
        """
        Plot ablation study comparing symbolic, neural, and hybrid approaches.
        
        Args:
            results: {
                'Symbolic': {'accuracy': 0.85, 'precision': 0.82, 'recall': 0.88, 'f1': 0.85},
                'Neural': {...},
                'Hybrid': {...}
            }
        """
        methods = list(results.keys())
        metrics = list(results[methods[0]].keys())
        
        # Prepare data
        data = {metric: [results[method][metric] for method in methods] for metric in metrics}
        
        x = np.arange(len(methods))
        width = 0.2
        
        fig, ax = plt.subplots(figsize=(12, 7))
        
        for i, metric in enumerate(metrics):
            offset = width * (i - len(metrics) / 2 + 0.5)
            ax.bar(x + offset, data[metric], width, label=metric.capitalize(), color=self.colors[i])
        
        ax.set_xlabel('Method', fontsize=14, fontweight='bold')
        ax.set_ylabel('Score', fontsize=14, fontweight='bold')
        ax.set_title('Ablation Study: Symbolic vs Neural vs Hybrid', fontsize=16, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(methods, fontsize=12)
        ax.legend(fontsize=11, loc='lower right')
        ax.set_ylim(0, 1.1)
        ax.grid(True, alpha=0.3, axis='y')
        
        # Add value labels on bars
        for i, metric in enumerate(metrics):
            offset = width * (i - len(metrics) / 2 + 0.5)
            for j, v in enumerate(data[metric]):
                ax.text(j + offset, v + 0.02, f'{v:.2f}', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "ablation_study.png", dpi=DPI, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Ablation study saved: {self.output_dir / 'ablation_study.png'}")
    
    def plot_gpu_benchmark(
        self,
        cpu_time: float,
        gpu_time: float,
        dataset_sizes: List[int],
        cpu_times: List[float],
        gpu_times: List[float]
    ):
        """
        Plot GPU vs CPU performance benchmark.
        
        Args:
            cpu_time: Single training time on CPU
            gpu_time: Single training time on GPU
            dataset_sizes: List of dataset sizes tested
            cpu_times: Training times on CPU for each size
            gpu_times: Training times on GPU for each size
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # Single comparison
        methods = ['CPU', 'GPU']
        times = [cpu_time, gpu_time]
        speedup = cpu_time / gpu_time if gpu_time > 0 else 1.0
        
        bars = axes[0].bar(methods, times, color=[self.colors[4], self.colors[5]], alpha=0.8, edgecolor='black')
        axes[0].set_ylabel('Training Time (seconds)', fontsize=12)
        axes[0].set_title(f'GPU Speedup: {speedup:.1f}x', fontsize=14, fontweight='bold')
        axes[0].grid(True, alpha=0.3, axis='y')
        
        # Add values on bars
        for bar, time in zip(bars, times):
            height = bar.get_height()
            axes[0].text(bar.get_x() + bar.get_width()/2., height,
                        f'{time:.2f}s', ha='center', va='bottom', fontsize=11)
        
        # Scalability
        axes[1].plot(dataset_sizes, cpu_times, marker='o', linewidth=2.5, 
                    markersize=8, label='CPU', color=self.colors[4])
        axes[1].plot(dataset_sizes, gpu_times, marker='s', linewidth=2.5, 
                    markersize=8, label='GPU', color=self.colors[5])
        
        axes[1].set_xlabel('Dataset Size (nodes)', fontsize=12)
        axes[1].set_ylabel('Training Time (seconds)', fontsize=12)
        axes[1].set_title('Scalability: CPU vs GPU', fontsize=14, fontweight='bold')
        axes[1].legend(fontsize=11)
        axes[1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "gpu_benchmark.png", dpi=DPI, bbox_inches='tight')
        plt.close()
        
        print(f"✓ GPU benchmark saved: {self.output_dir / 'gpu_benchmark.png'}")
    
    def plot_confidence_comparison(
        self,
        symbolic_confidences: List[float],
        neural_confidences: List[float],
        hybrid_confidences: List[float]
    ):
        """Compare confidence scores across reasoning methods."""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        data = [symbolic_confidences, neural_confidences, hybrid_confidences]
        labels = ['Symbolic', 'Neural', 'Hybrid']
        
        bp = ax.boxplot(data, labels=labels, patch_artist=True, widths=0.6)
        
        # Color boxes
        for patch, color in zip(bp['boxes'], self.colors[:3]):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        ax.set_ylabel('Confidence Score', fontsize=14)
        ax.set_title('Confidence Score Distribution by Method', fontsize=16, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        ax.set_ylim(0, 1.05)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "confidence_comparison.png", dpi=DPI, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Confidence comparison saved: {self.output_dir / 'confidence_comparison.png'}")
    
    def generate_summary_table(
        self,
        metrics: Dict[str, Any]
    ):
        """Generate a summary table of key metrics."""
        df = pd.DataFrame([metrics]).T
        df.columns = ['Value']
        
        fig, ax = plt.subplots(figsize=(8, len(metrics) * 0.5))
        ax.axis('tight')
        ax.axis('off')
        
        table = ax.table(cellText=df.values, rowLabels=df.index,
                        colLabels=df.columns, cellLoc='left', loc='center',
                        colWidths=[0.7, 0.3])
        
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1, 2)
        
        # Style header
        for (i, j), cell in table.get_celld().items():
            if i == 0:
                cell.set_facecolor(self.colors[0])
                cell.set_text_props(weight='bold', color='white')
            elif j == -1:
                cell.set_facecolor(self.colors[1])
                cell.set_text_props(weight='bold', color='white')
        
        plt.title('Performance Summary', fontsize=16, fontweight='bold', pad=20)
        plt.tight_layout()
        plt.savefig(self.output_dir / "summary_table.png", dpi=DPI, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Summary table saved: {self.output_dir / 'summary_table.png'}")


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("📊 THESIS VISUALIZATION GENERATOR")
    print("=" * 70)
    print("\nGenerating publication-quality figures for research thesis...\n")
    
    visualizer = ThesisVisualizer()
    
    # Example: Training loss
    example_losses = [1.5, 1.4, 1.35, 1.3, 1.25, 1.2, 1.18, 1.15, 1.13, 1.11]
    visualizer.plot_training_loss(example_losses)
    
    # Example: Ablation study
    example_ablation = {
        'Symbolic': {'accuracy': 0.78, 'precision': 0.75, 'recall': 0.82, 'f1': 0.78},
        'Neural': {'accuracy': 0.82, 'precision': 0.80, 'recall': 0.85, 'f1': 0.82},
        'Hybrid': {'accuracy': 0.89, 'precision': 0.87, 'recall': 0.92, 'f1': 0.89}
    }
    visualizer.plot_ablation_study(example_ablation)
    
    # Example: GPU benchmark
    visualizer.plot_gpu_benchmark(
        cpu_time=5.2,
        gpu_time=0.8,
        dataset_sizes=[100, 500, 1000, 5000],
        cpu_times=[0.5, 2.1, 5.2, 28.5],
        gpu_times=[0.1, 0.3, 0.8, 4.2]
    )
    
    # Example: Summary metrics
    example_metrics = {
        'Graph Nodes': 73,
        'Graph Edges': 126,
        'Embedding Dim': 32,
        'Training Epochs': 100,
        'Final Loss': 1.15,
        'Link Prediction Accuracy': '89.2%',
        'GPU Speedup': '6.5x',
        'Hybrid Confidence': 0.87
    }
    visualizer.generate_summary_table(example_metrics)
    
    print("\n" + "=" * 70)
    print("✅ ALL VISUALIZATIONS GENERATED SUCCESSFULLY!")
    print(f"📁 Output directory: {self.output_dir.absolute()}")
    print("=" * 70)
    print("\n💡 Use these figures in your thesis/research paper!")


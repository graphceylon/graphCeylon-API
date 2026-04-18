"""Quick diagnostic script for hotel embedding quality"""
import torch
import sys
sys.path.insert(0, "src")
from gnn.models import HotelRecommenderGNN, ModelConfig
from gnn.export_graph import GraphExporter
import torch.nn.functional as F

data, mappings, _, names = GraphExporter.load("data/gnn/graphceylon_hotels.pt")
metadata = (list(data.node_types), list(data.edge_types))
in_ch = {nt: data[nt].x.shape[1] if hasattr(data[nt], "x") else 1 for nt in data.node_types}
config = ModelConfig(hidden_channels=64, out_channels=32, num_layers=2)
model = HotelRecommenderGNN(metadata, in_ch, config)
cp = torch.load("checkpoints/hotel_recommender_best.pt", weights_only=False)
model.load_state_dict(cp["model_state_dict"])
model.eval()
print(f"Loaded from epoch {cp['epoch']}")

with torch.no_grad():
    emb = model.encode(data)
    h = emb["Hotel"]
    h_norm = F.normalize(h, dim=1)
    sim = torch.mm(h_norm, h_norm.t())
    n = sim.shape[0]
    mask = ~torch.eye(n, dtype=bool)
    print(f"Hotels: {n}")
    print(f"Avg cross-sim: {sim[mask].mean():.4f}")
    print(f"Min cross-sim: {sim[mask].min():.4f}")
    print(f"Max cross-sim: {sim[mask].max():.4f}")
    print(f"Std cross-sim: {sim[mask].std():.4f}")

    # Check specific hotels
    hotel_map = mappings.get("Hotel", None)
    if hotel_map:
        nm = hotel_map.neo4j_to_idx
        idx1 = nm.get("hotel_cinnamon_lakeside_colombo")
        idx2 = nm.get("hotel_granbell_hotel_colombo")
        idx3 = nm.get("hotel_mystique_hideout")
        if idx1 is not None and idx2 is not None:
            print(f"\nCinnamon vs Granbell (same city): {sim[idx1, idx2]:.6f}")
        if idx1 is not None and idx3 is not None:
            print(f"Cinnamon vs Mystique (diff area): {sim[idx1, idx3]:.6f}")
        if idx1 is not None:
            print(f"\nCinnamon raw emb[:8]: {h[idx1, :8].tolist()}")
        if idx2 is not None:
            print(f"Granbell raw emb[:8]: {h[idx2, :8].tolist()}")
        if idx3 is not None:
            print(f"Mystique raw emb[:8]: {h[idx3, :8].tolist()}")

    # Distribution analysis
    vals = sim[mask].flatten()
    print("\n--- Similarity Distribution ---")
    for thresh in [0.999, 0.99, 0.95, 0.90, 0.80, 0.50, 0.0]:
        pct = (vals >= thresh).float().mean() * 100
        print(f"  Pairs with sim >= {thresh}: {pct:.1f}%")

    # Per-dimension variance
    print(f"\n--- Embedding Stats ---")
    print(f"Mean norm (raw): {h.norm(dim=1).mean():.4f}")
    print(f"Std norm (raw):  {h.norm(dim=1).std():.4f}")
    per_dim_std = h.std(dim=0)
    print(f"Per-dim std min: {per_dim_std.min():.6f}")
    print(f"Per-dim std max: {per_dim_std.max():.6f}")
    print(f"Per-dim std mean: {per_dim_std.mean():.6f}")
    print(f"Dims with std < 0.01: {(per_dim_std < 0.01).sum().item()}/{h.shape[1]}")

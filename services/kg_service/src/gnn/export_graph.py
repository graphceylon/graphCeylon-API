"""
GraphCeylon - Neo4j to PyTorch Geometric Export Module

Exports the knowledge graph from Neo4j to PyTorch Geometric HeteroData format
for training Graph Neural Networks.

Usage:
    from gnn.export_graph import GraphExporter
    
    exporter = GraphExporter()
    data = exporter.export()
    exporter.save(data, "graph_data.pt")
"""

import torch
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from neo4j import GraphDatabase
import json
from datetime import datetime


@dataclass
class NodeMapping:
    """Maps Neo4j node IDs to sequential tensor indices"""
    neo4j_to_idx: Dict[str, int]
    idx_to_neo4j: Dict[int, str]
    
    @classmethod
    def from_ids(cls, ids: List[str]) -> 'NodeMapping':
        neo4j_to_idx = {id_: idx for idx, id_ in enumerate(ids)}
        idx_to_neo4j = {idx: id_ for id_, idx in neo4j_to_idx.items()}
        return cls(neo4j_to_idx, idx_to_neo4j)


class GraphExporter:
    """
    Exports Neo4j graph to PyTorch Geometric HeteroData format.
    
    Supports heterogeneous graphs with multiple node and edge types.
    """
    
    def __init__(
        self,
        uri: str = "bolt://127.0.0.1:7687",
        user: str = "neo4j",
        password: str = "password"
    ):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.node_mappings: Dict[str, NodeMapping] = {}
        
        # Feature configuration for each node type
        self.node_feature_config = {
            'Hotel': {
                'numerical': ['rating', 'reviews_count', 'latitude', 'longitude', 'distance_to_attraction_km'],
                'categorical': ['price_tier', 'proximity_level'],
                'binary': ['eco_certified'],
            },
            'RailwayStation': {
                'numerical': ['latitude', 'longitude', 'google_rating', 'google_ratings_total'],
                'categorical': ['province', 'district'],
                'binary': ['is_major_station', 'enriched'],
            },
            'TrainSchedule': {
                'numerical': ['distance_km', 'duration_minutes'],
                'categorical': ['train_type'],
                'binary': [],
            },
            'PointOfInterest': {
                'numerical': ['latitude', 'longitude', 'rating', 'reviews'],
                'categorical': ['category'],
                'binary': [],
            },
            'Attraction': {
                'numerical': ['latitude', 'longitude'],
                'categorical': ['province', 'district'],
                'binary': [],
            },
            'Amenity': {
                'numerical': [],
                'categorical': ['category'],
                'binary': [],
            },
            'District': {
                'numerical': [],
                'categorical': ['provinceCode'],
                'binary': [],
            },
            'Province': {
                'numerical': ['districtCount'],
                'categorical': [],
                'binary': [],
            },
            'Domain': {
                'numerical': ['order'],
                'categorical': [],
                'binary': [],
            },
            'Holiday': {
                'numerical': ['duration_days', 'day', 'month', 'year'],
                'categorical': ['holiday_type', 'category'],
                'binary': ['isPublicHoliday'],
            },
        }
        
        # Edge types to export
        self.edge_types = [
            ('Hotel', 'OFFERS_AMENITY', 'Amenity'),
            ('Hotel', 'NEARBY_POI', 'PointOfInterest'),
            ('Hotel', 'ACCESSIBLE_VIA', 'PointOfInterest'),
            ('Hotel', 'NEAR_ATTRACTION', 'Attraction'),
            ('Hotel', 'LOCATED_IN_DISTRICT', 'District'),
            ('Hotel', 'LOCATED_IN_PROVINCE', 'Province'),
            ('Hotel', 'BELONGS_TO_DOMAIN', 'Domain'),
            ('TrainSchedule', 'DEPARTS_FROM', 'RailwayStation'),
            ('TrainSchedule', 'ARRIVES_AT', 'RailwayStation'),
            ('TrainSchedule', 'BELONGS_TO_DOMAIN', 'Domain'),
            ('RailwayStation', 'CONNECTED_BY_TRAIN', 'RailwayStation'),
            ('RailwayStation', 'LOCATED_IN_DISTRICT', 'District'),
            ('RailwayStation', 'BELONGS_TO_DOMAIN', 'Domain'),
            ('Attraction', 'LOCATED_IN', 'District'),
            ('Attraction', 'IN_PROVINCE', 'Province'),
            ('Attraction', 'BEST_SEASON', 'Month'),
            ('Attraction', 'SIMILAR_TO', 'Attraction'),
            ('District', 'IN_PROVINCE', 'Province'),
            ('District', 'SIMILAR_TO', 'District'),
        ]
        
        # Categorical encodings (populated during export)
        self.categorical_encodings: Dict[str, Dict[str, int]] = {}
    
    def close(self):
        """Close the Neo4j driver connection"""
        self.driver.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _get_categorical_encoding(self, field: str, value: Any) -> int:
        """Get or create one-hot encoding index for categorical value"""
        if field not in self.categorical_encodings:
            self.categorical_encodings[field] = {}
        
        value_str = str(value) if value is not None else "UNKNOWN"
        
        if value_str not in self.categorical_encodings[field]:
            self.categorical_encodings[field][value_str] = len(self.categorical_encodings[field])
        
        return self.categorical_encodings[field][value_str]
    
    def _normalize(self, values: List[float], method: str = 'minmax') -> torch.Tensor:
        """Normalize numerical values"""
        arr = np.array(values, dtype=np.float32)
        
        # Handle NaN values
        nan_mask = np.isnan(arr)
        if nan_mask.any():
            arr[nan_mask] = np.nanmean(arr)  # Impute with mean
        
        if method == 'minmax':
            min_val, max_val = arr.min(), arr.max()
            if max_val - min_val > 0:
                arr = (arr - min_val) / (max_val - min_val)
            else:
                arr = np.zeros_like(arr)
        elif method == 'zscore':
            mean, std = arr.mean(), arr.std()
            if std > 0:
                arr = (arr - mean) / std
            else:
                arr = np.zeros_like(arr)
        
        return torch.tensor(arr, dtype=torch.float32)
    
    def _parse_duration(self, duration_str: str) -> float:
        """Parse duration string to minutes"""
        if not duration_str:
            return 0.0
        
        try:
            # Handle formats like "2h 45m", "45m", "2h"
            hours, minutes = 0, 0
            if 'h' in duration_str:
                parts = duration_str.split('h')
                hours = int(parts[0].strip())
                if len(parts) > 1 and 'm' in parts[1]:
                    minutes = int(parts[1].replace('m', '').strip())
            elif 'm' in duration_str:
                minutes = int(duration_str.replace('m', '').strip())
            return hours * 60 + minutes
        except:
            return 0.0
    
    def _parse_distance(self, distance_str: str) -> float:
        """Parse distance string to km"""
        if not distance_str:
            return 0.0
        
        try:
            # Handle formats like "120.5 km", "120.5km"
            return float(distance_str.lower().replace('km', '').strip())
        except:
            return 0.0
    
    def export_nodes(self, node_type: str) -> Tuple[torch.Tensor, NodeMapping, Dict]:
        """
        Export nodes of a specific type with their features.
        
        Returns:
            - feature tensor [num_nodes, num_features]
            - node mapping (Neo4j ID <-> tensor index)
            - metadata dict
        """
        with self.driver.session() as session:
            # Get ID field based on node type
            id_field = self._get_id_field(node_type)
            
            # Query all nodes of this type
            result = session.run(f"""
                MATCH (n:{node_type})
                RETURN n, {id_field} as node_id
            """)
            
            records = list(result)
            
            if not records:
                return torch.zeros((0, 1)), NodeMapping.from_ids([]), {}
            
            # Extract node IDs and create mapping
            node_ids = [str(r['node_id']) for r in records]
            mapping = NodeMapping.from_ids(node_ids)
            self.node_mappings[node_type] = mapping
            
            # Extract features
            config = self.node_feature_config.get(node_type, {
                'numerical': [],
                'categorical': [],
                'binary': []
            })
            
            features = []
            
            for record in records:
                node = record['n']
                node_features = []
                
                # Numerical features
                for field in config.get('numerical', []):
                    value = node.get(field)
                    if field == 'duration':
                        value = self._parse_duration(value)
                    elif field == 'distance':
                        value = self._parse_distance(value)
                    node_features.append(float(value) if value is not None else 0.0)
                
                # Categorical features (as indices for later embedding)
                for field in config.get('categorical', []):
                    value = node.get(field)
                    idx = self._get_categorical_encoding(f"{node_type}_{field}", value)
                    node_features.append(float(idx))
                
                # Binary features
                for field in config.get('binary', []):
                    value = node.get(field)
                    node_features.append(1.0 if value else 0.0)
                
                features.append(node_features)
            
            # Convert to tensor
            if features and features[0]:
                feature_tensor = torch.tensor(features, dtype=torch.float32)
            else:
                feature_tensor = torch.zeros((len(records), 1), dtype=torch.float32)
            
            # Normalize numerical features
            num_numerical = len(config.get('numerical', []))
            if num_numerical > 0:
                feature_tensor[:, :num_numerical] = self._normalize(
                    feature_tensor[:, :num_numerical].numpy().flatten()
                ).reshape(-1, num_numerical)
            
            metadata = {
                'num_nodes': len(records),
                'num_features': feature_tensor.shape[1],
                'feature_names': (
                    config.get('numerical', []) + 
                    config.get('categorical', []) + 
                    config.get('binary', [])
                ),
                'node_ids': node_ids,
            }
            
            return feature_tensor, mapping, metadata
    
    def _get_id_field(self, node_type: str) -> str:
        """Get the ID field for a node type"""
        id_fields = {
            'Hotel': 'n.hotel_id',
            'RailwayStation': 'n.station_id',
            'TrainSchedule': 'n.schedule_id',
            'PointOfInterest': 'n.poi_id',
            'Attraction': 'n.title',
            'Amenity': 'n.name',
            'District': 'n.name',
            'Province': 'n.name',
            'Domain': 'n.code',
            'Holiday': 'n.id',
            'Month': 'n.name',
            'Year': 'n.name',
        }
        return id_fields.get(node_type, 'id(n)')
    
    def export_edges(
        self, 
        src_type: str, 
        rel_type: str, 
        dst_type: str
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor], Dict]:
        """
        Export edges of a specific type.
        
        Returns:
            - edge_index tensor [2, num_edges]
            - edge_attr tensor [num_edges, num_features] or None
            - metadata dict
        """
        # Ensure node mappings exist
        if src_type not in self.node_mappings:
            self.export_nodes(src_type)
        if dst_type not in self.node_mappings:
            self.export_nodes(dst_type)
        
        src_mapping = self.node_mappings.get(src_type)
        dst_mapping = self.node_mappings.get(dst_type)
        
        if not src_mapping or not dst_mapping:
            return torch.zeros((2, 0), dtype=torch.long), None, {'num_edges': 0}
        
        src_id_field = self._get_id_field(src_type)
        dst_id_field = self._get_id_field(dst_type).replace('n.', 'b.')
        
        with self.driver.session() as session:
            result = session.run(f"""
                MATCH (n:{src_type})-[r:{rel_type}]->(b:{dst_type})
                RETURN {src_id_field} as src_id, {dst_id_field} as dst_id, properties(r) as rel_props
            """)
            
            records = list(result)
            
            if not records:
                return torch.zeros((2, 0), dtype=torch.long), None, {'num_edges': 0}
            
            src_indices = []
            dst_indices = []
            edge_attrs = []
            
            for record in records:
                src_id = str(record['src_id'])
                dst_id = str(record['dst_id'])
                
                if src_id in src_mapping.neo4j_to_idx and dst_id in dst_mapping.neo4j_to_idx:
                    src_indices.append(src_mapping.neo4j_to_idx[src_id])
                    dst_indices.append(dst_mapping.neo4j_to_idx[dst_id])
                    
                    # Extract edge attributes if any (only numerical)
                    props = record['rel_props']
                    if props:
                        numeric_props = []
                        for v in props.values():
                            if isinstance(v, (int, float)):
                                numeric_props.append(float(v))
                        if numeric_props:
                            edge_attrs.append(numeric_props)
            
            edge_index = torch.tensor([src_indices, dst_indices], dtype=torch.long)
            
            edge_attr = None
            if edge_attrs and all(len(e) == len(edge_attrs[0]) for e in edge_attrs):
                try:
                    edge_attr = torch.tensor(edge_attrs, dtype=torch.float32)
                except (ValueError, TypeError):
                    edge_attr = None  # Skip if conversion fails
            
            metadata = {
                'num_edges': edge_index.shape[1],
                'src_type': src_type,
                'dst_type': dst_type,
                'rel_type': rel_type,
            }
            
            return edge_index, edge_attr, metadata
    
    def export(self) -> 'HeteroData':
        """
        Export the full heterogeneous graph to PyTorch Geometric format.
        
        Returns:
            HeteroData object containing all nodes and edges
        """
        try:
            from torch_geometric.data import HeteroData
        except ImportError:
            raise ImportError(
                "PyTorch Geometric is required. Install with: "
                "pip install torch-geometric"
            )
        
        data = HeteroData()
        export_metadata = {
            'exported_at': datetime.now().isoformat(),
            'nodes': {},
            'edges': {},
        }
        
        # Export node types
        node_types = set()
        for src, rel, dst in self.edge_types:
            node_types.add(src)
            node_types.add(dst)
        
        print("Exporting nodes...")
        for node_type in node_types:
            print(f"  - {node_type}")
            features, mapping, meta = self.export_nodes(node_type)
            
            if features.shape[0] > 0:
                data[node_type].x = features
                data[node_type].num_nodes = features.shape[0]
                export_metadata['nodes'][node_type] = meta
        
        # Export edge types
        print("\nExporting edges...")
        for src_type, rel_type, dst_type in self.edge_types:
            edge_key = (src_type, rel_type, dst_type)
            print(f"  - {src_type} --[{rel_type}]--> {dst_type}")
            
            edge_index, edge_attr, meta = self.export_edges(src_type, rel_type, dst_type)
            
            if edge_index.shape[1] > 0:
                data[edge_key].edge_index = edge_index
                if edge_attr is not None:
                    data[edge_key].edge_attr = edge_attr
                export_metadata['edges'][f"{src_type}_{rel_type}_{dst_type}"] = meta
        
        # Store metadata
        data.metadata = export_metadata
        data.node_mappings = self.node_mappings
        data.categorical_encodings = self.categorical_encodings
        
        print(f"\n✅ Export complete!")
        print(f"   Nodes: {sum(m['num_nodes'] for m in export_metadata['nodes'].values())}")
        print(f"   Edges: {sum(m['num_edges'] for m in export_metadata['edges'].values())}")
        
        return data
    
    def save(self, data: 'HeteroData', path: str):
        """Save HeteroData to disk"""
        torch.save({
            'data': data,
            'node_mappings': {k: (v.neo4j_to_idx, v.idx_to_neo4j) for k, v in self.node_mappings.items()},
            'categorical_encodings': self.categorical_encodings,
        }, path)
        print(f"💾 Saved to {path}")
    
    @staticmethod
    def load(path: str) -> Tuple['HeteroData', Dict, Dict]:
        """Load HeteroData from disk"""
        checkpoint = torch.load(path, weights_only=False)
        data = checkpoint['data']
        node_mappings = {
            k: NodeMapping(v[0], v[1]) 
            for k, v in checkpoint['node_mappings'].items()
        }
        categorical_encodings = checkpoint['categorical_encodings']
        return data, node_mappings, categorical_encodings


class TrainScheduleGraphExporter(GraphExporter):
    """
    Specialized exporter for train schedule subgraph.
    Optimized for route optimization tasks.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Focus on transportation nodes/edges
        self.edge_types = [
            ('TrainSchedule', 'DEPARTS_FROM', 'RailwayStation'),
            ('TrainSchedule', 'ARRIVES_AT', 'RailwayStation'),
            ('RailwayStation', 'CONNECTED_BY_TRAIN', 'RailwayStation'),
            ('RailwayStation', 'LOCATED_IN_DISTRICT', 'District'),
        ]
    
    def export_with_temporal_features(self) -> 'HeteroData':
        """Export with temporal encoding for schedules"""
        data = self.export()
        
        # Add temporal features to schedules
        with self.driver.session() as session:
            result = session.run("""
                MATCH (t:TrainSchedule)
                RETURN t.schedule_id as id, t.departure_time as dep, t.arrival_time as arr
            """)
            
            temporal_features = []
            for record in result:
                dep_hour = self._parse_time_to_hour(record['dep'])
                arr_hour = self._parse_time_to_hour(record['arr'])
                
                # Cyclical encoding for time
                temporal_features.append([
                    np.sin(2 * np.pi * dep_hour / 24),
                    np.cos(2 * np.pi * dep_hour / 24),
                    np.sin(2 * np.pi * arr_hour / 24),
                    np.cos(2 * np.pi * arr_hour / 24),
                ])
            
            if temporal_features:
                temporal_tensor = torch.tensor(temporal_features, dtype=torch.float32)
                if 'TrainSchedule' in data.node_types:
                    data['TrainSchedule'].temporal_x = temporal_tensor
        
        return data
    
    def _parse_time_to_hour(self, time_str: str) -> float:
        """Parse time string to hour (0-24)"""
        if not time_str:
            return 12.0
        
        try:
            # Handle formats like "08:00 AM", "2:30 PM"
            time_str = time_str.upper().strip()
            is_pm = 'PM' in time_str
            time_str = time_str.replace('AM', '').replace('PM', '').strip()
            
            parts = time_str.split(':')
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            
            if is_pm and hour != 12:
                hour += 12
            elif not is_pm and hour == 12:
                hour = 0
            
            return hour + minute / 60
        except:
            return 12.0


class HotelGraphExporter(GraphExporter):
    """
    Specialized exporter for hotel recommendation subgraph.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Focus on hotel-related nodes/edges
        self.edge_types = [
            ('Hotel', 'OFFERS_AMENITY', 'Amenity'),
            ('Hotel', 'NEARBY_POI', 'PointOfInterest'),
            ('Hotel', 'NEAR_ATTRACTION', 'Attraction'),
            ('Hotel', 'LOCATED_IN_DISTRICT', 'District'),
            ('Hotel', 'LOCATED_IN_PROVINCE', 'Province'),
            ('Attraction', 'SIMILAR_TO', 'Attraction'),
            ('District', 'IN_PROVINCE', 'Province'),
        ]


if __name__ == "__main__":
    # Example usage
    print("🚀 GraphCeylon - Exporting to PyTorch Geometric\n")
    
    with GraphExporter() as exporter:
        # Full graph export
        data = exporter.export()
        exporter.save(data, "graphceylon_full.pt")
    
    # Specialized exports
    with TrainScheduleGraphExporter() as exporter:
        train_data = exporter.export_with_temporal_features()
        exporter.save(train_data, "graphceylon_trains.pt")
    
    with HotelGraphExporter() as exporter:
        hotel_data = exporter.export()
        exporter.save(hotel_data, "graphceylon_hotels.pt")
    
    print("\n✅ All exports complete!")

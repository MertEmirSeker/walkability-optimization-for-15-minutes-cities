"""
Pedestrian network graph creation and management.
Builds NetworkX graph from database and separates node sets (N, M, L).
"""
import networkx as nx
import pandas as pd
from typing import Set, Dict, List, Tuple
from sqlalchemy import text
from src.utils.database import get_db_manager


class PedestrianGraph:
    """Manages pedestrian network graph and node sets."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize pedestrian graph."""
        self.db = get_db_manager(config_path)
        self.G = None
        self.N = set()  # Residential locations
        self.M = set()  # Candidate locations
        self.L = {}     # Existing amenities: {amenity_type: set of node_ids}
        self.node_mapping = {}  # Maps database node_id to graph node_id
        
    def load_from_database(self):
        """Load graph structure from database."""
        print("Loading pedestrian network from database...")
        
        with self.db.get_session() as session:
            # Load nodes
            nodes_query = """
                SELECT node_id, osm_id, node_type, latitude, longitude
                FROM nodes
                ORDER BY node_id
            """
            nodes_df = pd.read_sql(text(nodes_query), session.connection())
            
            # Load edges
            edges_query = """
                SELECT e.from_node_id, e.to_node_id, e.length_meters
                FROM edges e
                JOIN nodes n1 ON e.from_node_id = n1.node_id
                JOIN nodes n2 ON e.to_node_id = n2.node_id
            """
            edges_df = pd.read_sql(text(edges_query), session.connection())
            
            # Create NetworkX graph
            self.G = nx.DiGraph()  # Directed graph for pedestrian network
            
            # Add nodes
            for _, row in nodes_df.iterrows():
                node_id = row['node_id']
                self.G.add_node(
                    node_id,
                    osm_id=row['osm_id'],
                    node_type=row['node_type'],
                    latitude=row['latitude'],
                    longitude=row['longitude']
                )
                self.node_mapping[node_id] = node_id
            
            # Add edges
            for _, row in edges_df.iterrows():
                from_id = row['from_node_id']
                to_id = row['to_node_id']
                length = row['length_meters']
                
                if from_id in self.G and to_id in self.G:
                    self.G.add_edge(from_id, to_id, weight=length, length=length)
            
            # Make undirected for bidirectional walking
            self.G = self.G.to_undirected()
            
            print(f"Loaded graph with {len(self.G.nodes)} nodes and {len(self.G.edges)} edges")
        
        # Load node sets for the full graph
        self._load_node_sets()
        
    def _load_node_sets(self):
        """Load residential (N), candidate (M), and existing amenities (L) sets."""
        print("Loading node sets...")
        
        with self.db.get_session() as session:
            # Load residential locations (N)
            residential_query = """
                SELECT node_id FROM residential_locations
            """
            result = session.execute(text(residential_query))
            self.N = {row[0] for row in result}
            # Keep only nodes that exist in the (possibly restricted) graph
            self.N = {n for n in self.N if n in self.G.nodes}
            print(f"Loaded {len(self.N)} residential locations (N)")
            
            # Load candidate locations (M)
            candidate_query = """
                SELECT node_id FROM candidate_locations
            """
            result = session.execute(text(candidate_query))
            self.M = {row[0] for row in result}
            self.M = {m for m in self.M if m in self.G.nodes}
            print(f"Loaded {len(self.M)} candidate locations (M)")
            
            # Load existing amenities (L) by type
            amenities_query = """
                SELECT ea.node_id, at.type_name
                FROM existing_amenities ea
                JOIN amenity_types at ON ea.amenity_type_id = at.amenity_type_id
            """
            result = session.execute(text(amenities_query))
            
            self.L = {}
            for row in result:
                node_id, amenity_type = row
                if node_id not in self.G.nodes:
                    continue
                if amenity_type not in self.L:
                    self.L[amenity_type] = set()
                self.L[amenity_type].add(node_id)
            
            for amenity_type, nodes in self.L.items():
                print(f"Loaded {len(nodes)} existing {amenity_type} amenities")
    
    def get_node_coordinates(self, node_id: int) -> Tuple[float, float]:
        """Get (latitude, longitude) for a node."""
        if node_id in self.G.nodes:
            data = self.G.nodes[node_id]
            return (data['latitude'], data['longitude'])
        return (None, None)
    
    def get_all_amenity_locations(self, amenity_type: str) -> Set[int]:
        """
        Get all EXISTING locations for an amenity type.
        
        NOTE: This should ONLY return existing amenities, NOT candidates!
        Candidates are added separately in compute_weighted_distance via allocated_amenities parameter.
        """
        existing = self.L.get(amenity_type, set())
        return existing.copy()  # Return only existing amenities
    
    def validate_connectivity(self) -> Dict[str, bool]:
        """Validate graph connectivity and node sets."""
        results = {}
        
        if self.G is None:
            return {'graph_loaded': False}
        
        # Check if graph is connected
        is_connected = nx.is_connected(self.G)
        results['is_connected'] = is_connected
        
        # Check if all residential nodes are in graph
        residential_in_graph = all(n in self.G.nodes for n in self.N)
        results['residential_in_graph'] = residential_in_graph
        
        # Check if all candidate nodes are in graph
        candidate_in_graph = all(m in self.G.nodes for m in self.M)
        results['candidate_in_graph'] = candidate_in_graph
        
        # Check if all amenity nodes are in graph
        amenity_in_graph = all(
            node_id in self.G.nodes
            for nodes in self.L.values()
            for node_id in nodes
        )
        results['amenity_in_graph'] = amenity_in_graph
        
        # Check reachability: can residential nodes reach candidates/amenities?
        if is_connected:
            results['all_reachable'] = True
        else:
            # Check largest connected component
            largest_cc = max(nx.connected_components(self.G), key=len)
            residential_in_cc = all(n in largest_cc for n in self.N)
            results['residential_in_largest_cc'] = residential_in_cc
        
        return results
    
    def get_subgraph(self, node_set: Set[int]) -> nx.Graph:
        """Get subgraph containing only specified nodes."""
        return self.G.subgraph(node_set).copy()
    
    def get_statistics(self) -> Dict:
        """Get graph statistics."""
        if self.G is None:
            return {}
        
        stats = {
            'num_nodes': len(self.G.nodes),
            'num_edges': len(self.G.edges),
            'num_residential': len(self.N),
            'num_candidates': len(self.M),
            'num_amenity_types': len(self.L),
            'total_existing_amenities': sum(len(nodes) for nodes in self.L.values()),
            'is_connected': nx.is_connected(self.G),
            'num_connected_components': nx.number_connected_components(self.G)
        }
        
        if len(self.G.edges) > 0:
            edge_lengths = [data['length'] for _, _, data in self.G.edges(data=True)]
            stats['avg_edge_length'] = sum(edge_lengths) / len(edge_lengths)
            stats['min_edge_length'] = min(edge_lengths)
            stats['max_edge_length'] = max(edge_lengths)
        
        return stats
    
    def print_statistics(self):
        """Print graph statistics."""
        stats = self.get_statistics()
        print("\n" + "=" * 60)
        print("Pedestrian Graph Statistics")
        print("=" * 60)
        for key, value in stats.items():
            print(f"{key}: {value}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    graph = PedestrianGraph()
    graph.load_from_database()
    graph.print_statistics()
    
    # Validate connectivity
    validation = graph.validate_connectivity()
    print("Connectivity Validation:")
    for key, value in validation.items():
        print(f"  {key}: {value}")


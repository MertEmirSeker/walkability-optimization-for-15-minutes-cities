"""
Shortest path distance computation using Dijkstra's algorithm.
Computes distances between residential locations (N) and 
candidate/existing locations (M ∪ L).
"""
import networkx as nx
import numpy as np
from typing import Dict, Set, Tuple, List
from sqlalchemy import text
from src.network.pedestrian_graph import PedestrianGraph
from src.utils.database import get_db_manager


class ShortestPathCalculator:
    """Computes and stores shortest path distances."""
    
    def __init__(self, graph: PedestrianGraph):
        """Initialize with pedestrian graph."""
        self.graph = graph
        self.db = graph.db
        self.distance_matrix = {}  # {(i, j): distance}
        self.D_infinity = 2400.0  # Maximum distance (meters) - from paper
        
    def compute_all_distances(self, save_to_db: bool = True):
        """
        Compute shortest path distances for all (i, j) pairs where:
        - i ∈ N (residential locations)
        - j ∈ M ∪ L (candidate + existing locations)
        """
        print("Computing shortest path distances...")
        
        if self.graph.G is None:
            raise ValueError("Graph not loaded. Call graph.load_from_database() first.")
        
        G = self.graph.G
        N = self.graph.N
        M = self.graph.M
        
        # Get all destination nodes (M ∪ L)
        destinations = M.copy()
        for amenity_nodes in self.graph.L.values():
            destinations.update(amenity_nodes)
        
        print(f"Computing distances from {len(N)} residential locations")
        print(f"to {len(destinations)} destination locations...")
        
        total_pairs = len(N) * len(destinations)
        computed = 0
        
        # Compute distances using Dijkstra
        for i, residential_id in enumerate(N):
            if residential_id not in G:
                continue
            
            # Single-source shortest paths from residential location i
            try:
                distances = nx.single_source_dijkstra_path_length(
                    G, residential_id, weight='length'
                )
            except nx.NetworkXNoPath:
                distances = {}
            
            # Store distances to all destinations
            for j in destinations:
                if j not in G:
                    continue
                
                distance = distances.get(j, self.D_infinity)
                self.distance_matrix[(residential_id, j)] = distance
                computed += 1
                
                if computed % 1000 == 0:
                    print(f"  Computed {computed}/{total_pairs} pairs...")
        
        print(f"Computed {computed} distance pairs")
        
        if save_to_db:
            self._save_to_database()
    
    def _save_to_database(self):
        """Save computed distances to database."""
        print("Saving distances to database...")
        
        with self.db.get_session() as session:
            # Clear existing shortest paths (optional - comment out to keep old data)
            # session.execute(text("TRUNCATE TABLE shortest_paths"))
            
            # Batch insert distances
            batch_size = 1000
            batch = []
            
            for (from_id, to_id), distance in self.distance_matrix.items():
                batch.append({
                    'from_node_id': from_id,
                    'to_node_id': to_id,
                    'distance_meters': distance
                })
                
                if len(batch) >= batch_size:
                    self._insert_batch(session, batch)
                    batch = []
            
            # Insert remaining
            if batch:
                self._insert_batch(session, batch)
        
        print("Distances saved to database")
    
    def _insert_batch(self, session, batch: list):
        """Insert a batch of distances."""
        if not batch:
            return
        
        values = []
        for item in batch:
            values.append(
                f"({item['from_node_id']}, {item['to_node_id']}, {item['distance_meters']})"
            )
        
        query = f"""
            INSERT INTO shortest_paths (from_node_id, to_node_id, distance_meters)
            VALUES {', '.join(values)}
            ON CONFLICT (from_node_id, to_node_id) 
            DO UPDATE SET distance_meters = EXCLUDED.distance_meters
        """
        session.execute(text(query))
    
    def load_from_database(self):
        """Load pre-computed distances from database."""
        print("Loading distances from database (not recommended for full city)...")
        # Kept for backwards compatibility but unused in full-city runs.
        with self.db.get_session() as session:
            query = """
                SELECT from_node_id, to_node_id, distance_meters
                FROM shortest_paths
                LIMIT 100000
            """
            result = session.execute(text(query))
            
            self.distance_matrix = {}
            count = 0
            for row in result:
                from_id, to_id, distance = row
                self.distance_matrix[(from_id, to_id)] = float(distance)
                count += 1
            
            print(f"Loaded {count} distance pairs from database (sample)")

    def load_batch_for_residential(self, residential_ids: List[int]):
        """
        Load distances from DB only for a batch of residential nodes.
        This avoids loading the entire shortest_paths table into memory.
        """
        if not residential_ids:
            self.distance_matrix = {}
            return
        
        print(f"Loading distances for batch of {len(residential_ids)} residential nodes...")
        id_list = ",".join(str(int(r)) for r in residential_ids)
        
        with self.db.get_session() as session:
            query = f"""
                SELECT from_node_id, to_node_id, distance_meters
                FROM shortest_paths
                WHERE from_node_id IN ({id_list})
            """
            result = session.execute(text(query))
            
            self.distance_matrix = {}
            count = 0
            for row in result:
                from_id, to_id, distance = row
                self.distance_matrix[(from_id, to_id)] = float(distance)
                count += 1
            
            print(f"Loaded {count} distance pairs for current batch")
    
    def get_distance(self, from_node: int, to_node: int) -> float:
        """Get distance between two nodes."""
        return self.distance_matrix.get((from_node, to_node), self.D_infinity)
    
    def get_distances_to_amenities(self, residential_id: int, 
                                   amenity_type: str) -> Dict[int, float]:
        """
        Get distances from a residential location to all locations
        of a specific amenity type (existing + candidates).
        """
        destinations = self.graph.get_all_amenity_locations(amenity_type)
        
        distances = {}
        for dest_id in destinations:
            distance = self.get_distance(residential_id, dest_id)
            distances[dest_id] = distance
        
        return distances
    
    def get_nearest_amenities(self, residential_id: int, amenity_type: str, 
                            k: int = 1) -> List[Tuple[int, float]]:
        """
        Get k nearest amenities of a given type for a residential location.
        Returns list of (node_id, distance) tuples sorted by distance.
        """
        distances = self.get_distances_to_amenities(residential_id, amenity_type)
        
        # Sort by distance and return top k
        sorted_distances = sorted(distances.items(), key=lambda x: x[1])
        return sorted_distances[:k]
    
    def create_distance_matrix(self, residential_ids: Set[int], 
                              destination_ids: Set[int]) -> np.ndarray:
        """
        Create a numpy distance matrix for given node sets.
        Useful for optimization algorithms.
        """
        matrix = np.full((len(residential_ids), len(destination_ids)), self.D_infinity)
        
        residential_list = list(residential_ids)
        destination_list = list(destination_ids)
        
        for i, res_id in enumerate(residential_list):
            for j, dest_id in enumerate(destination_list):
                matrix[i, j] = self.get_distance(res_id, dest_id)
        
        return matrix
    
    def get_statistics(self) -> Dict:
        """Get statistics about computed distances."""
        if not self.distance_matrix:
            return {}
        
        distances = list(self.distance_matrix.values())
        
        stats = {
            'num_pairs': len(self.distance_matrix),
            'min_distance': min(distances),
            'max_distance': max(distances),
            'mean_distance': np.mean(distances),
            'median_distance': np.median(distances),
            'std_distance': np.std(distances),
            'pairs_within_400m': sum(1 for d in distances if d <= 400),
            'pairs_within_1800m': sum(1 for d in distances if d <= 1800),
            'pairs_within_2400m': sum(1 for d in distances if d <= 2400),
            'pairs_unreachable': sum(1 for d in distances if d >= self.D_infinity)
        }
        
        return stats
    
    def print_statistics(self):
        """Print distance statistics."""
        stats = self.get_statistics()
        print("\n" + "=" * 60)
        print("Shortest Path Distance Statistics")
        print("=" * 60)
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"{key}: {value:.2f}")
            else:
                print(f"{key}: {value}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    # Example usage
    graph = PedestrianGraph()
    graph.load_from_database()
    
    calculator = ShortestPathCalculator(graph)
    
    # Check if distances exist in database
    try:
        calculator.load_from_database()
        if len(calculator.distance_matrix) == 0:
            print("No distances in database, computing...")
            calculator.compute_all_distances()
        else:
            print("Loaded distances from database")
    except Exception as e:
        print(f"Error loading from database: {e}")
        print("Computing distances...")
        calculator.compute_all_distances()
    
    calculator.print_statistics()


"""
WalkScore calculation based on weighted walking distances.
Implements Piecewise Linear Function (PWL) as described in the paper.
"""
import numpy as np
from typing import Dict, List, Set, Tuple
import yaml
from sqlalchemy import text
from src.network.pedestrian_graph import PedestrianGraph
from src.network.shortest_paths import ShortestPathCalculator
from src.utils.database import get_db_manager


class WalkScoreCalculator:
    """Calculates WalkScore for residential locations."""
    
    def __init__(self, graph: PedestrianGraph, path_calculator: ShortestPathCalculator,
                 config_path: str = "config.yaml"):
        """Initialize WalkScore calculator."""
        self.graph = graph
        self.path_calculator = path_calculator
        self.db = graph.db
        
        # Load configuration
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        walkscore_config = self.config['walkscore']
        self.breakpoints = walkscore_config['breakpoints']  # [0, 400, 1800, 2400]
        self.scores = walkscore_config['scores']  # [100, 100, 0, 0]
        
        # Load amenity weights from database
        self._load_amenity_weights()
    
    def _load_amenity_weights(self):
        """Load amenity type weights from database."""
        with self.db.get_session() as session:
            # Load plain amenity weights
            query = """
                SELECT type_name, weight
                FROM amenity_types
                WHERE type_category = 'plain'
            """
            result = session.execute(text(query))
            self.plain_weights = {row[0]: float(row[1]) for row in result}
            
            # Load depth weights
            depth_query = """
                SELECT at.type_name, dw.choice_rank, dw.weight
                FROM depth_weights dw
                JOIN amenity_types at ON dw.amenity_type_id = at.amenity_type_id
                WHERE at.type_category = 'depth'
                ORDER BY at.type_name, dw.choice_rank
            """
            result = session.execute(text(depth_query))
            
            self.depth_weights = {}
            for row in result:
                type_name, rank, weight = row
                if type_name not in self.depth_weights:
                    self.depth_weights[type_name] = {}
                self.depth_weights[type_name][rank] = float(weight)
    
    def piecewise_linear_score(self, distance: float) -> float:
        """
        Calculate WalkScore using Piecewise Linear Function.
        
        Args:
            distance: Weighted walking distance in meters
            
        Returns:
            WalkScore (0-100)
        """
        # Clamp distance to valid range
        distance = max(0, min(distance, self.breakpoints[-1]))
        
        # Find which segment the distance falls into
        for i in range(len(self.breakpoints) - 1):
            if self.breakpoints[i] <= distance <= self.breakpoints[i + 1]:
                # Linear interpolation
                x1, y1 = self.breakpoints[i], self.scores[i]
                x2, y2 = self.breakpoints[i + 1], self.scores[i + 1]
                
                if x2 == x1:
                    return y1
                
                # Linear interpolation: y = y1 + (y2 - y1) * (x - x1) / (x2 - x1)
                score = y1 + (y2 - y1) * (distance - x1) / (x2 - x1)
                return max(0, min(100, score))
        
        # Distance beyond maximum breakpoint
        return self.scores[-1]
    
    def compute_weighted_distance(self, residential_id: int, 
                                 allocated_amenities: Dict[str, Set[int]] = None) -> float:
        """
        Compute weighted walking distance (li) for a residential location.
        
        Formula from paper:
        li = Σ(wa * Di,a) for a ∈ Aplain
           + Σ(Σ(wap * Di,a^p)) for a ∈ Adepth
        
        Args:
            residential_id: Residential location node ID
            allocated_amenities: Dict of {amenity_type: set of allocated node_ids}
                              (for optimization scenarios)
        
        Returns:
            Weighted distance li
        """
        if allocated_amenities is None:
            allocated_amenities = {}
        
        weighted_distance = 0.0
        total_weight = 0.0
        
        # Process plain amenities (single nearest choice)
        for amenity_type, weight in self.plain_weights.items():
            # Get all possible locations (existing + allocated)
            all_locations = self.graph.get_all_amenity_locations(amenity_type)
            
            # Add allocated locations for this type
            if amenity_type in allocated_amenities:
                all_locations.update(allocated_amenities[amenity_type])
            
            # Find nearest location
            if all_locations:
                min_distance = self.path_calculator.D_infinity
                for loc_id in all_locations:
                    distance = self.path_calculator.get_distance(residential_id, loc_id)
                    min_distance = min(min_distance, distance)
                
                weighted_distance += weight * min_distance
                total_weight += weight
        
        # Process depth amenities (multiple choices)
        for amenity_type, depth_weights_dict in self.depth_weights.items():
            # Get all possible locations
            all_locations = self.graph.get_all_amenity_locations(amenity_type)
            
            # Add allocated locations
            if amenity_type in allocated_amenities:
                all_locations.update(allocated_amenities[amenity_type])
            
            if all_locations:
                # Get distances to all locations
                distances = []
                for loc_id in all_locations:
                    distance = self.path_calculator.get_distance(residential_id, loc_id)
                    distances.append((loc_id, distance))
                
                # Sort by distance and take top r choices
                distances.sort(key=lambda x: x[1])
                r = len(depth_weights_dict)
                
                # Calculate weighted sum
                for rank in range(1, min(r + 1, len(distances) + 1)):
                    if rank in depth_weights_dict:
                        w = depth_weights_dict[rank]
                        distance = distances[rank - 1][1]
                        weighted_distance += w * distance
                        total_weight += w
                
                # For unavailable choices, use D_infinity
                for rank in range(len(distances) + 1, r + 1):
                    if rank in depth_weights_dict:
                        w = depth_weights_dict[rank]
                        weighted_distance += w * self.path_calculator.D_infinity
                        total_weight += w
        
        if total_weight > 0:
            weighted_distance /= total_weight
        
        return weighted_distance
    
    def compute_walkscore(self, residential_id: int,
                         allocated_amenities: Dict[str, Set[int]] = None) -> float:
        """
        Compute WalkScore for a residential location.
        
        Args:
            residential_id: Residential location node ID
            allocated_amenities: Dict of allocated amenities (for optimization)
        
        Returns:
            WalkScore (0-100)
        """
        weighted_distance = self.compute_weighted_distance(residential_id, allocated_amenities)
        return self.piecewise_linear_score(weighted_distance)
    
    def compute_baseline_scores(self, save_to_db: bool = True) -> Dict[int, float]:
        """
        Compute baseline WalkScores for all residential locations.
        
        Returns:
            Dict mapping residential_id -> WalkScore
        """
        print("Computing baseline WalkScores...")
        
        scores: Dict[int, float] = {}
        residential_ids = list(self.graph.N)
        total = len(residential_ids)
        batch_size = 500  # number of residential nodes per batch
        
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch_ids = residential_ids[start:end]
            
            # Load only distances for this batch
            self.path_calculator.load_batch_for_residential(batch_ids)
            
            for i, res_id in enumerate(batch_ids, start=start + 1):
                score = self.compute_walkscore(res_id)
                scores[res_id] = score
                
                if i % 100 == 0:
                    print(f"  Computed {i}/{total} scores...")
        
        print(f"Computed {len(scores)} baseline WalkScores")
        
        if save_to_db:
            self._save_scores_to_db(scores, scenario='baseline')
        
        return scores
    
    def _save_scores_to_db(self, scores: Dict[int, float], scenario: str = 'baseline'):
        """Save WalkScores to database."""
        print(f"Saving {scenario} scores to database...")
        
        with self.db.get_session() as session:
            residential_ids = list(scores.keys())
            batch_size = 500
            
            for start in range(0, len(residential_ids), batch_size):
                end = min(start + batch_size, len(residential_ids))
                batch_ids = residential_ids[start:end]
                
                # Load distances only for this batch
                self.path_calculator.load_batch_for_residential(batch_ids)
                
                for res_id in batch_ids:
                    weighted_dist = self.compute_weighted_distance(res_id)
                    score = scores[res_id]
                    
                    query = """
                        INSERT INTO walkability_scores 
                            (residential_id, scenario, weighted_distance, walkscore)
                        VALUES (:residential_id, :scenario, :weighted_distance, :walkscore)
                        ON CONFLICT (residential_id, scenario)
                        DO UPDATE SET
                            weighted_distance = EXCLUDED.weighted_distance,
                            walkscore = EXCLUDED.walkscore,
                            computed_at = CURRENT_TIMESTAMP
                    """
                    session.execute(text(query), {
                        'residential_id': res_id,
                        'scenario': scenario,
                        'weighted_distance': weighted_dist,
                        'walkscore': score
                    })
        
        print(f"Saved {len(scores)} scores to database")
    
    def get_average_walkscore(self, scores: Dict[int, float] = None) -> float:
        """Calculate average WalkScore across all residential locations."""
        if scores is None:
            # Load from database
            with self.db.get_session() as session:
                query = """
                    SELECT AVG(walkscore) as avg_score
                    FROM walkability_scores
                    WHERE scenario = 'baseline'
                """
                result = session.execute(text(query))
                avg = result.scalar()
                return float(avg) if avg else 0.0
        
        if not scores:
            return 0.0
        
        return sum(scores.values()) / len(scores)
    
    def get_statistics(self, scores: Dict[int, float] = None) -> Dict:
        """Get statistics about WalkScores."""
        if scores is None:
            # Load from database
            with self.db.get_session() as session:
                query = """
                    SELECT walkscore
                    FROM walkability_scores
                    WHERE scenario = 'baseline'
                """
                result = session.execute(text(query))
                scores = {i: float(row[0]) for i, row in enumerate(result)}
        
        if not scores:
            return {}
        
        score_values = list(scores.values())
        
        stats = {
            'count': len(scores),
            'mean': np.mean(score_values),
            'median': np.median(score_values),
            'std': np.std(score_values),
            'min': np.min(score_values),
            'max': np.max(score_values),
            'q25': np.percentile(score_values, 25),
            'q75': np.percentile(score_values, 75),
            'scores_above_50': sum(1 for s in score_values if s >= 50),
            'scores_above_75': sum(1 for s in score_values if s >= 75)
        }
        
        return stats
    
    def print_statistics(self, scores: Dict[int, float] = None):
        """Print WalkScore statistics."""
        stats = self.get_statistics(scores)
        print("\n" + "=" * 60)
        print("WalkScore Statistics")
        print("=" * 60)
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"{key}: {value:.2f}")
            else:
                print(f"{key}: {value}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    # Example usage
    from src.network.pedestrian_graph import PedestrianGraph
    from src.network.shortest_paths import ShortestPathCalculator
    
    graph = PedestrianGraph()
    graph.load_from_database()
    
    path_calc = ShortestPathCalculator(graph)
    path_calc.load_from_database()
    
    scorer = WalkScoreCalculator(graph, path_calc)
    
    # Compute baseline scores
    baseline_scores = scorer.compute_baseline_scores()
    scorer.print_statistics(baseline_scores)
    
    avg_score = scorer.get_average_walkscore(baseline_scores)
    print(f"Average WalkScore: {avg_score:.2f}")


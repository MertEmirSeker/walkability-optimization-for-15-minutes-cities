"""
Greedy algorithm for Walkability Optimization.
Implements Algorithm 1 from the paper.
"""
from typing import Dict, Set, Tuple, List
import random
from src.network.pedestrian_graph import PedestrianGraph
from src.scoring.walkscore import WalkScoreCalculator
from src.utils.database import get_db_manager
from sqlalchemy import text


class GreedyOptimizer:
    """
    Greedy algorithm for walkability optimization.
    
    Algorithm 1 from paper:
    1. Start with empty solution S
    2. Iteratively select (amenity_type, location) pair that maximizes
       objective increase
    3. Stop when allocation limits or capacity constraints are met
    """
    
    def __init__(self, graph: PedestrianGraph, scorer: WalkScoreCalculator):
        """Initialize greedy optimizer."""
        self.graph = graph
        self.scorer = scorer
        self.db = graph.db
        
        # Load configuration
        import yaml
        with open("config.yaml", 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.max_amenities = self.config['optimization']['max_amenities_per_type']
        self.default_k = self.config['optimization']['default_k']
        self.greedy_sample_size = self.config['optimization'].get('greedy_sample_size', 2000)
        self.greedy_max_candidates = self.config['optimization'].get('greedy_max_candidates', 200)
    
    def optimize(self, k: int = None, amenity_types: List[str] = None) -> Dict[str, Set[int]]:
        """
        Run greedy optimization algorithm.
        
        Args:
            k: Maximum number of amenities to allocate per type
               (defaults to config value)
            amenity_types: List of amenity types to optimize
                         (defaults to all types)
        
        Returns:
            Dict mapping amenity_type -> set of allocated node_ids
        """
        if k is None:
            k = self.default_k
        
        if amenity_types is None:
            # Get all amenity types from database
            with self.db.get_session() as session:
                query = "SELECT type_name FROM amenity_types"
                result = session.execute(text(query))
                amenity_types = [row[0] for row in result]
        
        print("=" * 60)
        print(f"Running Greedy Optimization (k={k})")
        print("=" * 60)
        print(f"#residential: {len(self.graph.N)}, #candidates: {len(self.graph.M)}, "
              f"amenity_types: {amenity_types}")
        
        # Initialize solution: S = empty set
        S = {}  # {amenity_type: set of allocated node_ids}
        for a_type in amenity_types:
            S[a_type] = set()
        
        # Track allocation counts
        n_allocated = {a_type: 0 for a_type in amenity_types}
        
        # Track candidate capacities
        candidate_capacities = {}
        all_candidates = list(self.graph.M)

        # Hız için sadece sınırlı sayıda candidate üzerinde arama yap
        if len(all_candidates) > self.greedy_max_candidates:
            all_candidates = random.sample(all_candidates, self.greedy_max_candidates)

        for candidate_id in all_candidates:
            with self.db.get_session() as session:
                query = "SELECT capacity FROM candidate_locations WHERE node_id = :node_id"
                result = session.execute(text(query), {'node_id': candidate_id})
                capacity = result.scalar()
                candidate_capacities[candidate_id] = capacity if capacity else 1
        
        # Greedy iteration
        iteration = 0
        total_allocations = sum(k for _ in amenity_types)
        
        while True:
            # Check if we've allocated enough
            all_done = all(n_allocated[a_type] >= k for a_type in amenity_types)
            if all_done:
                break
            
            # Check if any candidates have capacity
            available_candidates = [
                cid for cid, cap in candidate_capacities.items()
                if cap > 0
            ]
            if not available_candidates:
                print("No more candidate locations with capacity")
                break
            
            # Find best (amenity_type, location) pair
            best_pair = None
            best_increase = float('-inf')
            
            for a_type in amenity_types:
                # Skip if already allocated k amenities of this type
                if n_allocated[a_type] >= k:
                    continue
                
                # Try each candidate location
                for candidate_id in available_candidates:
                    # Calculate objective increase
                    increase = self._calculate_objective_increase(
                        S, a_type, candidate_id
                    )
                    
                    if increase > best_increase:
                        best_increase = increase
                        best_pair = (a_type, candidate_id)
            
            if best_pair is None:
                break
            
            # Allocate best pair
            a_type, candidate_id = best_pair
            S[a_type].add(candidate_id)
            n_allocated[a_type] += 1
            candidate_capacities[candidate_id] -= 1
            
            iteration += 1
            if iteration % 5 == 0:
                current_obj = self._calculate_objective(S)
                print(f"Iteration {iteration}/{total_allocations}: "
                      f"avg WalkScore = {current_obj:.4f}, "
                      f"Allocated: {dict(n_allocated)}")
        
        print(f"\nOptimization completed after {iteration} iterations")
        print(f"Final allocations: {dict(n_allocated)}")
        
        # Calculate final objective
        final_obj = self._calculate_objective(S)
        print(f"Final average WalkScore: {final_obj:.4f}")
        
        return S
    
    def _calculate_objective_increase(self, current_S: Dict[str, Set[int]],
                                     amenity_type: str, candidate_id: int) -> float:
        """
        Calculate increase in objective (average WalkScore) if we allocate
        amenity_type to candidate_id.
        
        Returns:
            Increase in average WalkScore
        """
        # Current objective
        current_obj = self._calculate_objective(current_S)
        
        # New solution with added allocation
        new_S = {}
        for a_type, locations in current_S.items():
            new_S[a_type] = locations.copy()
        
        if amenity_type not in new_S:
            new_S[amenity_type] = set()
        new_S[amenity_type].add(candidate_id)
        
        # New objective
        new_obj = self._calculate_objective(new_S)
        
        return new_obj - current_obj
    
    def _calculate_objective(self, allocated_amenities: Dict[str, Set[int]]) -> float:
        """Approximate average WalkScore using a random residential sample."""
        total_score = 0.0
        count = 0

        all_res = list(self.graph.N)
        if not all_res:
            return 0.0

        sample_size = min(self.greedy_sample_size, len(all_res))
        sampled_res = random.sample(all_res, sample_size)

        for residential_id in sampled_res:
            score = self.scorer.compute_walkscore(residential_id, allocated_amenities)
            total_score += score
            count += 1

        return total_score / count if count > 0 else 0.0
    
    def save_results(self, solution: Dict[str, Set[int]], scenario: str = 'greedy'):
        """Save optimization results to database."""
        print(f"Saving {scenario} results to database...")
        
        # Calculate final objective
        final_obj = self._calculate_objective(solution)
        
        with self.db.get_session() as session:
            # Save allocation decisions
            for amenity_type, allocated_nodes in solution.items():
                # Get amenity_type_id
                type_query = "SELECT amenity_type_id FROM amenity_types WHERE type_name = :type_name"
                type_result = session.execute(text(type_query), {'type_name': amenity_type})
                amenity_type_id = type_result.scalar()
                
                if not amenity_type_id:
                    continue
                
                # Get candidate_id for each allocated node
                for node_id in allocated_nodes:
                    cand_query = """
                        SELECT candidate_id FROM candidate_locations WHERE node_id = :node_id
                    """
                    cand_result = session.execute(text(cand_query), {'node_id': node_id})
                    candidate_id = cand_result.scalar()
                    
                    if candidate_id:
                        # Count how many amenities of this type allocated to this candidate
                        allocation_count = sum(
                            1 for a_type, nodes in solution.items()
                            if a_type == amenity_type and node_id in nodes
                        )
                        
                        # Insert or update optimization result
                        insert_query = """
                            INSERT INTO optimization_results
                                (scenario, amenity_type_id, candidate_id, allocation_count,
                                 objective_value, solver)
                            VALUES (:scenario, :amenity_type_id, :candidate_id, 
                                    :allocation_count, :objective_value, 'greedy')
                            ON CONFLICT DO NOTHING
                        """
                        session.execute(text(insert_query), {
                            'scenario': scenario,
                            'amenity_type_id': amenity_type_id,
                            'candidate_id': candidate_id,
                            'allocation_count': allocation_count,
                            'objective_value': final_obj
                        })
            
            # Save WalkScores
            scores = {}
            for residential_id in self.graph.N:
                score = self.scorer.compute_walkscore(residential_id, solution)
                scores[residential_id] = score
            
            self.scorer._save_scores_to_db(scores, scenario=scenario)
        
        print(f"Saved results for scenario: {scenario}")


if __name__ == "__main__":
    from src.network.pedestrian_graph import PedestrianGraph
    from src.network.shortest_paths import ShortestPathCalculator
    from src.scoring.walkscore import WalkScoreCalculator
    
    print("Loading graph and computing distances...")
    graph = PedestrianGraph()
    graph.load_from_database()
    
    path_calc = ShortestPathCalculator(graph)
    path_calc.load_from_database()
    
    scorer = WalkScoreCalculator(graph, path_calc)
    
    # Run greedy optimization
    optimizer = GreedyOptimizer(graph, scorer)
    solution = optimizer.optimize(k=3)
    
    # Save results
    optimizer.save_results(solution, scenario='greedy_k3')
    
    print("\nOptimization complete!")


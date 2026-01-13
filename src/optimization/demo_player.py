"""
Demo Player for Optimization Replay.

Replays recorded optimization runs for quick demonstrations.
"""
import time
import random
from typing import Dict, Set, Callable, Optional
from sqlalchemy import text


class DemoPlayer:
    """Replays recorded optimization for demo purposes."""
    
    def __init__(self, db, graph, scorer):
        """
        Initialize demo player.
        
        Args:
            db: Database manager instance
            graph: PedestrianGraph instance
            scorer: WalkScoreCalculator instance
        """
        self.db = db
        self.graph = graph
        self.scorer = scorer
        
    def load_recording(self, scenario: str) -> Dict:
        """
        Load recording metadata and iterations from database.
        
        Args:
            scenario: Scenario name (e.g., 'greedy_k3')
            
        Returns:
            Dictionary with 'metadata' and 'iterations' keys
            
        Raises:
            ValueError: If recording not found
        """
        with self.db.get_session() as session:
            # Get metadata
            meta_query = """
                SELECT * FROM optimization_recordings
                WHERE scenario = :scenario
            """
            meta_result = session.execute(text(meta_query), {'scenario': scenario})
            meta = meta_result.fetchone()
            
            if not meta:
                raise ValueError(f"No recording found for scenario '{scenario}'")
            
            # Get iterations
            iter_query = """
                SELECT oi.*, at.type_name, cl.node_id as candidate_node_id
                FROM optimization_iterations oi
                JOIN amenity_types at ON oi.amenity_type_id = at.amenity_type_id
                JOIN candidate_locations cl ON oi.candidate_id = cl.candidate_id
                WHERE oi.scenario = :scenario
                ORDER BY oi.iteration_number
            """
            iter_result = session.execute(text(iter_query), {'scenario': scenario})
            iterations = iter_result.fetchall()
            
        meta_dict = {
            'scenario': meta[1],
            'algorithm': meta[2],
            'k_value': meta[3],
            'total_iterations': meta[4],
            'final_objective': meta[5],
            'total_time_seconds': meta[6],
            'recorded_at': meta[7]
        }
        
        iterations_list = [
            {
                'iteration_number': it[2],
                'amenity_type_id': it[3],
                'candidate_id': it[4],
                'improvement': float(it[5]),
                'current_objective': float(it[6]),
                'progress_pct': float(it[7]),
                'elapsed_seconds': float(it[8]),
                'type_name': it[10],
                'candidate_node_id': it[11]
            }
            for it in iterations
        ]
        
        return {'metadata': meta_dict, 'iterations': iterations_list}
    
    def replay(self, scenario: str, 
               on_iteration_callback: Optional[Callable] = None,
               delay_per_iteration: float = 0.5) -> Dict[str, Set[int]]:
        """
        Replay optimization with animation.
        
        Args:
            scenario: Scenario name to replay
            on_iteration_callback: Function called for each iteration with params:
                (iteration_num, progress, objective, improvement, amenity_type, node_id)
            delay_per_iteration: Delay in seconds between iterations (default 0.5s)
            
        Returns:
            Solution dictionary mapping amenity_type -> set of allocated node_ids
        """
        print(f"[DEMO] Loading recording for {scenario}...")
        recording = self.load_recording(scenario)
        
        metadata = recording['metadata']
        iterations = recording['iterations']
        
        print(f"[DEMO] Replaying {metadata['total_iterations']} iterations")
        print(f"[DEMO] Original run: {metadata['total_time_seconds']:.1f}s, "
              f"Final objective: {metadata['final_objective']:.4f}")
        print(f"[DEMO] Replay speed: ~{delay_per_iteration}s per iteration")
        
        solution = {}  # Build solution incrementally
        
        for iteration in iterations:
            # Simulate processing delay
            if iteration['iteration_number'] > 1:
                time.sleep(delay_per_iteration)
            
            # Add to solution
            amenity_type = iteration['type_name']
            if amenity_type not in solution:
                solution[amenity_type] = set()
            
            candidate_node_id = iteration['candidate_node_id']
            solution[amenity_type].add(candidate_node_id)
            
            # Callback for UI update
            if on_iteration_callback:
                on_iteration_callback(
                    iteration_num=iteration['iteration_number'],
                    progress=iteration['progress_pct'],
                    objective=iteration['current_objective'],
                    improvement=iteration['improvement'],
                    amenity_type=amenity_type,
                    node_id=candidate_node_id
                )
            
            # Print progress
            if iteration['iteration_number'] % 5 == 0:
                print(f"[DEMO] Iteration {iteration['iteration_number']}/{metadata['total_iterations']}: "
                      f"{iteration['progress_pct']:.1f}% | Obj: {iteration['current_objective']:.4f}")
        
        print(f"[DEMO] ✓ Replay completed!")
        return solution
    
    def quick_validate(self, solution: Dict[str, Set[int]], 
                      sample_size: int = 1000) -> Dict:
        """
        Quick validation of replayed solution.
        Re-compute objective on sample for verification.
        
        Args:
            solution: Solution to validate
            sample_size: Number of residential locations to sample
            
        Returns:
            Dictionary with validation results
        """
        print(f"[DEMO] Validating solution with {sample_size} samples...")
        
        # Sample residential locations
        all_residential = list(self.graph.residential_buildings)
        sample_size = min(sample_size, len(all_residential))
        sampled = random.sample(all_residential, sample_size)
        
        total = 0.0
        for res_id, snap_id in sampled:
            score = self.scorer.compute_walkscore(snap_id, solution)
            total += score
        
        sample_objective = total / sample_size
        
        result = {
            'sample_size': sample_size,
            'sample_objective': sample_objective,
            'total_residential': len(all_residential)
        }
        
        print(f"[DEMO] ✓ Validation complete: Sample objective = {sample_objective:.4f}")
        
        return result

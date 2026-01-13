"""
Greedy algorithm for Walkability Optimization.
Implements Algorithm 1 from the paper (CORRECTED VERSION).

Key fixes:
1. NO sampling - uses ALL residential locations
2. NO candidate limiting - uses ALL candidates
3. Exact objective computation
"""
from typing import Dict, Set, Tuple, List
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
        
        # FAST MODE: For testing/development, use sampling to speed up
        # Set to None to use ALL data (production mode)
        self.fast_mode_residential_sample = self.config['optimization'].get('fast_mode_residential_sample', None)
        self.fast_mode_candidate_sample = self.config['optimization'].get('fast_mode_candidate_sample', None)
        
        # Cache for WalkScores - CRITICAL for performance!
        self.walkscore_cache = {}  # {residential_id: score}
        self.current_S_cache = None  # Track which S the cache is valid for
        
        # Pre-compute nearby residentials for each candidate - CRITICAL for speed!
        self.nearby_residentials = {}  # {candidate_id: set of residential_ids within 3km}
    
    def optimize(self, k: int = None, amenity_types: List[str] = None, record_demo: bool = False) -> Dict[str, Set[int]]:
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
        
        # FAST MODE: Sample for testing if enabled
        original_N = set(self.graph.N)
        original_M = set(self.graph.M)
        
        if self.fast_mode_residential_sample and len(self.graph.N) > self.fast_mode_residential_sample:
            import random
            sampled_N = random.sample(list(self.graph.N), self.fast_mode_residential_sample)
            self.graph.N = set(sampled_N)
            print(f"[FAST MODE] Sampling {len(self.graph.N)} residential (from {len(original_N)})")
        
        if self.fast_mode_candidate_sample and len(self.graph.M) > self.fast_mode_candidate_sample:
            import random
            sampled_M = random.sample(list(self.graph.M), self.fast_mode_candidate_sample)
            self.graph.M = set(sampled_M)
            print(f"[FAST MODE] Sampling {len(self.graph.M)} candidates (from {len(original_M)})")
        
        print(f"#residential: {len(self.graph.N)}, #candidates: {len(self.graph.M)}, "
              f"amenity_types: {amenity_types}")
        
        # Initialize recorder if requested
        recorder = None
        if record_demo:
            from src.optimization.demo_recorder import DemoRecorder
            scenario = f'greedy_k{k}'
            total_allocations = k * len(amenity_types)
            recorder = DemoRecorder(self.db, scenario, 'greedy', k, total_allocations)
            print(f"[RECORDING] Demo mode enabled - saving iterations to database")
        
        # PRE-COMPUTE: Find nearby residentials for each candidate (within 3km)
        # This is done ONCE and saves MASSIVE time during evaluations!
        print("\n[Preprocessing] Computing nearby residentials for each candidate...")
        self._precompute_nearby_residentials()
        print(f"  ✓ Precomputation complete!")
        
        # Initialize solution: S = empty set
        S = {}  # {amenity_type: set of allocated node_ids}
        for a_type in amenity_types:
            S[a_type] = set()
        
        # Track allocation counts
        n_allocated = {a_type: 0 for a_type in amenity_types}
        
        # Track candidate capacities
        # PAPER: Use ALL candidates, no sampling!
        candidate_capacities = {}
        all_candidates = list(self.graph.M)

        print(f"Using ALL {len(all_candidates)} candidates (no sampling)")

        for candidate_id in all_candidates:
            with self.db.get_session() as session:
                query = "SELECT capacity FROM candidate_locations WHERE node_id = :node_id"
                result = session.execute(text(query), {'node_id': candidate_id})
                capacity = result.scalar()
                candidate_capacities[candidate_id] = capacity if capacity else 1
        
        # Greedy iteration
        iteration = 0
        total_allocations = sum(k for _ in amenity_types)
        
        # Track start time for global ETA
        import time 
        start_time_global = time.time()
        
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
            
            # Count evaluations for progress
            total_evaluations = 0
            num_types_remaining = sum(1 for a_type in amenity_types if n_allocated[a_type] < k)
            max_evaluations = num_types_remaining * len(available_candidates)
            
            print(f"\n  Iteration {iteration + 1}: Evaluating {max_evaluations} (type, candidate) pairs...")
            
            import time
            start_time = time.time()
            last_print_time = start_time
            
            for a_type in amenity_types:
                # Skip if already allocated k amenities of this type
                if n_allocated[a_type] >= k:
                    continue
                
                # Try each candidate location
                for idx, candidate_id in enumerate(available_candidates):
                    total_evaluations += 1
                    
                    # Calculate objective increase
                    increase = self._calculate_objective_increase(
                        S, a_type, candidate_id
                    )
                    
                    if increase > best_increase:
                        best_increase = increase
                        best_pair = (a_type, candidate_id)
                    
                    # Show progress every 1 second OR every 10 evaluations
                    current_time = time.time()
                    if (current_time - last_print_time >= 1.0) or (total_evaluations % 10 == 0):
                        elapsed = current_time - start_time
                        progress_pct = 100 * total_evaluations / max_evaluations
                        evals_per_sec = total_evaluations / elapsed if elapsed > 0 else 0
                        remaining = (max_evaluations - total_evaluations) / evals_per_sec if evals_per_sec > 0 else 0
                        
                        # Progress bar
                        bar_length = 30
                        filled = int(bar_length * total_evaluations / max_evaluations)
                        bar = '█' * filled + '░' * (bar_length - filled)
                        
                        print(f"    [{bar}] {progress_pct:.1f}% | "
                              f"{total_evaluations}/{max_evaluations} | "
                              f"Speed: {evals_per_sec:.1f} eval/s | "
                              f"ETA: {remaining:.0f}s | "
                              f"Best: {best_increase:.6f}", end='\r', flush=True)
                        
                        last_print_time = current_time
            
            print()  # New line after progress
            
            if best_pair is None:
                break
            
            # Allocate best pair
            a_type, candidate_id = best_pair
            S[a_type].add(candidate_id)
            n_allocated[a_type] += 1
            candidate_capacities[candidate_id] -= 1
            
            # CRITICAL: Update cache incrementally instead of rebuild!
            self._update_cache_after_allocation(S, a_type, candidate_id)
            
            iteration += 1
            print(f"\n  ✓ Allocated {a_type} at candidate {candidate_id}")
            print(f"    Improvement: +{best_increase:.6f}, Total iterations: {iteration}/{total_allocations}")
            print(f"    Current allocations: {dict(n_allocated)}")
            
            # Update PROGRESS.txt for Desktop App
            try:
                global_pct = 100 * iteration / total_allocations
                elapsed_global = time.time() - start_time_global
                allocs_per_sec = iteration / elapsed_global if elapsed_global > 0 else 0
                remaining_allocs = total_allocations - iteration
                eta_seconds = remaining_allocs / allocs_per_sec if allocs_per_sec > 0 else 0
                
                # Format ETA
                if eta_seconds < 60:
                    eta_str = f"{eta_seconds:.0f}s"
                else:
                    eta_str = f"{eta_seconds/60:.1f}m"

                # DIRECT UI COMMUNICATION via Stdout
                # Format: ::PROGRESS::percentage::status::eta
                print(f"::PROGRESS::{global_pct:.1f}::Running Optimization::{eta_str}", flush=True)

                # Still write to file as backup/log, but UI will prefer stdout
                with open("PROGRESS.txt", "w") as f:
                    f.write(f"Status: Running Optimization...\n")
                    f.write(f"Current Progress: {global_pct:.1f}%\n")
                    f.write(f"ETA: {eta_str}\n")
            except Exception as e:
                print(f"Warning: Could not write progress: {e}")
            
            # Calculate current objective every 5 iterations (or every iteration if recording)
            if record_demo:
                current_obj = self._calculate_objective(S)
                # Record to database
                recorder.record_iteration(a_type, candidate_id, best_increase, current_obj)
            elif iteration % 5 == 0:
                current_obj = self._calculate_objective(S)
                print(f"    Current avg WalkScore = {current_obj:.4f}")
        
        print(f"\nOptimization completed after {iteration} iterations")
        print(f"Final allocations: {dict(n_allocated)}")
        
        # Calculate final objective
        final_obj = self._calculate_objective(S)
        print(f"Final average WalkScore: {final_obj:.4f}")
        
        # Finalize recording if enabled
        if recorder:
            recorder.finalize(final_obj)
        
        # Restore original N and M if we sampled
        if self.fast_mode_residential_sample or self.fast_mode_candidate_sample:
            print(f"[FAST MODE] Restoring original graph sets")
            self.graph.N = original_N
            self.graph.M = original_M
        
        return S
    
    def _calculate_objective_increase(self, current_S: Dict[str, Set[int]],
                                     amenity_type: str, candidate_id: int) -> float:
        """
        Calculate increase in objective (average WalkScore) if we allocate
        amenity_type to candidate_id.
        
        KEY OPTIMIZATION: Incremental computation with caching!
        1. Cache WalkScores for current S
        2. Only recompute scores for residentials affected by new amenity
        3. Affected = within 3km (pre-computed!)
        
        Returns:
            Increase in average WalkScore
        """
        # Ensure cache is valid for current_S
        if not self._is_cache_valid(current_S):
            self._rebuild_cache(current_S)
        
        # OPTIMIZATION: Use pre-computed nearby residentials (network nodes)!
        affected_network_nodes = self.nearby_residentials.get(candidate_id, [])
        
        # If no residentials are close enough, no improvement
        if not affected_network_nodes:
            return 0.0
        
        # Create new solution with added allocation
        new_S = {}
        for a_type, locations in current_S.items():
            new_S[a_type] = locations.copy()
        
        if amenity_type not in new_S:
            new_S[amenity_type] = set()
        new_S[amenity_type].add(candidate_id)
        
        # ✅ CRITICAL FIX: Calculate improvement for ALL buildings that snap to affected nodes
        # Multiple buildings can snap to the same network node!
        total_improvement = 0.0
        
        # Find all buildings that snap to affected network nodes
        affected_buildings = [
            (res_id, snap_id) for res_id, snap_id in self.graph.residential_buildings
            if snap_id in affected_network_nodes
        ]
        
        for residential_id, snapped_node_id in affected_buildings:
            # Current WalkScore (from cache, using network node!)
            old_score = self.walkscore_cache[snapped_node_id]
            
            # New WalkScore with added amenity
            new_score = self.scorer.compute_walkscore(snapped_node_id, new_S)
            
            # Improvement for this building
            total_improvement += (new_score - old_score)
        
        # Average improvement across ALL residential BUILDINGS (not just affected network nodes!)
        # This is correct because unaffected residentials have 0 improvement
        # ✅ FIXED: Divide by total number of buildings, not unique network nodes
        num_buildings = len(self.graph.residential_buildings)
        improvement = total_improvement / num_buildings if num_buildings > 0 else 0.0
        
        return improvement
    
    def _is_cache_valid(self, current_S: Dict[str, Set[int]]) -> bool:
        """Check if walkscore_cache is valid for current_S."""
        if self.current_S_cache is None:
            return False
        
        # Check if S has changed
        for a_type, locations in current_S.items():
            if a_type not in self.current_S_cache:
                return False
            if locations != self.current_S_cache[a_type]:
                return False
        
        return True
    
    def _rebuild_cache(self, current_S: Dict[str, Set[int]]):
        """
        Rebuild WalkScore cache for current_S.
        
        NOTE: Cache is per network node (not per building), which is correct
        because multiple buildings can snap to the same network node.
        """
        print(f"  [Cache] Rebuilding WalkScore cache for {len(self.graph.N)} network nodes...")
        
        self.walkscore_cache = {}
        for network_node_id in self.graph.N:
            score = self.scorer.compute_walkscore(network_node_id, current_S)
            self.walkscore_cache[network_node_id] = score
        
        # Deep copy current_S to track cache validity
        self.current_S_cache = {}
        for a_type, locations in current_S.items():
            self.current_S_cache[a_type] = locations.copy()
        
        print(f"  [Cache] Rebuild complete!")
    
    def _precompute_nearby_residentials(self):
        """
        Pre-compute which residentials are within 3km of each candidate.
        
        This is done ONCE at the start and saves massive time during optimization!
        Without this: 4,976 evaluations × 34,424 distance checks = 171M checks
        With this: 1,244 candidates × 34,424 distance checks = 43M checks (ONCE!)
        """
        max_relevant_distance = 3000.0
        self.nearby_residentials = {}
        
        total = len(self.graph.M)
        for idx, candidate_id in enumerate(self.graph.M, 1):
            nearby = []
            for residential_id in self.graph.N:
                dist = self.scorer.path_calculator.get_distance(residential_id, candidate_id)
                if dist <= max_relevant_distance:
                    nearby.append(residential_id)
            
            self.nearby_residentials[candidate_id] = nearby
            
            if idx % 100 == 0:
                print(f"  Progress: {idx}/{total} candidates processed...", end='\r')
        
        print()  # New line
        if len(self.nearby_residentials) > 0:
            avg_nearby = sum(len(v) for v in self.nearby_residentials.values()) / len(self.nearby_residentials)
            print(f"  Avg residentials per candidate: {avg_nearby:.0f}")
        else:
            print("  ⚠️ WARNING: No candidate locations found!")
            raise ValueError("Cannot run optimization: No candidate locations in database. Please run data loading first.")
    
    def _update_cache_after_allocation(self, current_S: Dict[str, Set[int]], 
                                       amenity_type: str, candidate_id: int):
        """
        Incrementally update cache after allocating amenity_type to candidate_id.
        
        KEY INSIGHT: Only residentials within 3km are affected!
        - Use pre-computed nearby residentials
        - Recompute only their WalkScores
        - Keep rest of cache unchanged
        
        This is MUCH faster than rebuilding entire cache!
        """
        # Use pre-computed nearby network nodes
        affected_network_nodes = self.nearby_residentials.get(candidate_id, [])
        
        # Update only affected network nodes
        # NOTE: Multiple buildings may snap to each node, but cache is per node
        print(f"  [Cache] Updating {len(affected_network_nodes)} affected network nodes")
        
        for network_node_id in affected_network_nodes:
            # Recompute WalkScore with new allocation
            new_score = self.scorer.compute_walkscore(network_node_id, current_S)
            self.walkscore_cache[network_node_id] = new_score
        
        # Update current_S_cache to reflect new allocation
        if amenity_type not in self.current_S_cache:
            self.current_S_cache[amenity_type] = set()
        self.current_S_cache[amenity_type].add(candidate_id)
    
    def _calculate_objective(self, allocated_amenities: Dict[str, Set[int]]) -> float:
        """
        Calculate EXACT average WalkScore across ALL residential BUILDINGS.
        
        ✅ FIXED: Uses ALL buildings (26,931), not just network nodes (9,893)
        
        PAPER: Objective = (1/|N|) * Σ(i∈N) f(li)
        where f() = PWL function, li = weighted distance for residential i
        
        Returns:
            Average WalkScore across all residential buildings
        """
        total_score = 0.0
        count = 0

        if not self.graph.residential_buildings:
            return 0.0

        # Use ALL residential buildings - NO SAMPLING!
        for residential_id, snapped_node_id in self.graph.residential_buildings:
            # Use snapped_node_id for pathfinding
            score = self.scorer.compute_walkscore(snapped_node_id, allocated_amenities)
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
                # CRITICAL: solution contains snapped_node_id, not node_id
                for snapped_node_id in allocated_nodes:
                    cand_query = """
                        SELECT candidate_id FROM candidate_locations WHERE snapped_node_id = :snapped_node_id
                    """
                    cand_result = session.execute(text(cand_query), {'snapped_node_id': snapped_node_id})
                    candidate_id = cand_result.scalar()
                    
                    if candidate_id:
                        # Count how many amenities of this type allocated to this candidate
                        allocation_count = sum(
                            1 for a_type, nodes in solution.items()
                            if a_type == amenity_type and snapped_node_id in nodes
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
            
            # Save WalkScores for ALL buildings
            scores = {}
            weighted_distances = {}
            for residential_id, snapped_node_id in self.graph.residential_buildings:
                # Use snapped_node_id for pathfinding
                weighted_dist = self.scorer.compute_weighted_distance(snapped_node_id, solution)
                score = self.scorer.piecewise_linear_score(weighted_dist)
                # Store with residential_id (building ID)
                scores[residential_id] = score
                weighted_distances[residential_id] = weighted_dist
            
            self.scorer._save_scores_to_db(scores, weighted_distances, scenario=scenario)
        
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


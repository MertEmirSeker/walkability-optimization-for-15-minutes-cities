"""
CP (Constraint Programming) solver for Walkability Optimization.
Uses Google OR-Tools CP-SAT solver.

This is an alternative to MILP, often faster for discrete optimization problems.
"""
from typing import Dict, Set, List
import yaml
from sqlalchemy import text
from src.network.pedestrian_graph import PedestrianGraph
from src.scoring.walkscore import WalkScoreCalculator
from src.utils.database import get_db_manager


class CPOptimizer:
    """
    CP-SAT solver for walkability optimization.
    
    Uses Google OR-Tools CP-SAT solver which is:
    - Free and open-source
    - Often faster than MILP for discrete problems
    - Good for large-scale combinatorial optimization
    """
    
    def __init__(self, graph: PedestrianGraph, scorer: WalkScoreCalculator):
        """Initialize CP optimizer."""
        self.graph = graph
        self.scorer = scorer
        self.db = graph.db
        
        # Load configuration
        with open("config.yaml", 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # Try to import OR-Tools
        try:
            from ortools.sat.python import cp_model
            self.cp_model = cp_model
            print("Using OR-Tools CP-SAT solver")
        except ImportError:
            print("ERROR: OR-Tools not available!")
            print("Install with: pip install ortools")
            raise
    
    def optimize(self, k: int = None, amenity_types: List[str] = None) -> Dict[str, Set[int]]:
        """
        Run CP optimization.
        
        Args:
            k: Maximum number of amenities to allocate per type
            amenity_types: List of amenity types to optimize
        
        Returns:
            Dict mapping amenity_type -> set of allocated node_ids
        """
        if k is None:
            k = self.config['optimization']['default_k']
        
        if amenity_types is None:
            with self.db.get_session() as session:
                query = "SELECT type_name FROM amenity_types"
                result = session.execute(text(query))
                amenity_types = [row[0] for row in result]
        
        print("=" * 60)
        print(f"Running CP-SAT Optimization (k={k})")
        print("=" * 60)
        print(f"#residential: {len(self.graph.N)}, #candidates: {len(self.graph.M)}, "
              f"amenity_types: {amenity_types}")
        
        # Create model
        model = self.cp_model.CpModel()
        
        # Get candidate capacities
        candidate_capacities = {}
        for candidate_id in self.graph.M:
            with self.db.get_session() as session:
                query = "SELECT capacity FROM candidate_locations WHERE node_id = :node_id"
                result = session.execute(text(query), {'node_id': candidate_id})
                capacity = result.scalar()
                candidate_capacities[candidate_id] = capacity if capacity else 1
        
        print("\n[1/4] Creating decision variables...")
        # Decision variables: y_ja (boolean)
        y = {}
        for a_type in amenity_types:
            for candidate_id in self.graph.M:
                var_name = f"y_{candidate_id}_{a_type}"
                y[(candidate_id, a_type)] = model.NewBoolVar(var_name)
        
        print(f"  Created {len(y)} boolean variables")
        
        print("\n[2/4] Adding constraints...")
        
        # Constraint 1: Budget constraint (k amenities per type)
        for a_type in amenity_types:
            budget_vars = [y[(candidate_id, a_type)] for candidate_id in self.graph.M]
            model.Add(sum(budget_vars) <= k)
        print(f"  Added {len(amenity_types)} budget constraints")
        
        # Constraint 2: Capacity constraint
        for candidate_id in self.graph.M:
            capacity_vars = [y[(candidate_id, a_type)] for a_type in amenity_types]
            model.Add(sum(capacity_vars) <= candidate_capacities[candidate_id])
        print(f"  Added {len(self.graph.M)} capacity constraints")
        
        print("\n[3/4] Setting objective function...")
        # For CP-SAT, we need to approximate the objective
        # We'll use a linear approximation of WalkScore improvement
        
        # Precompute potential improvements for each allocation
        improvements = {}
        print("  Precomputing improvement estimates...")
        
        for idx, (candidate_id, a_type) in enumerate(y.keys()):
            if idx % 100 == 0:
                print(f"    Progress: {idx}/{len(y)}", end='\r')
            
            # Estimate improvement: count residentials within walking distance
            count = 0
            for residential_id in self.graph.N:
                dist = self.scorer.path_calculator.get_distance(residential_id, candidate_id)
                if dist <= 1000:  # Within 1km
                    count += 1
            
            # Scale to integer (CP-SAT requires integer coefficients)
            improvements[(candidate_id, a_type)] = int(count * 1000)
        
        print()
        
        # Objective: Maximize total improvement
        objective_terms = [
            y[(candidate_id, a_type)] * improvements[(candidate_id, a_type)]
            for (candidate_id, a_type) in y.keys()
        ]
        model.Maximize(sum(objective_terms))
        print("  Objective: Maximize coverage-based improvement")
        
        print("\n[4/4] Solving CP-SAT...")
        solver = self.cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 3600  # 1 hour
        solver.parameters.num_search_workers = 8  # Parallel search
        solver.parameters.log_search_progress = True
        
        status = solver.Solve(model)
        
        if status == self.cp_model.OPTIMAL or status == self.cp_model.FEASIBLE:
            print(f"\n✓ Optimization complete!")
            print(f"  Status: {'OPTIMAL' if status == self.cp_model.OPTIMAL else 'FEASIBLE'}")
            print(f"  Objective value: {solver.ObjectiveValue()}")
            print(f"  Runtime: {solver.WallTime():.2f}s")
            
            # Extract allocation decisions
            S = {a_type: set() for a_type in amenity_types}
            for (candidate_id, a_type), var in y.items():
                if solver.Value(var) == 1:
                    S[a_type].add(candidate_id)
            
            print(f"\nFinal allocations: {[(k, len(v)) for k, v in S.items()]}")
            return S
        else:
            print(f"\n✗ Optimization failed!")
            print(f"  Status: {status}")
            return {a_type: set() for a_type in amenity_types}
    
    def save_results(self, solution: Dict[str, Set[int]], scenario: str = 'cp'):
        """Save CP results to database."""
        print(f"Saving {scenario} results to database...")
        
        with self.db.get_session() as session:
            for amenity_type, allocated_nodes in solution.items():
                type_query = "SELECT amenity_type_id FROM amenity_types WHERE type_name = :type_name"
                type_result = session.execute(text(type_query), {'type_name': amenity_type})
                amenity_type_id = type_result.scalar()
                
                if not amenity_type_id:
                    continue
                
                for node_id in allocated_nodes:
                    cand_query = """
                        SELECT candidate_id FROM candidate_locations WHERE node_id = :node_id
                    """
                    cand_result = session.execute(text(cand_query), {'node_id': node_id})
                    candidate_id = cand_result.scalar()
                    
                    if candidate_id:
                        insert_query = """
                            INSERT INTO optimization_results
                                (scenario, amenity_type_id, candidate_id, allocation_count,
                                 objective_value, solver)
                            VALUES (:scenario, :amenity_type_id, :candidate_id, 
                                    1, 0.0, 'cp')
                            ON CONFLICT DO NOTHING
                        """
                        session.execute(text(insert_query), {
                            'scenario': scenario,
                            'amenity_type_id': amenity_type_id,
                            'candidate_id': candidate_id
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
    
    print("Loading graph...")
    graph = PedestrianGraph()
    graph.load_from_database()
    
    print("Loading shortest paths...")
    path_calc = ShortestPathCalculator(graph)
    path_calc.load_from_database()
    
    print("Creating WalkScore calculator...")
    scorer = WalkScoreCalculator(graph, path_calc)
    
    print("Running CP optimization...")
    optimizer = CPOptimizer(graph, scorer)
    solution = optimizer.optimize(k=1)
    
    optimizer.save_results(solution, scenario='cp_k1')
    print("\n✓ Optimization complete!")


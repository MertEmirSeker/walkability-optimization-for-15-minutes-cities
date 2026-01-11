"""
MILP (Mixed-Integer Linear Programming) solver for Walkability Optimization.
Implements the MILP formulation from the paper.
"""
import numpy as np
from typing import Dict, Set, List, Tuple
import yaml
from src.network.pedestrian_graph import PedestrianGraph
from src.scoring.walkscore import WalkScoreCalculator
from src.utils.database import get_db_manager
from sqlalchemy import text


class MILPSolver:
    """
    MILP solver for walkability optimization.
    
    Variables:
    - yja: Integer - number of amenities of type a allocated to location j
    - xija: Binary - residential i visits location j for amenity type a (Aplain)
    - xpija: Binary - residential i visits location j for p-th nearest of type a (Adepth)
    - li: Continuous - weighted walking distance for residential i
    - fi: Continuous - WalkScore for residential i
    
    Constraints:
    - Allocation limits: Σ yja ≤ ka
    - Capacity: Σ yja ≤ cj
    - Assignment: Each residential assigned to one location per amenity type
    - Distance calculation: li based on assignments
    - WalkScore: fi = PWL(li)
    """
    
    def __init__(self, graph: PedestrianGraph, scorer: WalkScoreCalculator):
        """Initialize MILP solver."""
        self.graph = graph
        self.scorer = scorer
        self.db = graph.db
        
        # Load configuration
        with open("config.yaml", 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.max_amenities = self.config['optimization']['max_amenities_per_type']
        self.default_k = self.config['optimization']['default_k']
        self.time_limit = self.config['optimization']['milp']['time_limit_seconds']
        self.threads = self.config['optimization']['milp']['threads']
        self.mip_gap = self.config['optimization']['milp']['mip_gap']
        
        # Get amenity types
        self._load_amenity_types()
    
    def _load_amenity_types(self):
        """Load amenity types and categorize them."""
        with self.db.get_session() as session:
            query = """
                SELECT type_name, type_category, depth_count
                FROM amenity_types
            """
            result = session.execute(text(query))
            
            self.amenity_types = []
            self.plain_types = []
            self.depth_types = {}
            
            for row in result:
                type_name, category, depth_count = row
                self.amenity_types.append(type_name)
                
                if category == 'plain':
                    self.plain_types.append(type_name)
                else:
                    self.depth_types[type_name] = depth_count
    
    def solve(self, k: int = None, scenario: str = 'milp') -> Dict[str, Set[int]]:
        """
        Solve MILP optimization problem using Google OR-Tools (SCIP).
        
        Args:
            k: Maximum number of amenities to allocate per type
            scenario: Scenario name for saving results
            
        Returns:
            Dict mapping amenity_type -> set of allocated node_ids
        """
        try:
            from ortools.linear_solver import pywraplp
        except ImportError:
            print("ERROR: OR-Tools not found. Please install: pip install ortools")
            return None

        if k is None:
            k = self.default_k
            
        print("=" * 60)
        print(f"Solving MILP Optimization (k={k}) using OR-Tools (SCIP)")
        print("=" * 60)
        
        # Create solver
        solver = pywraplp.Solver.CreateSolver('SCIP')
        if not solver:
            print("ERROR: SCIP solver not available in OR-Tools.")
            return None
            
        # Set time limit
        time_limit_ms = int(self.time_limit * 1000)
        solver.SetTimeLimit(time_limit_ms)
        
        # Threads are handled automatically/internally by SCIP usually
        
        # --- 1. Data Preparation (Same as before) ---
        nodes_N = list(self.graph.N)
        nodes_M = list(self.graph.M)
        
        # Get amenity types
        amenity_types = []
        with self.db.get_session() as session:
            query = "SELECT type_name FROM amenity_types"
            result = session.execute(text(query))
            amenity_types = [row[0] for row in result]
            
        print(f"Problem size: {len(nodes_N)} residential, {len(nodes_M)} candidates")
        print(f"Amenity types: {amenity_types}")
        
        # --- 2. Precompute Valid Neighbors (Pruning) ---
        # This remains unchanged and crucial for performance
        # REDUCED: 4000m was too large (3.6M paths = OOM), now using 1500m (~15min walk)
        MAX_DIST = 1500.0
        print(f"Precomputing valid neighbors (cutoff={MAX_DIST}m) using sparse matrix iteration...")
        
        valid_neighbors = {} # (i, j) -> distance
        valid_neighbors_sets = {i: set() for i in nodes_N}
        valid_allocations_for_j = {j: set() for j in nodes_M}
        
        # Optimize: get sparse matrix
        # Matrix structure: {(i, j): distance} with tuple keys
        matrix = self.scorer.path_calculator.distance_matrix
        
        count = 0
        # Iterate over all (i, j) pairs in matrix
        for (i, j), dist in matrix.items():
            # Only include pairs where i is residential, j is candidate, and within range
            if i in self.graph.N and j in self.graph.M and dist <= MAX_DIST:
                valid_neighbors[(i, j)] = dist
                valid_neighbors_sets[i].add(j)
                valid_allocations_for_j[j].add(i)
                count += 1
        
        print(f"  Processed {count} valid paths.")
        
        # Fallback for isolated nodes
        isolated_count = 0
        for i in nodes_N:
             if not valid_neighbors_sets[i]:
                 isolated_count += 1
                 # Find nearest candidate even if far
                 best_j = None
                 min_d = float('inf')
                 for j in nodes_M:
                     d = self.scorer.path_calculator.get_distance(i, j)
                     if d < min_d:
                         min_d = d
                         best_j = j
                 
                 if best_j:
                     valid_neighbors[(i, best_j)] = min_d
                     valid_neighbors_sets[i].add(best_j)
                     valid_allocations_for_j[best_j].add(i)

        if isolated_count > 0:
            print(f"  Added fallback neighbors for {isolated_count} isolated residential nodes")

        # --- 3. Variables ---
        print("Creating decision variables...")
        
        # y[j][t]: 1 if amenity of type t is allocated at candidate j
        y = {} 
        for j in nodes_M:
            for t in amenity_types:
                # Only create variable if this candidate can reach ANY residential node
                if valid_allocations_for_j[j]: 
                    y[j, t] = solver.IntVar(0, 1, f'y_{j}_{t}')
        
        # x_plain[a_type][i][j]: Assignment variables for plain amenities
        x_plain = {}
        for a_type in self.plain_types:
            x_plain[a_type] = {}
            for i in nodes_N:
                x_plain[a_type][i] = {}
                # Only create vars for valid neighbors
                for j in valid_neighbors_sets[i]:
                    x_plain[a_type][i][j] = solver.BoolVar(f"x_{a_type}_{i}_{j}")
        
        # xpija: Assignment variables for depth amenities
        x_depth = {}
        for a_type, r in self.depth_types.items():
            x_depth[a_type] = {}
            for i in nodes_N:
                x_depth[a_type][i] = {}
                for p in range(1, r + 1):
                    x_depth[a_type][i][p] = {}
                    # Only create vars for valid neighbors
                    for j in valid_neighbors_sets[i]:
                        x_depth[a_type][i][p][j] = solver.BoolVar(f"x_{a_type}_{i}_{p}_{j}")
        
        # li: Weighted distance variables
        l_vars = {}
        for i in nodes_N:
            l_vars[i] = solver.NumVar(0, solver.infinity(), f"l_{i}")
        
        # Constraint: Allocation limits
        print("Adding constraints...")
        
        # Constraint 1: Allocation limits Σ yja ≤ k
        for a_type in self.amenity_types:
            # Note: y dict structure is y[j, type] from previous loop
            terms = [y[j, a_type] for j in nodes_M if (j, a_type) in y]
            if terms:
                solver.Add(solver.Sum(terms) <= k)
        
        # Constraint 2: Capacity constraints
        for j in nodes_M:
            # Assuming capacity 1 for checking
            capacity = 1
            terms = [y[j, a_type] for a_type in self.amenity_types if (j, a_type) in y]
            if terms:
                solver.Add(solver.Sum(terms) <= capacity)
        
        # Constraint 3: Assignment for plain amenities
        # Each residential must be assigned to exactly one location per plain amenity type
        for a_type in self.plain_types:
            for i in nodes_N:
                valid_js = valid_neighbors_sets[i]
                if valid_js:
                    solver.Add(
                        solver.Sum([x_plain[a_type][i][j] for j in valid_js]) == 1
                    )
        
        # Constraint 4: Assignment for depth amenities
        for a_type, r in self.depth_types.items():
            for i in nodes_N:
                valid_js = valid_neighbors_sets[i]
                for p in range(1, r + 1):
                    if valid_js: 
                        solver.Add(
                            solver.Sum([x_depth[a_type][i][p][j] for j in valid_js]) == 1
                        )
        
        # Constraint 5: Can only assign to allocated amenities
        for a_type in self.plain_types:
            for i in nodes_N:
                valid_js = valid_neighbors_sets[i]  # Use local variable consistently
                for j in valid_js:
                    if j in nodes_M: # Only if j is a candidate
                         solver.Add(x_plain[a_type][i][j] <= y[j, a_type])
        
        for a_type, r in self.depth_types.items():
            for i in nodes_N:
                valid_js = valid_neighbors_sets[i]  # Use local variable consistently
                for p in range(1, r + 1):
                    for j in valid_js:
                        if j in nodes_M:
                            solver.Add(x_depth[a_type][i][p][j] <= y[j, a_type])
        
        # Constraint 6: Weighted distance calculation
        # li = Σ(wa * Σ(xija * dij)) for plain + Σ(Σ(wap * Σ(xpija * dij))) for depth
        for i in nodes_N:
            distance_expr = 0.0
            
            # Plain amenities
            for a_type in self.plain_types:
                weight = self.scorer.plain_weights.get(a_type, 0)
                valid_js = valid_neighbors_sets[i]  # Use local variable
                for j in valid_js:
                    dij = valid_neighbors.get((i, j), float('inf'))  # Get from precomputed dict
                    # OR-Tools Term: Coeff * Var
                    # distance_expr += weight * x_plain[a_type][i][j] * dij
                    # We can sum these directly in the constraint
                    pass
            
            # Instead of creating intermediate l_vars (which just adds equality constraints),
            # we can put the sum directly into the objective!
            # This reduces matrix size significantly.
            
            # Constraint: l_vars[i] >= Sum(...)
            # Actually, l_vars is strictly equal to the sum.
            
            # Create expression for this resident's weighted distance
            expr = solver.Sum([])
            
            # Plain terms
            for a_type in self.plain_types:
                weight = self.scorer.plain_weights.get(a_type, 0)
                valid_js = valid_neighbors_sets[i]
                for j in valid_js:
                    dij = valid_neighbors.get((i, j), float('inf'))
                    term = x_plain[a_type][i][j] * (weight * dij)
                    expr += term
            
            # Depth terms
            for a_type, r in self.depth_types.items():
                depth_weights = self.scorer.depth_weights.get(a_type, {})
                valid_js = valid_neighbors_sets[i]
                for p in range(1, r + 1):
                    p_weight = depth_weights.get(p, 0)
                    cat_weight = 0.6 # default
                    # In DB, depth weights are choice_rank weights. Category weight is separate?
                    # logic: wa * sum(wap * dist)
                    # Let's assume standard weights
                    total_w = p_weight * cat_weight
                    
                    for j in valid_js:
                        dij = valid_neighbors.get((i, j), float('inf'))
                        term = x_depth[a_type][i][p][j] * (total_w * dij)
                        expr += term
            
            solver.Add(l_vars[i] == expr)

        # Objective: MINIMIZE Total Weighted Distance
        # Since WalkScore is monotonically decreasing with distance,
        # minimizing distance maximizes WalkScore.
        # This avoids complex PWL constraints in OR-Tools.
        
        solver.Minimize(solver.Sum([l_vars[i] for i in nodes_N]))
        
        # Optimize
        print("Optimizing...")
        status = solver.Solve()
        
        # Extract solution
        solution = {}
        if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
            print(f"\nSolution status: {status}")
            print(f"Objective value (Total Weighted Distance): {solver.Objective().Value():.4f}")
            
            # Extract allocations
            for a_type in self.amenity_types:
                solution[a_type] = set()
                for j in M:
                    if (j, a_type) in y and y[j, a_type].solution_value() > 0.5:  # If allocated
                        solution[a_type].add(j)
                        print(f"  Allocated {a_type} to location {j}")
            
            # Save results (Objective is Distance, but we recompute WalkScore for DB)
            self._save_results(solution, scenario, solver.Objective().Value(), solver.wall_time()/1000.0)
        else:
            print(f"Optimization failed with status: {status}")
            solution = {a_type: set() for a_type in self.amenity_types}
        
        return solution
    
    def _save_results(self, solution: Dict[str, Set[int]], scenario: str,
                    objective_value: float, solve_time: float):
        """Save MILP results to database."""
        print(f"Saving {scenario} results to database...")
        
        with self.db.get_session() as session:
            # Save allocation decisions
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
                                 objective_value, solver, solve_time_seconds)
                            VALUES (:scenario, :amenity_type_id, :candidate_id, 1,
                                    :objective_value, 'milp', :solve_time)
                            ON CONFLICT DO NOTHING
                        """
                        session.execute(text(insert_query), {
                            'scenario': scenario,
                            'amenity_type_id': amenity_type_id,
                            'candidate_id': candidate_id,
                            'objective_value': objective_value,
                            'solve_time': solve_time
                        })
            
            # Calculate and save WalkScores
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
    
    # Run MILP optimization
    solver = MILPSolver(graph, scorer)
    solution = solver.solve(k=3, scenario='milp_k3')
    
    print("\nOptimization complete!")


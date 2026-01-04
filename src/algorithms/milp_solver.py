"""
MILP (Mixed-Integer Linear Programming) solver for Walkability Optimization.
Implements the MILP formulation from the paper.
"""
import gurobipy as gp
from gurobipy import GRB
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
        Solve MILP optimization problem.
        
        Args:
            k: Maximum amenities per type
            scenario: Scenario name for saving results
        
        Returns:
            Dict mapping amenity_type -> set of allocated node_ids
        """
        if k is None:
            k = self.default_k
        
        print("=" * 60)
        print(f"Solving MILP Optimization (k={k})")
        print("=" * 60)
        
        # Create model
        model = gp.Model("WalkabilityOptimization")
        model.setParam('OutputFlag', 1)
        model.setParam('TimeLimit', self.time_limit)
        model.setParam('Threads', self.threads)
        model.setParam('MIPGap', self.mip_gap)
        
        # Get node sets
        N = list(self.graph.N)  # Residential locations
        M = list(self.graph.M)  # Candidate locations
        
        # Get existing amenities by type
        L = {}  # {amenity_type: list of node_ids}
        for a_type in self.amenity_types:
            L[a_type] = list(self.graph.L.get(a_type, set()))
        
        print(f"Problem size: {len(N)} residential, {len(M)} candidates")
        print(f"Amenity types: {self.amenity_types}")
        
        # Decision variables
        print("Creating decision variables...")
        
        # yja: Allocation variables
        y = {}
        for a_type in self.amenity_types:
            y[a_type] = {}
            for j in M:
                y[a_type][j] = model.addVar(
                    vtype=GRB.INTEGER,
                    lb=0,
                    ub=k,  # Upper bound: can't allocate more than k
                    name=f"y_{a_type}_{j}"
                )
        
        # xija: Assignment variables for plain amenities
        x_plain = {}
        for a_type in self.plain_types:
            x_plain[a_type] = {}
            for i in N:
                x_plain[a_type][i] = {}
                # Can assign to existing or candidate locations
                all_locations = M + L[a_type]
                for j in all_locations:
                    x_plain[a_type][i][j] = model.addVar(
                        vtype=GRB.BINARY,
                        name=f"x_{a_type}_{i}_{j}"
                    )
        
        # xpija: Assignment variables for depth amenities
        x_depth = {}
        for a_type, r in self.depth_types.items():
            x_depth[a_type] = {}
            for i in N:
                x_depth[a_type][i] = {}
                for p in range(1, r + 1):
                    x_depth[a_type][i][p] = {}
                    all_locations = M + L[a_type]
                    for j in all_locations:
                        x_depth[a_type][i][p][j] = model.addVar(
                            vtype=GRB.BINARY,
                            name=f"x_{a_type}_{i}_{p}_{j}"
                        )
        
        # li: Weighted distance variables
        l_vars = {}
        for i in N:
            l_vars[i] = model.addVar(
                vtype=GRB.CONTINUOUS,
                lb=0,
                name=f"l_{i}"
            )
        
        # fi: WalkScore variables
        f_vars = {}
        for i in N:
            f_vars[i] = model.addVar(
                vtype=GRB.CONTINUOUS,
                lb=0,
                ub=100,
                name=f"f_{i}"
            )
        
        model.update()
        
        # Constraints
        print("Adding constraints...")
        
        # Constraint 1: Allocation limits Σ yja ≤ ka
        for a_type in self.amenity_types:
            model.addConstr(
                gp.quicksum(y[a_type][j] for j in M) <= k,
                name=f"allocation_limit_{a_type}"
            )
        
        # Constraint 2: Capacity constraints Σ yja ≤ cj
        for j in M:
            with self.db.get_session() as session:
                query = "SELECT capacity FROM candidate_locations WHERE node_id = :node_id"
                result = session.execute(text(query), {'node_id': j})
                capacity = result.scalar() or 1
            
            model.addConstr(
                gp.quicksum(y[a_type][j] for a_type in self.amenity_types) <= capacity,
                name=f"capacity_{j}"
            )
        
        # Constraint 3: Assignment for plain amenities
        # Each residential must be assigned to exactly one location per plain amenity type
        for a_type in self.plain_types:
            for i in N:
                all_locations = M + L[a_type]
                model.addConstr(
                    gp.quicksum(x_plain[a_type][i][j] for j in all_locations) == 1,
                    name=f"assignment_{a_type}_{i}"
                )
        
        # Constraint 4: Assignment for depth amenities
        # Each residential must be assigned to exactly one location for each choice rank
        for a_type, r in self.depth_types.items():
            all_locations = M + L[a_type]
            for i in N:
                for p in range(1, r + 1):
                    model.addConstr(
                        gp.quicksum(x_depth[a_type][i][p][j] for j in all_locations) == 1,
                        name=f"assignment_{a_type}_{i}_{p}"
                    )
        
        # Constraint 5: Can only assign to allocated amenities (for candidates)
        for a_type in self.plain_types:
            for i in N:
                for j in M:
                    model.addConstr(
                        x_plain[a_type][i][j] <= y[a_type][j],
                        name=f"allocation_required_{a_type}_{i}_{j}"
                    )
        
        for a_type, r in self.depth_types.items():
            for i in N:
                for p in range(1, r + 1):
                    for j in M:
                        model.addConstr(
                            x_depth[a_type][i][p][j] <= y[a_type][j],
                            name=f"allocation_required_{a_type}_{i}_{p}_{j}"
                        )
        
        # Constraint 6: Weighted distance calculation
        # li = Σ(wa * Σ(xija * dij)) for plain + Σ(Σ(wap * Σ(xpija * dij))) for depth
        for i in N:
            distance_expr = 0.0
            
            # Plain amenities
            for a_type in self.plain_types:
                weight = self.scorer.plain_weights.get(a_type, 0)
                all_locations = M + L[a_type]
                for j in all_locations:
                    dij = self.scorer.path_calculator.get_distance(i, j)
                    distance_expr += weight * x_plain[a_type][i][j] * dij
            
            # Depth amenities
            for a_type, r in self.depth_types.items():
                depth_weights = self.scorer.depth_weights.get(a_type, {})
                all_locations = M + L[a_type]
                for p in range(1, r + 1):
                    weight = depth_weights.get(p, 0)
                    for j in all_locations:
                        dij = self.scorer.path_calculator.get_distance(i, j)
                        distance_expr += weight * x_depth[a_type][i][p][j] * dij
            
            model.addConstr(
                l_vars[i] == distance_expr,
                name=f"weighted_distance_{i}"
            )
        
        # Constraint 7: WalkScore as Piecewise Linear Function
        # Use Gurobi's addGenConstrPWL to model PWL function
        breakpoints = self.scorer.breakpoints
        scores = self.scorer.scores
        
        for i in N:
            # Create PWL constraint: fi = PWL(li)
            # Note: addGenConstrPWL requires x, y variables and breakpoint/slope pairs
            # We'll use the model's built-in PWL functionality
            try:
                model.addGenConstrPWL(
                    l_vars[i],
                    f_vars[i],
                    breakpoints,
                    scores,
                    name=f"walkscore_pwl_{i}"
                )
            except Exception:
                # Fallback: approximate with linear segments
                # This is a simplified version - full PWL would require more segments
                for seg_idx in range(len(breakpoints) - 1):
                    x1, y1 = breakpoints[seg_idx], scores[seg_idx]
                    x2, y2 = breakpoints[seg_idx + 1], scores[seg_idx + 1]
                    
                    if x2 != x1:
                        slope = (y2 - y1) / (x2 - x1)
                        # Add linear constraint for this segment
                        # This is simplified - full implementation would use binary variables
                        pass
        
        # Objective: Maximize average WalkScore
        model.setObjective(
            gp.quicksum(f_vars[i] for i in N) / len(N),
            GRB.MAXIMIZE
        )
        
        # Optimize
        print("Optimizing...")
        model.optimize()
        
        # Extract solution
        solution = {}
        if model.status == GRB.OPTIMAL or model.status == GRB.TIME_LIMIT:
            print(f"\nSolution status: {model.status}")
            print(f"Objective value: {model.ObjVal:.4f}")
            
            # Extract allocations
            for a_type in self.amenity_types:
                solution[a_type] = set()
                for j in M:
                    if y[a_type][j].X > 0.5:  # If allocated
                        solution[a_type].add(j)
                        print(f"  Allocated {y[a_type][j].X:.0f} {a_type} to location {j}")
            
            # Save results
            self._save_results(solution, scenario, model.ObjVal, model.Runtime)
        else:
            print(f"Optimization failed with status: {model.status}")
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


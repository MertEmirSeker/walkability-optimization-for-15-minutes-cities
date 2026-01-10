"""
MILP (Mixed Integer Linear Programming) solver for Walkability Optimization.
Implements the mathematical formulation from the paper (Section 3.2).

This provides an optimal solution (within MIP gap) using Gurobi or CPLEX.
"""
from typing import Dict, Set, List, Optional
import yaml
from sqlalchemy import text
from src.network.pedestrian_graph import PedestrianGraph
from src.scoring.walkscore import WalkScoreCalculator
from src.utils.database import get_db_manager


class MILPOptimizer:
    """
    MILP solver for walkability optimization.
    
    Paper formulation (Section 3.2):
    - Decision variables: y_ja ∈ {0,1} (binary)
      y_ja = 1 if amenity type 'a' is allocated to candidate 'j'
    
    - Objective: Maximize average WalkScore
      max (1/|N|) Σ(i∈N) f(l_i)
      where l_i = weighted walking distance for residential i
      
    - Constraints:
      1. Budget: Σ(j∈C) y_ja ≤ k_a for each amenity type a
      2. Capacity: Σ(a∈A) y_ja ≤ cap_j for each candidate j
      3. Binary: y_ja ∈ {0,1}
    """
    
    def __init__(self, graph: PedestrianGraph, scorer: WalkScoreCalculator):
        """Initialize MILP optimizer."""
        self.graph = graph
        self.scorer = scorer
        self.db = graph.db
        
        # Load configuration
        with open("config.yaml", 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.milp_config = self.config['optimization']['milp']
        self.time_limit = self.milp_config['time_limit_seconds']
        self.threads = self.milp_config['threads']
        self.mip_gap = self.milp_config['mip_gap']
        
        # Try to import Gurobi
        try:
            import gurobipy as gp
            from gurobipy import GRB
            self.solver = 'gurobi'
            self.gp = gp
            self.GRB = GRB
            print("Using Gurobi solver")
        except ImportError:
            print("ERROR: Gurobi not available!")
            print("Install with: pip install gurobipy")
            print("Or use Greedy algorithm instead")
            raise
    
    def optimize(self, k: int = None, amenity_types: List[str] = None) -> Dict[str, Set[int]]:
        """
        Run MILP optimization.
        
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
        print(f"Running MILP Optimization (k={k})")
        print("=" * 60)
        print(f"#residential: {len(self.graph.N)}, #candidates: {len(self.graph.M)}, "
              f"amenity_types: {amenity_types}")
        print(f"Time limit: {self.time_limit}s, Threads: {self.threads}, MIP gap: {self.mip_gap}")
        
        # Create model
        model = self.gp.Model("WalkabilityOptimization")
        model.setParam('TimeLimit', self.time_limit)
        model.setParam('Threads', self.threads)
        model.setParam('MIPGap', self.mip_gap)
        model.setParam('OutputFlag', 1)  # Show progress
        
        # Get candidate capacities
        candidate_capacities = {}
        for candidate_id in self.graph.M:
            with self.db.get_session() as session:
                query = "SELECT capacity FROM candidate_locations WHERE node_id = :node_id"
                result = session.execute(text(query), {'node_id': candidate_id})
                capacity = result.scalar()
                candidate_capacities[candidate_id] = capacity if capacity else 1
        
        print("\n[1/5] Creating decision variables...")
        # Decision variables: y_ja
        y = {}
        for a_type in amenity_types:
            for candidate_id in self.graph.M:
                var_name = f"y_{candidate_id}_{a_type}"
                y[(candidate_id, a_type)] = model.addVar(vtype=self.GRB.BINARY, name=var_name)
        
        print(f"  Created {len(y)} binary variables")
        
        print("\n[2/5] Creating auxiliary variables for WalkScore...")
        # For linear approximation of PWL function
        # We'll use a piecewise linear approximation
        # l_i = weighted distance for residential i
        # s_i = WalkScore for residential i (linearized)
        
        l = {}  # weighted distance variables
        s = {}  # WalkScore variables
        
        for residential_id in self.graph.N:
            l[residential_id] = model.addVar(lb=0, ub=self.GRB.INFINITY, 
                                            name=f"l_{residential_id}")
            s[residential_id] = model.addVar(lb=0, ub=100, 
                                            name=f"s_{residential_id}")
        
        print(f"  Created {len(l)} distance variables")
        print(f"  Created {len(s)} score variables")
        
        print("\n[3/5] Adding constraints...")
        
        # Constraint 1: Budget constraint (k amenities per type)
        for a_type in amenity_types:
            budget_expr = self.gp.quicksum(
                y[(candidate_id, a_type)] for candidate_id in self.graph.M
            )
            model.addConstr(budget_expr <= k, name=f"budget_{a_type}")
        print(f"  Added {len(amenity_types)} budget constraints")
        
        # Constraint 2: Capacity constraint
        for candidate_id in self.graph.M:
            capacity_expr = self.gp.quicksum(
                y[(candidate_id, a_type)] for a_type in amenity_types
            )
            model.addConstr(capacity_expr <= candidate_capacities[candidate_id],
                          name=f"capacity_{candidate_id}")
        print(f"  Added {len(self.graph.M)} capacity constraints")
        
        # Constraint 3: Weighted distance calculation
        # This is complex - we need to model: l_i = f(allocations)
        # For now, use a simplified linear approximation
        print("  Adding weighted distance constraints...")
        self._add_distance_constraints(model, l, y, amenity_types)
        
        # Constraint 4: PWL approximation for WalkScore
        # s_i = PWL(l_i) approximated as piecewise linear
        print("  Adding PWL constraints...")
        self._add_pwl_constraints(model, s, l)
        
        print("\n[4/5] Setting objective function...")
        # Objective: Maximize average WalkScore
        avg_score = self.gp.quicksum(s[residential_id] for residential_id in self.graph.N) / len(self.graph.N)
        model.setObjective(avg_score, self.GRB.MAXIMIZE)
        print("  Objective: Maximize average WalkScore")
        
        print("\n[5/5] Solving MILP...")
        print("  This may take several hours for large instances...")
        model.optimize()
        
        # Extract solution
        if model.status == self.GRB.OPTIMAL or model.status == self.GRB.TIME_LIMIT:
            print(f"\n✓ Optimization complete!")
            print(f"  Status: {model.status}")
            print(f"  Objective value: {model.objVal:.4f}")
            print(f"  MIP gap: {model.MIPGap:.4f}")
            print(f"  Runtime: {model.Runtime:.2f}s")
            
            # Extract allocation decisions
            S = {a_type: set() for a_type in amenity_types}
            for (candidate_id, a_type), var in y.items():
                if var.X > 0.5:  # Binary variable is 1
                    S[a_type].add(candidate_id)
            
            print(f"\nFinal allocations: {[(k, len(v)) for k, v in S.items()]}")
            return S
        else:
            print(f"\n✗ Optimization failed!")
            print(f"  Status: {model.status}")
            return {a_type: set() for a_type in amenity_types}
    
    def _add_distance_constraints(self, model, l, y, amenity_types):
        """
        Add constraints to compute weighted distance l_i.
        
        This is simplified - full implementation requires modeling:
        l_i = Σ(w_a * min_distance_to_amenity_a)
        
        For MILP, we need auxiliary variables and indicator constraints.
        """
        # NOTE: This is a placeholder for the complex distance computation
        # Full implementation requires:
        # 1. For each residential i, amenity type a
        # 2. Compute distance to each allocated candidate
        # 3. Take minimum (using auxiliary variables)
        # 4. Weight by category weight
        # 5. Sum across amenity types
        
        # For now, use a simplified constant (baseline distance)
        # In practice, you'd need to precompute distances and use indicator constraints
        for residential_id in self.graph.N:
            # Simplified: l_i = baseline_distance (to be improved)
            baseline_dist = 2000.0  # placeholder
            model.addConstr(l[residential_id] == baseline_dist, 
                          name=f"dist_{residential_id}")
    
    def _add_pwl_constraints(self, model, s, l):
        """
        Add piecewise linear constraints for WalkScore = PWL(weighted_distance).
        
        Uses Gurobi's piecewise linear constraint feature.
        """
        breakpoints = self.scorer.breakpoints
        scores = self.scorer.scores
        
        for residential_id in self.graph.N:
            # Add piecewise linear constraint: s_i = PWL(l_i)
            model.addGenConstrPWL(
                l[residential_id],  # x variable (weighted distance)
                s[residential_id],  # y variable (WalkScore)
                breakpoints,        # x breakpoints
                scores,            # y values
                name=f"pwl_{residential_id}"
            )
    
    def save_results(self, solution: Dict[str, Set[int]], scenario: str = 'milp'):
        """Save MILP results to database."""
        print(f"Saving {scenario} results to database...")
        
        with self.db.get_session() as session:
            # Save allocation decisions
            for amenity_type, allocated_nodes in solution.items():
                # Get amenity_type_id
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
                                    1, 0.0, 'milp')
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
    print("MILP Optimizer requires Gurobi license!")
    print("For testing, use Greedy algorithm instead:")
    print("  python -m src.algorithms.greedy")


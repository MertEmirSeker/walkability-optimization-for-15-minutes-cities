"""
Evaluation metrics and success criteria checking.
Implements success criteria from the presentation.
"""
from typing import Dict, Set, List, Tuple
import yaml
from sqlalchemy import text
from src.network.pedestrian_graph import PedestrianGraph
from src.scoring.walkscore import WalkScoreCalculator
from src.utils.database import get_db_manager


class MetricsEvaluator:
    """Evaluates optimization results against success criteria."""
    
    def __init__(self, graph: PedestrianGraph, scorer: WalkScoreCalculator,
                 config_path: str = "config.yaml"):
        """Initialize metrics evaluator."""
        self.graph = graph
        self.scorer = scorer
        self.db = graph.db
        
        # Load configuration
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.success_criteria = self.config['success_criteria']
        self.fifteen_minutes_meters = self.config['walkscore']['fifteen_minutes_meters']
    
    def evaluate_scenario(self, scenario: str, 
                         solution: Dict[str, Set[int]] = None) -> Dict:
        """
        Evaluate a scenario against success criteria.
        
        Args:
            scenario: Scenario name (e.g., 'baseline', 'greedy_k3')
            solution: Optimization solution (if None, loads from database)
        
        Returns:
            Dict with evaluation metrics and success status
        """
        print(f"\n{'='*60}")
        print(f"Evaluating scenario: {scenario}")
        print(f"{'='*60}\n")
        
        # Load solution if not provided (SKIP for baseline)
        if solution is None and scenario != 'baseline':
            solution = self._load_solution(scenario)
            if solution:
                print(f"Loaded solution for {scenario} with {sum(len(v) for v in solution.values())} allocated amenities")
        
        # Load WalkScores
        baseline_scores = self._load_scores('baseline')
        scenario_scores = self._load_scores(scenario)
        
        if not scenario_scores:
            print(f"No scores found for scenario: {scenario}")
            return {}
        
        # Calculate metrics
        metrics = {}
        
        # 1. WalkScore increase
        baseline_avg = self.scorer.get_average_walkscore(baseline_scores)
        scenario_avg = self.scorer.get_average_walkscore(scenario_scores)
        walkscore_increase = scenario_avg - baseline_avg
        metrics['walkscore_increase'] = walkscore_increase
        metrics['baseline_avg_walkscore'] = baseline_avg
        metrics['scenario_avg_walkscore'] = scenario_avg
        
        print(f"Baseline average WalkScore: {baseline_avg:.2f}")
        print(f"Scenario average WalkScore: {scenario_avg:.2f}")
        print(f"WalkScore increase: {walkscore_increase:.2f} points")
        
        # 2. Average walking distance reduction
        baseline_distances = self._calculate_avg_distances(baseline_scores)
        scenario_distances = self._calculate_avg_distances(scenario_scores, solution)
        metrics['baseline_avg_distance'] = baseline_distances
        metrics['scenario_avg_distance'] = scenario_distances
        
        print(f"\nBaseline average distance: {baseline_distances:.2f} m")
        print(f"Scenario average distance: {scenario_distances:.2f} m")
        
        # 3. 15-minute coverage
        coverage = self._calculate_coverage(solution)
        metrics['coverage_percent'] = coverage
        
        print(f"\n15-minute coverage: {coverage:.2f}%")
        
        # Check success criteria
        success = self._check_success_criteria(metrics)
        metrics['success'] = success
        
        print(f"\n{'='*60}")
        print("Success Criteria Check:")
        print(f"{'='*60}")
        print(f"✓ Coverage ≥ {self.success_criteria['residential_coverage_percentage']}%: "
              f"{coverage:.2f}% {'✓' if success['coverage'] else '✗'}")
        print(f"✓ WalkScore increase ≥ {self.success_criteria['min_walkscore_increase']} points: "
              f"{walkscore_increase:.2f} {'✓' if success['walkscore'] else '✗'}")
        print(f"\nOverall: {'SUCCESS ✓' if all(success.values()) else 'PARTIAL/FAILED ✗'}")
        print(f"{'='*60}\n")
        
        return metrics
    
    def _load_scores(self, scenario: str) -> Dict[int, float]:
        """Load WalkScores from database."""
        with self.db.get_session() as session:
            query = """
                SELECT residential_id, walkscore
                FROM walkability_scores
                WHERE scenario = :scenario
            """
            result = session.execute(text(query), {'scenario': scenario})
            return {row[0]: float(row[1]) for row in result}

    def _load_solution(self, scenario: str) -> Dict[str, Set[int]]:
        """Load optimization solution from database."""
        solution = {}
        with self.db.get_session() as session:
            # Join with amenity_types to get type name
            query = """
                SELECT t.type_name, r.candidate_id
                FROM optimization_results r
                JOIN amenity_types t ON r.amenity_type_id = t.amenity_type_id
                WHERE r.scenario = :scenario
            """
            result = session.execute(text(query), {'scenario': scenario})
            
            for row in result:
                amenity_type = row[0]
                location_id = row[1]
                
                if amenity_type not in solution:
                    solution[amenity_type] = set()
                solution[amenity_type].add(location_id)
                
        return solution
    
    def _calculate_avg_distances(self, scores: Dict[int, float],
                                solution: Dict[str, Set[int]] = None) -> float:
        """Calculate average walking distance."""
        total_distance = 0.0
        count = 0
        
        for residential_id in self.graph.N:
            weighted_dist = self.scorer.compute_weighted_distance(
                residential_id, solution
            )
            total_distance += weighted_dist
            count += 1
        
        return total_distance / count if count > 0 else 0.0
    
    def _calculate_coverage(self, solution: Dict[str, Set[int]] = None) -> float:
        """
        Calculate percentage of residential locations that can reach
        all amenities within 15 minutes.
        """
        if solution is None:
            solution = {}
        
        covered_count = 0
        total_count = 0
        
        for residential_id in self.graph.N:
            total_count += 1
            can_reach_all = True
            
            # Check each amenity type defined in config
            amenity_types = list(self.config['amenities'].keys())
            for amenity_type in amenity_types:
                # Get nearest amenity location
                distances = self.scorer.path_calculator.get_distances_to_amenities(
                    residential_id, amenity_type
                )
                
                # Add allocated locations
                if amenity_type in solution:
                    for allocated_id in solution[amenity_type]:
                        dist = self.scorer.path_calculator.get_distance(
                            residential_id, allocated_id
                        )
                        distances[allocated_id] = dist
                
                if distances:
                    min_distance = min(distances.values())
                    if min_distance > self.fifteen_minutes_meters:
                        can_reach_all = False
                        break
                else:
                    can_reach_all = False
                    break
            
            if can_reach_all:
                covered_count += 1
        
        return (covered_count / total_count * 100) if total_count > 0 else 0.0
    
    def _check_success_criteria(self, metrics: Dict) -> Dict[str, bool]:
        """Check if success criteria are met."""
        return {
            'coverage': metrics.get('coverage_percent', 0) >= \
                       self.success_criteria['residential_coverage_percentage'],
            'walkscore': metrics.get('walkscore_increase', 0) >= \
                        self.success_criteria['min_walkscore_increase']
        }
    
    def generate_report(self, scenarios: List[str] = None) -> str:
        """Generate evaluation report for multiple scenarios."""
        if scenarios is None:
            scenarios = ['baseline', 'greedy_k3', 'milp_k3']
        
        report = []
        report.append("=" * 80)
        report.append("WALKABILITY OPTIMIZATION EVALUATION REPORT")
        report.append("=" * 80)
        report.append("")
        
        for scenario in scenarios:
            metrics = self.evaluate_scenario(scenario)
            if metrics:
                report.append(f"Scenario: {scenario}")
                report.append(f"  Average WalkScore: {metrics.get('scenario_avg_walkscore', 0):.2f}")
                report.append(f"  WalkScore Increase: {metrics.get('walkscore_increase', 0):.2f} points")
                report.append(f"  15-Minute Coverage: {metrics.get('coverage_percent', 0):.2f}%")
                report.append(f"  Success: {'✓' if metrics.get('success', {}).get('coverage') and metrics.get('success', {}).get('walkscore') else '✗'}")
                report.append("")
        
        report.append("=" * 80)
        
        return "\n".join(report)


if __name__ == "__main__":
    from src.network.pedestrian_graph import PedestrianGraph
    from src.network.shortest_paths import ShortestPathCalculator
    from src.scoring.walkscore import WalkScoreCalculator
    
    print("Loading data...")
    graph = PedestrianGraph()
    graph.load_from_database()
    
    path_calc = ShortestPathCalculator(graph)
    path_calc.load_from_database()
    
    scorer = WalkScoreCalculator(graph, path_calc)
    
    # Evaluate
    evaluator = MetricsEvaluator(graph, scorer)
    report = evaluator.generate_report()
    print(report)


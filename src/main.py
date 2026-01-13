"""
Main pipeline for Walkability Optimization.
Orchestrates data loading, graph creation, optimization, and visualization.
"""
import argparse
import sys
import os

# Add project root to path (works from both src/ and project root)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.network.pedestrian_graph import PedestrianGraph
from src.network.shortest_paths import ShortestPathCalculator
from src.scoring.walkscore import WalkScoreCalculator
from src.algorithms.greedy import GreedyOptimizer
from src.visualization.map_visualizer import MapVisualizer
from src.evaluation.metrics import MetricsEvaluator
from src.utils.database import get_db_manager


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(description='Walkability Optimization Pipeline')
    parser.add_argument('--skip-data-load', action='store_true',
                       help='Skip OSM data loading (use existing data)')
    parser.add_argument('--skip-distances', action='store_true',
                       help='Skip distance computation (use existing)')
    parser.add_argument('--skip-baseline', action='store_true',
                       help='Skip baseline score computation')
    parser.add_argument('--algorithm', choices=['greedy'],
                       default='greedy', help='Optimization algorithm to run (greedy)')
    parser.add_argument('--k', type=int, default=3,
                       help='Number of amenities to allocate per type')
    parser.add_argument('--visualize', action='store_true',
                       help='Generate visualization maps')
    parser.add_argument('--evaluate', action='store_true',
                       help='Evaluate results against success criteria')
    parser.add_argument('--record-demo', action='store_true',
                       help='Record optimization iterations for demo replay')
    parser.add_argument('--demo-mode', type=str,
                       help='Replay recorded optimization (e.g., greedy_k3)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("WALKABILITY OPTIMIZATION PIPELINE")
    print("Balıkesir City Center")
    print("=" * 80)
    print()
    
    # Step 1: Database connection
    print("Step 1: Connecting to database...")
    db = get_db_manager()
    if not db.check_connection():
        print("ERROR: Database connection failed!")
        print("Please ensure PostgreSQL is running and database is created.")
        print("Run: createdb walkability_db")
        print("Run: psql walkability_db < database/schema.sql")
        return 1
    print("✓ Database connected\n")
    
    # Step 2: Load OSM data (if needed)
    if not args.skip_data_load:
        print("Step 2: Loading OSM data...")
        from src.data_collection.osm_loader import OSMDataLoader
        loader = OSMDataLoader()
        try:
            loader.load_all_data()
            print("✓ OSM data loaded\n")
        except Exception as e:
            print(f"ERROR loading OSM data: {e}")
            print("Continuing with existing data...\n")
    else:
        print("Step 2: Skipping OSM data loading (using existing data)\n")
    
    # Step 3: Create pedestrian graph
    print("Step 3: Creating pedestrian network graph...")
    graph = PedestrianGraph()
    try:
        graph.load_from_database()
        graph.print_statistics()
        
        # Validate connectivity
        validation = graph.validate_connectivity()
        if not validation.get('is_connected', False):
            print("WARNING: Graph is not fully connected!")
            print("Some locations may be unreachable.\n")
        else:
            print("✓ Graph created and validated\n")
    except Exception as e:
        print(f"ERROR creating graph: {e}")
        return 1
    
    # Step 4: Compute shortest paths
    if not args.skip_distances:
        print("Step 4: Computing shortest path distances...")
        path_calc = ShortestPathCalculator(graph)
        try:
            # Try loading from database first
            path_calc.load_from_database()
            if len(path_calc.distance_matrix) == 0:
                print("No distances in database, computing...")
                path_calc.compute_all_distances()
            else:
                print("✓ Loaded distances from database")
            path_calc.print_statistics()
            print()
        except Exception as e:
            print(f"ERROR computing distances: {e}")
            return 1
    else:
        print("Step 4: Skipping distance computation (using existing)\n")
        path_calc = ShortestPathCalculator(graph)
        path_calc.load_from_database()
    
    # Step 5: Compute baseline WalkScores
    if not args.skip_baseline:
        print("Step 5: Computing baseline WalkScores...")
        scorer = WalkScoreCalculator(graph, path_calc)
        try:
            baseline_scores = scorer.compute_baseline_scores()
            scorer.print_statistics(baseline_scores)
            avg_baseline = scorer.get_average_walkscore(baseline_scores)
            print(f"Baseline average WalkScore: {avg_baseline:.2f}")
            
            # CRITICAL FIX: compute_baseline_scores uses batch loading which CLEARS the distance matrix!
            # We must reload the full distance matrix for the optimization algorithms to work correctly.
            print("\n[System] Reloading full distance matrix for optimization...")
            if not args.skip_distances:
                 path_calc.load_from_database()
            else:
                 # Even if we skipped calculation, we need to load what's in DB
                 path_calc.load_from_database()
                 
            print("✓ Distance matrix restored\n")

        except Exception as e:
            print(f"ERROR computing baseline scores: {e}")
            return 1
    else:
        print("Step 5: Skipping baseline computation (using existing)\n")
        scorer = WalkScoreCalculator(graph, path_calc)
    
    # Step 6: Run optimization
    solutions = {}
    
    # Demo Mode: Replay recorded optimization
    if args.demo_mode:
        print(f"=" * 80)
        print(f"DEMO MODE: Replaying {args.demo_mode}")
        print(f"=" * 80)
        
        from src.optimization.demo_player import DemoPlayer
        player = DemoPlayer(db, graph, scorer)
        
        try:
            def on_iteration(iteration_num, progress, objective, improvement, amenity_type, node_id):
                """Callback for progress updates."""
                if iteration_num % 5 == 0:
                    print(f"  Iteration {iteration_num}: {progress:.1f}% | "
                          f"Obj: {objective:.4f} | +{improvement:.6f}")
                    # Emit progress for UI
                    print(f"::PROGRESS::{progress:.1f}::Demo Replay::{iteration_num} iterations", flush=True)
            
            solution = player.replay(args.demo_mode, 
                                    on_iteration_callback=on_iteration,
                                    delay_per_iteration=0.5)
            
            # Quick validation
            if len(solution) > 0:
                validation = player.quick_validate(solution, sample_size=1000)
                print(f"Validation (n={validation['sample_size']}): {validation['sample_objective']:.4f}")
            
            solutions['greedy'] = solution
            print("✓ Demo replay completed\\n")
            
        except Exception as e:
            print(f"ERROR in demo replay: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    # Normal Optimization
    elif args.algorithm in ['greedy', 'both']:
        print("Step 6a: Running Greedy optimization...")
        greedy_opt = GreedyOptimizer(graph, scorer)
        try:
            greedy_solution = greedy_opt.optimize(k=args.k, record_demo=args.record_demo)
            greedy_opt.save_results(greedy_solution, scenario=f'greedy_k{args.k}')
            solutions['greedy'] = greedy_solution
            print("✓ Greedy optimization completed\n")
        except Exception as e:
            print(f"ERROR in greedy optimization: {e}")
            import traceback
            traceback.print_exc()
    

    
    # Step 7: Visualization
    if args.visualize and solutions:
        print("Step 7: Creating visualizations...")
        visualizer = MapVisualizer(graph, scorer)
        
        try:
            # Baseline maps (both normal and heatmap)
            visualizer.create_baseline_map("visualizations/baseline_map.html")
            visualizer.create_baseline_heatmap("visualizations/baseline_heatmap.html")
            
            # Optimized maps (both normal and heatmap for each algorithm)
            for algo_name, solution in solutions.items():
                if solution:
                    scenario = f'{algo_name}_k{args.k}'
                    
                    # Normal map (blue dots + amenities)
                    visualizer.create_optimized_map(
                        solution, scenario, f"visualizations/{scenario}_map.html"
                    )
                    
                    # Heatmap (gradient visualization)
                    visualizer.create_optimized_heatmap(
                        solution, scenario, f"visualizations/{scenario}_heatmap.html"
                    )
                    
                    # Comparison map
                    visualizer.create_comparison_map(
                        solution, scenario, f"visualizations/{scenario}_comparison.html"
                    )
            
            print("✓ Visualizations created\n")
        except Exception as e:
            print(f"ERROR creating visualizations: {e}")
            import traceback
            traceback.print_exc()
    
    # Step 8: Evaluation
    if args.evaluate:
        print("Step 8: Evaluating results...")
        evaluator = MetricsEvaluator(graph, scorer)
        
        scenarios_to_evaluate = ['baseline']
        if 'greedy' in solutions:
            scenarios_to_evaluate.append(f'greedy_k{args.k}')
        if 'milp' in solutions:
            scenarios_to_evaluate.append(f'milp_k{args.k}')
        
        try:
            report = evaluator.generate_report(scenarios_to_evaluate)
            print(report)
            
            # Save report
            os.makedirs('results', exist_ok=True)
            with open(f'results/evaluation_report.txt', 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\nReport saved to results/evaluation_report.txt")
        except Exception as e:
            print(f"ERROR in evaluation: {e}")
            import traceback
            traceback.print_exc()
    
    print("=" * 80)
    print("PIPELINE COMPLETED")
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
Main pipeline script for walkability optimization.

This script runs the complete pipeline:
1. Load OSM data
2. Build pedestrian network
3. Compute shortest paths
4. Calculate baseline WalkScores
5. Run optimization
6. Generate visualizations
7. Save results
"""
import argparse
import time
import json
from datetime import datetime
from pathlib import Path


def run_pipeline(args):
    """Run the complete optimization pipeline."""
    
    print("="*70)
    print("WALKABILITY OPTIMIZATION PIPELINE")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Solver: {args.solver}")
    print(f"k (amenities per type): {args.k}")
    print("="*70)
    
    start_time = time.time()
    results = {}
    
    # Create results directory
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    (results_dir / "maps").mkdir(exist_ok=True)
    (results_dir / "plots").mkdir(exist_ok=True)
    (results_dir / "data").mkdir(exist_ok=True)
    
    try:
        # Step 1: Load or verify data
        if args.load_data:
            print("\n" + "="*70)
            print("STEP 1: Loading OSM Data")
            print("="*70)
            
            from src.data_collection.osm_loader import OSMLoader
            
            loader = OSMLoader()
            stats = loader.load_all()
            results['data_loading'] = stats
            
            print(f"\n✓ Data loading complete!")
            print(f"  Residential: {stats.get('residential', 0)}")
            print(f"  Candidates: {stats.get('candidates', 0)}")
            print(f"  Amenities: {stats.get('amenities', 0)}")
        
        # Step 2: Build pedestrian network
        print("\n" + "="*70)
        print("STEP 2: Building Pedestrian Network")
        print("="*70)
        
        from src.network.pedestrian_graph import PedestrianGraph
        
        graph = PedestrianGraph()
        
        if args.rebuild_network:
            graph.build_from_database()
            graph.save_to_database()
        else:
            graph.load_from_database()
        
        results['network'] = {
            'nodes': len(graph.G.nodes()),
            'edges': len(graph.G.edges()),
            'residential': len(graph.N),
            'candidates': len(graph.M)
        }
        
        print(f"\n✓ Network ready!")
        print(f"  Nodes: {results['network']['nodes']}")
        print(f"  Edges: {results['network']['edges']}")
        print(f"  Residential: {results['network']['residential']}")
        print(f"  Candidates: {results['network']['candidates']}")
        
        # Step 3: Compute shortest paths
        print("\n" + "="*70)
        print("STEP 3: Computing Shortest Paths")
        print("="*70)
        
        from src.network.shortest_paths import ShortestPathCalculator
        
        path_calc = ShortestPathCalculator(graph)
        
        if args.recompute_paths:
            path_calc.compute_all_pairs()
            path_calc.save_to_database()
        else:
            path_calc.load_from_database()
        
        results['paths'] = {
            'total_pairs': len(path_calc.distances)
        }
        
        print(f"\n✓ Shortest paths ready!")
        print(f"  Computed pairs: {results['paths']['total_pairs']}")
        
        # Step 4: Calculate baseline WalkScores
        print("\n" + "="*70)
        print("STEP 4: Calculating Baseline WalkScores")
        print("="*70)
        
        from src.scoring.walkscore import WalkScoreCalculator
        
        scorer = WalkScoreCalculator(graph, path_calc)
        
        baseline_scores = scorer.compute_baseline_scores(save_to_db=True)
        baseline_avg = sum(baseline_scores.values()) / len(baseline_scores)
        baseline_stats = scorer.get_statistics(baseline_scores)
        
        results['baseline'] = {
            'average_walkscore': baseline_avg,
            'statistics': baseline_stats
        }
        
        print(f"\n✓ Baseline WalkScores computed!")
        print(f"  Average: {baseline_avg:.2f}")
        print(f"  Coverage ≥50: {baseline_stats['scores_above_50']} ({100*baseline_stats['scores_above_50']/baseline_stats['count']:.1f}%)")
        
        # Step 5: Run optimization
        print("\n" + "="*70)
        print("STEP 5: Running Optimization")
        print("="*70)
        
        if args.solver == 'greedy':
            from src.algorithms.greedy import GreedyOptimizer
            optimizer = GreedyOptimizer(graph, scorer)
        elif args.solver == 'milp':
            from src.algorithms.milp import MILPOptimizer
            optimizer = MILPOptimizer(graph, scorer)
        elif args.solver == 'cp':
            from src.algorithms.cp import CPOptimizer
            optimizer = CPOptimizer(graph, scorer)
        else:
            raise ValueError(f"Unknown solver: {args.solver}")
        
        solution = optimizer.optimize(k=args.k)
        
        # Calculate optimized WalkScores
        print("\nComputing optimized WalkScores...")
        optimized_scores = {}
        for residential_id in graph.N:
            optimized_scores[residential_id] = scorer.compute_walkscore(residential_id, solution)
        
        optimized_avg = sum(optimized_scores.values()) / len(optimized_scores)
        optimized_stats = scorer.get_statistics(optimized_scores)
        
        improvement = optimized_avg - baseline_avg
        improvement_pct = 100 * improvement / baseline_avg if baseline_avg > 0 else 0
        
        results['optimization'] = {
            'solver': args.solver,
            'k': args.k,
            'solution': {k: list(v) for k, v in solution.items()},
            'total_allocations': sum(len(v) for v in solution.values()),
            'average_walkscore': optimized_avg,
            'improvement': improvement,
            'improvement_percent': improvement_pct,
            'statistics': optimized_stats
        }
        
        print(f"\n✓ Optimization complete!")
        print(f"  Baseline avg: {baseline_avg:.2f}")
        print(f"  Optimized avg: {optimized_avg:.2f}")
        print(f"  Improvement: +{improvement:.2f} ({improvement_pct:+.2f}%)")
        print(f"  Total allocations: {results['optimization']['total_allocations']}")
        
        # Save results to database
        optimizer.save_results(solution, scenario=f"{args.solver}_k{args.k}")
        
        # Step 6: Generate visualizations
        if not args.skip_viz:
            print("\n" + "="*70)
            print("STEP 6: Generating Visualizations")
            print("="*70)
            
            from src.visualization.map_plotter import MapPlotter, StatisticsPlotter
            
            # Maps
            map_plotter = MapPlotter(graph, scorer, graph.db)
            
            print("\nCreating walkability map...")
            map_plotter.plot_walkability_map(
                optimized_scores, 
                solution,
                "results/maps/walkability_map.html"
            )
            
            print("Creating comparison map...")
            map_plotter.plot_comparison_map(
                baseline_scores,
                optimized_scores,
                solution,
                "results/maps/comparison_map.html"
            )
            
            # Plots
            stats_plotter = StatisticsPlotter()
            
            print("Creating distribution plots...")
            stats_plotter.plot_walkscore_distribution(
                baseline_scores,
                "results/plots/baseline_distribution.png"
            )
            
            stats_plotter.plot_walkscore_distribution(
                optimized_scores,
                "results/plots/optimized_distribution.png"
            )
            
            print("Creating comparison plots...")
            stats_plotter.plot_comparison(
                baseline_scores,
                optimized_scores,
                "results/plots/comparison.png"
            )
            
            print(f"\n✓ Visualizations complete!")
            print(f"  Maps: results/maps/")
            print(f"  Plots: results/plots/")
        
        # Step 7: Save results
        print("\n" + "="*70)
        print("STEP 7: Saving Results")
        print("="*70)
        
        results['pipeline'] = {
            'completed_at': datetime.now().isoformat(),
            'total_time_seconds': time.time() - start_time
        }
        
        results_file = f"results/data/results_{args.solver}_k{args.k}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✓ Results saved to {results_file}")
        
        # Print summary
        print("\n" + "="*70)
        print("PIPELINE SUMMARY")
        print("="*70)
        print(f"\nTotal time: {time.time() - start_time:.2f}s")
        print(f"Solver: {args.solver}")
        print(f"k: {args.k}")
        print(f"\nBaseline:")
        print(f"  Average WalkScore: {baseline_avg:.2f}")
        print(f"  Coverage ≥50: {100*baseline_stats['scores_above_50']/baseline_stats['count']:.1f}%")
        print(f"\nOptimized:")
        print(f"  Average WalkScore: {optimized_avg:.2f}")
        print(f"  Coverage ≥50: {100*optimized_stats['scores_above_50']/optimized_stats['count']:.1f}%")
        print(f"\nImprovement:")
        print(f"  Absolute: +{improvement:.2f}")
        print(f"  Relative: {improvement_pct:+.2f}%")
        print(f"  Allocations: {results['optimization']['total_allocations']}")
        print("\n" + "="*70)
        print("✓ PIPELINE COMPLETE!")
        print("="*70)
        
        return results
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run walkability optimization pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run Greedy with k=3 (default)
  python scripts/run_pipeline.py
  
  # Run MILP with k=5
  python scripts/run_pipeline.py --solver milp --k 5
  
  # Run CP with k=1 and reload data
  python scripts/run_pipeline.py --solver cp --k 1 --load-data
  
  # Run without visualizations (faster)
  python scripts/run_pipeline.py --skip-viz
        """
    )
    
    parser.add_argument(
        '--solver',
        choices=['greedy', 'milp', 'cp'],
        default='greedy',
        help='Optimization solver to use (default: greedy)'
    )
    
    parser.add_argument(
        '--k',
        type=int,
        default=3,
        help='Number of amenities to allocate per type (default: 3)'
    )
    
    parser.add_argument(
        '--load-data',
        action='store_true',
        help='Load fresh OSM data (default: use existing)'
    )
    
    parser.add_argument(
        '--rebuild-network',
        action='store_true',
        help='Rebuild pedestrian network (default: load from DB)'
    )
    
    parser.add_argument(
        '--recompute-paths',
        action='store_true',
        help='Recompute shortest paths (default: load from DB)'
    )
    
    parser.add_argument(
        '--skip-viz',
        action='store_true',
        help='Skip visualization generation (faster)'
    )
    
    args = parser.parse_args()
    
    run_pipeline(args)


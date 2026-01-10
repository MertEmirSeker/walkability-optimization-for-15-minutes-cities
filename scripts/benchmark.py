"""
Benchmarking and performance profiling script.

Compares different solvers (Greedy, MILP, CP) on various problem sizes.
"""
import time
import psutil
import json
from typing import Dict, List
import numpy as np
from datetime import datetime


class Benchmark:
    """Benchmark optimization algorithms."""
    
    def __init__(self):
        """Initialize benchmark."""
        self.results = []
    
    def run_benchmark(self, solver_name: str, optimize_func, k: int, 
                     problem_size: Dict):
        """
        Run benchmark for a single solver.
        
        Args:
            solver_name: Name of solver (greedy, milp, cp)
            optimize_func: Optimization function to call
            k: Number of amenities per type
            problem_size: Dict with #residential, #candidates, etc.
        
        Returns:
            Dict with timing and performance metrics
        """
        print(f"\n{'='*60}")
        print(f"Benchmarking {solver_name} (k={k})")
        print(f"{'='*60}")
        print(f"Problem size: {problem_size}")
        
        # Memory before
        process = psutil.Process()
        mem_before = process.memory_info().rss / (1024 * 1024)  # MB
        
        # Run optimization
        start_time = time.time()
        start_cpu = time.process_time()
        
        try:
            solution = optimize_func(k=k)
            success = True
            error = None
        except Exception as e:
            solution = {}
            success = False
            error = str(e)
            print(f"✗ ERROR: {error}")
        
        end_time = time.time()
        end_cpu = time.process_time()
        
        # Memory after
        mem_after = process.memory_info().rss / (1024 * 1024)  # MB
        mem_used = mem_after - mem_before
        
        # Compute metrics
        wall_time = end_time - start_time
        cpu_time = end_cpu - start_cpu
        
        # Count allocations
        total_allocations = sum(len(v) for v in solution.values()) if solution else 0
        
        result = {
            'solver': solver_name,
            'k': k,
            'problem_size': problem_size,
            'success': success,
            'error': error,
            'wall_time': wall_time,
            'cpu_time': cpu_time,
            'memory_mb': mem_used,
            'total_allocations': total_allocations,
            'solution': {k: list(v) for k, v in solution.items()} if solution else {},
            'timestamp': datetime.now().isoformat()
        }
        
        self.results.append(result)
        
        # Print summary
        if success:
            print(f"\n✓ Success!")
            print(f"  Wall time: {wall_time:.2f}s")
            print(f"  CPU time: {cpu_time:.2f}s")
            print(f"  Memory used: {mem_used:.2f} MB")
            print(f"  Total allocations: {total_allocations}")
        
        return result
    
    def compare_solvers(self, results: List[Dict]):
        """Compare multiple solver results."""
        print(f"\n{'='*60}")
        print("SOLVER COMPARISON")
        print(f"{'='*60}")
        
        # Sort by wall time
        results_sorted = sorted(results, key=lambda x: x.get('wall_time', float('inf')))
        
        print(f"\n{'Solver':<15} {'Time (s)':<12} {'Memory (MB)':<15} {'Success':<10}")
        print('-' * 60)
        
        for r in results_sorted:
            time_str = f"{r['wall_time']:.2f}" if r['success'] else "FAILED"
            mem_str = f"{r['memory_mb']:.2f}" if r['success'] else "-"
            success_str = "✓" if r['success'] else "✗"
            
            print(f"{r['solver']:<15} {time_str:<12} {mem_str:<15} {success_str:<10}")
        
        # Speedup analysis
        if len(results_sorted) > 1 and results_sorted[0]['success']:
            baseline_time = results_sorted[0]['wall_time']
            print(f"\nSpeedup relative to {results_sorted[0]['solver']}:")
            
            for r in results_sorted[1:]:
                if r['success']:
                    speedup = r['wall_time'] / baseline_time
                    print(f"  {r['solver']}: {speedup:.2f}x slower")
    
    def save_results(self, filename: str = "benchmark_results.json"):
        """Save benchmark results to JSON."""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n✓ Results saved to {filename}")
    
    def print_summary(self):
        """Print summary statistics."""
        print(f"\n{'='*60}")
        print("BENCHMARK SUMMARY")
        print(f"{'='*60}")
        
        successful = [r for r in self.results if r['success']]
        failed = [r for r in self.results if not r['success']]
        
        print(f"\nTotal runs: {len(self.results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        
        if successful:
            times = [r['wall_time'] for r in successful]
            memories = [r['memory_mb'] for r in successful]
            
            print(f"\nTiming statistics:")
            print(f"  Mean: {np.mean(times):.2f}s")
            print(f"  Median: {np.median(times):.2f}s")
            print(f"  Min: {np.min(times):.2f}s")
            print(f"  Max: {np.max(times):.2f}s")
            
            print(f"\nMemory statistics:")
            print(f"  Mean: {np.mean(memories):.2f} MB")
            print(f"  Median: {np.median(memories):.2f} MB")
            print(f"  Min: {np.min(memories):.2f} MB")
            print(f"  Max: {np.max(memories):.2f} MB")


class Profiler:
    """Profile code performance."""
    
    def __init__(self):
        """Initialize profiler."""
        self.timings = {}
    
    def profile_function(self, func, name: str, *args, **kwargs):
        """Profile a function call."""
        import cProfile
        import pstats
        import io
        
        print(f"\nProfiling {name}...")
        
        profiler = cProfile.Profile()
        profiler.enable()
        
        result = func(*args, **kwargs)
        
        profiler.disable()
        
        # Print stats
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(20)  # Top 20 functions
        
        print(s.getvalue())
        
        return result
    
    def profile_memory(self, func, *args, **kwargs):
        """Profile memory usage."""
        try:
            from memory_profiler import profile as mem_profile
            
            # Decorate and call
            decorated = mem_profile(func)
            result = decorated(*args, **kwargs)
            
            return result
        except ImportError:
            print("memory_profiler not installed. Install with: pip install memory-profiler")
            return func(*args, **kwargs)


if __name__ == "__main__":
    print("Benchmark and profiling utilities")
    print("Import this module to use Benchmark and Profiler classes")
    
    # Example usage:
    # from scripts.benchmark import Benchmark
    # benchmark = Benchmark()
    # 
    # result = benchmark.run_benchmark(
    #     solver_name='greedy',
    #     optimize_func=optimizer.optimize,
    #     k=3,
    #     problem_size={'residential': 34424, 'candidates': 1244}
    # )
    #
    # benchmark.print_summary()
    # benchmark.save_results()


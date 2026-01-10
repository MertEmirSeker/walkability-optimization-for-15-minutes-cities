# Walkability Optimization for 15-Minute Cities

**A comprehensive system for optimizing walkability in urban environments using mathematical optimization.**

Based on the research paper: "Walkability Optimization: Formulations, Algorithms, and a Case Study of Toronto" adapted for Balıkesir, Turkey.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Usage](#usage)
- [Algorithms](#algorithms)
- [Configuration](#configuration)
- [Visualization](#visualization)
- [Testing](#testing)
- [Performance](#performance)
- [Contributing](#contributing)
- [License](#license)

---

## 🌟 Overview

This project implements a complete pipeline for optimizing urban walkability by strategically placing new amenities (grocery stores, schools, restaurants, healthcare facilities) to maximize overall WalkScore across residential locations.

**Key Components:**
- **OSM Data Collection**: Comprehensive extraction of OpenStreetMap data
- **Pedestrian Network**: Graph-based representation of walkable paths
- **WalkScore Calculation**: Paper-accurate implementation of weighted distance metrics
- **Optimization Algorithms**: Greedy, MILP, and CP solvers
- **Visualization**: Interactive maps and statistical analysis
- **Benchmarking**: Performance profiling and comparison

**Problem Statement:**
Given:
- A pedestrian network G(V, E)
- Residential locations R
- Candidate locations C for new amenities
- Amenity types A (grocery, school, restaurant, healthcare)
- Budget constraints k_a for each amenity type

Find: Optimal allocation of amenities to candidates that maximizes average WalkScore across all residential locations.

---

## ✨ Features

### Data Collection
- ✅ Comprehensive OSM tag extraction (217 amenity tags, 37 residential types)
- ✅ Turkish context-aware (çay ocağı, esnaf lokantası, kuruyemişçi, etc.)
- ✅ Exclusion-based residential filtering (schools/hospitals excluded)
- ✅ 1.5km buffer for amenity/candidate search
- ✅ Data quality validation and duplicate detection

### WalkScore Calculation
- ✅ Piecewise Linear Function (PWL) implementation
- ✅ Weighted walking distance (no normalization - paper-accurate!)
- ✅ A_plain (single nearest) and A_depth (top-r) categories
- ✅ Category weights and depth weights from database
- ✅ Balıkesir-calibrated breakpoints

### Optimization Algorithms
- ✅ **Greedy Heuristic**: Fast, incremental caching, spatial filtering
- ✅ **MILP Solver**: Gurobi-based optimal solution
- ✅ **CP Solver**: OR-Tools constraint programming
- ✅ All algorithms guarantee monotonic improvement

### Visualization
- ✅ Interactive Folium maps with WalkScore heatmaps
- ✅ Before/after comparison maps
- ✅ Network graph visualization
- ✅ Statistical plots (distribution, CDF, box plots)
- ✅ Convergence analysis

### Performance Optimizations
- ✅ WalkScore caching with incremental updates
- ✅ Pre-computed nearby residentials (3km radius)
- ✅ Spatial filtering for affected areas
- ✅ FAST MODE for development (sampling)
- ✅ Batch processing for large datasets

---

## 🚀 Installation

### Prerequisites
- Python 3.9+
- PostgreSQL 13+ with PostGIS extension
- 8GB+ RAM recommended
- Optional: Gurobi license for MILP solver

### Step 1: Clone Repository
```bash
git clone https://github.com/yourusername/walkability-optimization-for-15-minutes-cities.git
cd walkability-optimization-for-15-minutes-cities
```

### Step 2: Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\\Scripts\\activate  # Windows
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

**Key Dependencies:**
- `osmnx`: OpenStreetMap data extraction
- `networkx`: Graph algorithms
- `sqlalchemy`: Database ORM
- `psycopg2-binary`: PostgreSQL driver
- `folium`: Interactive maps
- `matplotlib`, `seaborn`: Plotting
- `gurobipy`: MILP solver (optional, requires license)
- `ortools`: CP solver (free, open-source)

### Step 4: Setup Database
```bash
# Create database
createdb walkability_center_db

# Enable PostGIS
psql walkability_center_db -c "CREATE EXTENSION postgis;"

# Create schema
psql walkability_center_db < database/schema.sql
```

### Step 5: Configure
Edit `config.yaml`:
```yaml
database:
  host: localhost
  port: 5432
  database: walkability_center_db
  user: your_username
  password: ""
```

---

## 🎯 Quick Start

### Option 1: Run Full Pipeline
```bash
python scripts/run_pipeline.py
```

This will:
1. Load OSM data
2. Build pedestrian network
3. Compute shortest paths
4. Calculate baseline WalkScores
5. Run optimization (Greedy by default)
6. Generate visualizations
7. Save results to database

### Option 2: Step-by-Step

#### 1. Load OSM Data
```bash
python -m src.data_collection.osm_loader
```

#### 2. Build Network
```bash
python -m src.network.pedestrian_graph
```

#### 3. Compute Shortest Paths
```bash
python -m src.network.shortest_paths
```

#### 4. Calculate WalkScores
```bash
python -m src.scoring.walkscore
```

#### 5. Run Optimization
```bash
# Greedy (fast)
python -m src.algorithms.greedy

# MILP (optimal, requires Gurobi)
python -m src.algorithms.milp

# CP (good balance)
python -m src.algorithms.cp
```

#### 6. Visualize Results
```python
from src.visualization.map_plotter import MapPlotter, StatisticsPlotter
from src.network.pedestrian_graph import PedestrianGraph
from src.scoring.walkscore import WalkScoreCalculator

graph = PedestrianGraph()
graph.load_from_database()

scorer = WalkScoreCalculator(graph, path_calc)

# Create map
plotter = MapPlotter(graph, scorer, graph.db)
plotter.plot_walkability_map(scores, solution, "results/walkability_map.html")

# Create plots
stats_plotter = StatisticsPlotter()
stats_plotter.plot_walkscore_distribution(scores, "results/distribution.png")
```

---

## 📁 Project Structure

```
walkability-optimization-for-15-minutes-cities/
│
├── config.yaml                 # Configuration file
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── TODO.md                     # Detailed task list
│
├── database/
│   ├── schema.sql             # PostgreSQL schema
│   └── README.md              # Database documentation
│
├── src/
│   ├── data_collection/
│   │   └── osm_loader.py      # OSM data extraction
│   │
│   ├── network/
│   │   ├── pedestrian_graph.py    # Graph representation
│   │   └── shortest_paths.py      # Distance computation
│   │
│   ├── scoring/
│   │   └── walkscore.py       # WalkScore calculation
│   │
│   ├── algorithms/
│   │   ├── greedy.py          # Greedy heuristic
│   │   ├── milp.py            # MILP solver
│   │   └── cp.py              # CP-SAT solver
│   │
│   ├── visualization/
│   │   └── map_plotter.py     # Maps and plots
│   │
│   └── utils/
│       └── database.py        # Database utilities
│
├── scripts/
│   ├── run_pipeline.py        # Main pipeline script
│   └── benchmark.py           # Performance benchmarking
│
├── tests/
│   ├── test_walkscore.py      # Unit tests for WalkScore
│   ├── test_greedy.py         # Unit tests for Greedy
│   └── test_integration.py    # Integration tests
│
└── results/                   # Output directory
    ├── maps/                  # HTML maps
    ├── plots/                 # PNG/PDF plots
    └── data/                  # JSON/CSV results
```

---

## 📖 Usage

### Configuration

Edit `config.yaml` to customize:

**City Boundaries:**
```yaml
balikesir:
  boundary:
    north: 39.6700
    south: 39.6300
    east: 27.9100
    west: 27.8600
```

**WalkScore Parameters:**
```yaml
walkscore:
  breakpoints: [0, 400, 800, 1600, 2400]
  scores: [100, 100, 90, 70, 0]
```

**Optimization Settings:**
```yaml
optimization:
  default_k: 3
  fast_mode_residential_sample: 500  # For testing
  fast_mode_candidate_sample: 50     # For testing
```

**Fast Mode vs Production Mode:**
- **Fast Mode**: Use sampling for quick testing (5-10 minutes)
- **Production Mode**: Set to `null` to use all data (several hours)

---

## 🧮 Algorithms

### 1. Greedy Heuristic

**Paper Reference**: Algorithm 1, Section 3.1

**Time Complexity**: O(k × |A| × |C| × |R|) per iteration

**Key Optimizations:**
- WalkScore caching with incremental updates
- Pre-computed nearby residentials (3km radius)
- Spatial filtering for affected areas
- ~23x speedup from optimizations!

**Usage:**
```python
from src.algorithms.greedy import GreedyOptimizer

optimizer = GreedyOptimizer(graph, scorer)
solution = optimizer.optimize(k=3)
```

**Expected Performance:**
- k=1, 500 residential, 50 candidates: ~5 minutes
- k=3, 34K residential, 1.2K candidates: ~2-3 hours

### 2. MILP Solver

**Paper Reference**: Section 3.2

**Requires**: Gurobi license

**Features:**
- Optimal solution (within MIP gap)
- Piecewise linear constraints for PWL function
- Budget and capacity constraints

**Usage:**
```python
from src.algorithms.milp import MILPOptimizer

optimizer = MILPOptimizer(graph, scorer)
solution = optimizer.optimize(k=3)
```

**Note:** May take several hours for large instances.

### 3. CP-SAT Solver

**Free alternative to MILP**

**Uses**: Google OR-Tools

**Features:**
- No license required
- Often faster than MILP
- Good for discrete optimization

**Usage:**
```python
from src.algorithms.cp import CPOptimizer

optimizer = CPOptimizer(graph, scorer)
solution = optimizer.optimize(k=3)
```

---

## 📊 Visualization

### Interactive Maps

```python
from src.visualization.map_plotter import MapPlotter

plotter = MapPlotter(graph, scorer, db)

# WalkScore heatmap
plotter.plot_walkability_map(scores, solution, "map.html")

# Before/after comparison
plotter.plot_comparison_map(baseline_scores, optimized_scores, solution, "comparison.html")

# Network graph
plotter.plot_network_graph("network.html")
```

### Statistical Plots

```python
from src.visualization.map_plotter import StatisticsPlotter

stats = StatisticsPlotter()

# Distribution
stats.plot_walkscore_distribution(scores, "distribution.png")

# Comparison
stats.plot_comparison(baseline_scores, optimized_scores, "comparison.png")

# Convergence
stats.plot_convergence(history, "convergence.png")
```

---

## 🧪 Testing

Run unit tests:
```bash
python -m pytest tests/
```

Run specific test:
```bash
python -m pytest tests/test_walkscore.py -v
```

Run with coverage:
```bash
python -m pytest --cov=src tests/
```

---

## ⚡ Performance

### Benchmarking

```python
from scripts.benchmark import Benchmark

benchmark = Benchmark()

# Benchmark Greedy
result = benchmark.run_benchmark(
    solver_name='greedy',
    optimize_func=optimizer.optimize,
    k=3,
    problem_size={'residential': 34424, 'candidates': 1244}
)

# Compare solvers
benchmark.compare_solvers([result_greedy, result_milp, result_cp])

# Save results
benchmark.save_results("benchmark_results.json")
```

### Profiling

```python
from scripts.benchmark import Profiler

profiler = Profiler()

# Profile function
profiler.profile_function(optimizer.optimize, "greedy_optimize", k=3)

# Profile memory
profiler.profile_memory(scorer.compute_baseline_scores)
```

### Expected Performance Metrics

| Dataset | Residential | Candidates | Greedy | MILP | CP |
|---------|------------|-----------|--------|------|-----|
| Small | 500 | 50 | 5 min | 10 min | 8 min |
| Medium | 5,000 | 200 | 30 min | 2 hrs | 1 hr |
| Large | 34,424 | 1,244 | 3 hrs | 8+ hrs | 5 hrs |

---

## 📚 Documentation

### API Documentation

Generate API docs with Sphinx:
```bash
cd docs
make html
```

View at: `docs/_build/html/index.html`

### Key Classes

- **`PedestrianGraph`**: Graph representation of pedestrian network
- **`ShortestPathCalculator`**: Compute and cache shortest paths
- **`WalkScoreCalculator`**: Calculate WalkScores (paper-accurate!)
- **`GreedyOptimizer`**: Greedy heuristic algorithm
- **`MILPOptimizer`**: MILP solver
- **`CPOptimizer`**: CP-SAT solver
- **`MapPlotter`**: Interactive map visualization
- **`StatisticsPlotter`**: Statistical plots

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 📖 Citation

If you use this code in your research, please cite:

```bibtex
@article{walkability2024,
  title={Walkability Optimization for 15-Minute Cities: A Case Study of Balıkesir},
  author={Your Name},
  year={2024},
  based_on={Walkability Optimization: Formulations, Algorithms, and a Case Study of Toronto}
}
```

---

## 📞 Contact

For questions or issues, please open an issue on GitHub or contact:
- Email: your.email@example.com
- GitHub: [@yourusername](https://github.com/yourusername)

---

## 🙏 Acknowledgments

- Original paper: "Walkability Optimization: Formulations, Algorithms, and a Case Study of Toronto"
- OpenStreetMap contributors for geospatial data
- NetworkX and OSMnx for graph algorithms
- Gurobi and OR-Tools for optimization solvers

---

**Built with ❤️ for creating more walkable, livable cities!** 🌆🚶‍♂️

"""
MILP Test Script
Tests if Gurobi is installed and MILP solver works correctly.
"""
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def test_gurobi_installation():
    """Test 1: Check if Gurobi is installed."""
    print("=" * 60)
    print("TEST 1: Gurobi Installation")
    print("=" * 60)
    
    try:
        import gurobipy as gp
        from gurobipy import GRB
        print("✓ Gurobi installed successfully!")
        print(f"  Version: {gp.gurobi.version()}")
        return True
    except ImportError as e:
        print("✗ Gurobi NOT installed!")
        print(f"  Error: {e}")
        print("\nTo install Gurobi:")
        print("  1. pip install gurobipy")
        print("  2. Get free academic license: https://www.gurobi.com/academia/")
        return False


def test_simple_milp():
    """Test 2: Run a simple MILP problem."""
    print("\n" + "=" * 60)
    print("TEST 2: Simple MILP Problem")
    print("=" * 60)
    print("Problem: Maximize x + y subject to x + 2y <= 3, x,y >= 0")
    
    try:
        import gurobipy as gp
        from gurobipy import GRB
        
        # Create model
        model = gp.Model("test")
        model.setParam('OutputFlag', 0)  # Suppress output
        
        # Variables
        x = model.addVar(name="x", lb=0)
        y = model.addVar(name="y", lb=0)
        
        # Constraint
        model.addConstr(x + 2*y <= 3, "c1")
        
        # Objective
        model.setObjective(x + y, GRB.MAXIMIZE)
        
        # Solve
        model.optimize()
        
        if model.status == GRB.OPTIMAL:
            print(f"✓ MILP solver works!")
            print(f"  Optimal value: {model.objVal:.2f}")
            print(f"  x = {x.X:.2f}, y = {y.X:.2f}")
            return True
        else:
            print(f"✗ Solver failed with status: {model.status}")
            return False
            
    except Exception as e:
        print(f"✗ Error running MILP: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_milp_optimizer():
    """Test 3: Check if MILPSolver class is importable."""
    print("\n" + "=" * 60)
    print("TEST 3: MILPSolver Class Import")
    print("=" * 60)
    
    try:
        from src.algorithms.milp import MILPSolver
        print("✓ MILPSolver imported successfully!")
        print(f"  Class: {MILPSolver}")
        print(f"  Methods: {[m for m in dir(MILPSolver) if not m.startswith('_')]}")
        return True
    except ImportError as e:
        print(f"✗ Failed to import MILPSolver: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_connection():
    """Test 4: Check database connection."""
    print("\n" + "=" * 60)
    print("TEST 4: Database Connection")
    print("=" * 60)
    
    try:
        from src.utils.database import get_db_manager
        from sqlalchemy import text
        
        db = get_db_manager()
        with db.get_session() as session:
            result = session.execute(text("SELECT COUNT(*) FROM nodes"))
            node_count = result.scalar()
            
            result = session.execute(text("SELECT COUNT(*) FROM residential_locations"))
            res_count = result.scalar()
            
            result = session.execute(text("SELECT COUNT(*) FROM candidate_locations"))
            cand_count = result.scalar()
            
            print("✓ Database connected!")
            print(f"  Nodes: {node_count}")
            print(f"  Residential: {res_count}")
            print(f"  Candidates: {cand_count}")
            
            return node_count > 0 and res_count > 0
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_file():
    """Test 5: Check if config.yaml has MILP settings."""
    print("\n" + "=" * 60)
    print("TEST 5: Configuration File")
    print("=" * 60)
    
    try:
        import yaml
        
        with open("config.yaml", 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        milp_config = config['optimization']['milp']
        
        print("✓ Config loaded successfully!")
        print(f"  Time limit: {milp_config['time_limit_seconds']}s")
        print(f"  Threads: {milp_config['threads']}")
        print(f"  MIP gap: {milp_config['mip_gap']}")
        
        return True
    except Exception as e:
        print(f"✗ Config loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("MILP SOLVER TEST SUITE")
    print("=" * 60 + "\n")
    
    results = []
    
    # Test 1: Gurobi installation
    results.append(("Gurobi Installation", test_gurobi_installation()))
    
    if results[0][1]:  # Only continue if Gurobi is installed
        # Test 2: Simple MILP
        results.append(("Simple MILP", test_simple_milp()))
        
        # Test 3: MILPSolver import
        results.append(("MILPSolver Import", test_milp_optimizer()))
        
        # Test 4: Database
        results.append(("Database Connection", test_database_connection()))
        
        # Test 5: Config
        results.append(("Config File", test_config_file()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "-" * 60)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("=" * 60 + "\n")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! MILP is ready to use!")
        print("\nNext steps:")
        print("  python -m src.main --algorithm milp --k 1")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED!")
        print("\nFix the issues above before running MILP optimization.")
        return 1


if __name__ == "__main__":
    sys.exit(main())


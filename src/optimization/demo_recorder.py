"""
Demo Recorder for Optimization Runs.

Records each iteration of optimization to database for later replay.
"""
import time
from sqlalchemy import text


class DemoRecorder:
    """Records optimization iterations for demo replay."""
    
    def __init__(self, db, scenario: str, algorithm: str, k: int, total_expected: int):
        """
        Initialize demo recorder.
        
        Args:
            db: Database manager instance
            scenario: Scenario name (e.g., 'greedy_k3')
            algorithm: Algorithm name ('greedy', 'milp')
            k: Number of allocations per amenity type
            total_expected: Expected total iterations
        """
        self.db = db
        self.scenario = scenario
        self.algorithm = algorithm
        self.k = k
        self.total_expected = total_expected
        self.start_time = time.time()
        self.iteration_count = 0
        
        # Check if recording tables exist
        self._check_tables_exist()
        
        print(f"[RECORDING] Demo mode enabled for {scenario}")
        
    def _check_tables_exist(self):
        """Check if recording tables exist in database."""
        with self.db.get_session() as session:
            result = session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'optimization_iterations'
                )
            """))
            if not result.scalar():
                raise RuntimeError(
                    "Recording tables not found! "
                    "Run migration: psql walkability_db < database/migrations/001_add_demo_recording.sql"
                )
    
    def record_iteration(self, amenity_type: str, candidate_node_id: int,
                        improvement: float, current_objective: float):
        """
        Record a single iteration.
        
        Args:
            amenity_type: Name of amenity type (e.g., 'grocery')
            candidate_node_id: Network node ID where amenity was allocated
            improvement: Objective increase from this allocation
            current_objective: Current average WalkScore after allocation
        """
        self.iteration_count += 1
        elapsed = time.time() - self.start_time
        progress = (self.iteration_count / self.total_expected) * 100 if self.total_expected > 0 else 0
        
        try:
            with self.db.get_session() as session:
                # Get amenity_type_id
                type_query = """
                    SELECT amenity_type_id FROM amenity_types 
                    WHERE type_name = :type_name
                """
                amenity_type_id = session.execute(
                    text(type_query), {'type_name': amenity_type}
                ).scalar()
                
                if not amenity_type_id:
                    print(f"[RECORDING] Warning: Unknown amenity type '{amenity_type}', skipping")
                    return
                
                # Get candidate_id from node_id
                cand_query = """
                    SELECT candidate_id FROM candidate_locations 
                    WHERE node_id = :node_id
                """
                candidate_id = session.execute(
                    text(cand_query), {'node_id': candidate_node_id}
                ).scalar()
                
                if not candidate_id:
                    print(f"[RECORDING] Warning: Node {candidate_node_id} not in candidate_locations, skipping")
                    return
                
                # Insert iteration record
                insert_query = """
                    INSERT INTO optimization_iterations
                    (scenario, iteration_number, amenity_type_id, candidate_id,
                     improvement, current_objective, progress_pct, elapsed_seconds)
                    VALUES (:scenario, :iteration, :amenity_type_id, :candidate_id,
                            :improvement, :objective, :progress, :elapsed)
                """
                session.execute(text(insert_query), {
                    'scenario': self.scenario,
                    'iteration': self.iteration_count,
                    'amenity_type_id': amenity_type_id,
                    'candidate_id': candidate_id,
                    'improvement': improvement,
                    'objective': current_objective,
                    'progress': progress,
                    'elapsed': elapsed
                })
                session.commit()
                
                if self.iteration_count % 10 == 0:
                    print(f"[RECORDING] Saved iteration {self.iteration_count}/{self.total_expected}")
                    
        except Exception as e:
            print(f"[RECORDING] Error recording iteration {self.iteration_count}: {e}")
    
    def finalize(self, final_objective: float):
        """
        Save recording metadata after optimization completes.
        
        Args:
            final_objective: Final average WalkScore achieved
        """
        total_time = time.time() - self.start_time
        
        try:
            with self.db.get_session() as session:
                # Insert or update recording metadata
                query = """
                    INSERT INTO optimization_recordings
                    (scenario, algorithm, k_value, total_iterations,
                     final_objective, total_time_seconds)
                    VALUES (:scenario, :algorithm, :k, :iterations,
                            :objective, :time)
                    ON CONFLICT (scenario) DO UPDATE SET
                        total_iterations = EXCLUDED.total_iterations,
                        final_objective = EXCLUDED.final_objective,
                        total_time_seconds = EXCLUDED.total_time_seconds,
                        recorded_at = CURRENT_TIMESTAMP
                """
                session.execute(text(query), {
                    'scenario': self.scenario,
                    'algorithm': self.algorithm,
                    'k': self.k,
                    'iterations': self.iteration_count,
                    'objective': final_objective,
                    'time': total_time
                })
                session.commit()
                
            print(f"[RECORDING] ✓ Saved {self.iteration_count} iterations to database")
            print(f"[RECORDING] ✓ Total time: {total_time:.1f}s, Final objective: {final_objective:.4f}")
            
        except Exception as e:
            print(f"[RECORDING] Error finalizing recording: {e}")

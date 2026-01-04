"""
Database connection and utility functions for PostgreSQL.
"""
import os
import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from typing import Optional


class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize database manager with configuration."""
        self.config = self._load_config(config_path)
        self.engine = None
        self.Session = None
        
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    
    def connect(self):
        """Create database connection."""
        db_config = self.config['database']
        
        # Try to get credentials from environment variables first
        db_host = os.getenv('DB_HOST', db_config.get('host', 'localhost'))
        db_port = os.getenv('DB_PORT', db_config.get('port', 5432))
        db_name = os.getenv('DB_NAME', db_config.get('database', 'walkability_db'))
        db_user = os.getenv('DB_USER', db_config.get('user', 'postgres'))
        db_password = os.getenv('DB_PASSWORD', db_config.get('password', 'postgres'))
        
        connection_string = (
            f"postgresql://{db_user}:{db_password}@"
            f"{db_host}:{db_port}/{db_name}"
        )
        
        self.engine = create_engine(connection_string, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine)
        
    @contextmanager
    def get_session(self):
        """Get database session context manager."""
        if self.Session is None:
            self.connect()
        
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def execute_query(self, query: str, params: Optional[dict] = None):
        """Execute a raw SQL query."""
        with self.get_session() as session:
            result = session.execute(text(query), params or {})
            return result.fetchall()
    
    def check_connection(self) -> bool:
        """Check if database connection is working."""
        try:
            if self.engine is None:
                self.connect()
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print(f"Database connection failed: {e}")
            return False
    
    def create_schema(self, schema_path: str = "database/schema.sql"):
        """Create database schema from SQL file."""
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        if self.engine is None:
            self.connect()
        
        with self.engine.connect() as conn:
            # Execute schema SQL
            conn.execute(text(schema_sql))
            conn.commit()
        
        print(f"Schema created successfully from {schema_path}")


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(config_path: str = "config.yaml") -> DatabaseManager:
    """Get or create global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(config_path)
        _db_manager.connect()
    return _db_manager


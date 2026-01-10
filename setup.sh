#!/bin/bash
#
# Setup script for Walkability Optimization project
#

echo "======================================================================"
echo "Walkability Optimization Setup"
echo "======================================================================"

# Check Python version
echo -e "\n[1/6] Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "  Python version: $python_version"

if ! command -v python3 &> /dev/null; then
    echo "  ✗ ERROR: Python 3 not found!"
    exit 1
fi

# Create virtual environment
echo -e "\n[2/6] Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment already exists"
fi

# Activate virtual environment
echo -e "\n[3/6] Activating virtual environment..."
source venv/bin/activate
echo "  ✓ Virtual environment activated"

# Install dependencies
echo -e "\n[4/6] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "  ✓ Dependencies installed"

# Check PostgreSQL
echo -e "\n[5/6] Checking PostgreSQL..."
if command -v psql &> /dev/null; then
    psql_version=$(psql --version | awk '{print $3}')
    echo "  PostgreSQL version: $psql_version"
    
    # Check if database exists
    if psql -lqt | cut -d \| -f 1 | grep -qw walkability_center_db; then
        echo "  ✓ Database 'walkability_center_db' exists"
    else
        echo "  Creating database..."
        createdb walkability_center_db
        psql walkability_center_db -c "CREATE EXTENSION postgis;"
        echo "  ✓ Database created"
    fi
    
    # Load schema
    echo "  Loading database schema..."
    psql walkability_center_db < database/schema.sql 2>/dev/null
    echo "  ✓ Schema loaded"
else
    echo "  ✗ WARNING: PostgreSQL not found!"
    echo "  Please install PostgreSQL 13+ and PostGIS"
fi

# Create results directories
echo -e "\n[6/6] Creating results directories..."
mkdir -p results/maps
mkdir -p results/plots
mkdir -p results/data
echo "  ✓ Results directories created"

# Final message
echo -e "\n======================================================================"
echo "Setup Complete!"
echo "======================================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Configure your database connection in config.yaml:"
echo "   nano config.yaml"
echo ""
echo "2. Run the pipeline:"
echo "   source venv/bin/activate"
echo "   python scripts/run_pipeline.py"
echo ""
echo "3. Or run step-by-step:"
echo "   python -m src.data_collection.osm_loader"
echo "   python -m src.network.pedestrian_graph"
echo "   python -m src.network.shortest_paths"
echo "   python -m src.scoring.walkscore"
echo "   python -m src.algorithms.greedy"
echo ""
echo "For more information, see README.md"
echo "======================================================================"


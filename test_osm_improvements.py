#!/usr/bin/env python3
"""
Test script for improved OSM data collection.
Tests all the enhancements made to osm_loader.py
"""
import sys
from src.data_collection.osm_loader import OSMDataLoader
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_residential_types():
    """Test that residential building types are loaded from config."""
    logger.info("\n=== Testing Residential Building Types ===")
    loader = OSMDataLoader()
    
    logger.info(f"Loaded {len(loader.RESIDENTIAL_BUILDING_TYPES)} residential building types")
    logger.info(f"Sample types: {list(loader.RESIDENTIAL_BUILDING_TYPES)[:10]}")
    
    assert len(loader.RESIDENTIAL_BUILDING_TYPES) > 0, "No residential building types loaded!"
    logger.info("✓ Residential building types loaded successfully")


def test_data_quality_params():
    """Test that data quality parameters are loaded from config."""
    logger.info("\n=== Testing Data Quality Parameters ===")
    loader = OSMDataLoader()
    
    logger.info(f"Max snapping distance: {loader.MAX_SNAPPING_DISTANCE}m")
    logger.info(f"Duplicate threshold: {loader.DUPLICATE_THRESHOLD}m")
    logger.info(f"Amenity duplicate threshold: {loader.AMENITY_DUPLICATE_THRESHOLD}m")
    logger.info(f"Validation enabled: {loader.enable_validation}")
    logger.info(f"Duplicate detection enabled: {loader.enable_duplicate_detection}")
    
    assert loader.MAX_SNAPPING_DISTANCE > 0, "Invalid snapping distance!"
    assert loader.enable_validation, "Validation should be enabled!"
    logger.info("✓ Data quality parameters loaded successfully")


def test_amenity_tags():
    """Test that amenity tags are loaded from config."""
    logger.info("\n=== Testing Amenity Tags ===")
    loader = OSMDataLoader()
    
    # Test ONLY the 4 core amenities
    for amenity_type in ['grocery', 'restaurant', 'school', 'healthcare']:
        tags = loader._get_amenity_tags_from_config(amenity_type)
        logger.info(f"{amenity_type}: {tags}")
        assert tags, f"No tags found for {amenity_type}!"
        logger.info(f"  -> {len([v for vals in tags.values() for v in (vals if isinstance(vals, list) else [vals])])} total tags")
    
    logger.info("✓ All 4 core amenity tags loaded successfully")


def test_candidate_tags():
    """Test that candidate location tags are loaded from config."""
    logger.info("\n=== Testing Candidate Location Tags ===")
    loader = OSMDataLoader()
    
    candidate_tags = loader._get_candidate_tags_from_config()
    logger.info(f"Loaded {len(candidate_tags)} candidate tag groups")
    for i, tags in enumerate(candidate_tags[:5], 1):
        logger.info(f"  Group {i}: {tags}")
    
    assert len(candidate_tags) > 0, "No candidate tags loaded!"
    logger.info("✓ Candidate location tags loaded successfully")


def test_validation():
    """Test coordinate validation."""
    logger.info("\n=== Testing Coordinate Validation ===")
    loader = OSMDataLoader()
    
    import pandas as pd
    from shapely.geometry import Point
    
    # Create test data with some invalid coordinates
    test_data = pd.DataFrame({
        'geometry': [
            Point(27.8750, 39.6400),  # Valid (inside bounds)
            Point(27.9500, 39.6400),  # Invalid (outside bounds)
            Point(27.8750, 40.0000),  # Invalid (outside bounds)
        ]
    })
    
    validated = loader._validate_coordinates(test_data)
    logger.info(f"Before validation: {len(test_data)} locations")
    logger.info(f"After validation: {len(validated)} locations")
    
    assert len(validated) < len(test_data), "Validation should have removed invalid coordinates!"
    logger.info("✓ Coordinate validation working correctly")


def test_statistics():
    """Test statistics tracking."""
    logger.info("\n=== Testing Statistics Tracking ===")
    loader = OSMDataLoader()
    
    logger.info(f"Stats structure: {list(loader.stats.keys())}")
    logger.info(f"Load timestamp: {loader.stats['load_timestamp']}")
    
    assert 'load_timestamp' in loader.stats, "Load timestamp not tracked!"
    assert 'amenities_by_type' in loader.stats, "Amenity stats not tracked!"
    assert 'data_quality_issues' in loader.stats, "Data quality issues not tracked!"
    logger.info("✓ Statistics tracking set up correctly")


def main():
    """Run all tests."""
    logger.info("=" * 70)
    logger.info("OSM DATA COLLECTION IMPROVEMENTS - TEST SUITE")
    logger.info("=" * 70)
    
    tests = [
        test_residential_types,
        test_data_quality_params,
        test_amenity_tags,
        test_candidate_tags,
        test_validation,
        test_statistics,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            logger.error(f"✗ Test failed: {test.__name__}")
            logger.error(f"  Error: {e}")
            failed += 1
        except Exception as e:
            logger.error(f"✗ Test error: {test.__name__}")
            logger.error(f"  Error: {e}", exc_info=True)
            failed += 1
    
    logger.info("\n" + "=" * 70)
    logger.info(f"TEST RESULTS: {passed} passed, {failed} failed")
    logger.info("=" * 70)
    
    if failed == 0:
        logger.info("✓ All tests passed!")
        return 0
    else:
        logger.error(f"✗ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())


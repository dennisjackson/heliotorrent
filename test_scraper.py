import pytest
from scraper import get_data_tile_paths, get_hash_tile_paths

def test_get_data_tile_paths_single_tile():
    """Test when start and end entries are in the same tile"""
    paths = list(get_data_tile_paths(0, 255))
    assert len(paths) == 1
    assert paths[0] == "tile/data/x000/x000/000"

def test_get_data_tile_paths_adjacent_tiles():
    """Test when start and end entries are in adjacent tiles"""
    paths = list(get_data_tile_paths(255, 256))
    assert len(paths) == 2
    assert paths[0] == "tile/data/x000/x000/000"
    assert paths[1] == "tile/data/x000/x000/001"

def test_get_data_tile_paths_multiple_tiles():
    """Test when start and end entries span multiple tiles"""
    paths = list(get_data_tile_paths(256*5, 256*8 + 100))
    assert len(paths) == 4
    assert paths[0] == "tile/data/x000/x000/005"
    assert paths[1] == "tile/data/x000/x000/006"
    assert paths[2] == "tile/data/x000/x000/007"
    assert paths[3] == "tile/data/x000/x000/008"

def test_get_data_tile_paths_large_indices():
    """Test with large indices that span multiple path segments"""
    paths = list(get_data_tile_paths(256*1234567, 256*1234569))
    assert len(paths) == 3
    assert paths[0] == "tile/data/x001/x234/567"
    assert paths[1] == "tile/data/x001/x234/568"
    assert paths[2] == "tile/data/x001/x234/569"

def test_get_hash_tile_paths_single_tile():
    """Test when start and end entries are in the same tile"""
    paths = list(get_hash_tile_paths(0, 255))
    assert len(paths) == 6  # 6 levels (0-5)
    # Check level 0
    assert paths[0] == "tile/0/x000/x000/000"
    # Check level 5
    assert paths[5] == "tile/5/x000/x000/000"

def test_get_hash_tile_paths_adjacent_tiles():
    """Test when start and end entries are in adjacent tiles"""
    paths = list(get_hash_tile_paths(255, 256))
    assert len(paths) == 12  # 6 levels * 2 tiles
    # Check first tile at level 0
    assert paths[0] == "tile/0/x000/x000/000"
    # Check second tile at level 0
    assert paths[1] == "tile/0/x000/x000/001"
    # Check first tile at level 5
    assert paths[10] == "tile/5/x000/x000/000"
    # Check second tile at level 5
    assert paths[11] == "tile/5/x000/x000/001"

def test_get_hash_tile_paths_multiple_tiles():
    """Test when start and end entries span multiple tiles"""
    paths = list(get_hash_tile_paths(256*5, 256*8 + 100))
    assert len(paths) == 24  # 6 levels * 4 tiles
    # Check first tile at level 0
    assert paths[0] == "tile/0/x000/x000/005"
    # Check last tile at level 0
    assert paths[3] == "tile/0/x000/x000/008"
    # Check first tile at level 5
    assert paths[20] == "tile/5/x000/x000/005"
    # Check last tile at level 5
    assert paths[23] == "tile/5/x000/x000/008"

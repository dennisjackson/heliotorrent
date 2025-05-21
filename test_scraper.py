import pytest
from scraper import get_data_tile_paths

def test_get_data_tile_paths_single_tile():
    """Test when start and end entries are in the same tile"""
    paths = list(get_data_tile_paths(0, 255))
    assert len(paths) == 1
    assert paths[0] == "x000/x000/000"
    
def test_get_data_tile_paths_adjacent_tiles():
    """Test when start and end entries are in adjacent tiles"""
    paths = list(get_data_tile_paths(255, 256))
    assert len(paths) == 2
    assert paths[0] == "x000/x000/000"
    assert paths[1] == "x000/x000/001"
    
def test_get_data_tile_paths_multiple_tiles():
    """Test when start and end entries span multiple tiles"""
    paths = list(get_data_tile_paths(256*5, 256*8 + 100))
    assert len(paths) == 4
    assert paths[0] == "x000/x000/005"
    assert paths[1] == "x000/x000/006"
    assert paths[2] == "x000/x000/007"
    assert paths[3] == "x000/x000/008"
    
def test_get_data_tile_paths_large_indices():
    """Test with large indices that span multiple path segments"""
    paths = list(get_data_tile_paths(256*1234567, 256*1234569))
    assert len(paths) == 3
    assert paths[0] == "x001/x234/567"
    assert paths[1] == "x001/x234/568"
    assert paths[2] == "x001/x234/569"

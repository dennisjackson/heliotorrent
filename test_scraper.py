import unittest
from scraper import get_data_tile_paths

class TestScraper(unittest.TestCase):
    def test_get_data_tile_paths_single_tile(self):
        """Test when start and end entries are in the same tile"""
        paths = list(get_data_tile_paths(0, 255))
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0], "x000/x000/000")
        
    def test_get_data_tile_paths_adjacent_tiles(self):
        """Test when start and end entries are in adjacent tiles"""
        paths = list(get_data_tile_paths(255, 256))
        self.assertEqual(len(paths), 2)
        self.assertEqual(paths[0], "x000/x000/000")
        self.assertEqual(paths[1], "x000/x000/001")
        
    def test_get_data_tile_paths_multiple_tiles(self):
        """Test when start and end entries span multiple tiles"""
        paths = list(get_data_tile_paths(256*5, 256*8 + 100))
        self.assertEqual(len(paths), 4)
        self.assertEqual(paths[0], "x000/x000/005")
        self.assertEqual(paths[1], "x000/x000/006")
        self.assertEqual(paths[2], "x000/x000/007")
        self.assertEqual(paths[3], "x000/x000/008")
        
    def test_get_data_tile_paths_large_indices(self):
        """Test with large indices that span multiple path segments"""
        paths = list(get_data_tile_paths(256*1234567, 256*1234569))
        self.assertEqual(len(paths), 3)
        self.assertEqual(paths[0], "x001/x234/567")
        self.assertEqual(paths[1], "x001/x234/568")
        self.assertEqual(paths[2], "x001/x234/569")

if __name__ == "__main__":
    unittest.main()

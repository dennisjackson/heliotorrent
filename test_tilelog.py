import os
import shutil
import pytest
import logging
from TileLog import TileLog


@pytest.fixture
def tile_log():
    logging.basicConfig(level=logging.INFO, force=True)  # Enable debug logs
    monitoring_url = "https://tuscolo2026h1.skylight.geomys.org/"
    storage_dir = "test_data"
    max_size = 1024  # Limit for testing

    # Ensure clean test environment
    if os.path.exists(storage_dir):
        shutil.rmtree(storage_dir)

    tile_log_instance = TileLog(monitoring_url, storage_dir, max_size)

    yield tile_log_instance

    # Clean up test environment
    if os.path.exists(storage_dir):
        shutil.rmtree(storage_dir)


def test_initialization(tile_log):
    assert os.path.exists(tile_log.storage)
    assert os.path.exists(tile_log.checkpoints)
    assert os.path.exists(tile_log.torrents)
    assert os.path.exists(tile_log.tiles)


def test_get_latest_tree_size(tile_log):
    size = tile_log.get_latest_tree_size(refresh=True)
    assert size > 0, "Tree size should be greater than 0"


def test_download_tiles(tile_log):
    start_index = 0
    stop_index = 256  # Small range for testing
    tile_log.download_tiles(start_index, stop_index)
    tile_files = os.listdir(tile_log.tiles)
    assert len(tile_files) > 0, "Tiles should be downloaded"


def test_make_torrents(tile_log):
    start_index = 0
    stop_index = 4096 * 256  # Ensure valid range for torrent creation
    ranges = [(start_index, stop_index)]
    tile_log.download_tiles(start_index, stop_index)
    tile_log.make_torrents(ranges)
    torrent_files = os.listdir(tile_log.torrents)
    assert len(torrent_files) > 0, "Torrents should be created"


def test_delete_tiles(tile_log):
    start_index = 0
    stop_index = 256
    tile_log.download_tiles(start_index, stop_index)
    tile_log.delete_tiles(start_index, stop_index)
    tile_files = [
        os.path.join(root, f)
        for root, _, files in os.walk(tile_log.tiles)
        for f in files
    ]
    assert len(tile_files) == 0, "All tile files should be deleted"

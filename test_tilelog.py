import json
import os
import shutil
import sys
import pytest
import logging
from TileLog import TileLog


@pytest.fixture
def tile_log(monkeypatch):
    logging.basicConfig(level=logging.DEBUG, force=True)  # Enable debug logs
    monkeypatch.setattr("TileLog.FETCH_CHECKPOINT_BACKOFF", 5)
    monitoring_url = "https://tuscolo2026h1.skylight.geomys.org/"
    storage_dir = "test/storage"
    torrent_dir = "test/torrents"
    feed_url = "http://localhost:8000/feed.xml"
    max_size = 1024  # Limit for testing
    log_name = "tuscolo_pytest"

    if shutil.which("wget2") is None:
        logging.error("wget2 is required but not installed or not in PATH.")
        sys.exit(1)

    # Ensure clean test environment
    if os.path.exists(storage_dir):
        shutil.rmtree(storage_dir)
    if os.path.exists(torrent_dir):
        shutil.rmtree(torrent_dir)

    tile_log_instance = TileLog(
        log_name=log_name,
        monitoring_url=monitoring_url,
        storage_dir=storage_dir,
        torrent_dir=torrent_dir,
        feed_url=feed_url,
        max_size=max_size,
    )

    yield tile_log_instance

    # Clean up test environment
    if os.path.exists(storage_dir):
        shutil.rmtree(storage_dir)
    if os.path.exists(torrent_dir):
        shutil.rmtree(torrent_dir)


def test_initialization(tile_log):
    assert os.path.exists(tile_log.storage_dir)
    assert os.path.exists(tile_log.checkpoints_dir)
    assert os.path.exists(tile_log.torrents_dir)
    assert os.path.exists(tile_log.tiles_dir)


def test_get_latest_tree_size(tile_log):
    size = tile_log.get_latest_tree_size(refresh=True)
    assert size > 0, "Tree size should be greater than 0"


def test_download_tiles(tile_log):
    start_index = 0
    stop_index = 256  # Small range for testing
    tile_log.download_tiles(start_index, stop_index)
    tile_files = [f for _, _, files in os.walk(tile_log.tiles_dir) for f in files]
    assert len(tile_files) > 0, "Tiles should be downloaded"


def test_make_torrents_and_rss_feed(tile_log, monkeypatch):
    # Monkeypatch to make the test faster
    monkeypatch.setattr("TileLog.ENTRIES_PER_LEAF_TORRENT", 256)
    start_index = 0
    stop_index = 4 * 256  # Small range for testing
    ranges = [(i, i + 256) for i in range(start_index, stop_index, 256)]
    tile_log.download_tiles(start_index, stop_index)
    tile_log.make_torrents(ranges)
    torrent_files = os.listdir(tile_log.torrents_dir)
    assert len(torrent_files) >= 4, "Torrents should be created"

    tile_log.make_rss_feed()
    feed_path = os.path.join(tile_log.torrents_dir, "feed.xml")
    assert os.path.exists(feed_path)
    with open(feed_path, "r") as f:
        content = f.read()
        assert "L01-0-256.torrent" in content
        assert "http://localhost:8000/L01-0-256.torrent" in content

    manifest_path = os.path.join(tile_log.torrents_dir, "torrents.json")
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    assert manifest["log_name"] == tile_log.log_name
    assert "last_updated" in manifest
    assert len(manifest["torrents"]) >= 4
    first_entry = manifest["torrents"][0]
    assert first_entry["start_index"] == 0
    assert first_entry["end_index"] == 256
    assert first_entry["torrent_url"].startswith("http://localhost:8000/")
    assert "creation_time" in first_entry

    html_path = os.path.join(tile_log.torrents_dir, "index.html")
    assert os.path.exists(html_path)
    with open(html_path, "r", encoding="utf-8") as html_file:
        html = html_file.read()
    assert '<a href="http://localhost:8000/feed.xml"' in html
    assert '<a href="http://localhost:8000/torrents.json"' in html
    assert "L01-0-256.torrent" in html


def test_delete_tiles(tile_log):
    start_index = 0
    stop_index = 256
    tile_log.download_tiles(start_index, stop_index)
    tile_log.delete_tiles(start_index, stop_index)
    tile_files = [
        os.path.join(root, f)
        for root, _, files in os.walk(tile_log.tiles_dir)
        for f in files
    ]
    assert len(tile_files) == 0, "All tile files should be deleted"

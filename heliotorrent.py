#!/usr/bin/env python3
"""
Heliotorrent - Build torrents for Sunlight Logs.

This script monitors one or more logs, downloads tiles, creates torrents,
and generates RSS feeds for the log data.
"""

import argparse
import logging
import os
import shutil
import time
import sys
from multiprocessing import Process
from typing import List, Optional, Tuple

import coloredlogs
import yaml

from TileLog import TileLog


def log_loop(
    log_name: str,
    log_url: str,
    frequency: int,
    feed_url: str,
    out_dir: str,
    torrent_dir: str,
    entry_limit: Optional[int],
    verbose: bool,
    delete_tiles: bool,
) -> None:
    """
    Main processing loop for a single log.

    Args:
        log_name: Friendly name for the log
        log_url: URL of the log to scrape
        frequency: How often to run in seconds
        feed_url: URL for the RSS feed
        out_dir: Directory to save scraped files
        torrent_dir: Directory to store torrent files
        entry_limit: Maximum number of entries to fetch
        verbose: Whether to emit verbose logs
        delete_tiles: Whether to delete used tiles after processing
    """
    fmt = f"%(asctime)s {log_name} %(levelname)s: %(message)s"
    coloredlogs.install(level="DEBUG" if verbose else "INFO", fmt=fmt)
    tl = TileLog(log_url, out_dir, entry_limit,torrent_dir,feed_url)

    while True:
        start_time = time.time()
        latest_size = tl.get_latest_tree_size(refresh=True)
        missing_ranges = tl.get_missing_torrent_ranges(0, latest_size)

        for start_index, stop_index in missing_ranges:
            logging.info(f"Processing range {start_index} to {stop_index}")
            tl.download_tiles(start_index, stop_index)
            tl.make_torrents([(start_index, stop_index)])
            tl.make_rss_feed()
            if delete_tiles:
                tl.delete_tiles(start_index, stop_index)

        running_time = time.time() - start_time

        if frequency == 0:
            sys.exit(0)

        if running_time < frequency:
            to_sleep = frequency - running_time
            logging.debug(f"Sleeping for {to_sleep:.2f} seconds")
            time.sleep(to_sleep)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build torrents for Sunlight Logs",
        epilog="Example: ./heliotorrent.py --config config.yaml",
    )
    parser.add_argument(
        "--config",
        help="Path to YAML configuration file.",
    )
    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="Generate an example YAML configuration file and exit.",
    )
    parser.add_argument(
        "--verbose",
        help="Emit verbose logs",
        action="store_true",
    )
    args = parser.parse_args()

    EXAMPLE_CONFIG = """\
# Global settings for Heliotorrent
# Directory to save downloaded tiles
out_dir: "torrents"
# Directory to store generated torrent files
data_dir: "data"

# List of logs to monitor
logs:
  - # A friendly name for this log
    name: "tuscolo2026h1"
    # URL of the log to scrape
    log_url: "https://tuscolo2026h1.skylight.geomys.org/"
    # URL for the RSS feed
    feed_url: "http://127.0.0.1/tuscolo2026h1.skylight.geomys.org.xml"
    # How often to run in seconds (0 for one-time run)
    frequency: 300
    # Maximum number of entries to fetch (null for no limit)
    entry_limit: null
    # Delete used tiles after processing
    delete_tiles: false

# You can add more logs here. Optional keys will use default values.
#  - name: "another-log"
#    log_url: "https://another.log.server/log/"
#    feed_url: "http://127.0.0.1/another.log.server.xml"
#    # frequency, entry_limit, and delete_tiles are optional.
"""

    if args.generate_config:
        print(EXAMPLE_CONFIG)
        sys.exit(0)

    if not args.config:
        parser.error("--config is required unless --generate-config is used.")

    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    # Extract global settings
    out_dir = config.get("out_dir", "torrents")
    data_dir = config.get("data_dir", "data")

    # Create and start a process for each log
    processes = []
    for log_config in config.get("logs", []):
        log_url =
        feed_url =
        name =

        if not log_url or not feed_url or not name:
            logging.warning(
                "Skipping log entry with missing name, log_url or feed_url"
            )
            continue

        process = Process(
            target=log_loop,
            daemon=True,
            args=(
                log_config.get("name"),
                log_config.get("log_url"),
                log_config.get("frequency", 300),
                log_config.get("feed_url"),
                out_dir,
                data_dir,
                log_config.get("entry_limit", None),
                args.verbose,
                log_config.get("delete_tiles", False),
            ),
        )
        processes.append(process)
        process.start()

    # Wait for all processes to complete
    for process in processes:
        process.join()

#!/usr/bin/env python3
"""
Heliotorrent - Build torrents for Sunlight Logs.

This script monitors one or more logs, downloads tiles, creates torrents,
and generates RSS feeds for the log data.
"""

import argparse
import logging
import time
import sys
from multiprocessing import Process
from typing import List, Optional, Tuple

import coloredlogs

from TileLog import TileLog


def log_loop(
    log_url: str,
    frequency: int,
    feed_url: str,
    out_dir: str,
    entry_limit: Optional[int],
    verbose: bool,
    delete_tiles: bool,
) -> None:
    """
    Main processing loop for a single log.

    Args:
        log_url: URL of the log to scrape
        frequency: How often to run in seconds
        feed_url: URL for the RSS feed
        out_dir: Directory to save scraped files
        entry_limit: Maximum number of entries to fetch
        verbose: Whether to emit verbose logs
        delete_tiles: Whether to delete used tiles after processing
    """
    log_name = log_url.removeprefix("https://")
    fmt = f"%(asctime)s {log_name} %(levelname)s: %(message)s"
    coloredlogs.install(level="DEBUG" if verbose else "INFO", fmt=fmt)
    tl = TileLog(log_url, out_dir, entry_limit)

    while True:
        start_time = time.time()
        latest_size = tl.get_latest_tree_size(refresh=True)
        missing_ranges = tl.get_missing_torrent_ranges(0, latest_size)

        for start_index, stop_index in missing_ranges:
            logging.info(f"Processing range {start_index} to {stop_index}")
            tl.download_tiles(start_index, stop_index)
            tl.make_torrents([(start_index, stop_index)])
            tl.make_rss_feed(feed_url)
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
        epilog="Example: ./heliotorrent.py --logs https://tuscolo2026h1.skylight.geomys.org/ --out data/",
    )
    parser.add_argument(
        "--logs",
        type=lambda s: s.split(","),
        required=True,
        help="Comma-separated list of log URLs to monitor",
    )
    parser.add_argument(
        "--feed-url", help="Base URL for the RSS feed", default="http://127.0.0.1"
    )
    parser.add_argument("--out", help="Directory to save scraped files", default="data")
    parser.add_argument(
        "--frequency",
        type=int,
        help="How often to run in seconds (0 for one-time run)",
        default=300,
    )
    parser.add_argument(
        "--entry-limit",
        type=int,
        help="Maximum number of entries to fetch",
        default=None,
    )
    parser.add_argument(
        "--verbose",
        help="Emit verbose logs",
        action="store_true",
    )
    parser.add_argument(
        "--delete-tiles",
        help="Delete used tiles after processing",
        action="store_true",
    )
    args = parser.parse_args()

    # Create and start a process for each log
    processes = []
    for log_url in args.logs:
        process = Process(
            target=log_loop,
            daemon=True,
            args=(
                log_url,
                args.frequency,
                args.feed_url,
                args.out,
                args.entry_limit,
                args.verbose,
                args.delete_tiles,
            ),
        )
        processes.append(process)
        process.start()

    # Wait for all processes to complete
    for process in processes:
        process.join()

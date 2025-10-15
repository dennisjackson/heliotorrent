#!/usr/bin/env python3
"""
Heliotorrent - Build torrents for Sunlight Logs.

This script monitors one or more logs, downloads tiles, creates torrents,
and generates RSS feeds for the log data.
"""

import argparse
import logging
import random
import shutil
import time
import sys
import urllib.request
import json
from multiprocessing import Process
from typing import List, Optional, Dict, Any

import coloredlogs
import yaml

from TileLog import TileLog


def log_loop(
    log_name: str,
    log_url: str,
    frequency: int,
    feed_url: str,
    data_dir: str,
    torrent_dir: str,
    entry_limit: Optional[int],
    verbose: bool,
    delete_tiles: bool,
    webseeds: Optional[List[str]] = None,
) -> None:
    """
    Main processing loop for a single log.

    Args:
        log_name: Friendly name for the log
        log_url: URL of the log to scrape
        frequency: How often to run in seconds
        feed_url: URL for the RSS feed
        data_dir: Directory to save scraped files
        torrent_dir: Directory to store torrent files
        entry_limit: Maximum number of entries to fetch
        verbose: Whether to emit verbose logs
        delete_tiles: Whether to delete used tiles after processing
        webseeds: A list of webseed URLs to add to torrents
    """
    fmt = f"%(asctime)s {log_name} %(levelname)s: %(message)s"
    coloredlogs.install(level="DEBUG" if verbose else "INFO", fmt=fmt)
    tl = TileLog(
        log_name=log_name,
        monitoring_url=log_url,
        storage_dir=data_dir,
        torrent_dir=torrent_dir,
        feed_url=feed_url,
        max_size=entry_limit,
        webseeds=webseeds,
    )

    offset = 60 * random.uniform(0, 1)
    adjusted_frequency = frequency + offset

    # Wait for the offset time before starting the initial loop
    if frequency > 0 and not verbose:
        logging.debug(
            f"Applying initial offset wait of {offset:.2f} seconds (frequency will be {adjusted_frequency:.2f}s)"
        )
        time.sleep(offset)
    tl.make_rss_feed()

    while True:
        start_time = time.time()
        latest_size = tl.get_latest_tree_size(refresh=True)
        missing_ranges = tl.get_missing_torrent_ranges(0, latest_size)

        if missing_ranges:
            missing = sum([end - start for start, end in missing_ranges])
            logging.info(
                f"Missing {missing} entries across {len(missing_ranges)} torrents. {(latest_size - missing) / latest_size * 100:.2f}% Complete"
            )
            for start_index, stop_index in missing_ranges:
                logging.debug(f"Processing range {start_index} to {stop_index}")
                tl.download_tiles(start_index, stop_index)
                tl.make_torrents([(start_index, stop_index)])
                if delete_tiles:
                    tl.delete_tiles(start_index, stop_index)
                tl.make_rss_feed()
        else:
            logging.info("No missing ranges to process.")

        running_time = time.time() - start_time

        if frequency == 0:
            sys.exit(0)

        # Using the adjusted frequency that includes the random offset
        if running_time < adjusted_frequency:
            to_sleep = adjusted_frequency - running_time
            logging.debug(f"Sleeping for {to_sleep:.2f} seconds")
            time.sleep(to_sleep)


def fetch_log_list(url: str) -> Dict[str, Any]:
    """
    Fetch and parse the CT log list from the given URL.

    Args:
        url: URL to fetch the log list from

    Returns:
        Parsed JSON data as a dictionary
    """
    with urllib.request.urlopen(url) as response:
        data = response.read()
    return json.loads(data)


def generate_config_from_log_list(
    log_list: Dict[str, Any], data_dir: str, torrent_dir: str, feed_url_base: str
) -> str:
    """
    Generate a YAML config from the CT log list.

    Args:
        log_list: Parsed log list JSON
        data_dir: Directory to save downloaded tiles
        torrent_dir: Directory to store generated torrent files
        feed_url_base: Base URL for the RSS feed

    Returns:
        YAML config as a string
    """
    config = {
        "data_dir": data_dir,
        "torrent_dir": torrent_dir,
        "feed_url_base": feed_url_base,
        "frequency": 3600,
        "entry_limit": None,
        "delete_tiles": True,
        "logs": [],
    }

    # current_time = datetime.now().isoformat()

    for operator in log_list.get("operators", []):
        # operator_name = operator.get("name", "Unknown")

        # Process tiled logs
        for tiled_log in operator.get("tiled_logs", []):
            monitoring_url = tiled_log.get("monitoring_url")
            if not monitoring_url:
                logging.error("No url for tiled log, skipping")
                continue

            # Create sanitized name for the log
            description = tiled_log.get("description", "")
            log_name = (
                description.replace(" ", "_").replace("'", "").replace("/", "_").lower()
            )

            config["logs"].append(
                {
                    "name": log_name,
                    "log_url": monitoring_url,
                }
            )

    return yaml.dump(config, default_flow_style=False, sort_keys=False)


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
        "--generate-config-from-log-list",
        nargs="?",
        const="https://www.gstatic.com/ct/log_list/v3/all_logs_list.json",
        help="Generate a config from the CT log list (default: https://www.gstatic.com/ct/log_list/v3/all_logs_list.json)",
    )
    parser.add_argument(
        "--feed-url-base",
        default="http://127.0.0.1/torrents",
        help="Base URL for the RSS feed when generating config from log list",
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
data_dir: "data"
# Directory to store generated torrent files
torrent_dir: "torrents"
# Base URL for RSS feeds. The feed for each log will be at {feed_url_base}/{log_name}/feed.xml
feed_url_base: "http://127.0.0.1/torrents"
# How often to run in seconds (0 for one-time run, 3600 is a good default)
frequency: 0
# Maximum number of entries to fetch (null for no limit, 1048576 for 1 torrent)
entry_limit: 1048576
# Delete used tiles after processing
delete_tiles: true
# Global webseeds to add to all torrents. This can be overridden on a per-log basis.
webseeds:
  - "http://global.webseed.example.com/webseed/"

# List of logs to monitor
logs:
  - # A friendly name for this log
    name: "tuscolo2026h1"
    # URL of the log to scrape
    log_url: "https://tuscolo2026h1.skylight.geomys.org/"
    # The following values can be uncommented to override the global settings.
    # feed_url: "http://127.0.0.1/tuscolo2026h1/feed.xml"
    # frequency: 300
    # entry_limit: null
    # delete_tiles: false
    # webseeds:
    #  - "http://webseed.example.com/"

# You can add more logs here. Optional keys will use default values.
#  - name: "another-log"
#    log_url: "https://another.log.server/log/"
"""

    if args.generate_config:
        print(EXAMPLE_CONFIG)
        sys.exit(0)

    if args.generate_config_from_log_list:
        try:
            log_list = fetch_log_list(args.generate_config_from_log_list)
            config_yaml = generate_config_from_log_list(
                log_list, "data", "torrents", args.feed_url_base
            )
            print(config_yaml)
            sys.exit(0)
        except Exception as e:
            logging.error(f"Error generating config from log list: {e}")
            sys.exit(1)

    if not args.config:
        parser.error(
            "--config is required unless --generate-config or --generate-config-from-log-list is used."
        )

    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    if shutil.which("wget2") is None:
        logging.error("wget2 is required but not installed or not in PATH.")
        sys.exit(1)

    # Extract global settings
    data_dir = config.get("data_dir", "data")
    torrent_dir = config.get("torrent_dir", "torrents")
    global_webseeds = config.get("webseeds")
    feed_url_base = config.get("feed_url_base")
    frequency = config.get("frequency", 300)
    entry_limit = config.get("entry_limit")
    delete_tiles = config.get("delete_tiles", False)

    # Create and start a process for each log
    logging.info(
        f"Starting processes for {len(config.get('logs', []))} logs. Processes will sleep for a random offset before starting to minimize contention."
    )
    processes = []
    for log_config in config.get("logs", []):
        if not isinstance(log_config, dict):
            logging.error(f"invalid log entry in config: {log_config}")
            exit(-1)

        name = log_config.get("name")
        log_url = log_config.get("log_url")
        feed_url = log_config.get("feed_url")

        if not feed_url and feed_url_base:
            feed_url = f"{feed_url_base.rstrip('/')}/{name}/feed.xml"

        # Use per-log webseeds if available, otherwise use global webseeds
        webseeds = log_config.get("webseeds", global_webseeds)

        p = Process(
            target=log_loop,
            args=(
                name,
                log_url,
                log_config.get("frequency", frequency),
                feed_url,
                data_dir,
                torrent_dir,
                log_config.get("entry_limit", entry_limit),
                args.verbose,
                log_config.get("delete_tiles", delete_tiles),
                webseeds,
            ),
        )
        processes.append(p)
        p.start()

    # Wait for all processes to complete
    for process in processes:
        process.join()

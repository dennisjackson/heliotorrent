#!/usr/bin/env python3
"""
Heliotorrent - Build torrents for Sunlight Logs.

This script monitors one or more logs, downloads tiles, creates torrents,
and generates RSS feeds for the log data.
"""

import argparse
import logging
import os
import random
import shutil
import subprocess
import sys
import time
from multiprocessing import Process
from pathlib import Path
from typing import List, Optional

import coloredlogs
import yaml

from TileLog import TileLog, build_user_agent
from interactive_config import (
    get_default_config,
    render_config,
    run_interactive_config,
)


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
    user_agent: str,
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
        user_agent: User-Agent header / identifier for outbound requests
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
        user_agent=user_agent,
    )

    offset = 60 * random.uniform(0, 1)
    adjusted_frequency = frequency + offset

    # Wait for the offset time before starting the initial loop
    if frequency > 0 and not verbose:
        logging.debug(
            f"Applying initial offset wait of {offset:.2f} seconds (frequency will be {adjusted_frequency:.2f}s)"
        )
        try:
            time.sleep(offset)
        except InterruptedError:
            logging.warning("Sleep interrupted; shutting down.")
            sys.exit(0)
    tl.make_rss_feed()

    while True:
        start_time = time.time()
        latest_size = tl.get_latest_tree_size(refresh=True)
        missing_ranges = tl.get_missing_torrent_ranges(0, latest_size)

        if missing_ranges:
            for start_index, stop_index in missing_ranges:
                missing = sum([end - start for start, end in missing_ranges])
                logging.info(
                    f"{(latest_size - missing) / latest_size * 100:.2f}% Complete. Missing {len(missing_ranges)} torrents."
                )
                logging.debug(f"Processing range {start_index} to {stop_index}")
                tl.download_tiles(start_index, stop_index)
                tl.make_torrents([(start_index, stop_index)])
                if delete_tiles:
                    tl.delete_tiles(start_index, stop_index)
                tl.make_rss_feed()
        else:
            logging.info("100% Complete. All torrents are up to date.")

        running_time = time.time() - start_time

        if frequency == 0:
            sys.exit(0)

        # Using the adjusted frequency that includes the random offset
        if running_time < adjusted_frequency:
            to_sleep = adjusted_frequency - running_time
            logging.debug(f"Sleeping for {to_sleep:.2f} seconds")
            try:
                time.sleep(to_sleep)
            except InterruptedError:
                logging.warning("Sleep interrupted; shutting down.")
                sys.exit(0)


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
        "--interactive",
        action="store_true",
        help="Interactively populate configuration values when used with --generate-config.",
    )
    parser.add_argument(
        "--verbose",
        help="Emit verbose logs",
        action="store_true",
    )
    parser.add_argument(
        "--heliostat",
        help="Path or executable name for the heliostat binary. When omitted, heliostat is not started.",
    )
    args = parser.parse_args()

    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.INFO)

    if args.interactive and not args.generate_config:
        parser.error("--interactive can only be used together with --generate-config.")

    if args.generate_config:
        if args.interactive:
            interactive_config, save_path = run_interactive_config()
            config_content = render_config(interactive_config)

            # Save to file
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(config_content)
                print(f"Configuration saved to {save_path}")
            except IOError as e:
                print(f"Error saving configuration to {save_path}: {e}")
                print("Configuration content:")
                print(config_content)
        else:
            print(render_config(get_default_config()))
        sys.exit(0)

    if not args.config:
        parser.error("--config is required unless --generate-config is used.")

    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    if shutil.which("wget2") is None:
        logging.error("wget2 is required but not installed or not in PATH.")
        sys.exit(1)

    # Extract global settings
    data_dir = config.get("data_dir", "data")
    torrent_dir = config.get("torrent_dir", "torrents")
    global_webseeds = config.get("webseeds") or []
    feed_url_base = config.get("feed_url_base")
    frequency = config.get("frequency", 300)
    entry_limit = config.get("entry_limit")
    delete_tiles = config.get("delete_tiles", False)
    contact_email = config.get("scraper_contact_email")
    if contact_email is None or not str(contact_email).strip():
        logging.error(
            "scraper_contact_email must be set to a non-empty string in the config."
        )
        sys.exit(1)
    try:
        user_agent = build_user_agent(str(contact_email))
    except ValueError as exc:
        logging.error(str(exc))
        sys.exit(1)

    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(torrent_dir, exist_ok=True)

    heliostat_process: Optional[subprocess.Popen[str]] = None
    if args.heliostat:
        heliostat_candidate = Path(args.heliostat)
        if not heliostat_candidate.is_file():
            logging.error(
                f"heliostat binary '{args.heliostat}' not found. Provide a valid path or ensure it is on PATH."
            )
            sys.exit(1)

        try:
            heliostat_process = subprocess.Popen(
                [heliostat_candidate, "--config-file", args.config],
                stdout=sys.stdout,
                stderr=sys.stderr,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            logging.error(f"Failed to start heliostat: {exc}")
            sys.exit(1)


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
        webseeds = log_config.get("webseeds")
        if not webseeds:
            if global_webseeds:
                webseeds = [f"{x.rstrip('/')}/{name}/" for x in global_webseeds]
            else:
                webseeds = None

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
                user_agent,
                webseeds,
            ),
        )
        processes.append(p)
        p.start()

    try:
        for process in processes:
            process.join()
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received; shutting down.")
        sys.exit(130)

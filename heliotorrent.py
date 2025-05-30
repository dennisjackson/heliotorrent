#!/usr/bin/env python3

import argparse
import logging
import time
import sys

import coloredlogs

from TileLog import TileLog

if __name__ == "__main__":
    coloredlogs.install(level="INFO")

    parser = argparse.ArgumentParser(description="Build torrents for a Sunlight Logs")
    parser.add_argument("log_url", help="URL of the log to scrape")
    parser.add_argument("--out", help="Directory to save scraped files", default="data")
    parser.add_argument(
        "--frequency", type=int, help="How often to run in seconds", default=300
    )
    parser.add_argument(
        "--entry-limit",
        type=int,
        help="Maximum number of entries to fetch",
        default=None,
    )

    args = parser.parse_args()
    tl = TileLog(args.log_url, args.out, args.entry_limit)
    while True:
        start_time = time.time()
        tl.download_tiles()
        tl.make_torrents()
        tl.make_rss_feed("127.0.0.1")
        running_time = time.time() - start_time
        if args.frequency == 0:
            sys.exit(0)
        if running_time < args.frequency:
            to_sleep = args.frequency - running_time
            logging.debug(f"Sleeping for {to_sleep} seconds")
            time.sleep(to_sleep)


# Example:
# ./heliotorrent.py https://tuscolo2026h1.skylight.geomys.org/ data/

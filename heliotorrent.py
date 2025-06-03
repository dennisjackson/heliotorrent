#!/usr/bin/env python3

import argparse
import logging
import time
import sys
from multiprocessing import Process
from urllib.parse import urlsplit

import coloredlogs

from TileLog import TileLog

def log_loop(arg):
    (tl_url, frequency,feed_url, outDir, entry_limit,verbose) = arg
    fmt = f'%(asctime)s {tl_url.removeprefix('https://')} %(levelname)s: %(message)s'
    coloredlogs.install(level="DEBUG" if verbose else "INFO",fmt=fmt)
    tl = TileLog(tl_url, outDir, entry_limit)

    while True:
        start_time = time.time()
        tl.download_tiles()
        tl.make_torrents()
        tl.make_rss_feed(feed_url)
        running_time = time.time() - start_time
        if frequency == 0:
            sys.exit(0)
        if running_time < frequency:
            to_sleep = frequency - running_time
            logging.debug(f"Sleeping for {to_sleep} seconds")
            time.sleep(to_sleep)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build torrents for a Sunlight Logs")
    # parser.add_argument("log_url", help="URL of the log to scrape")
    parser.add_argument('--logs', type=lambda s: s.split(','),help='comaa seperated list of logs')
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
    parser.add_argument(
        "--verbose",
        help="Emit verbose logs",
        action="store_true",
    )
    args = parser.parse_args()

    procs = [Process(target=log_loop, daemon=True, args=((tl, args.frequency, "127.0.0.1", args.out,args.entry_limit,args.verbose),)) for tl in args.logs]

    for p in procs:
        p.start()

    for p in procs:
        p.join()


# Example:
# ./heliotorrent.py https://tuscolo2026h1.skylight.geomys.org/ data/

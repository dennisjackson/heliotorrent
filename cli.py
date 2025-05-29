import argparse
import logging
import coloredlogs
import time
from TileLog import TileLog

if __name__ == "__main__":
    coloredlogs.install(level='INFO')

    parser = argparse.ArgumentParser(description="Build torrents for a Sunlight Logs")
    parser.add_argument("log_url", help="URL of the log to scrape")
    parser.add_argument("--out", help="Directory to save scraped files", default="data")
    parser.add_argument('--frequency',help="How often to run in seconds",default=300)

    args = parser.parse_args()
    tl = TileLog(args.log_url, args.out)
    while True:
        start_time = time.time()
        tl.download_tiles()
        tl.make_torrents()
        tl.make_rss_feed('127.0.0.1')
        running_time = time.time() - start_time
        if running_time < args.frequency:
            to_sleep = args.frequency - running_time
            logging.debug(f"Sleeping for {to_sleep} seconds")
            time.sleep(to_sleep)



# Example:
# python make_torrents.py https://tuscolo2026h1.skylight.geomys.org/ data/

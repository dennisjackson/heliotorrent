import argparse
import logging
from TileLog import TileLog

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Build torrents for a Sunlight Logs"
    )
    parser.add_argument("log_url", help="URL of the log to scrape")
    parser.add_argument("--out", help="Directory to save scraped files",default='data')

    args = parser.parse_args()
    tl = TileLog(args.log_url, args.out,4096*256*100)
    tl.make_torrents()


# Example:
# python make_torrents.py https://tuscolo2026h1.skylight.geomys.org/ data/
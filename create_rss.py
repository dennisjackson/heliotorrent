import argparse
import logging
from TileLog import TileLog

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Scrape log tiles from a Sunlight server"
    )
    parser.add_argument("log_url", help="URL of the log to scrape")
    parser.add_argument("--out", help="Directory to save scraped files", default="data")

    args = parser.parse_args()
    tl = TileLog(args.log_url, args.out)
    tl.make_rss_feed("127.0.0.1")


# Example:
# python create_rss.py https://tuscolo2026h1.skylight.geomys.org/ data/

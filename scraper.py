import argparse
import logging
import subprocess
import sys
from util import *

USER_AGENT = "Heliotorrent v0.0.0 Contact: scraper-reports@dennis-jackson.uk"


def run_wget(output_dir, monitoring_path, tiles):
    command = [
        "wget",
        "--input-file=-",
        f"--base={monitoring_path}",
        "--no-clobber",
        "--retry-connrefused",
        "--retry-on-host-error",
        f"--directory-prefix={output_dir}",
        "--compression=gzip",
        "--no-verbose",
        "--force-directories",
        f"--user-agent={USER_AGENT}",
    ]
    subprocess.run(
        command, input="\n".join(tiles).encode(), stdout=sys.stdout, check=True
    )


def scrape_log(log_url, output_dir, max_limit=None):
    tree_size, chkpt = fetch_checkpoint(log_url)
    save_checkpoint(output_dir, url_to_dir(log_url), tree_size, chkpt)
    logging.info(f"{log_url} has {tree_size} entries")
    if not max_limit:
        max_limit = tree_size
    limit = min(max_limit, tree_size)
    run_wget(output_dir, log_url, [x for x in get_data_tile_paths(0, limit, tree_size)])
    run_wget(output_dir, log_url, [x for x in get_hash_tile_paths(0, limit, tree_size)])
    run_wget(
        output_dir,
        log_url,
        [
            x
            for x in get_hash_tile_paths(
                0, limit, tree_size, levelStart=2, partials_req=True
            )
        ],
    )
    logging.info(f"Fetched all tiles up to {limit} for {log_url}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Scrape log tiles from a Sunlight server"
    )
    parser.add_argument("log_url", help="URL of the log to scrape")
    parser.add_argument("output_dir", help="Directory to save scraped files")
    parser.add_argument(
        "--max-limit",
        type=int,
        help="Maximum number of entries to scrape (defaults to tree size)",
    )

    args = parser.parse_args()
    scrape_log(args.log_url, args.output_dir, args.max_limit)


# Example:
# python scraper.py https://tuscolo2026h1.skylight.geomys.org/ data/ --max-limit 1024

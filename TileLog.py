from glob import glob
import logging
import urllib.request
from urllib.parse import urlsplit
import os
from concurrent.futures import ThreadPoolExecutor
import math
from datetime import datetime, timezone
import random
import time
import re

from feedgen.feed import FeedGenerator

from util import (
    get_data_tile_paths,
    get_hash_tile_paths,
    create_torrent_file,
    get_torrent_file_info,
    run_scraper,
)

VERSION = "v0.0.0"
USER_AGENT = f"Heliotorrent {VERSION} Contact: scraper-reports@dennis-jackson.uk"
ENTRIES_PER_LEAF_TORRENT = 4096 * 256  # 4096 tiles per torrent
TRACKER_LIST_URL = (
    "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt"
)


class TileLog:
    def __init__(self, monitoring_url, storage_dir, torrent_dir, feed_url, max_size=None):
        self.monitoring_url = monitoring_url.removesuffix("/")
        self.log_name = monitoring_url.removeprefix("https://").removesuffix("/")
        self.max_size = max_size
        self.feed_url = feed_url

        # TODO calculate this when we are about to invoke wget. Doesn't need to be stored.
        self.nested_dir_count = len(urlsplit(self.monitoring_url).path.split("/")) - 1


        self.storage_dir = os.path.join(storage_dir, self.log_name)
        self.checkpoints_dir = os.path.join(self.storage_dir, "checkpoint")
        self.tiles_dir = os.path.join(self.storage_dir, "tile")

        self.torrents_dir = os.path.join(torrent_dir, self.log_name)

        if max_size:
            logging.warning(
                f"Running TileLog with maximum entry limit of {self.max_size}"
            )
        try:
            with urllib.request.urlopen(TRACKER_LIST_URL) as r:
                self.trackers = [
                    x.decode().strip() for x in r.readlines() if len(x) > 1
                ]
                logging.debug(
                    f"Discovered {len(self.trackers)} trackers from {TRACKER_LIST_URL}"
                )
        except Exception as e:
            logging.error(
                f"Error fetching trackers from {TRACKER_LIST_URL}", exc_info=e
            )
        for x in [
            self.storage_dir,
            self.tiles_dir,
            self.checkpoints_dir,
            self.torrents_dir,
        ]:
            os.makedirs(x, exist_ok=True)
        self.generate_readme()

    def generate_readme(self):
        readme_path = os.path.join(self.storage_dir, "README.md")
        content = f"""# {self.log_name} Tile Log

This directory contains tiles scraped from the monitoring URL: {self.monitoring_url}.
This Torrent was produced by {VERSION}
"""
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)
        logging.info(f"Generated README file at {readme_path}")

    def __get_leaf_tile_paths(self, start_index=None, stop_index=None):
        if start_index is None:
            start_index = 0
        if stop_index is None:
            stop_index = self.get_latest_tree_size()
        paths = []
        paths += get_data_tile_paths(start_index, stop_index, stop_index)
        paths += get_hash_tile_paths(
            start_index,
            stop_index,
            stop_index,
            level_start=0,
            level_end=2,
            partials_req=False,
        )
        return paths

    def __get_upper_tree_tile_paths(self, start_index=None, stop_index=None):
        if start_index is None:
            start_index = 0
        if stop_index is None:
            stop_index = self.get_latest_tree_size()
        paths = []
        paths += get_hash_tile_paths(
            start_index, stop_index, stop_index, level_start=2, partials_req=True
        )
        return paths

    def __get_all_tile_paths(self, start_index=None, stop_index=None):
        paths = []
        paths += self.__get_leaf_tile_paths(start_index, stop_index)
        paths += self.__get_upper_tree_tile_paths(start_index, stop_index)
        return paths

    def get_latest_tree_size(self, refresh=False):
        size = self.__get_latest_checkpoint(refresh=refresh)[0]
        if self.max_size:
            return min(size, self.max_size)
        else:
            return size

    # Functions for scraping logs

    def __get_latest_checkpoint(self, refresh=False):
        if refresh:
            try:
                chkpt_url = f"{self.monitoring_url}/checkpoint"
                with urllib.request.urlopen(chkpt_url) as r:
                    chkpt = r.read().decode()
                    size = chkpt.splitlines()[1]
                    logging.info(f"Fetched checkpoint of size {size}")
            except Exception as e:
                logging.error(f"Failed to fetch checkpoint at {chkpt_url}", exc_info=e)
            with open(os.path.join(self.checkpoints_dir, size), "w", encoding="utf-8") as w:
                w.write(chkpt)
        latest = max(
            (int(os.path.basename(x)) for x in glob(f"{self.checkpoints_dir}/" + "*"))
        )
        p = os.path.join(self.checkpoints_dir, str(latest))
        return latest, p

    def download_tiles(self, start_index=None, stop_index=None):
        if start_index is None:
            start_index = self.get_latest_tree_size(refresh=False)  # 0?
        if stop_index is None:
            stop_index = self.get_latest_tree_size(refresh=True)
        tiles_to_scrape = (stop_index - start_index) // 256
        log_level = logging.getLogger().getEffectiveLevel()
        command = [
            "wget",
            "--input-file=-",
            "--no-clobber",
            "--retry-connrefused",
            "--retry-on-host-error",
            f"--directory-prefix={self.tiles_dir}",
            "--force-directories",
            '--no-host-directories',
            "--compression=gzip",
            "--no-verbose" if log_level is logging.DEBUG else "--quiet",
            f'--user-agent="{USER_AGENT}"',
            f'--cut-dirs={self.nested_dir_count+1}',
        ]
        tiles = self.__get_leaf_tile_paths(
            start_index, stop_index
        )  # todo fixme only downloads leafs
        tiles = [self.monitoring_url + "/" + t for t in tiles]
        random.shuffle(tiles)  # Shuffling ensures each worker gets a balanced load
        logging.debug(
            f"Identified {tiles_to_scrape} new tiles between {start_index} and {stop_index}"
        )

        # Split 100 chunks across 10 workers
        chunk_size = math.ceil(len(tiles) / 100)
        chunks = [
            (command, tiles[i : i + chunk_size])
            for i in range(0, len(tiles), chunk_size)
        ]

        assert sum((len(x[1]) for x in chunks)) == len(tiles)
        for command, tiles in chunks:
            assert len(tiles) > 0

        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(run_scraper, chunks)

        logging.info(
            f"Fetched all tiles between entries {start_index} and {stop_index}"
        )

    # Functions for creating torrent files

    def __should_generate_new_upper_torrent(self, current_checkpoint):
        torrents = glob(os.path.join(self.torrents_dir, "L2345-0-[0-9]*.torrent"))
        last_modified = max(torrents, key=os.path.getmtime, default=None)
        if (
            last_modified
            and time.time() - os.path.getmtime(last_modified) < 6 * 60 * 60
        ):
            logging.debug(
                f"Not generating a new upper tree torrent, last modified too recent: {os.path.getmtime(last_modified)}"
            )
            return False
        last_checkpoint_size = max(
            [int(re.search(r"-(\d+)\.torrent$", p).group(1)) for p in torrents],
            default=0,
        )
        logging.debug(f"last upper torrent generated {last_modified}, considered stale")
        if (
            current_checkpoint // ENTRIES_PER_LEAF_TORRENT
            - last_checkpoint_size // ENTRIES_PER_LEAF_TORRENT
            > 0
        ):
            logging.debug(
                f"entries since last checkpoint: {current_checkpoint -last_checkpoint_size }"
            )
            return True
        logging.debug(
            f"Not generating a new upper tree torrent, no new leaf torrents. new:{current_checkpoint}, old:{last_checkpoint_size}"
        )
        return False

    def make_torrents(self, ranges):
        for startIndex, endIndex in ranges:
            assert (
                endIndex - startIndex
            ) == ENTRIES_PER_LEAF_TORRENT, (
                f"Elements in torrent must match {ENTRIES_PER_LEAF_TORRENT} (ENTRIES_PER_LEAF_TORRENT)"
            )
            name = f"{self.log_name}-L01-{startIndex}-{endIndex}"
            tp = os.path.join(self.torrents_dir, f"L01-{startIndex}-{endIndex}.torrent")
            paths = self.__get_leaf_tile_paths(
                start_index=startIndex, stop_index=endIndex
            )
            paths = [os.path.join(self.storage_dir, x) for x in paths]
            paths += [os.path.join(self.storage_dir, "README.md")]
            create_torrent_file(
                name, "HelioTorrent " + VERSION, paths, self.trackers, tp
            )
        logging.info(f"Generated L01 torrents for ranges: {ranges}")

    def make_upper_torrents(self):
        size = self.get_latest_tree_size()
        if self.__should_generate_new_upper_torrent(size):
            name = f"{self.log_name}-L2345-0-{size}"
            paths = self.__get_upper_tree_tile_paths(0, size)
            paths = [os.path.join(self.storage_dir, x) for x in paths]
            paths += [self.__get_latest_checkpoint()[1]]
            paths += [os.path.join(self.storage_dir, "README.md")]
            tp = os.path.join(self.torrents_dir, f"L2345-0-{size}.torrent")
            if self.max_size:
                logging.warning(
                    "max_size is set, so upper tree torrent may be missing files"
                )
            create_torrent_file(
                name, "HelioTorrent " + VERSION, paths, self.trackers, tp
            )
            logging.info(f"Generated upper tree torrent: {tp}")

    def get_missing_torrent_ranges(self, start_index, stop_index):
        existing_torrents = glob(os.path.join(self.torrents_dir, "L01-*-*.torrent"))
        existing_ranges = [
            tuple(
                map(
                    int,
                    re.search(
                        r"L01-(\d+)-(\d+)\.torrent$", os.path.basename(t)
                    ).groups(),
                )
            )
            for t in existing_torrents
        ]
        existing_ranges.sort()

        missing_ranges = []
        current_start = start_index

        for start, end in existing_ranges:
            if current_start < start:
                missing_ranges.append((current_start, start))
            current_start = max(current_start, end)

        if current_start < stop_index:
            missing_ranges.append((current_start, stop_index))

        split_ranges = []
        for start, end in missing_ranges:
            while start < end:
                chunk_end = start + ENTRIES_PER_LEAF_TORRENT
                if chunk_end > end:
                    break
                split_ranges.append((start, chunk_end))
                start = chunk_end
        logging.info("Identified missing ranges: " + str(split_ranges))
        return split_ranges

    # Functions specific to creating RSS feeds

    def add_torrent_to_feed(self, feed_generator, t):
        logging.debug(f"Adding {t} to feed")
        mtime = datetime.fromtimestamp(os.path.getmtime(t), tz=timezone.utc)
        t_name = os.path.basename(t).strip(".torrent")
        (ih, size) = get_torrent_file_info(t)

        fe = feed_generator.add_item()
        fe.title(t_name)
        fe.torrent.infohash(ih)
        fe.torrent.contentlength(f"{size}")
        fe.torrent.filename(t_name)
        fe.published(mtime)
        # fe.enclosure(
        #     url=f"magnet:?xt=urn:btih:{ih}",
        #     length=size,
        #     type="application/x-bittorrent",
        # )
        base_url = self.feed_url.rsplit("/", 1)[0]
        fe.enclosure(
            url=f"{base_url}/{t_name}.torrent",
            length=str(size),
            type="application/x-bittorrent",
        )

    def make_rss_feed(self):
        # TODO: Make an index.html file in a new function?
        fg = FeedGenerator()
        fg.load_extension("torrent")
        fg.title(self.log_name)
        fg.link(href=self.feed_url)
        fg.description("TODO")
        # TODO Make different feeds for data level, tile and both?
        paths = glob(os.path.join(self.torrents_dir, "*.torrent"))
        for p in paths:
            self.add_torrent_to_feed(fg, p)
        fp = os.path.join(self.torrents_dir, "feed.xml")
        fg.rss_file(fp, pretty=True)
        logging.info(f"Wrote {fp} with {len(paths)} torrent files")

    def delete_tiles(self, start_index, stop_index):
        data_tile_paths = list(get_data_tile_paths(start_index, stop_index, stop_index))
        hash_tile_paths = list(
            get_hash_tile_paths(
                start_index,
                stop_index,
                stop_index,
                level_start=0,
                level_end=1,
                partials_req=False,
            )
        )
        all_tile_paths = data_tile_paths + hash_tile_paths

        for tile_path in all_tile_paths:
            full_path = os.path.join(self.storage_dir, tile_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                logging.info(f"Deleted tile: {full_path}")
            else:
                logging.debug(f"Tile not found, skipping: {full_path}")

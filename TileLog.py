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
TILES_PER_LEAF_TORRENT = 4096 * 256  # 4096 tiles per torrent
TRACKER_LIST_URL = (
    "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt"
)


class TileLog:
    def __init__(self, monitoring_url, storage_dir, max_size=None):
        self.url = monitoring_url.removesuffix('/')
        self.log_name = monitoring_url.removeprefix('https://')
        self.storage = storage_dir + "/" + self.log_name
        self.checkpoints = self.storage + "/checkpoints"
        self.torrents = storage_dir + "/torrents/" + self.log_name
        self.tiles = self.storage + "/tile"
        self.max_size = max_size
        # TODO - Create a readme file here
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
        for x in [self.checkpoints, self.torrents, self.tiles]:
            os.makedirs(x, exist_ok=True)

    def __get_leaf_tile_paths(self, start_index=None, stop_index=None):
        if start_index is None:
            start_index = 0
        if stop_index is None:
            stop_index = self.__get_latest_tree_size()
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
            stop_index = self.__get_latest_tree_size()
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

    def __get_latest_tree_size(self, refresh=False):
        size = self.__get_latest_checkpoint(refresh=refresh)[0]
        if self.max_size:
            return min(size, self.max_size)
        else:
            return size

    # Functions for scraping logs

    def __get_latest_checkpoint(self, refresh=False):
        if refresh:
            try:
                chkpt_url = f"{self.url}/checkpoint"
                with urllib.request.urlopen(chkpt_url) as r:
                    chkpt = r.read().decode()
                    size = chkpt.splitlines()[1]
                    logging.info(f"Fetched checkpoint of size {size}")
            except Exception as e:
                logging.error(f"Failed to fetch checkpoint at {chkpt_url}", exc_info=e)
            with open(f"{self.checkpoints}/{size}", "w", encoding="utf-8") as w:
                w.write(chkpt)
        latest = max(
            (int(os.path.basename(x)) for x in glob(f"{self.checkpoints}/" + "*"))
        )
        p = f"{self.checkpoints}/{latest}"
        return latest, p

    def download_tiles(self):
        old_size = self.__get_latest_tree_size(refresh=False)
        size = self.__get_latest_tree_size(refresh=True)
        tiles_to_scrape = (size - old_size) // 256
        log_level = logging.getLogger().getEffectiveLevel()
        command = [
            "wget",
            "--input-file=-",
            "--no-clobber",
            "--retry-connrefused",
            "--retry-on-host-error",
            f"--directory-prefix=data",  #TODO FIXME
            "--force-directories",
            "--compression=gzip",
            "--no-verbose" if log_level is logging.DEBUG else '--quiet',
            f'--user-agent="{USER_AGENT}"',
        ]
        tiles = self.__get_all_tile_paths()
        tiles = [self.url +'/' + t for t in tiles]
        random.shuffle(tiles)  # Shuffling ensures each worker gets a balanced load
        logging.debug(f"Identified {tiles_to_scrape} new tiles since last run")

        # Split 100 chunks across 10 workers
        chunk_size = math.ceil(len(tiles) / 100)
        chunks = [
            (command, tiles[i : i + chunk_size])
            for i in range(0, len(tiles), chunk_size)
        ]

        assert sum((len(x[1]) for x in chunks)) == len(tiles)
        for (command,tiles) in chunks:
            assert len(tiles) > 0

        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(run_scraper, chunks)

        logging.info(
            f"Fetched all {size // 256} tiles up to entry {size}"
        )

    # Functions for creating torrent files

    def __should_generate_new_upper_torrent(self, current_checkpoint):
        torrents = glob(f"{self.torrents}/L2345-0-[0-9]*.torrent")
        last_modified = max(torrents, key=os.path.getmtime, default=0)
        if time.time() - os.path.getmtime(last_modified) < 6 * 60 * 60:
            logging.debug(
                f"Not generating a new upper tree torrent, last modified too recent {last_modified}"
            )
            return False
        last_checkpoint_size = max(
            [int(re.search(r"-(\d+)\.torrent$", p).group(1)) for p in torrents],
            default=0,
        )
        logging.debug(f"last upper torrent generated {last_modified}, considered stale")
        if (
            current_checkpoint // TILES_PER_LEAF_TORRENT
            - last_checkpoint_size // TILES_PER_LEAF_TORRENT
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

    def make_torrents(self):
        size = self.__get_latest_tree_size()
        for i in range(TILES_PER_LEAF_TORRENT, size, TILES_PER_LEAF_TORRENT):
            startIndex = i - TILES_PER_LEAF_TORRENT
            endIndex = i
            name = f"{self.log_name}-L01-{startIndex}-{endIndex}"
            tp = f"{self.torrents}/L01-{startIndex}-{endIndex}.torrent"
            paths = self.__get_leaf_tile_paths(
                start_index=startIndex, stop_index=endIndex
            )
            paths = [f"{self.storage}/{x}" for x in paths]
            paths += [f"{self.storage}/README.md"]
            create_torrent_file(
                name, "HelioTorrent " + VERSION, paths, self.trackers, tp
            )
        if self.__should_generate_new_upper_torrent(size):
            name = f"{self.log_name}-L2345-0-{size}"
            paths = self.__get_upper_tree_tile_paths(0, size)
            paths = [f"{self.storage}/{x}" for x in paths]
            paths += [self.__get_latest_checkpoint()[1]]
            paths += [f"{self.storage}/README.md"]  # TODO needs creating
            tp = f"{self.torrents}/L2345-0-{size}.torrent"
            if self.max_size:
                logging.warning(
                    "max_size is set, so upper tree torrent may be misisng files"
                )
            create_torrent_file(
                name, "HelioTorrent " + VERSION, paths, self.trackers, tp
            )

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
        fe.enclosure(
            url=f"http://host.docker.internal:8000/tuscolo2026h1.skylight.geomys.org/torrents/{t_name}.torrent",
            length=size,  # todo should be size of file
            type="application/x-bittorrent",
        )

    def make_rss_feed(self, feed_url):
        # TODO: Make an index.html file in a new function?
        fg = FeedGenerator()
        fg.load_extension("torrent")
        fg.title(self.log_name)
        fg.link(href=feed_url)
        fg.description("TODO")
        # TODO Make different feeds for data level, tile and both?
        paths = glob(self.torrents + "/*.torrent")
        for p in paths:
            self.add_torrent_to_feed(fg, p)
        fp = f"{self.torrents}/feed.xml"
        fg.rss_file(fp, pretty=True)
        logging.info(f"Wrote {fp} with {len(paths)} torrent files")

from glob import glob
import logging
import urllib.request
from urllib.parse import urlsplit
import os
import subprocess
import sys
from datetime import datetime, timezone
import hashlib

from torf import Torrent
import humanize
import bencodepy

from feedgen.feed import FeedGenerator

from util import (
    get_data_tile_paths,
    get_hash_tile_paths,
)

VERSION = "v0.0.0"
USER_AGENT = f"Heliotorrent {VERSION} Contact: scraper-reports@dennis-jackson.uk"
TORRENT_SIZE = 4096 * 256  # 4096 tiles per torrent
TRACKER_LIST_URL = (
    "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt"
)


class TileLog:
    def __init__(self, monitoring_url, storage_dir, max_size=None):
        self.url = monitoring_url
        self.log_name = urlsplit(monitoring_url).netloc
        self.storage = storage_dir + "/" + self.log_name
        self.checkpoints = self.storage + "/checkpoints"
        self.torrents = self.storage + "/torrents"
        self.tiles = self.storage + "/tile"
        self.max_size = max_size
        with urllib.request.urlopen(TRACKER_LIST_URL) as r:
            self.trackers = [x.decode().strip() for x in r.readlines() if len(x) > 1]
            logging.info(
                f"Discovered {len(self.trackers)} trackers from {TRACKER_LIST_URL}"
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
            with urllib.request.urlopen(f"{self.url}/checkpoint") as r:
                chkpt = r.read().decode()
                size = chkpt.split("\n")[1]
                logging.debug(f"Fetched checkpoint of size {size} from {self.url}")
            with open(f"{self.checkpoints}/{size}", "w", encoding="utf-8") as w:
                w.write(chkpt)
        latest = max(
            (int(os.path.basename(x)) for x in glob(f"{self.checkpoints}/" + "*"))
        )
        p = f"{self.checkpoints}/{latest}"
        return latest, p

    def download_tiles(self):
        size = self.__get_latest_checkpoint(refresh=True)[0]
        command = [
            "wget",
            "--input-file=-",
            f"--base={self.url}",
            "--no-clobber",
            "--retry-connrefused",
            "--retry-on-host-error",
            f"--directory-prefix={self.tiles}",
            "--force-directories",
            "--no-host-directories",
            "--cut-dirs=1",
            "--compression=gzip",
            "--no-verbose",
            f"--user-agent={USER_AGENT}",
        ]
        subprocess.run(
            command,
            input="\n".join(self.__get_all_tile_paths()).encode(),
            stdout=sys.stdout,
            check=True,
        )
        logging.info(f"Fetched all tiles up to {size} for {self.log_name}")

    # Functions for creating torrent files

    def __create_torrent_file(self, name, paths, trackers, out_path):
        t = Torrent(
            trackers=trackers,
            private=False,
            created_by="HelioTorrent " + VERSION,
            creation_date=datetime.now(),
        )
        if os.path.isfile(out_path):
            logging.info(f"{out_path} already exists")
            return
        if not all(os.path.exists(p) for p in paths):
            for p in paths:
                if not os.path.exists(p):
                    logging.info(f"Missing file: {p}")
            logging.error(f"Missing files for torrent {name}")
            return
        t.filepaths = paths
        t.name = name
        t.generate()
        t.write(out_path)
        logging.info(
            f"Wrote {out_path} with content size {humanize.naturalsize(t.size)}"
        )

    def make_torrents(self):
        size = self.__get_latest_tree_size()
        for i in range(TORRENT_SIZE, size, TORRENT_SIZE):
            startIndex = i - TORRENT_SIZE
            endIndex = i
            name = f"{self.log_name}-L01-{startIndex}-{endIndex}"
            tp = f"{self.torrents}/L01-{startIndex}-{endIndex}.torrent"
            paths = self.__get_leaf_tile_paths(
                start_index=startIndex, stop_index=endIndex
            )
            paths = [f"{self.storage}/{x}" for x in paths]
            self.__create_torrent_file(name, paths, self.trackers, tp)

        name = f"{self.log_name}-L2345-0-{size}.torrent"
        paths = self.__get_upper_tree_tile_paths(0, size)
        paths = [f"{self.storage}/{x}" for x in paths]
        paths += [self.__get_latest_checkpoint()[1]]
        tp = f"{self.torrents}/L2345-0-{size}.torrent"
        if self.max_size:
            logging.warning(
                "max_size is set, so checkpoint in torrent may not be verifiable"
            )
            logging.warning("Partial tiles are likely missing")
        self.__create_torrent_file(name, paths, self.trackers, tp)

    # Functions specific to creating RSS feeds

    def __get_torrent_file_info(self, tf):
        with open(tf, "rb") as f:
            meta = bencodepy.decode(f.read())

        info = meta[b"info"]
        info_encoded = bencodepy.encode(info)
        infohash = hashlib.sha1(info_encoded).hexdigest()

        length = 0
        if b"files" in info:  # multi-file
            length = sum(f[b"length"] for f in info[b"files"])
        else:  # single-file
            length = info[b"length"]
        return (infohash, length)

    def add_torrent_to_feed(self, feed_generator, t):
        logging.debug(f"Adding {t} to feed")
        mtime = datetime.fromtimestamp(os.path.getmtime(t), tz=timezone.utc)
        t_name = os.path.basename(t).strip(".torrent")
        (ih, size) = self.__get_torrent_file_info(t)

        fe = feed_generator.add_item()
        fe.title(t_name)
        fe.torrent.infohash(ih)
        fe.torrent.contentlength(f"{size}")
        fe.torrent.filename(t_name)
        fe.published(mtime)
        fe.enclosure(
            url=f"magnet:?xt=urn:btih:{ih}",
            length=size,
            type="application/x-bittorrent",
        )

    def make_rss_feed(self, feed_url):
        fg = FeedGenerator()
        fg.load_extension("torrent")
        fg.title(self.log_name)
        fg.link(href=feed_url)
        fg.description("TODO")
        paths = glob(self.torrents + "/*.torrent")
        for p in paths:
            self.add_torrent_to_feed(fg, p)
        fp = f"{self.torrents}/feed.xml"
        fg.rss_file(fp, pretty=True)
        logging.info(f"Wrote {fp} with {len(paths)} torrent files")

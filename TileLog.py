from util import url_to_dir, get_data_tile_paths, get_hash_tile_paths, get_latest_checkpoint,fetch_checkpoint,save_checkpoint
from make_torrents import build_torrents
from create_rss import build_feed
from glob import glob
import logging
import urllib.request
from urllib.parse import urlsplit
import os
import subprocess
import sys

VERSION = "v0.0.0"
USER_AGENT = f"Heliotorrent {VERSION} Contact: scraper-reports@dennis-jackson.uk"

class TileLog:
    def __init__(self, monitoring_url, storage_dir):
        self.url = monitoring_url
        storage = storage_dir + '/' + urlsplit(monitoring_url).netloc
        self.checkpoints = storage + '/checkpoints'
        self.torrents = storage + '/torrents'
        self.tiles = storage + '/tile'
        for x in [self.checkpoints, self.torrents, self.tiles]:
            os.makedirs(x,exist_ok=True)

    def __get_leaf_tile_paths(self,start_index=None,stop_index=None):
        if start_index is None:
            start_index = 0
        if stop_index is None:
            stop_index = self.__get_latest_tree_size()
        paths = []
        paths += get_data_tile_paths(start_index,stop_index,
                                     stop_index)
        paths += get_hash_tile_paths(start_index,stop_index,stop_index,level_start=0,level_end=2,partials_req=False)
        return paths

    def __get_upper_tree_tile_paths(self,start_index=None,stop_index=None):
        if start_index is None:
            start_index = 0
        if stop_index is None:
            stop_index = self.__get_latest_tree_size()
        paths = []
        paths += get_hash_tile_paths(start_index,stop_index,stop_index,level_start=2,partials_req=True)
        return paths

    def __get_all_tile_paths(self,start_index=None,stop_index=None):
        paths = []
        paths += self.__get_leaf_tile_paths(start_index,stop_index)
        paths += self.__get_upper_tree_tile_paths(start_index,stop_index)
        return paths

    def __get_latest_tree_size(self,refresh=False):
        return self.__get_latest_checkpoint(refresh=refresh)[0]

    def __get_latest_checkpoint(self,refresh=False):
        if refresh:
            with urllib.request.urlopen(f"{self.url}/checkpoint") as r:
                chkpt = r.read().decode()
                size = chkpt.split("\n")[1]
                logging.debug(f"Fetched checkpoint of size {size} from {self.url}")
            with open(f"{self.checkpoints}/{size}", "w", encoding="utf-8") as w:
                w.write(chkpt)
        latest = max((int(os.path.basename(x)) for x in glob(f"{self.checkpoints}/" + "*")))
        p = "{self.checkpoints}/{size}"
        return latest, p

    def download_tiles(self):
        self.__get_latest_checkpoint(refresh=True)
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
        command, input="\n".join(self.__get_all_tile_paths()).encode(), stdout=sys.stdout, check=True
    )
        logging.info(f"Fetched all tiles up to {limit} for {log_url}")


    def make_torrents(self):
        build_torrents(self.torrents,self.url,self.__get_latest_tree_size())

    def make_rss_feed(self,feed_url):
        fg = build_feed(feed_url,self.url,glob(f'{self.torrents}'))
        fg.rss_file(f"{self.torrents}/feed.xml",pretty=True)

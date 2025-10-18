from glob import glob
import json
import logging
import os
import random
import re
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlsplit

from feedgen.feed import FeedGenerator

from .tilelog_html import write_root_index, write_torrent_index_html
from .util import (
    get_data_tile_paths,
    get_hash_tile_paths,
    create_torrent_file,
    run_scraper,
    get_torrent_file_info,
)


def _get_version() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        version = result.stdout.strip()
        if version:
            return version
    except Exception as exc:
        logging.error("Unable to derive git version; falling back to default: %s", exc)
    return "UNKNOWN"


VERSION = _get_version()

def build_user_agent(contact_email: str) -> str:
    email = (contact_email or "").strip()
    if not email:
        raise ValueError("Contact email must be provided to build a user agent.")
    return f"Heliotorrent/{VERSION} Contact: {email}"

ENTRIES_PER_LEAF_TORRENT = 4096 * 256  # 4096 tiles per torrent
TRACKER_LIST_URL = (
    "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt"
)
FETCH_CHECKPOINT_BACKOFF = 60
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_ASSETS_DIR = os.path.join(REPO_ROOT, "static")
DEFAULT_TORRENT_STYLESHEET = os.path.join(STATIC_ASSETS_DIR, "torrents.css")
PUBLIC_STYLESHEET_NAME = "style.css"


class TileLog:
    def __init__(
        self,
        log_name,
        monitoring_url,
        storage_dir,
        torrent_dir,
        feed_url,
        max_size=None,
        webseeds=None,
        user_agent=None,
    ):
        if not user_agent:
            raise ValueError("user_agent must be provided when creating TileLog.")
        self.monitoring_url = monitoring_url.removesuffix("/")
        self.user_agent = user_agent

        # Sanitize log_name to ensure it's suitable as a directory name
        sanitized_name = re.sub(r'[\\/*?:"<>|]', "_", log_name)  # Replace invalid chars
        sanitized_name = sanitized_name.strip()  # Remove leading/trailing whitespace
        if not sanitized_name:
            sanitized_name = (
                monitoring_url.removeprefix("https://")
                .removesuffix("/")
                .replace(".", "_")
                .replace("/", "_")
            )

        self.log_name = sanitized_name
        self.max_size = max_size
        self.feed_url = feed_url
        self.webseeds = webseeds

        self.storage_dir = os.path.join(storage_dir, self.log_name)
        self.checkpoints_dir = os.path.join(self.storage_dir, "checkpoint")
        self.tiles_dir = os.path.join(self.storage_dir, "tile")

        self.torrents_root_dir = torrent_dir
        self.torrents_dir = os.path.join(self.torrents_root_dir, self.log_name)

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
            self.trackers = []
        for x in [
            self.storage_dir,
            self.tiles_dir,
            self.checkpoints_dir,
            self.torrents_dir,
        ]:
            os.makedirs(x, exist_ok=True)
        self._install_static_assets()
        self.generate_readme()

    def _install_static_assets(self):
        if not os.path.exists(DEFAULT_TORRENT_STYLESHEET):
            logging.warning(
                "Default torrent stylesheet not found at %s; HTML output will be unstyled.",
                DEFAULT_TORRENT_STYLESHEET,
            )
            return

        os.makedirs(self.torrents_root_dir, exist_ok=True)
        target_path = os.path.join(self.torrents_root_dir, PUBLIC_STYLESHEET_NAME)
        try:
            shutil.copyfile(DEFAULT_TORRENT_STYLESHEET, target_path)
            logging.debug("Installed torrent stylesheet at %s", target_path)
        except OSError as exc:
            logging.warning(
                "Unable to copy torrent stylesheet to %s: %s", target_path, exc
            )

    def generate_readme(self):
        readme_path = os.path.join(self.storage_dir, "README.md")
        expected_content = f"""LOG URL: {self.monitoring_url}"""

        if os.path.exists(readme_path):
            with open(readme_path, "r", encoding="utf-8") as f:
                existing_content = f.read()

            if existing_content != expected_content:
                logging.error(
                    f"Existing README at {readme_path} has different content than expected. Changing this file will cause issues with the existing torrents. Continuing with existing file."
                )
        else:
            # File doesn't exist, create it
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(expected_content)
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

    def __get_latest_checkpoint(self, refresh=False, iterations=0):
        if iterations > 20:
            logging.critical("Repeated failures to fetch a checkpoint, giving up.")
            exit(1)
        if refresh:
            try:
                chkpt_url = f"{self.monitoring_url}/checkpoint"
                req = urllib.request.Request(
                    chkpt_url,
                    data=None,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept": "text/plain",
                    },
                )

                with urllib.request.urlopen(req) as r:
                    chkpt = r.read().decode()
                    size = chkpt.splitlines()[1]
                    logging.debug(f"Fetched checkpoint of size {size}")
            except Exception as e:
                logging.error(f"Failed to fetch checkpoint at {chkpt_url}", exc_info=e)
                time.sleep(FETCH_CHECKPOINT_BACKOFF)
                return self.__get_latest_checkpoint(
                    refresh=refresh, iterations=iterations + 1
                )
            with open(
                os.path.join(self.checkpoints_dir, size), "w", encoding="utf-8"
            ) as w:
                w.write(chkpt)
        latest = max(
            (int(os.path.basename(x)) for x in glob(f"{self.checkpoints_dir}/" + "*"))
        )
        p = os.path.join(self.checkpoints_dir, str(latest))
        return latest, p

    def download_tiles(self, start_index, stop_index):
        assert(start_index is not None and stop_index is not None)
        log_level = logging.getLogger().getEffectiveLevel()
        nested_dir_count = len(urlsplit(self.monitoring_url).path.split("/"))
        command = [
            "wget2",
            "--input-file=-",
            "--no-clobber",
            "--retry-connrefused",
            "--retry-on-http-error=*,'!404'",
            f"--directory-prefix={self.tiles_dir}",
            "--force-directories",
            "--no-host-directories",
            "--compression=gzip,zstd,identity",
            "--verbose" if log_level is logging.DEBUG else "--quiet",
            f'--user-agent="{self.user_agent}"',
            f"--cut-dirs={nested_dir_count}",
            "--tcp-fastopen",
            "--max-threads=5",
        ]
        tiles = self.__get_leaf_tile_paths(
            start_index, stop_index
        )
        tiles = [self.monitoring_url + "/" + t for t in tiles]
        random.shuffle(tiles)
        logging.debug(
            f"Identified {len(tiles)} new tiles between {start_index} and {stop_index}"
        )
        run_scraper((command, tiles))
        logging.debug(
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
                f"entries since last checkpoint: {current_checkpoint - last_checkpoint_size}"
            )
            return True
        logging.debug(
            f"Not generating a new upper tree torrent, no new leaf torrents. new:{current_checkpoint}, old:{last_checkpoint_size}"
        )
        return False

    def make_torrents(self, ranges):
        for startIndex, endIndex in ranges:
            assert (endIndex - startIndex) == ENTRIES_PER_LEAF_TORRENT, (
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
                name,
                "HelioTorrent " + VERSION,
                paths,
                self.trackers,
                tp,
                webseeds=self.webseeds,
            )
        logging.debug(f"Generated L01 torrents for ranges: {ranges}")

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
                name,
                "HelioTorrent " + VERSION,
                paths,
                self.trackers,
                tp,
                webseeds=self.webseeds,
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
        logging.debug("Identified missing ranges: " + str(split_ranges))
        return split_ranges

    # Functions specific to creating RSS feeds

    def add_torrent_to_feed(self, feed_generator, t):
        logging.debug(f"Adding {t} to feed")
        mtime = datetime.fromtimestamp(os.path.getmtime(t), tz=timezone.utc)
        t_name = os.path.basename(t).strip(".torrent")
        fe = feed_generator.add_item()
        fe.title(t_name)
        fe.published(mtime)
        base_url = self.feed_url.rsplit("/", 1)[0]
        fe.enclosure(
            url=f"{base_url}/{t_name}.torrent",
            length=str(os.path.getsize(t)),
            type="application/x-bittorrent",
        )

    def write_torrent_manifest(self, torrent_paths):
        base_url = self.feed_url.rsplit("/", 1)[0]
        manifest_entries = []
        for path in sorted(torrent_paths):
            torrent_name, _ = os.path.splitext(os.path.basename(path))
            match = re.search(r"^L\d+-(\d+)-(\d+)$", torrent_name)
            if not match:
                logging.warning(
                    f"Skipping torrent with unexpected name format: {path}"
                )
                continue
            start_index, end_index = map(int, match.groups())
            created = datetime.fromtimestamp(
                os.path.getmtime(path), tz=timezone.utc
            ).isoformat()

            # Get the actual data size from the torrent file
            torrent_info = get_torrent_file_info(path)
            if torrent_info:
                _, data_size_bytes = torrent_info
            else:
                data_size_bytes = 0
                logging.warning(f"Could not read torrent file {path}, size will be 0")

            manifest_entries.append(
                {
                    "start_index": start_index,
                    "end_index": end_index,
                    "data_size_bytes": data_size_bytes,
                    "creation_time": created,
                    "torrent_url": f"{base_url}/{torrent_name}.torrent",
                }
            )

        manifest_entries.sort(key=lambda item: (item["start_index"], item["end_index"]))
        manifest = {
            "log_name": self.log_name,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "torrents": manifest_entries,
        }
        manifest_path = os.path.join(self.torrents_dir, "torrents.json")
        with open(manifest_path, "w", encoding="utf-8") as manifest_file:
            json.dump(manifest, manifest_file, indent=2)
            manifest_file.write("\n")
        logging.debug(
            f"Wrote {manifest_path} with {len(manifest_entries)} torrent entries"
        )
        return manifest

    def make_rss_feed(self):
        fg = FeedGenerator()
        fg.load_extension("torrent")
        fg.title(self.log_name)
        fg.link(href=self.feed_url)
        fg.description(
            "Heliotorrent version " + VERSION + " - Feed for " + self.log_name
        )
        paths = glob(os.path.join(self.torrents_dir, "*.torrent"))
        for p in paths:
            self.add_torrent_to_feed(fg, p)
        fp = os.path.join(self.torrents_dir, "feed.xml")
        fg.rss_file(fp, pretty=True)
        logging.debug(f"Wrote {fp} with {len(paths)} torrent files")
        manifest = self.write_torrent_manifest(paths)
        write_torrent_index_html(
            log_name=self.log_name,
            feed_url=self.feed_url,
            manifest=manifest,
            torrents_dir=self.torrents_dir,
            version=VERSION,
        )
        write_root_index(
            torrents_root_dir=self.torrents_root_dir,
            version=VERSION,
        )

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
                logging.debug(f"Deleted tile: {full_path}")
            else:
                logging.warning(f"Tile not found, skipping deleting: {full_path}")

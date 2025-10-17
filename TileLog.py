from glob import glob
import json
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
import shutil

from feedgen.feed import FeedGenerator

from util import (
    get_data_tile_paths,
    get_hash_tile_paths,
    create_torrent_file,
    run_scraper,
)

VERSION = "v0.0.0"


def build_user_agent(contact_email: str) -> str:
    email = (contact_email or "").strip()
    if not email:
        raise ValueError("Contact email must be provided to build a user agent.")
    return f"Heliotorrent {VERSION} Contact: {email}"

ENTRIES_PER_LEAF_TORRENT = 4096 * 256  # 4096 tiles per torrent
TRACKER_LIST_URL = (
    "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt"
)
FETCH_CHECKPOINT_BACKOFF = 60
STATIC_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "static")
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
        for x in [
            self.storage_dir,
            self.tiles_dir,
            self.checkpoints_dir,
            self.torrents_dir,
        ]:
            os.makedirs(x, exist_ok=True)
        self._install_static_assets()
        self.generate_readme()

    @staticmethod
    def _format_timestamp(timestamp):
        """Return YYYY-MM-DD HH:MM in UTC for ISO timestamps; fallback to original on error."""
        if not timestamp:
            return "Unknown"
        try:
            dt = datetime.fromisoformat(timestamp)
        except (TypeError, ValueError):
            return timestamp
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")

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
                    f"Existing README at {readme_path} has different content than expected. Changing this file will cause issues with the existing torrents."
                )
                exit(-1)
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

    def download_tiles(self, start_index=None, stop_index=None):
        if start_index is None:
            start_index = self.get_latest_tree_size(refresh=False)  # 0?
        if stop_index is None:
            stop_index = self.get_latest_tree_size(refresh=True)
        tiles_to_scrape = (stop_index - start_index) // 256
        log_level = logging.getLogger().getEffectiveLevel()
        nested_dir_count = len(urlsplit(self.monitoring_url).path.split("/"))
        command = [
            "wget2",
            "--input-file=-",
            "--no-clobber",
            "--retry-connrefused",
            # "--retry-on-host-error",
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
        )  # todo fixme only downloads leafs
        tiles = [self.monitoring_url + "/" + t for t in tiles]
        random.shuffle(tiles)  # Shuffling ensures each worker gets a balanced load
        logging.debug(
            f"Identified {tiles_to_scrape} new tiles between {start_index} and {stop_index}"
        )

        # Split 100 chunks across 10 workers
        chunk_size = math.ceil(len(tiles) / 1)
        chunks = [
            (command, tiles[i : i + chunk_size])
            for i in range(0, len(tiles), chunk_size)
        ]

        assert sum((len(x[1]) for x in chunks)) == len(tiles)
        for command, tiles in chunks:
            assert len(tiles) > 0

        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.map(run_scraper, chunks)
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
            manifest_entries.append(
                {
                    "start_index": start_index,
                    "end_index": end_index,
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
        logging.info(
            f"Wrote {manifest_path} with {len(manifest_entries)} torrent entries"
        )
        return manifest

    def write_torrent_index_html(self, manifest):
        base_url = self.feed_url.rsplit("/", 1)[0]
        feed_url = self.feed_url
        json_url = f"{base_url}/torrents.json"
        stylesheet_path = os.path.join(self.torrents_root_dir, PUBLIC_STYLESHEET_NAME).replace(os.path.sep, "/")
        torrents = manifest["torrents"]
        last_updated_display = self._format_timestamp(manifest.get("last_updated"))

        html_lines = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            f"  <title>{self.log_name} Torrents</title>",
            f'  <link rel="stylesheet" href="{stylesheet_path}">',
            "</head>",
            "<body>",
            "  <main>",
            '    <section class="card">',
            "      <header>",
            '        <h1 class="page-title">',
            '          <span class="icon icon-log" aria-hidden="true"></span>',
            f"          {self.log_name}",
            "        </h1>",
            f"        <p class=\"page-subtitle\">Last updated {last_updated_display}</p>",
            '        <div class="actions">',
            f'          <a href="{feed_url}" class="icon-link">',
            '            <span class="icon icon-rss" aria-hidden="true"></span>',
            "            <span>RSS feed</span>",
            "          </a>",
            f'          <a href="{json_url}" class="icon-link">',
            '            <span class="icon icon-json" aria-hidden="true"></span>',
            "            <span>JSON manifest</span>",
            "          </a>",
            "        </div>",
            "      </header>",
            '      <ul class="meta-list">',
            "      </ul>",
        ]

        if torrents:
            html_lines.extend(
                [
                    '      <div class="table-wrapper">',
                    "        <table>",
                    "          <thead>",
                    "            <tr>",
                    "              <th>Range</th>",
                    "              <th>Created</th>",
                    "              <th>Download</th>",
                    "            </tr>",
                    "          </thead>",
                    "          <tbody>",
                ]
            )

            for entry in torrents:
                torrent_name = os.path.basename(entry["torrent_url"])
                created_display = self._format_timestamp(entry.get("creation_time"))
                html_lines.extend(
                    [
                        "            <tr>",
                        "              <td>",
                        '                <div class="cell-stack">',
                        f"                  <span>Start: {entry['start_index']}</span>",
                        f"                  <span>End: {entry['end_index']}</span>",
                        "                </div>",
                        "              </td>",
                        "              <td>",
                        '                <div class="cell-stack">',
                        f"                  <span>{created_display}</span>",
                        "                  <small>UTC</small>",
                        "                </div>",
                        "              </td>",
                        "              <td>",
                        f'                <a href="{entry["torrent_url"]}" class="icon-link">',
                        '                  <span class="icon icon-torrent" aria-hidden="true"></span>',
                        f'                  <span class="torrent-name">{torrent_name}</span>',
                        "                </a>",
                        "              </td>",
                        "            </tr>",
                    ]
                )

            html_lines.extend(
                [
                    "          </tbody>",
                    "        </table>",
                    "      </div>",
                ]
            )
        else:
            html_lines.extend(
                [
                    '      <div class="empty-state">No torrents available yet.</div>',
                ]
            )

        html_lines.extend(
            [
                "    </section>",
                "  </main>",
                f"  <footer>Generated by Heliotorrent {VERSION}</footer>",
                "</body>",
                "</html>",
            ]
        )
        html_content = "\n".join(html_lines) + "\n"
        html_path = os.path.join(self.torrents_dir, "index.html")
        with open(html_path, "w", encoding="utf-8") as html_file:
            html_file.write(html_content)
        logging.info(f"Wrote {html_path} for torrent index")

    def write_root_index(self):
        try:
            entries = sorted(
                entry
                for entry in os.listdir(self.torrents_root_dir)
                if os.path.isdir(os.path.join(self.torrents_root_dir, entry))
            )
        except FileNotFoundError:
            logging.warning(
                f"Torrents root directory missing: {self.torrents_root_dir}"
            )
            return

        table_rows = []
        for entry in entries:
            dir_path = os.path.join(self.torrents_root_dir, entry)
            manifest_path = os.path.join(dir_path, "torrents.json")
            feed_path = os.path.join(dir_path, "feed.xml")
            html_path = os.path.join(dir_path, "index.html")
            torrent_files = glob(os.path.join(dir_path, "*.torrent"))

            manifest_data = None
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as manifest_file:
                        manifest_data = json.load(manifest_file)
                except (json.JSONDecodeError, OSError) as exc:
                    logging.warning(
                        f"Unable to load manifest for {entry}: {exc}", exc_info=True
                    )

            display_name = (
                manifest_data.get("log_name")
                if manifest_data and manifest_data.get("log_name")
                else entry
            )
            torrent_count = (
                len(manifest_data.get("torrents", []))
                if manifest_data
                else len(torrent_files)
            )

            log_link = f"{entry}/index.html" if os.path.exists(html_path) else None
            rss_link = f"{entry}/feed.xml" if os.path.exists(feed_path) else None
            json_link = f"{entry}/torrents.json" if os.path.exists(manifest_path) else None

            table_rows.append(
                {
                    "name": display_name,
                    "log_link": log_link,
                    "rss_link": rss_link,
                    "json_link": json_link,
                    "torrent_count": torrent_count,
                }
            )

        stylesheet_path = PUBLIC_STYLESHEET_NAME
        total_logs = len(table_rows)
        total_torrents = sum(row["torrent_count"] for row in table_rows)
        logs_label = "log" if total_logs == 1 else "logs"
        torrents_label = "torrent" if total_torrents == 1 else "torrents"
        if total_logs:
            subtitle = (
                f"Tracking {total_logs} {logs_label} "
                f"with {total_torrents} {torrents_label}."
            )
        else:
            subtitle = "No torrent feeds have been generated yet."

        html_lines = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            "  <title>Heliotorrent Feeds</title>",
            f'  <link rel="stylesheet" href="{stylesheet_path}">',
            "</head>",
            "<body>",
            "  <main>",
            '    <section class="card">',
            '      <h1 class="page-title">Heliotorrent Feeds</h1>',
            f'      <p class="page-subtitle">{subtitle}</p>',
        ]

        if total_logs:
            html_lines.extend(
                [
                    '      <ul class="meta-list">',
                    f"        <li class=\"badge\">Feeds: {total_logs}</li>",
                    f"        <li class=\"badge\">Torrents: {total_torrents}</li>",
                    "      </ul>",
                    '      <div class="table-wrapper">',
                    "        <table>",
                    "          <thead>",
                    "            <tr>",
                    "              <th>Log</th>",
                    "              <th>Torrents</th>",
                    "              <th>Resources</th>",
                    "            </tr>",
                    "          </thead>",
                    "          <tbody>",
                ]
            )

            for row in table_rows:
                if row["log_link"]:
                    name_cell = [
                        '            <a href="'
                        + row["log_link"]
                        + '" class="icon-link is-primary">',
                        '              <span class="icon icon-log" aria-hidden="true"></span>',
                        f"              <span>{row['name']}</span>",
                        "            </a>",
                    ]
                else:
                    name_cell = [
                        '            <div class="cell-stack">',
                        f"              <span>{row['name']}</span>",
                        '              <small>Index not available</small>',
                        "            </div>",
                    ]

                rss_cell = (
                    [
                        '            <a href="'
                        + row["rss_link"]
                        + '" class="icon-link">',
                        '              <span class="icon icon-rss" aria-hidden="true"></span>',
                        "              <span>RSS</span>",
                        "            </a>",
                    ]
                    if row["rss_link"]
                    else ['            <span class="muted">RSS unavailable</span>']
                )

                json_cell = (
                    [
                        '            <a href="'
                        + row["json_link"]
                        + '" class="icon-link">',
                        '              <span class="icon icon-json" aria-hidden="true"></span>',
                        "              <span>JSON</span>",
                        "            </a>",
                    ]
                    if row["json_link"]
                    else ['            <span class="muted">JSON unavailable</span>']
                )

                html_lines.extend(
                    [
                        "            <tr>",
                        "              <td>",
                        *name_cell,
                        "              </td>",
                        "              <td>",
                        f"                <span class=\"badge\">{row['torrent_count']} file{'s' if row['torrent_count'] != 1 else ''}</span>",
                        "              </td>",
                        "              <td>",
                        '                <div class="actions">',
                        *rss_cell,
                        *json_cell,
                        "                </div>",
                        "              </td>",
                        "            </tr>",
                    ]
                )

            html_lines.extend(
                [
                    "          </tbody>",
                    "        </table>",
                    "      </div>",
                ]
            )
        else:
            html_lines.append('      <div class="empty-state">Run Heliotorrent to publish your first feed.</div>')

        html_lines.extend(
            [
                "    </section>",
                "  </main>",
                f"  <footer>Generated by Heliotorrent {VERSION}</footer>",
                "</body>",
                "</html>",
            ]
        )
        html_content = "\n".join(html_lines) + "\n"
        index_path = os.path.join(self.torrents_root_dir, "index.html")
        with open(index_path, "w", encoding="utf-8") as index_file:
            index_file.write(html_content)
        logging.info(
            f"Wrote {index_path} listing {len(table_rows)} torrent feed directories"
        )

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
        logging.info(f"Wrote {fp} with {len(paths)} torrent files")
        manifest = self.write_torrent_manifest(paths)
        self.write_torrent_index_html(manifest)
        self.write_root_index()

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

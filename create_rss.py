from glob import glob
import os
from datetime import datetime, timezone
import hashlib
import logging

import bencodepy
from feedgen.feed import FeedGenerator
from util import url_to_dir


def get_torrent_info(tf):
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


def add_item(feed_generator, torrent_path):
    t = torrent_path
    logging.debug(f"Adding {t} to torrent")
    mtime = datetime.fromtimestamp(os.path.getmtime(t), tz=timezone.utc)
    t_name = os.path.basename(t).strip(".torrent")
    (ih, size) = get_torrent_info(t)

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


def build_feed(feed_url, feed_name, paths):
    fg = FeedGenerator()
    fg.load_extension("torrent")
    fg.title(feed_name)
    fg.link(href=feed_url)
    fg.description("TODO")
    for p in paths:
        add_item(fg, p)
    return fg


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    name = url_to_dir("https://tuscolo2026h1.skylight.geomys.org/")
    feed = build_feed("127.0.0.1", name, glob(f"data/{name}/torrents/*"))
    logging.debug(feed.rss_str(pretty=True).decode())

    feed.rss_file("data/feed.xml", pretty=True)

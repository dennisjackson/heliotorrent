from feedgen.feed import FeedGenerator
import glob
import os
from datetime import datetime, timezone
import bencodepy
import hashlib


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


fg = FeedGenerator()
fg.load_extension("torrent")
fg.title("TODO")
fg.link(href="https://example.com")
fg.description("TODO")

for t in glob.glob("data/torrents/*"):
    print(t)
    mtime = os.path.getmtime(t)
    mtime = datetime.fromtimestamp(mtime, tz=timezone.utc)
    name = os.path.basename(t).strip(".torrent")
    (ih, size) = get_torrent_info(t)
    fe = fg.add_item()
    fe.title(name)
    fe.torrent.infohash(ih)
    fe.torrent.contentlength(f"{size}")
    fe.torrent.filename(name)
    fe.published(mtime)
    fe.enclosure(
        url="magnet:?xt=urn:btih:37c2662e6792ccb6fb78ffd4ac9cc035cd26c918",
        length=size,
        type="application/x-bittorrent",
    )

rss = fg.rss_str(pretty=True)
print(rss.decode())
fg.rss_file("data/feed.xml", pretty=True)

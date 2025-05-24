
# TODO

## HTTP Sources

HTTP Sources for torrents will need to be a spec extension. The main rub is that the torrent client will prefix the fetch with the name of the torrent.

My idea would be to define the URL to be

{monitoring-prefix}/torrent/

Which will then become {monitoring-prefix}/torrent/torrent-name/tile_path
So the HTTP server needs to rewrite it to {monitoring-prefix}/tile_path

I need to test this though

## Issuers

Need to scrape or ask the server CLI to allow listing the files.

## Checkpoints

Maybe its not even worth doing for now?

## Remaining nits with the scripts

* scraper.py needs to fetch the tree size and run dynamically.
* make_torrents.py needs to avoid recreating existing files.
* create_rss.py needs to make folder suitable for serving multiple logs.

## Verification

* Need to verify files on download.

## Compression

Pro: Reduces bandwidth usage
Downside: Increases storage requirement by 50% for folks actually working with the data. Unless they decompress in memory.

## Automated seeding

I tested that qbittorrent can seed it to transmission-cli running on GCP. It was pretty simple. Just apt-get install. Then run it with the magnet link. It will download the torrent  file. Then run it with the torrent file. transmission-remote is meant to be better.

With qbittorrent I think its even easier. We just need the rules setup with RSS so that it auto-discovers the right folder for seeding,

Easy to serve the RSS feed with python -m http.server 8000 in the data directory.

I probably want to split the torrents and feeds by monitoring prefix
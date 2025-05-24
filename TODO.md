
# TODO

## Must do

### Remaining nits with the scripts

* A lot of tidy up and refactoring is needed.
* make_torrents.py needs a cli.
* create_rss.py needs to make a feed for each log.

### Automated seeding

I tested that qbittorrent can seed it to transmission-cli running on GCP. It was pretty simple. Just apt-get install. Then run it with the magnet link. It will download the torrent  file. Then run it with the torrent file. transmission-remote is meant to be better.

With qbittorrent I think its even easier. We just need the rules setup with RSS so that it auto-discovers the right folder for seeding,

Easy to serve the RSS feed with python -m http.server 8000 in the data directory.

### Hosting

Host on github pages under a branch.
Add a html file as a jumping off point for the different RSS feeds and a setup guide.
For PoC - Just one Let's Encrypt and one Gensys log?

## Nice to have

### HTTP Sources

HTTP Sources for torrents will need to be a spec extension. The main rub is that the torrent client will prefix the fetch with the name of the torrent.

My idea would be to define the URL to be

{monitoring-prefix}/torrent/

Which will then become {monitoring-prefix}/torrent/torrent-name/tile_path
So the HTTP server needs to rewrite it to {monitoring-prefix}/tile_path

I need to test this though.

Can also add http links to the RSS feed to save the magnet lookup

### Issuers

Need to scrape or ask the server CLI to allow listing the files.

### Checkpoints

Maybe its not even worth doing for now?

### Verification

* Need to verify files on download.

### Compression

Pro: Reduces bandwidth usage
Downside: Increases storage requirement by 50% for folks actually working with the data. Unless they decompress in memory.

### Convergent Hashes

It would be nice if two different clients generating the torrents would generate the same magnet files.

# TODO

##  Must do

### Seeding

* Ok so a duct taped solution is now together:
* Now the qbittorrent config needs all wrapping up together.
* Let's just put it all on Cloudflare Pages!
* qBittorrent config will need the seeding limit turned off as well (already done via GUI)
* I think the qbittorrent config is actually trivial. It's just a case of packaging the config files which are plaintext anyway.
  * The rules and rss feed need transforming, but that should be pretty smooth anyway.

### Hosting

Host on cloudflare pages under a branch.
Add a html file as a jumping off point for the different RSS feeds and a setup guide.
For PoC - Just one Let's Encrypt and one Gensys log?

### Long term seeding plan

 * Actually kind of awkward to bootstrap
 * I think a VPS with a webhost that proxies the log for a http seed might actually be the best way forward.
 * Just rewrite requests to go to the log direct. It will get rate limited though without agreement. Can pop a cache on it but still...
 * Either caddy or nginx

## Nice to have

* Fix all the path joins!
* prioritise missing tiles from higher up in the tree. only fetch so many low-level tiles per scraping run.

###  HTTP Sources

HTTP Sources for torrents will need to be a spec extension. The main rub is that the torrent client will prefix the fetch with the name of the torrent.

My idea would be to define the URL to be

{monitoring-prefix}/torrent/

Which will then become {monitoring-prefix}/torrent/torrent-name/tile_path
So the HTTP server needs to rewrite it to {monitoring-prefix}/tile_path

I need to test this though.

Can also add http links to the RSS feed to save the magnet lookup (and serve the raw torrent files)

###  Issuers

Need to scrape or ask the server CLI to allow listing the files.

###  Checkpoints

Maybe its not even worth doing for now?

### Verification

* Need to verify files on download.

### Compression

Pro: Reduces bandwidth usage
Downside: Increases storage requirement by 50% for folks actually working with the data. Unless they decompress in memory.

### Convergent Hashes

It would be nice if two different clients generating the torrents would generate the same magnet files.
I think this is possible for data tiles.

### Hybrid Torrents

Support v2 and v1 Torrents. Sounds like torrent-file rather than torf might be the way to go.

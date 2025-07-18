
# TODO

## Further Notes

- feed.json - as an alternative to xml for non-torrent clients.
- Status page which checks index / tiles / torrents / rss?

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

* Have Nginx up and running.
* Urls seem to be set correctly but qbittorrent still isn't happy. Need to figure out why.
* Hypothesis was use of gzip. But think I have a module to disable that. qbittorrent patch notes suggest it does support gzip
* Docker thingy is running on gcp.

* After quite a lot of faff...
* Torrent clients typically don't support gzip / content encoding. Transmission uses CURL with it [disabled](https://github.com/transmission/transmission/blob/f7373cb6483bd624c065cdc5a3b53908ee9b1902/libtransmission/web.cc#L636). Qbittorent/libtorrent has a handrolled [client](https://github.com/arvidn/libtorrent/blob/2e16847613497a033d005076330adc264471b3fa/src/web_peer_connection.cpp).
* I'm experimenting with compiling transmission with gzip decoding enabled.
* The Static CT spec kind of violates expectations here by serving gzip even if transmission asks for no encoding.
* Nginx doesn't seem to be able to fix this and will quite happily serve a lot of invalid content in the wrong config.
* On the server side, I think I'll need something written in Rust / Go to serve as the proxy.
* Thankfully, it looks like ChatGPt has a pretty good idea.
* Transmissions logs seem much better than qbittorrent. Can be grabbed from the UI.
  * Transmission has no native rss feed support though.
  * Maybe FlexGet would be the solution? Or some other manual script?

* I vibe coded some rust. I guess I should re-use the heliostat name.

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

### Log List?

https://www.gstatic.com/ct/log_list/v3/all_logs_list.json

# Storage Options

Heztner has large disks via Storage Share but won't be very performant. Can be mounted.
OVH has unlimited bandwidth.
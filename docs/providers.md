# Setting up a HelioTorrent instance

HelioTorrent can be configured by anybody. This document describes how to use the software in this repository to serve Static CT over BitTorrent. Providers interested in using their own software stack should see [Spec.md] and [Design.md].

Running HelioTorrent doesn't require any privileged access to a static CT log.

## Setting up HelioTorrent

HelioTorrent is a python application packaged with [uv]. HelioTorrent needs network access, roughly 2 GB of scratch space per log, and outputs generated torrent files and feeds to a specified folder. This folder can then be served over HTTP with Heliostat, or your preferred hosting platform of choice.

1. Fetch a copy of the source with `git clone <TODO>`.
2. Install the dependencies with `uv sync`. If you don't have a copy of `uv`, see the instructions [here](https://docs.astral.sh/uv/getting-started/installation/).
3. Install wget2 via your package manage of choice.
4. You can generate a configuration file interactively with the command `uv run heliotorrent.py --generate-config --interactive`. Heliotorrent will walk you through the varios options.

The configuration file is YAML-formatted. An example listing is given below:

```yaml
# Global settings for Heliotorrent
# Configure directories, ports, and the base feed URL. Each log's feed defaults to <feed_url_base>/<log_name>/feed.xml.
data_dir: data
torrent_dir: torrents
# https_port: 8443
http_port: 8080
# tls_cert: null
# tls_key: null
feed_url_base: http://127.0.0.1:8080/torrents
scraper_contact_email: null #Required, this must bet set
frequency: 3600
entry_limit: 0
delete_tiles: true
webseeds:
- http://127.0.0.1:8080/webseed/
logs:
- name: tuscolo2026h1
  log_url: https://tuscolo2026h1.skylight.geomys.org/
# You can add more logs here. Optional keys override the global defaults above.
#  - name: "another-log"
#    log_url: "https://another.log.server/log/"
    # Optional Keys:
    # feed_url: "http://127.0.0.1/alternative-location/feed.xml"
    # frequency: 300
    # entry_limit: null
    # delete_tiles: false
    # webseeds:
    #  - "http://webseed.example.com/"
```

5. You can now run HelioTorrent with `uv run heliotorrent.py --config <your_config_file>`.

However, you properly want to run Heliostat, which acts as webseed and shares the same config file as well below.

## Setting up Heliostat

Heliostat is a rust application packaged in the heliostat directory. If you'd like to build it, you need to invoke `cargo build --release` in the heliostat directory. It shares the same configuration file format as HelioTorrent.

HTTPS support is nice to have, if not essential, and can be configured via `certbot`. You'll need to make the resulting TLS certificate and private key readable to Heliostat and then configure the paths and the HTTPS port in the config file.

Although can run heliostat independently, HelioTorrent can also take care of it for you, just extend the heliotorrent invoation with `--heliostat <path-to-binary>`. So all together:

`uv run heliotorrent.py --config <your_config_file> --heliostat heliostat/target/release/heliostat`

Heliostat could be run independently of HelioTorrent, however, it does need to serve the

## Running as a Daemon

By default HelioTorrent will log messages to the `log` directory and to the console. You can configure HelioTorrent as a service with systemD or simply leaving it running in the background with a session manager `termux`.
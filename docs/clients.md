# Consuming a Log via HelioTorrent

HelioTorrent exposes an RSS feed of torrents or magnet links that represent new log data as it is produced. Any BitTorrent client that can subscribe to RSS (natively or via an add‑on) can automatically fetch and seed these entries.

The instructions below cover two setups:

- Transmission + FlexGet
- qBittorrent (built‑in RSS)

FlexGet supports many other clients. TODO.

## Transmission + FlexGet

Transmission does not natively support RSS feeds. However, FlexGet can poll feeds and hands entries to Transmission over its RPC API.

1) [Install Transmission](https://transmissionbt.com/download) and enable remote control from localhost:
   - Desktop: enable “Remote”/RPC in Preferences.
   - Daemon (`transmission-daemon`): edit its `settings.json` (stop the daemon first) and set:
     - `"rpc-enabled": true`
     - `"rpc-bind-address": "127.0.0.1"` (or appropriate interface)
     - `"rpc-username"` / `"rpc-password"`
   - Restart the daemon and confirm the web UI or `transmission-remote` works.

2) [Install FlexGet](https://www.flexget.com/Install):
   - `uv tool install flexget` or
   - `pipx install flexget` (or `pip install --user flexget`)

4) Create a minimal FlexGet config at `~/.config/flexget/config.yml` or see the example in this repo `experiments/flexget.yaml`:

```yaml
templates:
  heliotorrent_transmission:
    transmission:
      host: localhost
      port: 9091
      username: your_user
      password: your_pass
      path: DOWNLOAD_LOCATION

tasks:
  heliotorrent_LOG_NAME:
    rss: FEED_URL
    accept_all: yes
    template: heliotorrent_transmission

schedules:
  - tasks: [heliotorrent]
    interval:
      minutes: 60
```

4) Run FlexGet as a daemon: `flexget daemon start` (or run once with `flexget execute`).
5) Verify in Transmission that new feed items appear and begin seeding.

## qBittorrent (Built‑in RSS)

1) Install qBittorrent from your package manager or https://www.qbittorrent.org/.
2) Open Preferences:
   - RSS: Enable RSS support
3) Add the feed:
   - View → RSS Reader → “New subscription” → paste `FEED_URL`.
   - Confirm that items populate under the feed.
4) Auto‑download rule:
   - Tools → RSS Downloader → “Add” rule named `LOG_NAME`.
   - Disable “Smart episode filter”.
5) Configure approprite seeding and bandwidth rules.
6) Verify: New feed items should be added automatically and begin downloading & seeding.

## Integrating with CT Clients

OPEN ISSUE

This remains an open issue. There are two broad paths which could be taken. The first is to integrate BitTorrent support inside clients via native libraries. This has the benefit of preserving their existing semantics, can offer BitTorrent by default.

The second would be to implement a shim which exposes a classic Sunlight interface but proxies requests to either local filesystem (provisioned by a BitTorrent client) or uses a BitTorrent library to stream requests directly. There are various packages which allow torrents to be mounted via a virtual file system.

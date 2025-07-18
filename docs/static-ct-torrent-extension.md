# Serving Static Certificate Transparency Tiles over BitTorrent

This spec defines a mechanism for serving the Tiles used in Static Certificate Transparency over BitTorrent. This mechanism extends those defined in [Static CT API](https://c2sp.org/static-ct-api) and aims to maximize compatibility with the existing practices of CT Logs, Monitors and Clients.

Static CT can be served over BitTorrent by a log operator or by a third party. It requires no modifications to logs.

This document specifies how Tiles are served over BitTorrent.

## Conventions used in this document

TODO: Reference Static CT API

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this
document are to be interpreted as described in [BCP 14][] [RFC 2119][] [RFC
8174][] when, and only when, they appear in all capitals, as shown here.

[BCP 14]: https://www.rfc-editor.org/info/bcp14
[RFC 2119]: https://www.rfc-editor.org/rfc/rfc2119.html

## Overview

Tiles are packaged into individual torrents which cover the data tiles and level 0 and level 1 hash tiles for a contiguous range of entries. Each torrent covers 4096 data tiles, their matching level 0 hash tiles and their 16 L1 hash tiles, which is roughly 2 GB of data. These torrents do not overlap and are immutable over the life of the log.

For even very large logs, the higher level tiles occupy less than 16 MB in total and are often in a partial state. Consequently, clients should still fetch these tiles directly from the log. Similarly, checkpoints and issuers should be read directly from the log. Even with this restriction, for a log taking 100 TB on disk, 99.999% of the log's data is available over BitTorrent.

Clients and Monitors can discover new torrents either by fetching the latest checkpoint and calculating the URL at which the corresponding torrents can be found, or by consuming an RSS feed describing the available torrents. Automatically consuming RSS feeds of torrents is widely supported by contemporary torrent clients, making it easy for bandwidth to be donated to the log in a trustless way, without having to run any custom software. This document specifies how the torrent files and RSS feed should be constructed and served.

Modern torrent clients support [WebSeeds](https://www.bittorrent.org/beps/bep_0019.html), a standardized mechanism for fetching torrent content over HTTP. This document specifies how log operators or third parties can operate a WebSeed for a log. Multiple WebSeeds can be in operation for the same log. Bittorrent clients will automatically balance their requests between the available WebSeeds and BitTorrent seeds.

Even in the pathological possible case, where there is a single webseed, no other Bitorrent seeds and two clients trying to download a torrent, the use of Bitorrent can reduce the bandwidth used by the webseed (and Tile Log) by ~40%. That is, log operators benefit from substantially reduced bandwidth costs even if clients only download data through BitTorrent and never actually seed the content.

## Creating Torrents

A Tile Torrent for a given log is determined contains the tiles that cover a contiguous range of entries.

Tile Torrents SHOULD contain cover exactly X entries. This implies they contain X data tiles, Y L0 hash tiles and Z L1 hash tiles.

Tile Torrents SHOULD use a directory structure identical that used in Static CT. That is:
 - Data Tiles are located at ...
 - Hash Tiles are located at ...

Tile Torrents SHOULD include a README.md at their top level which contains the syntax:

```
LOG_URL: <log monitoring URL>
```

Tile Torrents SHOULD NOT contain any other files.

Tile Torrents SHOULD include a WebSeed entry, as described below.

Tile Torrents MUST support the BitTorrent v1 protocol. Tile Torrents SHOULD support the BitTorrent v2 protocol.

A Tile Torrent should only be constructed once the covered range of entries has been included in the log.

In practice, Torrents produced following this standard will be around 2 GB in size and be produced roughly hourly.

## Serving Torrents

If a log operator is directly offering Torrent support, the Torrent files MUST be named `L01-<startIndex>-<endIndex>.torrent` and served at `<monitoring_prefix>/torrents/<file_name>`.

A third party may wish to offer Torrent support without the log operator's involvement, if so the same naming MUST be kept.

An RSS feed describing the available torrents SHOULD be offered. The feed should be served at `torrents/feed.xml`. The feed should contain at minimum:

TODO

This feed should be regenerated whenever new torrents are available.

## Seeding Torrents

Torrent Clients are not natively compatible with fetching Tiles over HTTP.

A Tile Webseed is defined by a URL prefix. At that URL, the server MUST:

* Ignore the first directory after the prefix (this will be the torrents name).
* Treat the remained as the path to the file desired by the Torrent Client. This should be handled appropriately.
* Serve HTTP content uncompressed.

This can be achieved by serving the README directly. All other files can be served by rewriting them into requests suitable for the Tile log.

If the Webseed operator is not the Tile Log operator, care must be taken to follow the guidance in [Static CT API], e.g. by setting an appropriate user-agent and supporting gzip compression when fetching from the log.

Multiple WebSeeds can be used in parallel for the same log. External WebSeed operators can serve many torrent clients but present as a single ordinary client to log operators.

WebSeeds do not have strict uptime requirements, however if no webseeds or regular seeds are available for a torrent, clients will not be able to finish their downloads.

## Consuming Torrents

Clients consuming torrents.
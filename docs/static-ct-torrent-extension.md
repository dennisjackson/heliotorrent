# Serving Static Certificate Transparency Tiles over BitTorrent

This spec defines a mechanism for serving the Tiles used in Static Certificate Transparency over BitTorrent. The primary motivation is to reduce bandwidth costs for log operators, be compatible with a broad range of existing BitTorrent clients, and minimize operational complexity.

## Conventions used in this document

TODO: Reference Static CT API

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this
document are to be interpreted as described in [BCP 14][] [RFC 2119][] [RFC
8174][] when, and only when, they appear in all capitals, as shown here.

[BCP 14]: https://www.rfc-editor.org/info/bcp14
[RFC 2119]: https://www.rfc-editor.org/rfc/rfc2119.html

## Overview

This document is divided into three sections. Firstly, it lays out how Static CT tiles are packaged into individual torrents. Secondly, it describes how these individual torrents can be included in RSS and JSON feeds and made available for automatic consumption by clients. Finally, it describes how these torrents can be seeded via HTTP.

This specification makes a number of decisions to maximize compatibility, deployability and simplicity. In particular, it focuses on making the vast majority of a log's data available over BitTorrent (>99.999%), leaving a small number of files, such as checkpoints and issuers that will need to be fetched over HTTP as described in the[The Static Certificate Transparency API](https://c2sp.org/static-ct-api).

## Creating Torrents

A Tile Torrent for a given log is determined by a contiguous range of entries and includes the corresponding data tiles, level 0 and level 1 hash tiles for those entries.

Tile Torrents SHOULD contain cover exactly 1,048,576 (`4096 * 256`) entries, meaning they contain 4096 data tiles, 4096 L0 hash tiles and 16 L1 hash tiles.

Tiles in Tile Torrents MUST use paths and a directory structure identical the one used for monitoring Static CT. That is:
 - Data Tile `N` is located at `/tile/data/<N>`
 - Hash Tile `N` of level `L` is at `/tile/<L>/<N>

`N` is encoded as in the Static CT Specification. Using a different directory structure will make impossible for clients to parse tiles correctly.

Tile Torrents SHOULD include a README.md at their top level which contains the syntax:

```
LOG_URL: <log monitoring URL>
```

This file at the top level smooths over some inconsistencies in popular torrent clients. If `README.md` is included, it MUST use the exact foramt given here.

Tile Torrents SHOULD NOT contain any other files. A Tile Torrent should only be constructed once the covered range of entries has been included in the log. A Tile Torrent should not contain partial tiles or higher level leaves.


Tile Torrents SHOULD BE named helpfully, e.g. describing the log name and the entries the torrent includes.

Tile Torrents SHOULD include a WebSeed URL, as described in the section below.

Tile Torrents MUST support the BitTorrent v1 protocol. Tile Torrents SHOULD support the BitTorrent v2 protocol.

< Open Issue: Vary the size of Tile Torrents dynamically to support lower-rate log shards? >

## Serving Torrent Files

Each torrent file MUST be made available over HTTPS for clients to download.

### RSS Feeds

Many torrent clients support subscribing to RSS feeds and automatically ingesting the torrents they advertise.

The RSS feed must follow the [BEP 36](https://www.bittorrent.org/beps/bep_0036.html) specification for RSS 2.0 torrent feeds.

Each torrent available to clients should be included as an item with an enclosure URL, as described in the following syntax:

```
<item>
<title>{torrent_name}</title>
<enclosure url="{torrent URL}" length="{file size of the .torrent file}" type="application/x-bittorrent"/>
<pubDate>{Published date}</pubDate>
</item>
```

There is no limit as to the number of torrents that can be included in a single feed.

### JSON Feeds

Although RSS feeds are convenient for existing torrent clients, JSON offers more flexibility for dedicated tooling.

A JSON feed corresponds to the following JSON dictionary:
```
{
log_name: "log name"
last_updated: "Timestamp"
torrents: [Array of Torrent entries]
}
```

A torrent entry is a JSON Dict with the following structure:
```
{
    start_index: int
    end_index: int
    data_size_bytes: int
    creation_time: Timestamp
    torrent_url: String
}
```

### Advertising Feeds

The RSS and JSON feeds for a torrent SHOULD be advertised in the log's manifest.

< TODO Link to Clint's Proposal >

## Seeding Torrents

Once a torrent file has been produced and made available to download for clients, it must be

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

What can they rely on in terms of behavior.
What do they have to do?

## Cut Overview

[WebSeeds](https://www.bittorrent.org/beps/bep_0019.html),

Tiles are packaged into individual torrents which cover the data tiles and level 0 and level 1 hash tiles for a contiguous range of entries. Each torrent covers 4096 data tiles, their matching level 0 hash tiles and their 16 L1 hash tiles, which is roughly 2 GB of data. These torrents do not overlap and are immutable over the life of the log.

For even very large logs, the higher level tiles occupy less than 16 MB in total and are often in a partial state. Consequently, clients should still fetch these tiles directly from the log. Similarly, checkpoints and issuers should be read directly from the log. Even with this restriction, for a log taking 100 TB on disk, 99.999% of the log's data is available over BitTorrent.

Clients and Monitors can discover new torrents either by fetching the latest checkpoint and calculating the URL at which the corresponding torrents can be found, or by consuming an RSS feed describing the available torrents. Automatically consuming RSS feeds of torrents is widely supported by contemporary torrent clients, making it easy for bandwidth to be donated to the log in a trustless way, without having to run any custom software. This document specifies how the torrent files and RSS feed should be constructed and served.

Modern torrent clients support  a standardized mechanism for fetching torrent content over HTTP. This document specifies how log operators or third parties can operate a WebSeed for a log. Multiple WebSeeds can be in operation for the same log. Bittorrent clients will automatically balance their requests between the available WebSeeds and BitTorrent seeds.

Even in the pathological possible case, where there is a single webseed, no other Bitorrent seeds and two clients trying to download a torrent, the use of Bitorrent can reduce the bandwidth used by the webseed (and Tile Log) by ~40%. That is, log operators benefit from substantially reduced bandwidth costs even if clients only download data through BitTorrent and never actually seed the content.
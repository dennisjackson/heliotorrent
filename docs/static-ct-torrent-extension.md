# Serving Static Certificate Transparency Tiles over BitTorrent

This spec defines a mechanism for serving the Tiles used in Static Certificate Transparency over BitTorrent. The primary motivation is to reduce bandwidth costs for log operators, be compatible with a broad range of existing BitTorrent clients, and minimize operational complexity for log operators.

## Conventions used in this document

TODO: Reference CS2SP Spec

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this
document are to be interpreted as described in [BCP 14][] [RFC 2119][] [RFC
8174][] when, and only when, they appear in all capitals, as shown here.

[BCP 14]: https://www.rfc-editor.org/info/bcp14
[RFC 2119]: https://www.rfc-editor.org/rfc/rfc2119.html

## Overview

This document is divided into three sections. Firstly, it lays out how Static CT tiles are packaged into individual torrents. Secondly, it describes how these individual torrents can be included in RSS and JSON feeds and made available for automatic consumption by clients. Finally, it describes how these torrents can be seeded via HTTP(S) and consumed by clients.

This specification makes a number of decisions to maximize compatibility, deployability and simplicity. In particular, it focuses on making the vast majority of a log's data available over BitTorrent (>99.999%), leaving a small number of files, such as checkpoints and issuers that will need to be fetched over HTTP(S) as described in the[The Static Certificate Transparency API](https://c2sp.org/static-ct-api).

The party providing Tile Torrents need not be the log operator, it can be provided entirely by third parties on independent infrastructure. Log operators wanting to provide Tile Torrents need no specific infrastructure beyond a HTTP(S) server.

Clients wanting to contribute bandwidth to Tile Torrents are able to use existing BitTorrent clients off the shelf.

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

Once a torrent file has been produced and made available to download for clients, it must be seeded. That means, making the content of the torrent available to torrent clients.

[BEP 19](https://www.bittorrent.org/beps/bep_0019.html) is a widely implemented standard that allows torrent clients to fetch data over HTTP(S).

However, BEP 19 and the Static CT API are incompatible with each other. This section describes how a HTTP server can act as a web seed for Tile Torrents.

The Tile Torrent WebSeed may have a full copy of the log available locally or it may be fetch the log via the Static CT Monitoring API in order to respond to client's requests. If so, it MUST follow the relevant guidance for user agents etc. Use Caching. TODO.

TODO: SHOULD be a local caching copy. MAY be a transparent proxy.

A Tile Torrent WebSeed for a specific Static CT log is configured defined by a URL Prefix. When a HTTP Request is received for that prefix, the WebSeed MUST trim the first directory from the request after that prefix. This is the torrent file's name.

If the remaining path identifies a file path for a tile in the log, the WebSeed must respond with that file.

if the remaining file path is `README.MD` then the WebSeed must respond with the content given above.

The WebSeed for a log must make every file in a Tile Torrent available. Webseeds missing files or with differing contents will be rejected by clients and will be unusuable.

Webseeds SHOULD support HTTPS. Webseeds MUST support HTTP/1.1.

Webseeds MUST respect the `Accepts-Encoding` header and respond with appropriately encoded content. Webseeds which ignore `Acceps-Encoding` and respond with gzip encoded content (as in the Static CT Specification) will be unusuable for BitTorrent clients which don't support gzip.

Multiple WebSeeds can be used in parallel for the same log. External WebSeed operators can serve many torrent clients but present as a single ordinary client to log operators.

WebSeeds do not have strict uptime requirements, however if no webseeds or regular seeds are available for a torrent, clients will not be able to finish their downloads.

## Consuming Tile Torrents to monitor CT

Clients wanting to make use of Tile Torrents need to integrate support for either RSS or JSON feeds. It is RECOMMENDED to use the JSON feed.

Once the client has fetched a JSON feed, it must decide whether to fetch a given tile via BitTorrent or via the Static CT Monitoring API.
The client SHOULD try to fetch the tile via BitTorrent and fall back to the Static CT Monitoring API after a set timeout.

Note that a Tile Torrent can never supplant the Static CT Monitoring API because critical endpoints such as checkpoints, issuers and higher level hash tiles are only available via the Static Monitoring API.

## Supporting Log Operators

Parties wishing to support log operators are RECOMMENDED to setup a BitTorrent client of their choice, configure it for unlimited seeding using the specific client's recommended settings and subscribe to the various RSS feeds.

Parties not wishing to use BitTorrent clients directly may consider setting up their own webseeds. Log operators providing Tile Torrents can integrate these webseeds alongside their own and advertise them in tile torrents.

There is no penalty to the log operator for including a webseed which is faulty or later becomes unavailable. Clients will simply drop that Webseed and continue to download from peers or use any alternative webseeds provided.
# Serving Static Certificate Transparency Tiles over BitTorrent

This document defines a mechanism for distributing Static Certificate Transparency (CT) tiles via BitTorrent. The primary motivation is to reduce bandwidth costs for log operators, be compatible with a broad range of existing BitTorrent clients, and limit operational complexity for log operators.

## Conventions Used in This Document

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this
document are to be interpreted as described in [BCP 14][] [RFC 2119][] [RFC
8174][] when, and only when, they appear in all capitals, as shown here.

[BCP 14]: https://www.rfc-editor.org/info/bcp14
[RFC 2119]: https://www.rfc-editor.org/rfc/rfc2119.html

## Overview

This specification covers four topics:
- Packaging Static CT tiles into Tile Torrents.
- Advertising Tile Torrents through RSS and JSON feeds for automated discovery.
- Seeding Tile Torrents via HTTP(S) Webseeds
- Client Behavior when consuming Tile Torrents

The specification aims to maximize compatibility, deployability, and simplicity. It makes almost the entire log corpus available via BitTorrent (>99.999%), aiming to reduce costs for log operators, but does not cover every file. For example, checkpoints, some hash tiles and issuer descriptions still be fetched directly from the log operator as described in the [Static Certificate Transparency API Spec](https://c2sp.org/static-ct-api).

The entity creating and serving tile torrents need not be the log operator; third parties may provide them independently. Clients that wish to contribute bandwidth can use existing BitTorrent clients without modification. Log operators can also seed Tile Torrents without needing to run BitTorrent-specific software. 

## Creating Torrents

A tile torrent for a given log is defined by a contiguous range of entries. It MUST include the corresponding data tiles and level 0 (L0) and level 1 (L1) hash tiles for that range.

Tile torrents SHOULD cover exactly 1,048,576 (`4096 * 256`) entries. Such a torrent therefore contains 4,096 data tiles, 4,096 L0 hash tiles, and 16 L1 hash tiles.

Tiles in a tile torrent MUST use the same directory structure as used by the Static CT API. Specifically:
- Data tile `N` MUST be stored at `/tile/data/<N>`.
- Hash tile `N` at tree level `L` MUST be stored at `/tile/<L>/<N>`.

`N` MUST be encoded as a path exactly as specified by the Static CT specification. Deviating from this structure makes the torrent unusable for clients.

Tile torrents SHOULD include a top-level `README.md` containing the following line:

```
LOG_URL: <log monitoring URL>
```

Placing a file at the top level of a torrent smooths over some inconsistencies in widely used clients. If `README.md` is included, it MUST use the exact format given here. Otherwise, the tile torrent will be unusuable.

Tile torrents SHOULD NOT include additional files. A torrent MUST be constructed only after all covered entries have been integrated into the log. Torrents SHOULD NOT contain partial tiles or hash tiles above level 1.

Tile torrents SHOULD be named descriptively, for example by including the log name and covered entry range.

Tile torrents SHOULD advertise at least one WebSeed URL, as described in the section below below.

Tile torrents MUST support the BitTorrent v1 protocol. Tile torrents SHOULD support the BitTorrent v2 protocol.

OPEN ISSUE: Consider varying the tile torrent size to accommodate lower-rate log shards.

## Serving Torrent Files

Each torrent file MUST be published over HTTPS for retrieval by clients.

### RSS Feeds

Many BitTorrent clients can subscribe to RSS feeds and automatically download the torrents they advertise.

The RSS feed MUST conform to the [BEP 36](https://www.bittorrent.org/beps/bep_0036.html) specification for RSS 2.0 torrent feeds.

Each torrent advertised to clients MUST appear as an `<item>` element with an `<enclosure>` whose attributes match the torrent metadata, as illustrated below.

```
<item>
<title>{torrent_name}</title>
<enclosure url="{torrent URL}" length="{.torrent file size in bytes}" type="application/x-bittorrent"/>
<pubDate>{publication date}</pubDate>
</item>
```

An RSS feed MAY include any number of torrent items.

### JSON Feeds

JSON feeds may be friendlier than RSS feeds for tooling specific to CT.

A JSON feed MUST expose an object with the following schema.

```json
{
  "log_name": "example-log",
  "last_updated": "2024-01-01T00:00:00Z",
  "torrents": [
    {
      "start_index": 0,
      "end_index": 1048575,
      "data_size_bytes": 123456789,
      "creation_time": "2024-01-01T00:00:00Z",
      "torrent_url": "https://example.net/example-log-0-1048575.torrent"
    }
  ]
}
```

`log_name` identifies the log. `last_updated` and `creation_time` SHOULD be RFC 3339 timestamps in UTC. `torrents` is an array; each element describes a single torrent covering the inclusive `start_index` through `end_index`, the total torrent size in bytes, and the HTTPS URL of the `.torrent` file.

### Advertising Feeds

OPEN ISSUE: Consider integration with the log's JSON manifest. Clint Wilson has proposed [discussion](https://groups.google.com/a/chromium.org/g/ct-policy/c/ikbxKXp_Nl4) formalizing the existing manifests.

Alternative: Recommend a fixed path under the monitoring prefix.

## Seeding Torrents

Publishing a torrent file by itself doesn't enable clients to download the contents; the associated content must be seeded so that clients can complete downloads.

[BEP 19](https://www.bittorrent.org/beps/bep_0019.html) defines HTTP-based web seeds. BEP 19 is widely implemented but incompatible with the Static CT API. This section describes how a HTTP server can act as a web seed for tile torrents.

A WebSeed MAY serve content from a complete local copy of the log or MAY fetch tiles via the Static CT Monitoring API. When fetching from a log, it MUST follow any policies prescribed by the log operator (for example, including a contact address in it's User-Agent) and SHOULD cache responses indefinitely to minimize load on the log.

Each WebSeed serves torrent content from a URL prefix. Upon receiving an HTTP request below that prefix, the WebSeed MUST remove the first path segment following the prefix; the removed segment is the name of the torrent. The remaining path identifies a file within the torrent.

- If the remaining path matches a tile file, the WebSeed MUST return the corresponding bytes.
- If the remaining path is `README.md`, the WebSeed MUST return the README content defined above.

A WebSeed MUST make every file in the torrent available. Clients reject WebSeeds that omit files or serve mismatched content.

WebSeeds SHOULD support HTTPS and MUST support HTTP/1.1.

WebSeeds MUST honor the `Accept-Encoding` header and encode responses accordingly. A WebSeed that responds with gzip or other formats without negotiation is unusable for most BitTorrent clients.

Multiple WebSeeds MAY operate simultaneously for the same log.

WebSeeds do not require strict uptime; however, if no WebSeed or traditional peer is available, clients cannot complete the torrent download.

## Consuming Tile Torrents

Clients that consume tile torrents SHOULD implement at least one of the discovery mechanisms described above. JSON feeds are RECOMMENDED.

After retrieving a feed entry, a client MUST decide whether to fetch the referenced tiles via BitTorrent or via the Static CT Monitoring API. Clients SHOULD attempt the BitTorrent transfer first and fall back to the Monitoring API after an implementation-defined timeout.

Tile torrents do not replace the Static CT Monitoring API. Endpoints such as checkpoints, issuer descriptions, and higher-level hash tiles remain available exclusively through the Monitoring API.

## Supporting Log Operators

Parties that wish to support log operators are RECOMMENDED to configure a BitTorrent client for indefinite seeding and then subscribe to the relevant RSS feeds.

Parties that prefer not to run a BitTorrent client MAY operate WebSeeds. Log operators can advertise third-party WebSeeds alongside their own in the torrents they publish.

Including a faulty or unavailable WebSeed does not penalize the log operator. Clients simply exclude that WebSeed and continue downloading from remaining peers or WebSeeds.

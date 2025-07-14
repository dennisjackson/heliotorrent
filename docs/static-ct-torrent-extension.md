# Serving Static Certificate Transparency over BitTorrent

This spec defines a mechanism for serving the Tiles used in Static Certificate Transparency over BitTorrent. This mechanism extends those defined in [Static CT API][] and aims to maximize compatability with the existing practices of CT Logs, Monitors and Clients.

Static CT can be served over BitTorrent by a log operator or by a third party, in a trustless manner. It requires no modifications to logs.

This document specifies how Tiles are served over BitTorrent and how clients can consume them.

This document was developed alongside the HelioTorrent implementation found at TODO.

* TOOD: C2SP Conventions

## Conventions used in this document

TODO: Reference Static CT API

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this
document are to be interpreted as described in [BCP 14][] [RFC 2119][] [RFC
8174][] when, and only when, they appear in all capitals, as shown here.

[BCP 14]: https://www.rfc-editor.org/info/bcp14
[RFC 2119]: https://www.rfc-editor.org/rfc/rfc2119.html

## Overview

TileLogs are packaged into individual torrents which cover the data tiles and level 0 and level 1 hash tiles for a contigious range. Each torrent covers 4096 data tiles, their matching level 0 hash tiles and their 16 L1 hash tiles, which is roughly 2 GB of data. These torrents do not overlap and are immutable over the life of the log.

Higher level tiles occupy less than 16 MB, even for a very large log over 100 TB in size and are often in a partial state. Consequently, these tiles, as well as checkpoints and issuers, should be fetched directly by clients from the Static CT API. Nonetheless, this means 99.999% of the log's data can be fetched via BitTorrent.

Clients or Monitors can discover new torrents either by fetching the latest checkpoint and calculating the URL at which the corresponding torrents can be found, or by consuming an RSS feed describing the available torrents. Automatically consuming RSS feeds of torrents is widely supported by contemporary torrent clients, making it easy for bandwidth to be donated to the log in a trustless way, without having to run any custom software.

This document also describes how TileLog Torrents can be seeded over HTTP via WebSeeds, which is also widely supported by Torrent Clients and allows torrents to be seeded without the need for log operators or third parties to operate torrent clients directly.

## Torrent Operators

First or Third Party
Defined by a URL
Swarm will share.

## Seeding Torrents

MUST serve at a URL
URL SHOULD be
MUST ignore the first directory
MUST serve uncompressed.
MUST serve the README

## Torrent Construction

A TileLog Torrent contains a subset of files in the TileLog directory. Each torrent is defined by a start index and a stop index of entries. The start and stop indexes must be multiples of `TODO`.

The torrent for (`X`,`Y`) contains the corresponding data tiles and L01 and L1 tiles. For example:

* Paths Example

Torrents additionally contain a README file, indicating the URL of the log. This is located at PATH.

Torrent name.

Torrent WebSeed

Torrent Version

Torrents SHOULD be served at PATH
Torrents can be compressed.

## Feed Construction

Feeds are published at FEED URL.
Feed contents.
Feed can be compressed.

## Client and Monitor Behavior

Clients fetch the feed, fetch the torrent and download it.
Clients should seed.
Clients should unpack on top of each other.
Clients should validate.
Clients can download a subset by..

## Design Decisions

* Compression
* Higher Level Tiles
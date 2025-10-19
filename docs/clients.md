# Consuming a log via HelioTorrent

## Using a BitTorrent Client

Almost any Bittorrent client can consume Heliotorrent feeds, provided that it either supports RSS subscriptions, or has a third party integration which does. Some popular open source options include:

    * Transmission
    * qBitTorrent
    * Deluge
    * Aria2

qBitTorrent integrates support for RSS subscriptions natively, the others have a number of plugins which do. One particuarly useful option is FlexGet which supports all of these clients.

### HelioTorrent with Transmission and FlexGet

* Install Transmission for your operating system.
* Enable the RPC interface
* Install FlexGet
* Configure FlexGet
* Profit.

### HelioTorrent with qBitTorrent

* Install qBitTorrent
* Enable RSS Support
* Add a feed
* Add an auto-downloader rule

## Integrating with CT Clients

This remains an open issue. There are two broad paths which could be taken. The first is to integrate BitTorrent support inside clients via native libraries. This has the benefit of preserving their existing semantics, can offer BitTorrent by default.

The second would be to implement a shim which exposes a classic Sunlight interface but proxies requests to either local filesystem (provisioned by a BitTorrent client) or uses a BitTorrent library to stream requests directly. There are various packages which allow torrents to be mounted via a virtual file system.
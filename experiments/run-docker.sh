docker run -d \
  --name=qbittorrent \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Etc/UTC \
  -e WEBUI_PORT=8080 \
  -e TORRENTING_PORT=6881 \
  -p 8080:8080 \
  -p 6881:6881 \
  -p 6881:6881/udp \
  -v //Users/djackson/Documents/codebases/heliotorrent/experiments:/config \
  -v /Users/djackson/Documents/codebases/heliotorrent/data/tuscolo2026h1.skylight.geomys.org:/downloads `#optional` \
  --restart unless-stopped \
  lscr.io/linuxserver/qbittorrent:latest


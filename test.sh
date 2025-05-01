rm -r test/

mkdir -p test/tile/data/x001/x134
mkdir -p test/tile/data/x001/x128

wget https://rome2025h1.fly.storage.tigris.dev/tile/data/x001/x134/068 -O test/tile/data/x001/x134/068
wget https://rome2025h1.fly.storage.tigris.dev/tile/data/x001/x128/044 -O test/tile/data/x001/x128/044

# imdl torrent create --link --input test/ --name "piece1" --output test/1.torrent
# imdl torrent create --link --input test/ --name "piece2" --output test/2.torrent


# imdl torrent create --link --show --input test/tile/data/x001/x128/044 --name "piece1" --glob "test/tile/data/x001/x128/*" --output test/1.torrent
# imdl torrent create --link --show  --name "piece2" --glob "test/tile/data/x001/x134/*" --output test/2.torrent ./test --include-junk --include-hidden
imdl torrent create --link --show  --name "abc" --glob "*/x001/x128/*" --output test/1.torrent ./test #--include-junk --include-hidden
imdl torrent create --link --show  --name "abc" --glob "*/x001/x134/*" --output test/2.torrent ./test #--include-junk --include-hidden

# imdl torrent show test/1.torrent
# imdl torrent show test/2.torrent
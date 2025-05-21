

# Tiles are served as at
#     <monitoring prefix>/tile/<L>/<N>[.p/<W>]
# with `Content-Type: application/octet-stream`.
# `<L>` is the “level” of the tile, and MUST be a decimal ASCII integer between 0
# and 5, with no additional leading zeroes.
# `<N>` is the index of the tile within the level. It MUST be a non-negative
# integer encoded into 3-digit path elements. All but the last path element MUST
# begin with an `x`. For example, index 1234067 will be encoded as
# `x001/x234/067`.

def get_data_tile_paths(startEntry,endEntry):
    #TODO
    #Yield the tile paths, e.g. `x001/x234/067`

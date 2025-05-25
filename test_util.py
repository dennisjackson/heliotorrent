from util import int_to_parts, get_hash_tile_paths


def to_list(y):
    return list(x for x in y)


def test_int_to_parts():
    assert int_to_parts(1234067) == ["x001", "x234", "067"]
    assert int_to_parts(1) == ["001"]


def test_get_hash_tile_paths():
    assert to_list(get_hash_tile_paths(0, 256, 256)) == ["tile/0/000"]
    assert to_list(get_hash_tile_paths(0, 512, 1024)) == ["tile/0/000", "tile/0/001"]
    assert to_list(get_hash_tile_paths(768, 1024, 1024)) == ["tile/0/003"]
    assert to_list(get_hash_tile_paths(256 * 1000, 256 * 1001, 256 * 1001)) == [
        "tile/0/x001/000"
    ]
    assert to_list(get_hash_tile_paths(0, 256, 127, partials_req=True)) == [
        "tile/0/000.p/127"
    ]
    assert to_list(get_hash_tile_paths(0, 256, 256, partials_req=True)) == [
        "tile/0/000",
        "tile/1/000.p/1",
    ]
    assert to_list(
        get_hash_tile_paths(0, 256, 256, partials_req=True, level_end=1)
    ) == ["tile/0/000"]


print(to_list(get_hash_tile_paths(0, 256, 256, partials_req=True)))

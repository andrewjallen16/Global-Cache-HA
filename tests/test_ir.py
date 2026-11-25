from conftest import load

ir = load("ir")


def test_pronto_to_gc():
    body = ir.parse_ir_code("0000 006d 0002 0002 0157 00ac 0015 0015 0015 0040 0015 0015")
    assert body == "38029,1,5,343,172,21,21,21,64,21,21"


def test_pronto_without_repeat_has_offset_1():
    body = ir.parse_ir_code("0000 006d 0002 0000 0157 00ac 0015 0015")
    assert body.split(",")[:3] == ["38029", "1", "1"]


def test_full_sendir_string_is_rewritten_to_body():
    assert ir.parse_ir_code("sendir,1:1,1,38000,1,1,342,171,21,21,21,64") == \
        "38000,1,1,342,171,21,21,21,64"


def test_body_passthrough_and_validation():
    assert ir.parse_ir_code("38000,1,1,10,10") == "38000,1,1,10,10"
    for bad in ("", "garbage", "38000,1,1,10", "10,1,1,10,10", "38000,1,2,10,10", "38000,99,1,10,10"):
        try:
            ir.parse_ir_code(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted bad code {bad!r}")


def test_timings_signed_ints():
    # 9000us mark, 4500us space, 560us mark -> trailing gap appended
    body = ir.timings_to_gc([9000, -4500, 560], 38000)
    freq, count, offset, *cycles = body.split(",")
    assert (freq, count, offset) == ("38000", "1", "1")
    assert cycles[:3] == ["342", "171", "21"]
    assert len(cycles) % 2 == 0 and int(cycles[-1]) == 1520  # 40 ms gap


def test_timings_legacy_objects_and_merging():
    class T:
        def __init__(self, h, l):
            self.high_us, self.low_us = h, l

    body = ir.timings_to_gc([T(1000, 500), T(0, 500), T(1000, 0), T(1000, 1000)], 40000)
    # marks/spaces of the same sign are merged: +1000 -1000 +2000 -1000
    assert body.split(",")[3:] == ["40", "40", "80", "40"]


def test_timings_empty_rejected():
    try:
        ir.timings_to_gc([], 38000)
    except ValueError:
        return
    raise AssertionError("empty timings accepted")

"""Helpers for converting IR codes into Global Caché's sendir format.

Internally every code is stored as the "body" of a sendir command, i.e.
everything after ``sendir,<connector>,<id>,``:

    <frequency>,<count>,<offset>,<on1>,<off1>,<on2>,<off2>,...
"""
from __future__ import annotations


def parse_ir_code(code: str) -> str:
    """Convert a user supplied IR code into a normalised sendir body.

    Accepted formats:
      * a full Global Caché string:  sendir,1:1,1,38000,1,1,343,172,...
      * just the body:               38000,1,1,343,172,...
      * a Pronto hex code:           0000 006d 0022 0002 ...
    Raises ValueError if the code cannot be understood.
    """
    text = code.strip()
    if not text:
        raise ValueError("Empty IR code")

    if text.lower().startswith("sendir"):
        parts = [p.strip() for p in text.split(",")]
        if len(parts) < 8:
            raise ValueError("sendir string is too short")
        return _validate(parts[3:])

    if "," in text:
        return _validate([p.strip() for p in text.split(",")])

    return _pronto_to_gc(text)


def _validate(parts: list[str]) -> str:
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        raise ValueError("IR code contains non-numeric values") from None

    if len(nums) < 5 or (len(nums) - 3) % 2:
        raise ValueError(
            "IR code needs frequency, count, offset and complete on/off pairs"
        )
    freq, count, offset = nums[:3]
    if not 20000 <= freq <= 500000:
        raise ValueError(f"Carrier frequency {freq} Hz is out of range")
    if not 1 <= count <= 20:
        raise ValueError(f"Repeat count {count} is out of range (1-20)")
    if offset < 1 or offset % 2 == 0 or offset > len(nums) - 3:
        raise ValueError(f"Invalid repeat offset {offset}")
    return ",".join(str(n) for n in nums)


def _pronto_to_gc(text: str) -> str:
    try:
        words = [int(w, 16) for w in text.split()]
    except ValueError:
        raise ValueError("Not a valid Pronto hex code") from None

    if len(words) < 6 or words[0] != 0:
        raise ValueError("Only raw Pronto codes (starting with 0000) are supported")

    freq_code, once, repeat = words[1], words[2], words[3]
    if freq_code == 0:
        raise ValueError("Pronto frequency word is zero")
    needed = 4 + 2 * (once + repeat)
    if len(words) < needed:
        raise ValueError("Pronto code is shorter than its header says")

    freq = round(1_000_000 / (freq_code * 0.241246))
    pairs = words[4:needed]
    offset = 2 * once + 1 if repeat else 1
    return f"{freq},1,{offset}," + ",".join(str(p) for p in pairs)


GC_MAX_CYCLES = 65535
TRAILING_GAP_US = 40_000
DEFAULT_CARRIER_HZ = 38_000


def timings_to_gc(raw_timings, modulation: int | None) -> str:
    """Convert Home Assistant ``infrared`` raw timings to a sendir body.

    ``raw_timings`` comes from ``Command.get_raw_timings()``. Current
    infrared-protocols releases return signed microseconds (positive = mark,
    negative = space); older ones returned objects with ``high_us``/``low_us``.
    Both are accepted.
    """
    freq = int(modulation or DEFAULT_CARRIER_HZ)
    freq = max(20_000, min(500_000, freq))

    signed: list[int] = []
    for item in raw_timings:
        if hasattr(item, "high_us"):
            signed.extend((int(item.high_us), -int(item.low_us)))
        else:
            signed.append(int(item))

    merged: list[int] = []
    for value in signed:
        if value == 0:
            continue
        if merged and (merged[-1] > 0) == (value > 0):
            merged[-1] += value
        else:
            merged.append(value)

    while merged and merged[0] < 0:  # a signal has to begin with a mark
        merged.pop(0)
    if not merged:
        raise ValueError("Command contains no timings")
    if merged[-1] > 0:  # GC wants on/off pairs; close with an inter-frame gap
        merged.append(-TRAILING_GAP_US)

    cycles = [
        max(1, min(GC_MAX_CYCLES, round(abs(v) * freq / 1_000_000))) for v in merged
    ]
    return f"{freq},1,1," + ",".join(str(c) for c in cycles)

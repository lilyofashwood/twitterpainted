"""Bounded zlib/gzip expansion for untrusted recovered carrier bytes."""

import zlib

MAX_COMPRESSED_BYTES = 2 * 1024 * 1024
MAX_DECOMPRESSED_BYTES = 2 * 1024 * 1024


def decompress_deflate(
    data: bytes,
    *,
    wbits: int = zlib.MAX_WBITS,
    max_output: int = MAX_DECOMPRESSED_BYTES,
    reject_trailing: bool = False,
) -> bytes:
    """Decode one complete stream, permitting trailing carrier bytes.

    The extra output byte distinguishes an exact-cap payload from expansion
    beyond the cap. Never call an unbounded flush on hostile input. Trailing
    streams are not recursively or automatically expanded.
    """
    if not isinstance(data, bytes) or not data:
        raise ValueError("compressed payload must be nonempty bytes")
    if not isinstance(max_output, int) or isinstance(max_output, bool) or max_output < 1:
        raise ValueError("decompressed byte limit must be positive")
    if len(data) > MAX_COMPRESSED_BYTES:
        raise ValueError("compressed payload exceeds 2 MiB limit")
    try:
        decoder = zlib.decompressobj(wbits)
        payload = decoder.decompress(data, max_output + 1)
    except zlib.error as exc:
        raise ValueError(f"invalid compressed stream: {exc}") from exc
    if len(payload) > max_output or decoder.unconsumed_tail:
        raise ValueError(f"decompressed payload exceeds {max_output} byte limit")
    if not decoder.eof:
        raise ValueError("truncated compressed stream")
    if reject_trailing and decoder.unused_data:
        raise ValueError("trailing data or concatenated compressed streams")
    return payload


bounded_deflate = decompress_deflate

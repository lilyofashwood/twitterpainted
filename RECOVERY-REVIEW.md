# 𓂀 workshop engineering notes · 2026-09-10 𓋹

These notes record the September 10 recovery work now incorporated into `lilyofashwood/twitterpainted`. The authored identity, AGPL lineage, Twitter-survival PNG route, and separate full-lab JPEG experiment retain their own roles. See [the compression spell](docs/twitter-encoding.md) for the default carrier path and the downloaded Twitter original.

The recovered `veil-frame-rehab-v1.patch` predates much of this release. UTF-8 in the main encoder/simple decoder, profile-backed authoritative tool selection, advanced pixel-LSB PNG-only validation, and capability-probe labels were already implemented more precisely. Its old `veilframe` rename and selection replacement were not reapplied.

Focused repairs were adapted after full reads of the affected sources:

- Both file-writing encoder entry points now confine Unix/Windows upload names to a safe basename, including dot segments, control bytes and empty names.
- MP3Stego encode/decode, OpenPuff, DeepSound and Sonic Visualiser are planned integrations with placeholder wrappers. They report `planned`, `available: false`, and distinct `command_found` metadata. Selecting one reports `skipped`. Capability probes report installed-tool presence separately from carrier analysis.
- Zlib recovery in the simple and advanced LSB analyzers bounds compressed input and decoded output to 2 MiB and rejects invalid, truncated and over-limit streams. These decoders retain their first-stream/trailing-carrier behavior; the shared helper also supports strict trailing-data rejection for wrapper analysis.
- STEG compressed recovery now uses the same bounded zlib/raw-deflate helper and rejects failed expansion before writing any recovered payload. CRC mismatch artifacts remain available for investigation but are explicitly labeled `unverified_crc_mismatch`; a CRC match is not cryptographic authentication. Wrapper zlib/gzip/bzip2/LZMA and option/PNG text expansion are also bounded, and wrapper archive creation has a 30-second timeout.
- The opening clue now uses the Apoploe red/yellow-leaf proposal from `follow-the-melody-reclaimed.md`, mapped through the existing house glyph style. That wording is a new editorial proposal, not recovered manuscript text. Its literal answer remains implicit even after Unicode normalization; original links and the remainder of the README are retained.

September 10 verification: **137 tests and 32 subtests passed** with Python, Flask, SciPy and jpeglib. Checks cover filename handling (13 subcases), mocked tool readiness/execution, decoded-size boundaries, malformed/truncated compression, UTF-8/BOM/NUL preservation, analyzer call paths, rejection before export and the README clue. External backend calls use mocks. September 11 adds a front-door contract for the default Twitter route: **138 tests and 32 subtests pass**.

```sh
python3 -m unittest discover -s tests -p 'test_*_contracts.py' -v
```

The verification above covers the local implementation. The Docker toolchain is a separate installation path: several optional sources are unpinned, and some installation failures are suppressed. Check each external analyzer's readiness result before using it. The Twitter original-PNG record is described in the compression spell linked above.

Engineering follow-ups recorded September 10: stricter STEG header/PNG metadata validation, DCT cache bounds, individual R/G/B secret persistence in localStorage, case-sensitive input presentation, and upload/reduced-motion polish. The historical Unicode13 reference needs its three advertised Mongolian selectors. Decoder candidates use heuristic ranking; CRC checks accidental damage. These items are separate from the bounded-decompression repairs and the working default Twitter route.

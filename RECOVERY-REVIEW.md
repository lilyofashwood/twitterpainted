# 𓂀 private recovery review · 2026-09-10 𓋹

The authored `twitterpainted` identity, AGPL license boundary, public release history, and intentional full-lab JPEG failure experiment remain intact. No public deployment was changed by this recovery.

The recovered `veil-frame-rehab-v1.patch` predates much of this release. UTF-8 in the main encoder/simple decoder, profile-backed authoritative tool selection, advanced pixel-LSB PNG-only validation, and capability-probe labels were already implemented more precisely. Its old `veilframe` rename and selection replacement were not reapplied.

Focused repairs were adapted after full reads of the affected sources:

- Both file-writing encoder entry points now confine Unix/Windows upload names to a safe basename, including dot segments, control bytes and empty names.
- The Dockerfile creates zero-exit echo placeholders for MP3Stego encode/decode, OpenPuff, DeepSound and Sonic Visualiser. These integrations now report `planned`, `available: false`, and distinct `command_found` metadata. Selecting them reports `skipped`; their wrappers cannot be presented as successful carrier analysis. Other real capability probes remain available and are still only presence/help probes, not payload recovery.
- Zlib recovery in the simple and advanced LSB analyzers now bounds both compressed input and decoded output to 2 MiB. Invalid, truncated and over-limit streams are not successful recoveries. These carrier decoders retain their historic first-stream/trailing-carrier behavior; the shared helper also supports strict trailing-data rejection for wrapper analysis. This is a new safety limit, not an assertion that larger historic payloads were losslessly recovered.
- STEG compressed recovery now uses the same bounded zlib/raw-deflate helper and rejects failed expansion before writing any recovered payload. CRC mismatch artifacts remain available for investigation but are explicitly labeled `unverified_crc_mismatch`; a CRC match is not cryptographic authentication. Wrapper zlib/gzip/bzip2/LZMA and option/PNG text expansion are also bounded, and wrapper archive creation has a 30-second timeout.
- The opening clue now uses the Apoploe red/yellow-leaf proposal from `follow-the-melody-reclaimed.md`, mapped through the existing house glyph style. That wording is a new editorial proposal, not recovered manuscript text. Its literal answer remains implicit even after Unicode normalization; original links and the remainder of the README are retained.

Verification after the final STEG change: **137 tests and 32 subtests passed in 5.75 seconds**, using `/tmp/twitterpainted-review.pdUEr3/bin/python -m pytest -q`. The task-only environment includes Flask, SciPy and jpeglib. Focused checks cover filename handling (13 subcases), mocked tool readiness/execution, decoded-size boundaries, malformed/truncated compression, UTF-8/BOM/NUL preservation, actual analyzer call paths, rejection before export and the normalized README clue. External backend/tool boundaries are mocked; this is not operational verification of those programs.

```sh
python3 -m unittest discover -s tests -p 'test_*_contracts.py' -v
```

The original repository's text, JSON data and images were fully reviewed collectively; exact per-file readers and representation methods are recorded in the workspace audit ledgers. No Docker build, external steganography tool install or live X/Twitter transport test was performed. The Dockerfile downloads several unpinned upstream sources and suppresses failures for some optional installations; a successful image build alone is not proof that all tools work.

Remaining limitations include heuristic rather than authenticated decoder candidates; incomplete strict STEG header/PNG metadata validation; lifetime growth of DCT caches; automatic localStorage persistence of individual R/G/B secrets; visual lowercasing of case-sensitive input; and upload/reduced-motion accessibility work. The historical Unicode13 reference omits three advertised Mongolian selectors. These findings are recorded for follow-up, not silently presented as resolved by the bounded-decompression repair.

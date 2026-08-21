# provenance and notices

Twitterpainted is licensed as a whole under the GNU Affero General Public
License, version 3. See `LICENSE`.

Copyright © 2025–2026 lilyofashwood. Upstream portions retain their original
copyrights and license terms as described below.

Portions of `engine/encoder.py`—including the PNG conversion, 900 KiB
preflight, text-plane encoder, and zlib-plane encoder family—are modified
derivatives of Pliny's ST3GG application:

- source: <https://github.com/elder-plinius/ST3GG/blob/487f6e93167407ec4a68afc80834f72556f73845/app.py>
- source license: <https://github.com/elder-plinius/ST3GG/blob/487f6e93167407ec4a68afc80834f72556f73845/LICENSE>
- upstream commit: `487f6e93167407ec4a68afc80834f72556f73845`
- upstream project: `elder-plinius/ST3GG`, formerly `STEGOSAURUS-WRECKS`

Those portions were substantially modified for this application by
`lilyofashwood` during 2025–2026. The web interface, decoder/analyzer suite,
additional encoding methods, validation, tests, and deployment materials also
contain original and collaborative work from the same period.

Author's provenance note:

> the twitter trick was stolen from pliny because he used it to steal my heart.
> risky love; proper attribution.

Aperisolve inspired the analysis workflow. It is an alternative service, not a
runtime dependency, and no Aperisolve source is included here.

Users interacting with a hosted copy can obtain the corresponding source,
without charge, at <https://github.com/lilyofashwood/twitterpainted>.

# 𓂀 🖤 compression spell 🖤 𓋹

Twitterpainted has several different carrier paths. They solve different
problems and should not share one promise.

## twitterpaint: pixel lsb + png

`twitterpaint` wraps combined-RGB `simple_lsb` and separate R/G/B
`advanced_lsb` behind one mutually exclusive, text-only mode. Alpha and file
payloads are excluded. Its source carrier may be PNG or JPEG, because the app
first decodes the source into pixels. PNG is the lossless output default.

The quick demo intentionally exposes only this PNG output and now locks its
Twitter profile on. Before embedding, it redraws the cover to an opaque RGB
canvas no larger than 680 pixels on either edge. After browser serialization,
it removes every ancillary PNG chunk so the downloaded container matches the
metadata-free Pillow route used by the old Streamlit build. It re-embeds after
every size reduction until the finished PNG is at most 900 KiB. The final file
must contain at least 257 distinct RGB colors so Twitter cannot collapse it
into an indexed palette. The demo then reopens the actual PNG, checks the
dimensions, size, truecolor type, opacity, and color count, and recovers the
exact expected text. If any condition fails, it offers no download.

Every successful export also gets a short RGB-raster "paint mark" in its
filename. The decoder recalculates the same mark and compares it with the last
local export, so an older visually identical upload cannot masquerade as the
new carrier. The current encoder remains combined RGB or individual R/G/B
only; the decoder additionally reads legacy alpha-plane text from older demo
artifacts.

The 900 KiB preflight comes from Pliny's implementation. The 680-pixel ceiling
and 257-color guard encode the original-image constraints documented by
[tweetable-polyglot-png](https://github.com/davidbuchanan314/tweetable-polyglot-png).
Together they keep Twitterpaint inside the lossless original-PNG path instead
of merely hoping a locally valid file avoids recompression. JPEG conversion or
resizing still destroys pixel LSB, so the decoder must receive Twitter's
downloaded original—not a screenshot, preview, or transcoded copy.

The `nyanscence` receipt was a useful counterexample to the first diagnosis:
X preserved its PNG raster and IDAT stream exactly while removing one EXIF
chunk. It was the earlier alpha-plane carrier, not the newer combined-RGB
export. Whether that came from file selection or media reuse cannot be proven
from the receipt alone; the paint mark makes the distinction visible now.

## the full-lab jpeg experiment

The full Flask lab leaves JPEG selectable so its failure boundary can be
tested. It writes quality 95 with 4:4:4 chroma, reopens the file, and reports an
exact pass or fail without withholding the download. Quality 100, 4:4:4, and
the Orion smoke carrier still failed in local tests. No JPEG quality setting
can make pixel LSB a reliable JPEG scheme; JPEG changes the pixels that hold
those bits.

## the compression-tolerant option: dct + high + jpeg

The optional frequency-domain DCT mode can encode with high robustness and
JPEG output. Twitterpainted embeds the bitstream in lower-frequency luminance
coefficients and keeps the final carrier below 900 KiB.

The regression suite encodes and decodes this preset, then recompresses the
JPEG at quality 75 and decodes it again. The payload survives that tested form
of lossy JPEG recompression. It does not survive resizing: changing pixel
dimensions changes the block grid and destroys the bitstream.

This makes the preset JPEG-recompression-tolerant, not universally
compression-proof. Social platforms can crop, resize, transcode, strip data,
or change their pipelines without notice. Download the posted image and decode
that copy before trusting the channel.

## what pliny's two implementations actually do

The [historical Streamlit source](https://github.com/elder-plinius/ST3GG/blob/487f6e93167407ec4a68afc80834f72556f73845/app.py)
accepts PNG or JPEG inputs, but saves the preflight carrier as optimized PNG,
embeds afterward, and downloads PNG. It has no pixel-LSB JPEG output path.

The [current STE.GG browser source](https://github.com/elder-plinius/ST3GG/blob/main/index.html)
also emits ordinary LSB as PNG. Its genuine JPEG path first creates a JPEG at
selectable quality 90, 92, 95, or 98 (95 by default), then embeds with F5 in
JPEG coefficients. Its own UI warns that this F5 result does not survive
social-media recompression. A separate robust DCT experiment preconditions at
quality 85, uses stronger quantization plus five-block majority redundancy,
and still exports PNG. Those are different formats and decoders—not special
save settings that can rescue simple pixel LSB inside JPEG.

## provenance

> the twitter trick was stolen from pliny because he used it to steal my heart.

The conversion, preflight, and original text/zlib LSB encoder family are
modified from
[`elder-plinius/ST3GG@487f6e9`](https://github.com/elder-plinius/ST3GG/blob/487f6e93167407ec4a68afc80834f72556f73845/app.py),
which is AGPL-3.0. Twitterpainted preserves that license and documents the
modifications in `NOTICE.md`.

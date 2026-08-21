# research steganalysis adapters

Twitterpainted exposes eight optional research analyzers as independent,
selectable tools. They are intentionally absent from every default profile.
Selecting one either runs a configured backend against the uploaded carrier or
returns an explicit `skipped` readiness result. A missing executable, model, or
side-information file is never reported as a successful analysis.

Twitterpainted itself does not download model weights, fetch research
dependencies, or vendor these upstream frameworks. Install and review them
separately, then provide only the local paths described below. A separately
installed backend can still perform downloads documented by that backend when
Twitterpainted invokes it; Aletheia's feature paths, for example, can obtain its
Octave code and JPEG toolbox. Review backend behavior before enabling a
checkbox in a networked deployment.

## backend matrix

| checkbox | runtime and configuration | carrier | result contract |
| --- | --- | --- | --- |
| `aletheia` | Aletheia executable on `PATH`, or `TWITTERPAINTED_ALETHEIA_COMMAND` | readable image | runs `auto` on a staged one-image directory and requires a per-image detector row |
| `srnet` | Aletheia plus `TWITTERPAINTED_SRNET_MODEL` | readable image compatible with the checkpoint | runs `srnet-predict` on CPU and requires a probability for the uploaded filename |
| `siastegnet` | `TWITTERPAINTED_SIASTEGNET_RUNNER` and `TWITTERPAINTED_SIASTEGNET_MODEL` | readable image compatible with the checkpoint | requires the JSON model-runner protocol below |
| `xunet` | `TWITTERPAINTED_XUNET_RUNNER` and `TWITTERPAINTED_XUNET_MODEL` | JPEG | requires the JSON model-runner protocol below |
| `dctr` | Aletheia plus its Octave dependencies | JPEG | creates and validates a numeric DCT-residual feature vector; it does not invent a classifier verdict |
| `gfr` | Aletheia plus its Octave dependencies | JPEG | creates and validates a numeric Gabor-filter feature vector; it does not invent a classifier verdict |
| `maxsrmd2` | `TWITTERPAINTED_MAXSRMD2_RUNNER` and `TWITTERPAINTED_MAXSRMD2_SELECTION_MAP` | lossless PNG, BMP, or TIFF matching the selection map | creates and validates a numeric selection-channel-aware feature vector; the image alone is insufficient |
| `stegspy` | locally authorized `stegspy` on `PATH`, or `TWITTERPAINTED_STEGSPY_COMMAND` | readable image | runs the historical signature scanner and reports only recognized legacy signatures or `no_signal` |

`TWITTERPAINTED_ALETHEIA_COMMAND` and each runner variable may contain an
executable plus fixed arguments. Commands are parsed as an argument vector and
run without a shell. A non-executable Python script can be supplied by path and
will be launched with the active Python interpreter.

## model-runner protocol

The SiaStegNet and Xu-Net adapters call the configured runner as:

```text
RUNNER --input CARRIER --model CHECKPOINT --json
```

The runner must exit successfully and write a JSON object to stdout containing
one finite probability in the inclusive `0..1` range under
`stego_probability`, `probability`, or `score`:

```json
{"stego_probability": 0.625, "backend": "locally trained model"}
```

Plain prose, an out-of-range value, an exception, or a zero exit with no
validated value is an error. Model scores are checkpoint- and training-domain
dependent; they are not universal proof that a carrier is clean or contains a
payload.

The maxSRMd2 runner contract is:

```text
RUNNER --input CARRIER --selection-map MAP --output FEATURE_FILE
```

It must create a non-empty, finite, whitespace-delimited numeric feature
vector. DCTR and GFR use Aletheia's native `COMMAND INPUT OUTPUT` feature
extractor interface and apply the same output validation. Successful feature
passes package the vector (and Aletheia label file, when present) as a
downloadable ZIP artifact.

## provenance and license boundaries

- [Aletheia](https://github.com/daniellerch/aletheia) is MIT licensed. Its
  TensorFlow models, Octave packages, external utilities, and downloaded
  resources can carry additional terms.
- [SiaStegNet](https://github.com/SiaStg/SiaStegNet) publishes research code
  and pretrained-model guidance but no upstream license file was identified.
  Twitterpainted therefore supplies only a runner interface and does not copy
  its code or weights.
- [Xu-Net / Caffe deep JPEG steganalysis](https://github.com/GuanshuoXu/caffe_deep_learning_for_steganalysis)
  retains an upstream Caffe-derived license. Checkpoint terms still need
  separate review.
- [DCTR, GFR, and maxSRMd2 reference feature extractors](https://dde.binghamton.edu/download/feature_extractors/)
  originate with Binghamton University's Digital Data Embedding Laboratory.
  Twitterpainted uses Aletheia for DCTR/GFR and does not redistribute the
  separately hosted maxSRMd2 package because no redistributable license was
  identified there.
- [StegSpy](https://www.spy-hunter.com/stegspydownload.htm) is a copyrighted
  historical binary distributed under explicit upstream download and export
  terms. It is never bundled or fetched by Twitterpainted.

The analyzer catalog API and information mode expose each backend's source,
license note, license URL, applicable formats, operation type, and estimated
cost. These notes describe integration boundaries, not legal advice.

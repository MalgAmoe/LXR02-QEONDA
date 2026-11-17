# Frozen original DSP source

- Origin: https://github.com/MalgAmoe/LXR02-QEONDA
- Original commit: `20e6e6b6f7cee1b17504bcd68148a6e61fce11a8`
- Archive: `audio_source_20e6e6b.tar.gz`
- Archive SHA-256: `f51b7866d00d252e51324e2d22d981047f6fa47aa644889903115034c90535b3`
- File manifest / translation units: `audio_source_20e6e6b.json`

All 80 archived files are byte-for-byte original Git blobs, extracted using
`git show COMMIT:PATH` and independently matched against the original source tree
used in the portability investigation. There are no regenerated normalized-code
baselines or changes to original algorithms. Existing copyright notices remain;
original `LICENSE` (GPL-3.0) and `NOTICE.md` (additional permission/terms and
attribution) are included. Consult those files before redistribution.

## Selection and reproduction

The closure was obtained with AppleClang 17 `-MM -std=gnu11 -DLXR_HOST_TEST
-DAUDIO_PROBE_SCALE=1.f`, using the translation units listed in the manifest and
the current `audio_normalized_probe.c`. Include directories were the temporary
probe directory, current `tests`, current `tests/shim`, and original `Core/Inc`.
The current integration harness was copied beside the temporary probe with its
`../Core/` textual includes redirected to the original tree. The renderer header
was extracted from original `Soundengine.c` exactly as the test does.

Union the resulting original-tree dependency paths (normalize `..` segments),
translation units, `Core/Src/Soundengine/Soundengine.c`, `LICENSE` and `NOTICE.md`.
Read each file from the original commit, hash its original bytes with SHA-256,
and archive under repository-relative paths. The archive uses sorted paths,
regular files with mode 0644, zero timestamp/UID/GID and gzip mtime zero. This
retains the actual compiler dependency closure rather than all 245 candidate
files. System headers and the intentionally shared current probe/harness/shims
are not frozen here. No history is required to *run* the test.

The unchanged `audio_baseline_20e6e6b.txt.gz` remains historical measured evidence;
it is not used as a cross-platform numerical oracle. Do not regenerate this
source archive from current code or relax the regression ceiling.

## Portability verification

Investigation logs: `/tmp/qeonda-portability/` (local, not required by tests).

- Original test: native AppleClang 17 ARM64 passed; AppleClang 17 x86_64 via
  `/tmp/qeonda-audio.nJzfuD/cc-x86` and Rosetta reproduced O1 RAT error
  `0.12206080000032671` against historical observations.
- Fixed same-toolchain test: native AppleClang 17 ARM64, AppleClang 17 x86_64
  via Rosetta, and installed Homebrew Clang 22.1.4 ARM64 all passed both modes.
  Maximum O1 differences: ARM64 `0.003899392`, x86_64 `0.0039059456` old units;
  O3/fast-math observations were exact in all three configurations.
- Full existing host suite: **56/56** passed for each of those three compiler/
  architecture configurations. Five standalone Python harness regressions passed,
  including nonfinite values on either side and aggregate category/mode failures.
- Temporary current-source mutation changed Ringmod wet gain from 0.5 to 0.6:
  comparison failed in both modes, maximum `1916.75194` old units. The frozen
  baseline was unchanged; no tracked production file was mutated.
- `--record` capture completed and emitted compiler/target/host/flags/content-hash
  metadata; no historical observation file was overwritten.
- Linux was not available and was **not executed**. No dependency installation,
  target firmware change, hardware/timing/listening certification or CI change.

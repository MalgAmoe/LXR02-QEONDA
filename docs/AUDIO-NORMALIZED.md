# Normalized float32 audio

## Scope and identities

Implemented on `audio-float32-24bit`, HEAD
`20e6e6b6f7cee1b17504bcd68148a6e61fce11a8` plus uncommitted normalization changes.
LXR QEONDA remains **0.1**. No commits, pushes, card writes or installation.
The pre-existing `.vscode/settings.json` user edit is preserved.
SHA256 of `git diff --binary -- Core`:
`3a5d7cbb0fc814cca2d187a7860c392d9f8738f93f1c089332539313cc0c5fb5`.

Audio now means **old sample / 32768** from table READS through both DAC encoders.
No intermediate wrapper returns old audio units. Audio buffers remain float32;
parameters, project/storage formats, UI, uint32 phases, table data/storage and
shared LFO int16 sine reads are unchanged. No regeneration or new build options.
Firmware files retain their original CRLF/LF conventions.

## Boundary/source map

Paths below are under `Core/`.

| Source | Mapping / preserved behavior |
|---|---|
| `Inc/Soundengine/AudioSample.h` | Per-operation bounds become −1…32767/32768; original add/sub locations and fractional arithmetic remain. |
| `Src/Soundengine/DSPAudio/Oscillator.c` | Normalize **both** interpolation endpoints and held RNG noise; oscillator outputs are normalized. FM restores ×32768 **before** float multiply / uint32 quantization / phase shift. No negative clamp. |
| `…/transientGenerator.c` | Signed8 data /128 equals target `(signed8 << 8)/32768`, including negatives, without signed-shift C UB. Single-sample click is 127/128. Existing phase gate remains (last stored element 2204 is not played by block entry). Snap pitch is dimensionless, unchanged. |
| `…/ResonantFilter.c` | Input ×32768/32767; output gain /32768, including cheap/naive and shaper branches. Nonlinear integrator states are **not** rescaled. |
| `…/distortion.c` | Preserve voice distortion's /32767 laws with input ×32768/32767, output ×32767/32768. |
| `…/Snare.c` | Same source clip before EG/volume/fader and exceptional final bound, expressed in normalized units. |
| `…/MainCompressor.c`, `…/FX/Compressor.c` | Remove detector /32768. Gain, makeup, attack/release and mono saturation semantics remain. Main linear HP/LP states naturally follow normalized inputs; no extra state conversion. |
| `…/FX/Ringmod.c` | Normalized wet product ×0.5; retain historical mono destination-in-wet law and bounds. |
| `…/FX/Distortion.c` | Tube cell `(bound(n)+1)*64`; fraction `frac(n*64)` stays **unclipped** on overload. Fold/RAT already-normalized nonlinear states stay unchanged. Wet/delta/destination bounds retained; misleading clipping comment corrected. |
| `…/FX/Delay.c` | History retains old/32767 convention. Tap output ×32767/32768, bounded feedback input ×32768/32767. Every feedback/wet/delta/destination bound and history capacity remain. |
| `Inc/Soundengine/AudioOutput24.h` | Both outputs scale normalized audio ×8388608, clamp signed24 and truncate toward zero into existing padded transport. Main HP→LP→compressor order unchanged. |

## Differential evidence

`tests/audio_normalized_probe.c` was compiled unchanged against an archived
**20e6e6b** source tree and the new working tree. Baseline observations are frozen
in `tests/fixtures/audio_baseline_20e6e6b.txt.gz` (SHA256
`4d5dcf557507ee88f1511ce74489c1ca9d199d3a3549574224adec7e76598f11`).
Ordinary tests do not require Git history. Capture/replay commands:

```sh
python3 tests/test_audio_normalized.py --source build/normalized-baseline-source \
  --scale 1.f --record /tmp/audio-baseline.txt.gz
python3 tests/test_audio_normalized.py
```

AppleClang17, ASan/UBSan/float-cast-overflow, O1 and O3/fast-math/reciprocal-math;
**23,872 normalized observations per optimization**. Coverage: six actual voice
paths with settled controls and nonlinear filters, interpolated sine/table/PWM FM,
tube overload/fold/RAT, normal/ping-pong delay, ring, FX compressor, all routes,
active main HP/LP/compressor and both encoders. Hardware/control-rate calls are
substitutes. FM probe uses nonnegative modulation; negative cases are separately
covered by the labeled exhaustive ARM-conversion host model, not executed as
undefined native conversions.

| O1 category | Changed / observations | Maximum difference in old sample units |
|---|---:|---:|
| Drums | 1 /1536 | 0.000245760 |
| Snare | 2 /512 | 0.001933312 |
| Hat | 3 /512 | 8.52e−22 |
| Cymbal | 4 /512 | 4.26e−19 |
| Delay | 44 /3072 | 0.003899392 |
| FM, tube/fold/RAT, ring, FX compressor, routing, both packed outputs | 0 /17728 | 0 |

O1 delay RMS difference: **0.000147403 old units**. These are observed rounding
and tiny recursive-tail differences, not an equivalence assumption. At O3/fast-math
all 23,872 printed float32-round-trip observations matched. This limited host
corpus does **not** prove universal/ARM bit equivalence. Regression ceiling is
0.02 old units; it does not justify changing expected musical laws.

## Verification and image

Fresh `build/host-normalized`: **53/53 CTest passed**, AppleClang17.
Existing numerical oracles now use normalized inputs/outputs/tolerances; signed
transient-table reads, encoder sub-LSB tails, per-add cancellation, delay full-ring
history/feedback/crossfade and both renderer DMA halves remain covered.

Fresh `build/release-normalized`: ARM GNU **14.3.rel1 / GCC14.3.1**, Release O3.
FM codegen check, float32 codegen check and release-image verifier **passed**.
FM disassembly retains direct `vmul.f32`→`vcvt.u32.f32`, no preceding negative
clamp; checker additionally verifies ×32768 and /32768 constants. PWM has only its
downstream waveform bound. GCC may commute exact power-of-two scaling across
multiply; the uint32 quantizer remains after the compensated float product.
No cycle-speedup claim. Whitespace check and original firmware line-ending check
passed; waveform/transient table files, LFO and float history layouts were checked
byte-for-byte against HEAD.

| Static placement | Baseline `release-audio-simplified` | Normalized |
|---|---:|---:|
| ITCM /16384 | 15840 | 15608 |
| DTCM /131072 | 76392 | 76392 |
| RAM /393216 | 374780 | 374780 |
| `size` text / data / bss | 294988 /836 /413332 | 294620 /836 /413332 |
| Image payload bytes | 295832 | 295464 |

SHA256 identities:

- Baseline image: `f842bbe84dbcc1bdfe42b5b2f5a9781497a170d3ed39ff3a34379a3e5438e886`
- New image: `ab989225b107f9121eb341b782052ad6db620572844b7ef80757cb62da99b013`
- New BIN: `833181e6c8980acd6150303930ea1ae69f245249d99ceb47f54a66aa2bb75ba9`
- New ELF: `d4e9c746241fbe3dc6449e38d8449988aa24f5599c247cbe8499b589501fd830`

## Remaining acceptance

Primary agent personally reviewed production/test diffs and the differential
probe, reran all 53 host tests, ARM build, both codegen checks and image validation.
Verified 245 archived baseline files against commit 20e6e6b and independently
reproduced the frozen baseline fixture byte-for-byte. Wavetable/LFO identity and
firmware CRLF were checked directly. Independent read-only source review found
no concrete new bug, but did not have Git-diff access.
No hardware listening, DAC capture, worst-case audio deadlines,
runtime stack margin, SD/MIDI concurrency or interoperability tests were performed.
RAM/ITCM fit is not timing or stack certification. Real ARM negative-FM execution
and audible equivalence remain hardware checks, beyond instruction/model evidence.

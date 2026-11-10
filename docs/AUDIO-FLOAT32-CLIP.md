# Float32 hard-clipped mix comparison

> **Historical experiment evidence.** The variant options and commands below
> describe earlier source only and are no longer supported build modes.
> This branch now always uses full float32 audio, 24-bit output on both pairs,
> and per-operation mix clipping. Original int16 tables, uint32 phases and
> deliberate nonlinear effects remain. See [BUILD](BUILD.md) for current commands.

## Single-path simplification verification

On `audio-float32-24bit`, uncommitted atop
`2d62fabf4c185875dc86bb9400a1eae320986d8c`: removed all four audio options
and their alternate engine/test paths, retaining the enabled clipped implementation.
No waveform table, phase representation, nonlinear law or storage implementation
change. Firmware CRLF retained. The earlier clipped IMG/BIN/ELF were copied to
`build/audio-simplify-baseline/` before editing; all three final artifacts are
byte-identical to those copies.

Fresh native AppleClang 17 Debug host build with default ASan/UBSan:
**52/52 passed** (`ctest --test-dir build/host-audio-simplified --output-on-failure`).
The integration and focused clipping tests now both exercise production clipping;
old integer fixtures use float samples and real packed output. Fractional snare
expectations allow 2 ppm fast-math reassociation instead of integer truncation.

Fresh ARM GNU 14.3.rel1 / GCC 14.3.1 Release in
`build/release-audio-simplified`: build, `check_fm_arm_codegen.py`,
`check_audio_float32_arm.py` and `verify_release.py` all passed.
Payload: **295832 bytes**. SHA-256:

| Artifact | SHA-256 |
|---|---|
| IMG | `f842bbe84dbcc1bdfe42b5b2f5a9781497a170d3ed39ff3a34379a3e5438e886` |
| BIN | `458c6c532ebc1903ac2f0dd0449ad5783a12f7e80aa2f1ef2ea0787f1e737d90` |
| ELF | `8fa50dba78a0d68cf86329391ad2ef9334cdea771d48d868f381ca81da0482d6` |

Local logs and baseline copies: `build/audio-simplify-baseline/` (ignored build
artifacts, not portable fixtures). No commits, new branches, card writes or
installation. No new hardware timing, stack-margin or listening claims.

## Historical record (unchanged below)

This is a **listening/preference test, not a proven glitch fix**. It is an
uncommitted comparison atop the existing float32 work based on `38cf955`.
`LXR_FLOAT_MIX_CLIP` defaults OFF and requires `LXR_AUDIO_FLOAT32=ON` (which
requires 24-bit transport). The original unclipped image remains reproducible.
No branch, commit, installation or card write was performed.

## Build

With Arm GNU 14.3.rel1 on PATH:

```sh
cmake -S . -B build/float32-clip -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi.cmake \
  -DCMAKE_BUILD_TYPE=Release -DLXR_AUDIO_24BIT=ON \
  -DLXR_AUDIO_FLOAT32=ON -DLXR_FLOAT_MIX_CLIP=ON
cmake --build build/float32-clip --parallel 4
python3 tests/check_fm_arm_codegen.py build/float32-clip
python3 tests/check_audio_float32_arm.py build/float32-clip
python3 cmake/tools/verify_release.py build/float32-clip

CC=clang cmake -S . -B build/host-float32-clip -G Ninja \
  -DLXR_HOST_TESTS=ON -DLXR_AUDIO_24BIT=ON \
  -DLXR_AUDIO_FLOAT32=ON -DLXR_FLOAT_MIX_CLIP=ON
cmake --build build/host-float32-clip --parallel 4
ctest --test-dir build/host-float32-clip --output-on-failure
```

For the unchanged unclipped comparison use `build/float32` and explicitly
`-DLXR_FLOAT_MIX_CLIP=OFF`. Do not reuse the clip directory for that image.

## Baseline operation audit and deliberate equivalents

Bounds are **−32768…32767 in existing sample units**, in float32, retaining
fractional values below the bounds. `audio_mix_add` bounds **each add**, not just
the final mix. For example `30000 + 10000 - 10000` becomes `22767`, not `30000`.
No rate, buffer size, pan scale, gain law or final encoder change is involved.

| Baseline location (`38cf955`) | Comparison |
|---|---|
| `BufferTools.h` saturating add | Bound every sample addition, including odd sizes; shared drum/hat/cymbal source sums use this same helper, without edits to voice DSP |
| BufferTools saturating add-with-gain / subtract (currently no callers) | Bound sum **before** gain / bound difference; no additional post-gain clipping |
| `mixer_addDataToOutput` | Bound every voice addition to FX stereo bus, both physical stereo routes and all four mono routes; keep mono pan bypass and jack fallback |
| `FxBus_process`, FX OFF | Bound each destination add, stereo or mono |
| Tube/fold/RAT, ring, FX compressor | Bound baseline dry/wet **delta**, then each destination addition |
| Ring mono | Additionally bound historical destination-plus-modulated-source wet sum, before dry/wet; retain `/65536` |
| Normal and ping-pong delay | Bound dry/wet delta, then dry-plus-delta (baseline explicit outer SSAT), then destination addition |

**Not a bit-exact signed16 emulation:** baseline distortion/ring/compressor
`dry + clipped delta` narrows through `int16_t` or packed halfwords and can wrap.
Those originally non-saturating sums remain float and unbounded here, rather than
being silently replaced with clipping or reintroducing integer quantization.
Likewise plain `bufferTool_addBuffers` remains non-saturating. Original pan casts,
wet casts and table quantization removed by the float experiment are not restored.
Thus this restores the original *saturating operations*, not every integer artifact.

FX compressor envelope, ratio, makeup, coefficients and wet-source bound are
unchanged; only its mix additions/delta regain baseline saturation. Main compressor
is untouched, including accepted `R - 4R/(R + 12)` dB makeup. Existing internal
FX feedback/wet-source saturations are untouched (not toggled by this option).
Disabled reverb remains disabled and outside the active float implementation.
No new clipping was added to synthesis/filter algorithms or final output DSP.

## Verification and image

Native AppleClang17, ASan/UBSan: **52/52 passed** in the clip configuration.
The suite deliberately retains `test_audio_float32` as the unclipped regression
and adds `test_float_mix_clip` compiled from the same production sources with
clipping enabled. Legacy integer tests explicitly deselect both float and clip.
Clip fixtures cover signed fractional subthreshold values, both overload signs,
all seven voice routes, per-add cancellation on every route, all six FX output
routes with every enabled FX, mono/stereo, both delay modes, all three distortion
variants, wet fractional returns and hot dry/wet delta/outer-sum behavior.
Host GPIO, RNG and control-rate dispatch remain substitutes; these are numerical
regressions, not hardware/audio-deadline tests.

ARM GCC14.3.1 Release: normal, unclipped and clipped builds, final-ELF FM checks
and image verification passed. Both float codegen checks passed; clip paths use
float32 min/max, without packed integer saturation or float64 arithmetic. Enabling
clip without float32 was rejected at configure time. Firmware CRLF/whitespace
checks passed. Normal and unclipped BIN hashes match their pre-task artifacts:

| Build | BIN SHA256 |
|---|---|
| Normal | `917129b377c33b1da81869d1ea2451dcdb06ebffc3b4a5f9cd0e7989fb19080f` |
| Float32 unclipped | `c111370cb958f2f48810ecc124e4f97eed9c27eadbe38439ebe140bceaaa9d3b` |
| Float32 clip | `458c6c532ebc1903ac2f0dd0449ad5783a12f7e80aa2f1ef2ea0787f1e737d90` |

Image: `build/float32-clip/LXR_QEONDA_V0.1.img`, **295832-byte payload**.
SHA256: `f842bbe84dbcc1bdfe42b5b2f5a9781497a170d3ed39ff3a34379a3e5438e886`.
Unclipped image remains `7a3932e0eb3030c2bd2d3390e9f95bd6910a4fc27da8c4c6390dd2b2015af7e4`.

## Static costs, not measured cycles

Compared with the unclipped float image: payload **+1448 bytes**;
ITCM **14936 → 15840 bytes** (544 remaining), DTCM **76392 unchanged**,
ordinary RAM **374780 unchanged** (18436 remaining, including heap reservation).
Actual final-ELF static instruction counts below include all branches, not a
particular executed path. Min/max counts include existing internal bounds.

| Function | Instructions off → on | Float min/max off → on |
|---|---:|---:|
| Mixer block | 963 → 1156 | 0 → 120 |
| FX bus | 110 → 120 | 0 → 6 |
| Distortion | 733 → 774 | 30 → 66 |
| Ring | 101 → 129 | 0 → 18 |
| FX compressor | 163 → 178 | 8 → 20 |
| Delay normal | 343 → 364 | 8 → 26 |
| Delay ping-pong | 298 → 313 | 12 → 30 |

Recompiled actual compile-command entries with `-fstack-usage` into
`build/float32-clip/cost-evidence/`: reported fixed frames are unchanged:
mixer824, FX bus20, distortion88, ring48, FX compressor88, normal delay72,
ping-pong80 bytes. Ring/compressor retain dynamic scratch (64-frame float:
256/512 bytes respectively). This is not a whole-program stack bound.

Listening, dense-playback timing, interrupt/stack high-water, codec/analogue
behavior and whether clipping changes any reported glitch remain unverified.

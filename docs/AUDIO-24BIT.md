# Experimental 24-bit output stages

> **Historical experiment evidence.** The variant options and commands below
> describe earlier source only and are no longer supported build modes.
> Snapshot from the 2026-11-10 experiments, superseded by clipped-float
> simplification `20e6e6b` and normalization `95297b3`, now included in
> development `8a81f1c`. Current audio is normalized float32 with 24-bit output
> on both pairs and per-operation mix clipping. Original tables/phases remain.
> See [AUDIO-NORMALIZED](AUDIO-NORMALIZED.md) and [BUILD](BUILD.md).

## Historical record (unchanged below)

For the separately gated full active float32 experiment, see
[AUDIO-FLOAT32](AUDIO-FLOAT32.md). The transport-only and main-output-only modes
below remain unchanged when that experiment is OFF.

Transport-only mode (`LXR_MAIN_OUTPUT_24BIT=OFF`) atop `38cf955` (single-file project storage). Default
`LXR_AUDIO_24BIT=OFF` retains the normal firmware. No synthesis, mixing, limiter,
output routing, timer ownership or project-storage behavior changes. This is **not
increased synthesis precision**: the existing signed int16 mixer renders static
scratch blocks; each channel sample becomes two DMA halfwords `[sample, 0]`.
The resulting 24-bit signed payload is the int16 value multiplied by 256, with
zero padding below it. Interleaved L/R order and SPI2 main / SPI3 OUT2 stay intact.

## Build separately

With the reference ARM toolchain on PATH:

```sh
cmake -S . -B build/audio24 -G Ninja -DCMAKE_BUILD_TYPE=Release -DLXR_AUDIO_24BIT=ON
cmake --build build/audio24 --parallel 4
python3 tests/check_fm_arm_codegen.py build/audio24
python3 cmake/tools/verify_release.py build/audio24
```

Host experiment configuration:

```sh
CC=clang cmake -S . -B build/host-audio24 -G Ninja -DLXR_HOST_TESTS=ON -DLXR_AUDIO_24BIT=ON
cmake --build build/host-audio24 --parallel 4
ctest --test-dir build/host-audio24 --output-on-failure
```

## Transport and clocks (source-derived, not measured)

Both active interfaces in [main.c](../Core/Src/main.c) select 24B only when enabled.
64 stereo frames per half remain unchanged. HAL Size remains 256 channel samples
for the two-half ring; [HAL_I2S_Transmit_DMA](../Drivers/STM32F7xx_HAL_Driver/Src/stm32f7xx_hal_i2s.c)
doubles that to 512 halfwords in 24B mode (normal: 256 halfwords). Circular DMA
and halfword memory/peripheral alignment are unchanged. Recovery clears the entire
expanded ring and restarts both interfaces with Size256. Generation acknowledgement
occurs only after both scratch blocks have been packed; a newer request survives.

HSE16MHz / PLLM8 × PLLI2SN113 / PLLI2SR5 = 45.2MHz I2S source.
HAL with Philips framing and MCLK enabled uses 32×8 for 16B, 64×4 for
24B: both prescaler calculations use256. Requested44.1kHz gives divider4
(ODD0, I2SDIV2), hence Fs = 45,200,000 / (256×4) = **44,140.625Hz**.
MCLK is11.3MHz; BCLK changes from1.4125MHz (32Fs) to2.825MHz (64Fs).
Block period is about1.450ms in either mode. These calculations assume the
configured oscillator, not an oscillator measurement.

## Verification evidence

Reference compiler: Arm GCC14.3.1, Release O3; native AppleClang17.
Fresh normal baseline and post-change default BIN and QEONDA image match exactly:

- BIN SHA256 `917129b377c33b1da81869d1ea2451dcdb06ebffc3b4a5f9cd0e7989fb19080f`
- Normal image SHA256 `5452c765246ef9fb117bd42c27efa3b9f130fdd52eba482da5e4d378df66e818`
- Experiment image SHA256 `4ce996253c9a7091ccc75d70740416c8fc3450151639d9b2ed88f667389d6260`

| Static quantity (bytes) | Normal | Experiment |
|---|---:|---:|
| Image payload | 295880 | 295808 |
| ELF text | 295036 | 294964 |
| ELF data | 836 | 836 |
| ELF bss | 346028 | 347564 |
| ITCM used /16384 | 15336 | 15336 |
| DTCM used /131072 | 107392 | 108928 |
| RAM used /393216 | 276476 | 276476 |

Additional DTCM1536 bytes =1024 expanded rings +512 scratch. Smaller flash here
is an observed compiler/layout result, not a performance claim. Inspected linked
`soundengine_calcNextSampleBlock`: two128-iteration loops, each `ldrh`, sample
`strh`, zero `strh`, advancing source2/destination4 bytes; half offset512 bytes.
No float conversion, native int32 reinterpretation or pack helper call. Both loops
precede PRIMASK/generation acknowledgement. No cycle measurements were made.

Full native suites OFF and ON:49/49 each passed. ARM normal/experiment builds,
FM codegen checks and image-integrity verification passed for both. Extended
production extracted-source scheduling tests use ASan/UBSan and fake HAL: signed
extrema, L/R order, guards, both packed halves and both DAC destinations, callback
selection, Size256, full recovery clear/retry/fault paths, nested timer ownership,
and newer-generation injection at the post-pack/pre-ack seam. Source guards cover
initial output order/lengths, circular halfword DMA and HAL size doubling.
Firmware CRLF and whitespace checks passed.

Physical converter acceptance, scope confirmation of clocks/word alignment, channel
routing/listening, recovery on real DMA faults, and worst-case render-plus-pack
latency remain **unverified hardware gaps**. No improved precision or audible
quality is claimed. No card writes, installation, branch or commit were performed.

## Bounded main-output precision stage

`LXR_MAIN_OUTPUT_24BIT` defaults OFF and configuration rejects ON without
`LXR_AUDIO_24BIT`. Enable both in a separate ARM build (as above, adding
`-DLXR_MAIN_OUTPUT_24BIT=ON`); use the same two switches for host tests.

In this mode only, mixer skips its final main post-process call. Soundengine
runs that same HP -> LP -> compressor chain once on the int16 main scratch,
writing its float result directly into SPI2/main DMA as signed24, MS halfword
first. SPI3/OUT2 still uses `[int16,0]`. There is no additional block buffer,
second filter evaluation, limiter, dither, changed control, compressor law or
input scale. The original post-chain saturation remains **+32767/-32768 input
units**, mapping to +8388352/-8388608 codes (positive full scale intentionally
remains 255 codes below signed24 maximum). The encoder also explicitly bounds
signed24 before truncation toward zero. A halfword pair is `[code>>8,
(code&255)<<8]`, not a native int32 memory cast.

Recovered precision is **only fractional output generated by the main float
post-processing**, including tails and fractional compressor gain. Voices,
mixer accumulation, FX inputs/returns and the scratch input remain int16;
lost upstream information is not recovered. Settled HP/LP and compressor bypass
is exact int16 x256 padding, hence no extra precision then. Independent-stage
bypass and wet/parameter ramps retain their existing state and ordering.

### Precision-stage verification (uncommitted atop 38cf955)

AppleClang17 ASan/UBSan full suites: normal and both-options ON **50/50 each**.
The new production-TU test covers encoder signs, fractional values, signed24
bounds, halfword order/guards, settled bypass, real LP sub16-LSB tails, stereo
sign symmetry, resonant positive/negative saturation, compressor gain/output
and its return to exact bypass. Existing production mixer/FX routing tests
exercise all routes with the legacy output API; scheduling tests in ON mode
exercise both physical destinations/halves and post-pack acknowledgement with
a substituted DSP seam. These are complementary tests, not a full hardware or
whole-engine precision simulation.

ARM GCC14.3.1 Release builds, FM codegen and image verification passed for
normal, padded-only and precision modes. Normal and padded-only BINs compare
byte-identical to their pre-stage binaries (hashes above). Precision image:
`75d144d8718003e98ac2d841e1f6b688f2f4c042860d6f7f21f3065ad68f5c3d`.
Payload295848, text295004, data836, bss347564 bytes. Static placement:
ITCM15320/16384, DTCM108928/131072, RAM276476/393216. Relative to padded-only:
+40 text/payload bytes, unchanged data/bss/DTCM/RAM, ITCM -16 bytes from layout.
No additional scratch or per-block float array.

Inspected linked ARM `soundengine_calcNextSampleBlock`: one int16 pack loop
for OUT2, one `MainDjFilter_process24` call for main before generation ack;
mixer has no post-process call in this mode. Inspected post-chain encoding:
float bounds then multiply by256, `vcvt.s32.f32`, `sbfx #8,#16` and `lsls #8`,
two halfword stores per channel. There is no intervening int16 conversion;
the encoder's redundant bounds are optimized under the retained musical bounds.
These are static codegen observations, **not measured cycles or timing savings**.

Real converter alignment/acceptance, clock/routing scope checks, listening,
worst-case render deadlines, stack margin and real DMA recovery remain hardware
gaps. No card writes, installation, commits or branches were performed.

# Full active float32 audio experiment

> **Historical experiment evidence.** The variant options and commands below
> describe earlier source only and are no longer supported build modes.
> This branch now always uses full float32 audio, 24-bit output on both pairs,
> and per-operation mix clipping. Original int16 tables, uint32 phases and
> deliberate nonlinear effects remain. See [BUILD](BUILD.md) for current commands.

## Historical record (unchanged below)

Default **OFF**. `LXR_AUDIO_FLOAT32=ON` requires `LXR_AUDIO_24BIT=ON` and
selects the float main-output path automatically. `LXR_MAIN_OUTPUT_24BIT` may
remain OFF in the cache: the full experiment defines its implementation on.
The normal, transport-only and main-output-only configurations remain separate.
This is an uncommitted experiment atop `38cf955e85f058917ee24b14e4f18cbd09e60581`,
not an installed or hardware-accepted release.

For the separate default-off hard-clipped mix preference comparison, see
[AUDIO-FLOAT32-CLIP](AUDIO-FLOAT32-CLIP.md). The evidence below describes the
original **unclipped** configuration.

## Build and check

With Arm GNU 14.3.rel1 on PATH, from the application root:

```sh
cmake -S . -B build/float32 -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi.cmake \
  -DCMAKE_BUILD_TYPE=Release -DLXR_AUDIO_24BIT=ON -DLXR_AUDIO_FLOAT32=ON
cmake --build build/float32 --parallel 4
python3 tests/check_fm_arm_codegen.py build/float32
python3 tests/check_audio_float32_arm.py build/float32
python3 cmake/tools/verify_release.py build/float32

CC=clang cmake -S . -B build/host-float32 -G Ninja \
  -DLXR_HOST_TESTS=ON -DLXR_AUDIO_24BIT=ON -DLXR_AUDIO_FLOAT32=ON
cmake --build build/host-float32 --parallel 4
ctest --test-dir build/host-float32 --output-on-failure
```

An enabled full experiment without 24-bit transport fails configuration.
No card copy, installation, commit or branch creation is part of these commands.

## Signal path and deliberate boundaries

Audio retains the existing signed16-full-scale **units**, not normalized ±1 units.
`AudioSample` is float in this experiment and int16 otherwise. `AudioReal` selects
float recurrence/gain state instead of the legacy double state where applicable.

- Original sine/wavetable storage remains int16. Interpolation, oscillator outputs,
  FM modulation buffers, transient output, six voice sample buffers, sample-valued
  oscillator state and decimator holds retain fractional values.
- Voice filters, envelopes, drive, panning and routing feed float mix/FX sums.
  Packed QADD16 accumulation and pan casts are absent from the experimental path.
  Mono routing still bypasses panning; jack fallback and physical output ordering
  remain unchanged.
- FX OFF, tube/fold/RAT distortion, ring modulation, FX compressor and both delay
  modes accept and return float audio. Destination addition and dry/wet
  interpolation no longer saturate. FX wet amount still clamps to 100 at ingress,
  without rescaling or audio-loop validation.
- Main stereo HP → LP → compressor receives float, including over-full-scale sums.
  OUT2 and main stereo encode directly to signed24 only after their respective
  chains. The final encoder bounds to −8388608…8388607 and truncates toward zero;
  +32767.75 input units therefore survives (unlike the prior main-only experiment).
- Deliberate voice filter/PWM saturation, snare source clip **before** envelope /
  velocity / volume / fader, snare exceptional output bound, drive curves, FX wet
  source saturation and delay feedback saturation remain. No limiter or per-sample
  validity framework was added. Main compressor makeup remains
  `R - 4R/(R + 12)` dB.
- Ring gain remains `/65536`, including the historical mono destination-in-wet
  behaviour. Tube mono/stereo drive differences and its overload fractional
  remainder remain. RAT's clamped +1 diode lookup now uses the last table entry
  rather than reading entry 257, **only in the experiment**. Production-path ASan /
  UBSan testing reproduced that endpoint read before the experimental correction.

### Quantization deliberately retained

No tables were regenerated or changed. Synthesis tables retain their original
int16 storage; transient ROM remains its original int8 storage; existing FX lookup
tables retain their original float/double storage (converted to float for active
arithmetic). Table indices, uint32 modulo phase accumulators, phase increments and
parameter/MIDI widths remain integer. Noise deliberately interprets the RNG's low
signed16 word before float scaling. Sample-and-hold decimation still quantizes
**time**, not amplitude. Output is necessarily signed24. Disabled reverb and its
half-float implementation are not part of the active path; the experiment does
not enable it. No new bitcrusher or parameter-resolution change was introduced.

FM still uses the existing target float-to-uint32 conversion and fixed phase
shifts. Negative float-to-unsigned C is not portable: target codegen, not a native
negative-conversion test, is the evidence. No modulation redesign or negative
clamp was added. The unchanged transient signed shift also retains its previously
identified host-language limitation; positive ROM sample fixtures isolate the new
fractional transient path without suppressing that sanitizer limitation.

## Delay history and placement

Capacity remains **32768 samples**, with unchanged normal/ping-pong indices,
time ranges, crossfades, feedback laws and sample rate. A contiguous 128 KiB float
history in ordinary RAM overflowed the current layout by 14332 bytes. Instead,
`FxRamBuffer` owns a logical history split into **8192 floats / 32 KiB DTCM** and
**24576 floats / 96 KiB ordinary RAM**. The accessor selects the bank by index;
there is no allocation, capacity reduction or relocation of project/UI data.
This adds bank-selection work to delay access; no timing improvement is claimed.

Clocks and block size are unchanged from [the transport experiment](AUDIO-24BIT.md):
64 frames/half, calculated 44140.625 Hz with the configured oscillator.

## Verification of this working tree

Reference ARM GCC14.3.1 Release O3/fast-math; native AppleClang17 with ASan/UBSan.

- Normal host configuration: **51/51 passed**. Full-float host configuration:
  **51/51 passed**. Both run all legacy regressions plus a production float target.
  Legacy C targets explicitly retain the legacy precision selection; scheduling
  fixtures use the selected transport/full-float path.
- `test_audio_float32.c` exercises actual oscillator/tables, transient, SVF, all six
  voice block paths, snare clip placement/signs, mixer routes/pan/overload/fallback,
  fractional decimator holds, FX OFF and every enabled algorithm, delay split
  boundary/capacity, fractional history reads, gain laws and final float main
  filter/compressor/encoding. RNG, faders, GPIO and control-rate modulation/LFO/
  voice-async calls are host substitutes. Existing ingress tests cover FX wet
  clamping across controls.
- Handoff strengthening: normal and ping-pong delay run for longer than their
  complete logical rings in 64-frame production calls, mono/stereo, against a
  scalar history oracle. Every history entry and output is checked after each
  block, including split-bank/wrap interpolation, signed feedback bounds and
  wet/destination accumulation. Distinct-tap crossfade weights, completion,
  fractional-tap adoption, last-wins pending request and subsequent real 10ms
  fade completion are covered. Tone is unity in these history fixtures.
- Distortion wet numerical checks cover tube negative fractions and both overload
  signs (including unclipped fractional remainder), fold excursions, and both RAT
  diode endpoints through the actual processing chain, mono/stereo. These are
  focused numerical fixtures, not exhaustive parameter/state trajectories.
- Complete production mixer dispatch now runs six voice audio paths, held
  fractional decimator values and all routes (FX OFF for the FX bus). The actual
  renderer body is extracted at configure time from `Soundengine.c`, calling that
  mixer, real main DSP and both output encoders. Both DMA halves, untouched other
  half and consumed/no-request behavior are checked. Held samples isolate exact
  routing expectations; this does not test the real async/control-rate lifecycle.
- After these test-only changes, the full float ASan/UBSan suite passed **51/51**;
  a clean-first ARM float rebuild and final-ELF FM/float-codegen/image verification
  passed. Payload/image hash below is unchanged. No production DSP was edited.
- Normal, transport-only, main-output-only and full-float ARM builds passed.
  FM codegen checks passed for all four. In the float PWM function the one
  downstream min/max waveform bound replaces QSUB16; the checker separately
  verifies that FM multiply is directly followed by `vcvt.u32.f32` with no input
  clamp. The other two FM functions contain no float max instruction.
- `check_audio_float32_arm.py` passed on the final ELF: examined oscillator,
  mixer, FX bus and all enabled FX process functions use float32 arithmetic,
  without packed integer saturation or float64 arithmetic. Original double FX
  lookup loads/conversions are allowed; phase/index conversions remain intentional.
- Image verification passed for all four configurations. Existing firmware CRLF
  and `git -c core.whitespace=cr-at-eol diff --check` passed.

### Compatibility hashes

Normal BIN equals a fresh isolated `git archive HEAD` build. Prior option BINs
match their pre-experiment artifacts byte for byte:

| Configuration | BIN SHA256 |
|---|---|
| Normal | `917129b377c33b1da81869d1ea2451dcdb06ebffc3b4a5f9cd0e7989fb19080f` |
| Transport-only | `3136b8f9622850863762c598e376f6b1b862aa750cbaeb7dccc227c68005806e` |
| Main-output-only | `de7f20163333c2aef484d0af58810817fa6dc409a6a88a86233c0a4f9294d6ae` |
| Full float | `c111370cb958f2f48810ecc124e4f97eed9c27eadbe38439ebe140bceaaa9d3b` |

Full-float image: **294384 payload bytes**, SHA256
`7a3932e0eb3030c2bd2d3390e9f95bd6910a4fc27da8c4c6390dd2b2015af7e4`.

### Static memory and stack review

Final linked placement (not runtime high-water measurements):

| Region | Normal bytes | Full-float bytes | Full-float remaining |
|---|---:|---:|---:|
| ITCM | 15336 | 14936 | 1448 |
| DTCM | 107392 | 76392 | 54680 |
| Ordinary RAM, including 512-byte heap reservation | 276476 | 374780 | 18436 |

Stack remains based at the DTCM end; no transport scratch is on the audio stack.
Recompiled the actual compile-command entries with `-fstack-usage`, unchanged
reference flags, into a separate temporary output directory. Selected fixed
frame reports, normal → float bytes:

- renderer 16 → 32; mixer 448 → 824;
- drum 72 → 56, snare 64 → 64, hat/cymbal 48 → 40;
- FX compressor 104 → 88, ring 40 → 48, distortion 152 → 88;
- normal delay 72 → 72, ping-pong 80 → 80, main filter 72 → 72.

The voice/FX entries marked dynamic by GCC also allocate runtime-sized buffers:
64-frame float drum/ring scratch adds 256 bytes; snare/hat/cymbal and the FX
compressor add 512 bytes. These callees execute sequentially, not all at once.
The examined instrument-C mixer/callee chains are approximately 1.5 KiB before
library, caller and interrupt context. This is **not** a whole-program stack bound.
Static free DTCM is substantially larger, but neither that nor instruction counts
certify nested-interrupt stack margin or worst-case audio deadlines.

## Remaining acceptance

Hardware listening, dense-playback/FX deadline measurements, delay bank-access
cost, actual stack high-water, 24-bit codec interoperability and analogue noise /
headroom remain unverified. Removed incidental saturation intentionally changes
hot mixes and modulation inputs; this is not a claim of bit-identical sound in
the enabled experiment. Storage, persistence and musical workflow were not edited.
No commits, new branches, card writes or installation were performed.

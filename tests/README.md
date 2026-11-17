# Host unit tests

The registered suite mixes native C tests and Python-driven extracted-source harnesses using
your computer's C compiler (Clang or GCC). It needs no LXR, debug probe or Arm toolchain.
Sanitizer flags and host models vary by harness; passing tests do not certify target behavior.

## Running

From the repository root:

```sh
cmake --preset host-tests
cmake --build --preset host-tests
ctest --preset host-tests
```

You need CMake, Ninja, Python 3 and a C compiler: on macOS the Xcode Command Line Tools, on Linux e.g.
`sudo apt install build-essential`. MSVC isn't supported; on Windows use WSL or MSYS2.
`-DLXR_TEST_SANITIZERS=OFF` controls CMake-native targets only; some Python harnesses
hardcode sanitizer flags and still require a compatible compiler. Separate FM target-codegen
verification (`check_fm_arm_codegen.py`) requires a release ELF and Arm objdump; it is not
a requirement for the registered host suite.

The tests are a separate CMake project (see `LXR_HOST_TESTS` in the top-level
`CMakeLists.txt`), so they don't change the firmware build. They are built in `build/host-tests/`.
This integration runs the tests locally; the upstream GitHub Actions workflow was not imported.
See [INTEGRATION.md](INTEGRATION.md) for attribution, scope and the hardware checklist.

## How it works

| Folder / file | Contents |
|---|---|
| `shim/` | Stand-ins for `stm32f7xx_hal.h` and `stm32f7xx.h`: integer types, CMSIS intrinsics (`__CLZ`, `__SSAT`, `__QADD16`, ...) in portable C, and opaque HAL handle types. It comes first on the include path, so the firmware headers are used unchanged. |
| `framework/lxr_test.h` | `CHECK`, `CHECK_EQ`, `CHECK_MEM_EQ`, `RUN_TEST`, `TEST_REPORT`. A failed check prints the file, line and both values, then the test carries on. |
| `test_*.c` | Native test programs. |
| `test_*.py` | Extracted-source harnesses with individual stubs, models and compiler flags. |
| `CMakeLists.txt` | `lxr_add_host_test()` builds a test program from its test file and the firmware files it tests, and registers it with CTest. |

CMake-native test targets define `LXR_HOST_TEST`; individual Python harnesses
select their own definitions and stubs. This macro omits target-only section
attributes and, in the master DSP modules, CMSIS includes and interrupt-mask
transactions. Host passes therefore do not verify target interrupt synchronization
or scheduling; those require separate target verification.

## Adding a test

1. Write `tests/test_<name>.c` with `static void test_...(void)` functions and a `main()` that
   calls `RUN_TEST()` for each and returns `TEST_REPORT()`.
2. Add it to `tests/CMakeLists.txt`:

   ```cmake
   lxr_add_host_test(test_<name>
       SOURCES test_<name>.c
       FIRMWARE_SOURCES Core/Src/<file under test>.c
   )
   ```

3. If the linker reports missing functions or variables, the firmware file calls into code that
   isn't part of the test. Define them in the test file as simple stubs that record what was
   called. If the compiler reports a missing HAL type or intrinsic, add it to `shim/`.

Keep the firmware files themselves unchanged for testing. If a file is hard to test because it
mixes logic with hardware access, the better fix is to move the logic into its own function or
file, so that the firmware and the test share it.

### Real FatFs cleanup regression

`test_cleanup_fatfs.py` builds the bundled `ff.c` and production configuration
against a disposable 64 MiB RAM FAT32 disk. Only HAL header dependencies and
LP64 host integer widths are adapted. It exercises 194 populated files across
sector/cluster boundaries, single-slot directory locking, nested cleanup,
remount, surviving file contents and recovered free-cluster count. A disk-read
budget rejects the previous restart-per-file implementation. To reproduce that
intentional failure: `LXR_BASE_REV=50b74f2 python3 tests/test_cleanup_fatfs.py`.
Disk-operation counts are not SD latency measurements. Existing fake-filesystem
failure tests include nested cleanup; their failed-close model releases the
handle, unlike some possible actual FatFs failures.

## Slip-loop regression coverage

`test_slip_core` compiles the actual slip core, shift/flam helpers, scheduling
body, main-step writer and armed note writer at O0/O3 with ASan/UBSan. It covers
an extracted `afde83f` disabled-slip differential (38,880 pulses per optimization),
production automation-source fetch with stubbed endpoints, exact FIFO handover/
release event traces, FIFO, short-track aliases, prepress gates, live mutation/erase, phase-preserving
switches and all four windows × seven unequal tracks × 15 shifts × six flams.
`test_panel_navigation` now pairs the real panel dispatcher with the real slip core
for plain/modifier presses, owned releases, stopped no-op and mode cancellation.
`test_external_clock` pairs real clock/transport bodies with the slip core (step
and audio endpoints remain adapters). `test_perf_reload` checks cancellation
callbacks on actual activation/reload, not queued selection. `test_slip_led`
executes real owner-overlay/chase bodies with fake output bytes.

These are extracted-source tests, not a whole-device scheduler. No physical scan,
DIN/USB interoperability, worst-case cycles, runtime stack or listening claim.

The slip differential test uses `fixtures/slip_baseline_afde83f.c`, an extracted,
frozen pre-slip implementation with full source revision attribution. It does not
require Git history, so shallow CI checkouts and source archives run the same
comparison. Do not refresh this oracle merely to match changed production code.

## Empty-pattern occupancy regression

`test_pattern_occupancy` compiles extracted production mutation/backup bodies
with the real pattern/step layout and the whole Euclidean generator translation
unit. Activation and RAM-kit bodies exercise stopped/queued switching, all kit
modes (including one-shot skip), same-slot reloads, non-identity kit links and
empty/silent-used/imported-hit destinations. Empty/used whole copy and Save As
retain source links; full-field retention remains covered by `test_perf_reload`. Project
codec/runtime tests below now own persistence coverage; obsolete file/tmp format
and legacy fallback tests were removed with those runtime paths.
`test_slip_core` also checks occupancy through the production recording writer;
existing retention/save-as and kit-only Reload regressions remain enabled with
explicit used-slot fixtures. These tests do not certify SD interruption recovery,
physical restart, concurrent storage/edit timing, worst-case cycles or listening.

`test_panel_navigation` also executes production occupancy-query, selection-painter
and blink-handler bodies for all four banks, silent-used and first-hit slots,
empty current/queued markers, their 2:1 blink cadence, bank redraw, activation
handover and exit to normal step/chase. LED output and blink registration are
host seams; physical readability and clock cadence still need instrument review.

## Single-file project integration

`test_project_codec` links production codec/stream with memory-backed FatFs and
covers full-project round-trip, explicit wire bytes, malformed headers, length
rejection, truncation and I/O errors. `test_project_persistence` and `test_project_save` invoke
`test_project_runtime.py persistence` and `test_project_runtime.py save` directly, exercising
production project API bodies linked with the real staged SafeStorage, stream
and codec. Covers RAM-only saves, full RAM/current-edit capture, coherent compressor
publication, name browsing, boot selection/defaults, read errors, per-call injected
filesystem failures, short writes, live shuffle dispatch/save without pad-save,
and retained failed closes retried before staging cleanup. The fake distinguishes
missing parent/leaf errors and models open-file unlink and single directory-lock
exclusion. Engine/UI/timer and
filesystem endpoints remain substitutes, not hardware certification.

`test_project_callsites` guards boot/control dispatch and absence of tmp/autosave,
slot I/O and automatic transport-stop calls; it executes the literal song RAM
Save-As and interactive project-load branches (missing file/path versus other
errors). Existing audio, MIDI, Reload and pattern-selection tests now expect
no dirty-timer or slot-file calls, rather than retaining obsolete persistence.
See [runtime format and limits](../docs/PROJECT-STORAGE.md).

## Retired project measurement diagnostic

ProjectMeasure and its two measurement-only tests have been removed. Historical
coverage and evidence remain in [PROJECT-MEASUREMENT](../docs/PROJECT-MEASUREMENT.md);
that diagnostic is no longer a build option or part of this suite.

## Production float32 audio

All audio tests compile the sole production path: normalized float32 samples and delay
history, padded 24-bit output on both stereo pairs, per-operation mix clipping.
Original int16 tables and uint32 phases remain. Scheduling tests use the same
DMA geometry. Hardware/RNG/fader endpoints remain substitutes.
Run both `check_fm_arm_codegen.py` and `check_audio_float32_arm.py` against a
fresh ARM release; these are instruction checks, not hardware timing tests.

### Float handoff coverage

`test_audio_float32` checks multi-block normal/ping-pong delay against a scalar
history oracle beyond full-ring wrap (both banks), feedback bounds, wet output,
crossfade/pending transitions, and numerical tube/fold/RAT wet fixtures. It also
runs complete production mixer routing and an automatically extracted production
renderer body through the real main DSP and both encoders, checking both DMA
halves. Control-rate async/modulation/LFO calls, GPIO, RNG, faders and IRQ state
are substitutes; held fractional decimator samples make routing deterministic.
This does not establish hardware timing or real control-rate integration. See
[historical float investigation](../docs/AUDIO-FLOAT32.md) for context and gaps.

### Per-operation mix clipping

`test_float_mix_clip` shares production float sources and integration wiring
with `test_audio_float32`; neither changes compile-time audio behavior. The
first focuses on per-add overload/cancellation, wet-delta and destination bounds
across routes and effects; the second checks numerical history, voices, routing
and both output encoders. Filter/compressor tests decode the real packed output
without an alternate int16 API. See the historical
[operation audit](../docs/AUDIO-FLOAT32-CLIP.md) for clipping placement.

### Normalized audio differential

`test_audio_normalized.py` compiles `audio_normalized_probe.c` against production
sources at O1 and O3/fast-math with ASan/UBSan/float-cast-overflow. Frozen normalized
observations in `fixtures/audio_baseline_20e6e6b.txt.gz` came from the unchanged
20e6e6b tree using AppleClang 17, not from the normalized implementation. The same
probe runs against either tree; `--source ROOT --scale 1.f --record FILE.gz` is an
explicit baseline capture, not part of normal testing. Ordinary runs need no Git
history. Do not refresh the fixture to accommodate regressions.

The probe covers six voice paths, positive FM quantization, nonlinear voice/FX
processing, normal/ping-pong delay, every route and both output encoders. Negative
FM remains the explicitly labeled model in `test_wavetable_wrap.py` plus actual
ARM instruction checks. The integration test also checks both renderer DMA halves
and signed transient reads. See [AUDIO-NORMALIZED](../docs/AUDIO-NORMALIZED.md) for
measured differences, source/build identities and hardware gaps.

## Save Kit assignment

`test_save_kit.py` executes the production menu Save Kit/Save Morph branches and
RAM kit saver with modeled UI/IRQ endpoints. It covers every active pattern,
new/same kit slots, unrelated pattern links, unchanged morph assignment and
shared-saver semantics, both edit-buffer configurations, and saved PRIMASK
restoration. It does not model interrupt scheduling or device playback.
`test_project_codec` round-trips a non-identity pattern/kit link through the actual
project codec using memory-backed I/O; real SD/restart behavior remains a hardware check.

## Screensaver wake regression

`test_screensaver_wake.py` compiles the actual screensaver source and extracted
LCD nonblocking functions, menu sender, repaint request and UI handoff, using
production LCD constants. Its companion C scenarios sweep all four reachable
animation wait states over 0–500 ms remaining, drain every clear/command/data
phase (both LCD rows), check audio servicing, inactive/repeated touches, deferred
cache invalidation and completed redraw, including an already-pending menu flush.
The deadline assertion fails on the pre-fix source. Run directly with
`CC=clang python3 tests/test_screensaver_wake.py` or through CTest; no private
fixtures, historical Git objects or investigation-directory files are required.

GPIO, time, audio processing and page painting are host substitutes. The sender
poll advances simulated time; the measured bounds are deterministic model checks,
not device latency measurements. This does not verify OLED electrical timing,
real interrupt interleaving, audible continuity or time until visible repaint.
Unused plasma/state11 behavior and tick wrap are outside this regression's scope.

## Panel navigation and release tooling

`test_panel_navigation.py` covers live pattern selection, occupancy LEDs, slip
controls, Last Step, Config and load/save dialog exits. Config pads must not
change track lengths; Last Step retains track/all length editing. Held shortcut
releases cannot become step edits after dialog exits. Production category/reset
and eight-character name conversion helpers cover reentry, unsupported characters,
confirmation and cancellation. Named scenarios share engine/storage/LCD seams;
they do not certify physical-panel behavior or real-time performance.

`test_release_metadata.py` checks CMake metadata consumption, exact image selection
without stale-image fallback, missing/malformed metadata, invalid paths, payload
mismatches and CI output generation. It does not execute the hosted publishing job.

The frozen audio fixture is a **normalization regression reference**: it checks
that numerical-unit changes preserve the earlier float engine's intended results.
It is not support for old firmware or project files. Deliberate sound changes need
reviewed expectation changes, not automatic fixture regeneration.

# Retired project save/load wall-time diagnostic

**Retired:** ProjectMeasure, its build option and measurement-only tests were
removed at user request. Everything below records historical implementation and
evidence, not current behavior or supported build instructions. Use [BUILD](BUILD.md)
for current commands.

Default **OFF** (`LXR_PROJECT_MEASUREMENT`). No screen or USB diagnostic output.
This instruments the existing project entry points, not a new loader/save policy.
The original operation result is returned unchanged, including the loader's partial-RAM semantics: `result=0` is not media/power-loss or
concurrent-recording certification. Save's existing cleanup warning is recorded;
load has no equivalent aggregate warning (its field is zero).

## Historical build and test (retired; do not use)

From the application root, with Arm GNU 14.3.rel1 `bin` on PATH:

```sh
cmake -S . -B build/project-measure -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DLXR_PROJECT_MEASUREMENT=ON
cmake --build build/project-measure --parallel 4
python3 tests/check_fm_arm_codegen.py build/project-measure
cmake --preset host-tests
cmake --build --preset host-tests --parallel 4
ctest --preset host-tests
```

The output is `build/project-measure/LXR_QEONDA_V0.1.img`; the version stays 0.1.
This does not authorize card writes or installation. Keep diagnostic images apart
from normal updates. The normal-release verifier deliberately rejects this flag.
For normal firmware, configure `cmake --preset release
-DLXR_PROJECT_MEASUREMENT=OFF`, build, and run the checks in [BUILD](BUILD.md).

To check diagnostic image integrity without treating it as a normal release:

```sh
python3 - <<'PY'
from pathlib import Path
import hashlib, struct
p = Path('build/project-measure')
d = (p/'LXR_QEONDA_V0.1.img').read_bytes()
b = (p/'LXR_V2_STM32F765.bin').read_bytes()
magic, size, checksum = struct.unpack('<8sIB3x', d[:16])
assert magic == b'LXRV2IMG' and size == len(b) and size % 4 == 0
assert d[16:] == b and (sum(b) + checksum) & 255 == 255
print(size, hashlib.sha256(d).hexdigest())
PY
```

## Report and interpretation

After each operation, append a block to **`/projtime.txt`**, an absolute SD path.
No filesystem work is added inside the measured operation except the original
calls. An independent static `FIL` opens with OPEN_ALWAYS, seeks to EOF, writes,
and closes only after the operation returns and tracked storage handles are
closed. It does not change the current directory. There is no report recursion.
The background-audio begin/end pair surrounds **all report I/O**, preserving an
already-running timer. No transport stop or new interrupt-masked section is added.
Report failure never changes the original result, retries the operation, or
changes its recovery behavior. A failed report close retains its own FIL and
suppresses later reports rather than reusing it.

The first line records:

- `op`, zero-based project slot, original FatFs numeric `result`, save cleanup
  `warning`, sequencer running state at entry/exit (`play`), and the retained load API argument `clearTmp` (now informational; no tmp behavior).
- `wall_ms`: entry to reporting boundary, including display waits, RAM work,
  interrupts/audio, filesystem waits and instrumentation overhead. The tiny
  report-audio setup is included; report formatting/open/seek/write/close is not.
- `file_ms`: sum of the 13 instrumented FatFs API durations; subsequent lines give
  each API's call count and summed milliseconds. Includes directory/metadata calls,
  not only reads/writes. Calls are wrapped in presetManager, SafeStorage and
  ProjectStream (and retained SlotFiles helper instrumentation); FatFs internal calls are not wrapped, so no recursive double count.
- `other_ms = wall_ms - file_ms`: residual **wall time**, NOT foreground CPU time.
  Audio/interrupt work can occur in either bucket. Call-wrapper bookkeeping is
  mostly in the residual; tick reads/interrupt placement can affect attribution.
- `phase_ms=preparation/body/finalization`: disjoint lifecycle wall intervals,
  **overlapping** the file/residual breakdown, not additional time to add to it.
  Save preparation includes RAM capture, display, recovery and staging-directory
  setup; body is the staged writer callback; finalization includes promotion,
  old-directory cleanup and the saved-selection index write. Load preparation
  covers control reset/recovery; body runs through the single project read;
  finalization starts before kit normalization and compressor/global/kit activation.
  Early returns retain the phase reached; no attempt is made to repair their
  lifecycle. Tick-boundary rounding can make phase sums differ slightly from total.
- `read_bytes`/`write_bytes`: actual transferred bytes from operation calls (not
  requested bytes, disk sectors, metadata traffic or report bytes). `errors` counts
  non-OK FatFs returns, including expected missing-file probes, not just fatal errors.

## Safety boundaries and measurement limits

- Foreground-only, non-reentrant; no per-sample instrumentation or heap allocation.
  HAL's 32-bit millisecond tick and unsigned subtraction handle wrap and operations
  longer than a CPU cycle-counter wrap. Each interval/operation must be shorter
  than 2^32 ms (~49.7 days). Counts/byte totals are uint32, wrapping at 2^32.
  The tick must keep advancing: interrupt masking/priority starvation can undercount.
  Sub-ms calls may individually read zero; totals are not precise CPU measurements.
- Eight static ownership slots track successful FIL/DIR opens even outside a timed
  operation, removing them only after successful close. A retained handle suppresses
  reporting. Tracking overflow or failed findfirst (which may leave an opened DIR)
  conservatively suppresses reports until reboot. Explicit unmount does not reset
  diagnostic ownership; reporting can remain suppressed afterward. No loader,
  unmount or failed-close lifecycle redesign was introduced to recover diagnostics.
- Report failure can leave a partial block; missing reports do not imply missing
  operations. There is no report status UI, retry, timeout, truncation or rotation.
  The log grows; report traffic affects the next operation's media/cache state.
  Persistent SD BUSY can still wait indefinitely under existing policy.
- Report I/O preserves background audio but blocks foreground interaction while it
  runs. Added tick reads, call accounting and ownership tracking perturb timing;
  overhead and audio deadlines have **not** been measured on hardware. RAM/static
  fit and host tests do not establish stack margin, real media behavior or sound.

## Historical measurement-only verification (before storage integration)

The figures below predate runtime migration; use [PROJECT-STORAGE](PROJECT-STORAGE.md#final-integration-build-evidence)
for current integrated build/test identities.

Working tree based on development `01fefe977069143473e2fb899a6e7b7e7e0b3b92`,
Arm GCC 14.3.1, Release. No commit, branch, installation or card write.

- Host suite: **48/48 passed**. Complete production measurement C with clock/FatFs
  substitutes covers tick wrap plus a 70-second read, phase/residual accounting,
  bytes, no report recursion, pre-existing and failed-close FIL/DIR ownership,
  unsafe lifecycle suppression, report-open/short-write/close failures and failed
  findfirst suppression. Extracted production entry wrappers check return-value
  preservation and report-audio lifetime over running/stopped and unsafe contexts.
  Existing source-extraction tests now select the original operation bodies.
- Default-off BIN exactly matched a pre-edit build (`cmp`), SHA256
  `50316ea5fc550ed5de1a132df4cb8724f0034376455e571e7af7f99e6864b5f6`.
  Normal image payload 311848 bytes; image SHA256
  `ea670dee8044ca2ae2f3f4bedb4d4cdff0c67a7f39bb75c66c717432e69af30c`.
- Diagnostic payload 314640 bytes; BIN SHA256
  `e9d02fbaad8ee3276df83da05f8a8d23215ce27f4145d38a2ae91e057d61e9d2`;
  image SHA256
  `618ca233f2ba8f86041e94ee0dcc468d4f1d26facbe753ce88537f22aec6e872`.
  Header/alignment/checksum/payload comparison passed. Both builds passed FM ARM
  codegen checks; normal release verification passed and rejected the diagnostic.
- Diagnostic placement: ITCM 15352/16384, DTCM 107392/131072,
  RAM 273404/393216 bytes; RAM increase 1016 bytes. Instrumentation static objects
  total 1016 bytes (including the 560-byte independent FIL and 256-byte line).
  Flash-region increase 2792 bytes. No hardware timing, real SD reports, playback
  listening or MIDI/storage interoperability was tested.

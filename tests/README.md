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
`test_pattern_select` now pairs the real panel dispatcher with the real slip core
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

`test_pattern_occupancy` compiles extracted production mutation/backup and file/tmp
codec bodies with the real pattern/step layout and the whole Euclidean generator
translation unit. Memory-backed file seams cover empty/used/silent-used round trips,
legacy missing-tail fallback, required/invalid tags, read errors, and RAM-reset tmp
recovery. Actual activation and RAM-kit bodies exercise stopped/queued switching,
all kit modes, unchanged unsaved sounds and ordinary silent-used kit loading.
`test_slip_core` also checks occupancy through the production recording writer;
existing retention/save-as and kit-only Reload regressions remain enabled with
explicit used-slot fixtures. These tests do not certify SD interruption recovery,
physical restart, concurrent storage/edit timing, worst-case cycles or listening.

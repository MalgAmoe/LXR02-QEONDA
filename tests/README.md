# Host unit tests

These tests compile firmware source files with your computer's own C compiler (Clang or GCC)
and run them on the computer, so they need no LXR, debug probe or Arm toolchain. They use
AddressSanitizer and UndefinedBehaviorSanitizer, so an out-of-bounds access or undefined
behaviour in the code under test also fails the test.

## Running

From the repository root:

```sh
cmake --preset host-tests
cmake --build --preset host-tests
ctest --preset host-tests
```

You need CMake, Ninja and a C compiler: on macOS the Xcode Command Line Tools, on Linux e.g.
`sudo apt install build-essential`. MSVC isn't supported; on Windows use WSL or MSYS2.
Set `-DLXR_TEST_SANITIZERS=OFF` when configuring if your compiler has no sanitizers.

The tests are a separate CMake project (see `LXR_HOST_TESTS` in the top-level
`CMakeLists.txt`), so they don't change the firmware build. They are built in `build/host-tests/`.
This integration runs the tests locally; the upstream GitHub Actions workflow was not imported.
See [INTEGRATION.md](INTEGRATION.md) for attribution, scope and the hardware checklist.

## How it works

| Folder / file | Contents |
|---|---|
| `shim/` | Stand-ins for `stm32f7xx_hal.h` and `stm32f7xx.h`: integer types, CMSIS intrinsics (`__CLZ`, `__SSAT`, `__QADD16`, ...) in portable C, and opaque HAL handle types. It comes first on the include path, so the firmware headers are used unchanged. |
| `framework/lxr_test.h` | `CHECK`, `CHECK_EQ`, `CHECK_MEM_EQ`, `RUN_TEST`, `TEST_REPORT`. A failed check prints the file, line and both values, then the test carries on. |
| `test_*.c` | One test program each. |
| `CMakeLists.txt` | `lxr_add_host_test()` builds a test program from its test file and the firmware files it tests, and registers it with CTest. |

The compiler defines `LXR_HOST_TEST`. The firmware uses it only to leave out the
`.itcm_text`/`.dtcm` section attributes (`Core/Inc/Soundengine/config.h`, `Core/Inc/main.h`),
which don't exist on the host.

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

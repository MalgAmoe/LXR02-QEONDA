# LXR QEONDA 0.1

Custom firmware for the LXR V2 desktop drum machine (STM32F765 Cortex-M7): six voices,
step sequencing, FX, DIN/USB MIDI and SD-card storage, based on Erica Synths’ upstream firmware.
Version stays **0.1**; distinguish builds by Git revision and image hash.

## Features

- Held PERF step-8 break with independent manual rolls.
- Shift+Reload morph/filter reset and PERF refresh.
- Local MIX OUT order St1 → FX → St2 → L1 → R1 → L2 → R2; stored/MIDI values unchanged.
- Independent St1 master HP/LP and project master compressor with automatic makeup and ratio1 bypass.
- Shift+knob same-slot change-all across voices, with independent limits and no bulk step recording.
- Targeted synthesis, MIDI and staged-save/storage corrections.

## Build and install

Requires CMake 3.21+, Ninja, Python 3 and the Arm GNU Toolchain (`arm-none-eabi-gcc`,
including its C library) on PATH. From this repository root:

```sh
cmake --preset release
cmake --build --preset release
```

If needed, configure with `-DARM_TOOLCHAIN_DIR=/path/to/arm-none-eabi/bin`.
Copy `build/release/LXR_QEONDA_V0.1.img` to the FAT32 SD-card root; keep only one active
`LXR*.img` in the updater scan, preserving older images outside that scan. Safely eject.
With a functioning compatible desktop bootloader, hold the encoder while powering on,
wait for “LXR Updater”, then “Update OK!” and restart. Application updates do not replace
the bootloader; interrupted-update recovery is not guaranteed. Modified firmware is used
at your own risk and is not supported by Erica Synths.

## Documentation

[Host tests](tests/README.md) documents setup and limits; host passes are not hardware certification.
Detailed user, build/test and current-status guides are maintained **outside this application
repository** in the parent workspace: `analysis/USER-GUIDE.md`, `analysis/BUILD-TEST.md`,
`analysis/STATUS.md`. They are not included in a standalone clone, so these are workspace
locations, not links promised to work on GitHub. The original full README is preserved in
workspace `analysis/documentation-history/README-before-reorganization.md`.

## Acknowledgments

A massive thank you to [Erica Synths](https://www.ericasynths.lv/) for making the
[LXR desktop firmware source](https://github.com/erica-synths/lxr-desktop-app) available
and allowing the community to study, modify and build on it. This machine is even more a beast now :)

Thanks to [OpenElixir-02](https://github.com/tunefish777/openelixir-02) and contributors
for work informing investigations and fixes, particularly audio scheduling, circular DMA
and save-time audio stability. It is a separate project; this does not imply inclusion of
its complete engine or feature set.

## Licence and credits

Copyright (C) 2012-2026 Erica Synths. Firmware is GPL-3.0-only with the additional permissions
and terms in [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md). Modified firmware must be marked
as modified and not presented as official Erica Synths firmware. Distribution requires
complete corresponding source under the same licence. There is no warranty.

Erica Synths, LXR and LXR-02 names/logos are trademarks, not licensed by the GPL. Hardware
is Erica Synths’ intellectual property, not part of this repository or the GPL licence.
Third-party components retain their own licences; see NOTICE. The complete pre-reorganization
legal explanation and historical announcement remain in the workspace README snapshot;
LICENSE and NOTICE are unchanged and authoritative.

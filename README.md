# LXR QEONDA 0.1

Custom firmware for the LXR V2 desktop drum machine (STM32F765 Cortex-M7): six voices,
step sequencing, FX, DIN/USB MIDI and SD-card storage, based on Erica Synths’ upstream firmware.
Version stays **0.1** on the instrument. GitHub release tags such as `v0.1-build.12`
identify individual builds; use the release tag, Git revision and image hash to distinguish them.

## Features

- Momentary pattern mute: hold button 8 in PERF mode to mute programmed hits while keeping rolls available. Release to bring the pattern back in, still in time.
- Shift+Reload morph/filter reset and PERF refresh.
- Local MIX OUT order St1 → FX → St2 → L1 → R1 → L2 → R2; stored/MIDI values unchanged.
- Independent St1 master HP/LP and project master compressor with automatic makeup and ratio1 bypass.
- Shift+knob same-slot change-all across voices, with independent limits and no bulk step recording.
- Targeted synthesis, MIDI and staged-save/storage corrections.

## Download and install

Published firmware builds are available under [GitHub Releases](https://github.com/MalgAmoe/LXR02-QEONDA/releases).
Download **`LXR_QEONDA_V0.1.img`** and **`SHA256SUMS`** from the same release—not the
GitHub source-code ZIP. If no release has been published yet, build from source below.
You do not need to compile a published image.

Optionally verify the download from its folder:

```sh
# macOS
shasum -a 256 -c SHA256SUMS
# Linux
sha256sum -c SHA256SUMS
```

Copy the image to the FAT32 SD-card root; keep only one active `LXR*.img` in the updater
scan, preserving older images outside that scan. Safely eject. Hold the encoder while
powering on, wait for “LXR Updater”, then “Update OK!” and restart.
A functioning compatible desktop bootloader is required. Application updates do not replace
the bootloader; interrupted-update recovery is not guaranteed. Modified firmware is used
at your own risk and is not supported by Erica Synths.

## QEONDA controls

This is a supplement to the stock LXR manual. Repeated **PERF** presses cycle through
three banks; the four knobs control the following, left to right:

| Bank | Controls |
|---|---|
| A | BPM / roll speed / morph / sample-rate reduction |
| B | Shuffle / high-pass / low-pass / shared resonance |
| C | Compressor threshold / ratio / attack / release |

- **Momentary pattern mute:** hold PERF step button **8** to suppress programmed triggers.
  Manual rolls on buttons 1–7 remain available. Release, leave PERF or press Stop to cancel.
- **Master filters:** independent HP and LP act on **St1 only**, after FX. HP **0** and
  LP **127** bypass their respective filters. Resonance affects both. These are temporary
  session controls: ordinary loads retain them; startup and Shift+Reload reset them.
- **Master compressor:** acts on **St1 only**, after the filters. Threshold spans −48…0 dBFS,
  ratio 1:1…20:1, attack 0.1…100 ms and release 10…500 ms. **Ratio 1:1 bypasses compression.**
  Automatic makeup follows half the predicted reduction at 0 dBFS (up to +22.8 dB). It is not a limiter and does not guarantee no clipping.
  Settings are saved with the project, not the kit. Loading a project adopts its settings;
  older projects without compressor settings default to bypass. Kit/pattern loads and
  Shift+Reload do not reset compression. Save the project explicitly to retain edits.
- **Shift+Reload:** clears morph, resets the master filters and reloads the selected kit
  from **RAM—not from disk**. Existing pattern/kit-link behavior still applies; this is
  not a reset of every setting.
- **Shift+knob change-all:** on ordinary voice pages, changes the same knob slot across
  the seven tracks, relative to each parameter's own original kit value and limits.
  Different engines can have different functions in that slot—this is intentional.
  The gesture does not record step locks. Releasing Shift keeps the edits; use Reload
  to restore the kit.
- **MIX OUT order:** St1 → FX → St2 → L1 → R1 → L2 → R2. Stored/MIDI values and the
  FX processor's output ordering are unchanged.

## MIDI clock and storage

**USB-clock playback can be interrupted during project save/load**, because USB MIDI
consumption is delayed by storage work; queued clock bytes can be lost. For performances
that require playback through save/load, prefer internal clock or DIN MIDI clock.
The tested DIN-clock save/load session retained audio continuity and reported no new
missed-ready events or MIDI losses. This is evidence for that workload, not a guarantee
for every project or traffic pattern. Automated build/tests are not hardware certification.

## Build from source

Requires CMake 3.21+, Ninja, Python 3 and the Arm GNU Toolchain (`arm-none-eabi-gcc`,
including its C library) on PATH. From this repository root:

```sh
cmake --preset release
cmake --build --preset release
```

If needed, configure with `-DARM_TOOLCHAIN_DIR=/path/to/arm-none-eabi/bin`.
The resulting image is `build/release/LXR_QEONDA_V0.1.img`; install it using the steps above.

## Documentation

- [Detailed controls and project compatibility](docs/USER-GUIDE.md)
- [Build requirements and verification](docs/BUILD.md)

[Host tests](tests/README.md) documents setup and limits; host passes are not hardware certification.

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
Third-party components retain their own licences; see [NOTICE.md](NOTICE.md).
LICENSE and NOTICE are authoritative.

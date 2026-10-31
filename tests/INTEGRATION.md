# Host-test and MIDI bank-select integration

Imported from Justin Worrall's community branches, retaining source licence notices:

- Host infrastructure: https://github.com/jhw/lxr-desktop-app/commit/6f70b405c81345ef090ac659dd811cd3ba8af028
- CC0 fix and regression test: https://github.com/jhw/lxr-desktop-app/commit/55ec21aa26bf835928ccacd3e640c3f3394e97cc
- Original commit credits: Justin Worrall; co-authored by Claude Opus 5.5.

Local base: a43cd4fcda23ec3d577dc425261c3eb28bd5abff.
Branch: dev/host-tests-cc0. Imported existing-file changes preserve local line endings. No upstream GitHub workflow was imported; tests run locally. No DSP, bootloader or optimisation changes.

## Behaviour

CC0 values 0–63 select resident kits. Values 64–127 are ignored. The kit-loaded menu helper updates loaded-kit bookkeeping and the cached displayed name, while preserving an in-progress save destination. CC0 is excluded from step-automation recording. It deliberately does not assign the selected kit to the current pattern.

## Verification and limits

Run from the app repository:

```sh
cmake --preset host-tests
cmake --build --preset host-tests
ctest --preset host-tests
```

The front-panel test executes real frontPanelParser.c with stubbed loading/menu routines. It does not exercise menu_kitLoaded's internals or MidiParser.c's recording guard. The previous source failed 257 checks in the same harness; the imported parser passes. Host sanitizers do not establish MCU timing or concurrent behaviour.

Release build remains GCC 14.3.rel1, default -O3/ITCM settings. No device validation performed. Do not deploy until the source 1.7 versus installed/backed-up 1.71 version question and recovery compatibility are resolved.

## Device checklist (not yet performed)

Use disposable backed-up test data and the configured receiving MIDI channel:

- Select kits 0, 1 and 63 using CC0; verify sound, displayed kit/name, and subsequent load/save bookkeeping.
- Send values 64 and 127; verify sound, selected kit and names remain unchanged.
- With a kit save-name/confirmation dialog open, select another kit by CC0; confirm the destination slot is not unexpectedly moved. Verify cancellation too.
- Record with existing step automation, send CC0, and verify that automation is not overwritten.
- Check ordinary sound CCs still update and record normally.
- Verify menu-based kit loads and LFO target-voice remapping still work.
- In automatic pattern-kit mode, verify CC0 remains temporary and the next pattern loads its own kit.

No flashing, SD writes or hardware tests are part of the integration operation.

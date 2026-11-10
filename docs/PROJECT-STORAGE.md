# Single-file project storage

Runtime integration is committed as `38cf955`, included in development `8a81f1c`.
Single-file storage received hardware acceptance for beat/sound/shuffle restart
and a small save/load timing sample; this is not media-fault or power-loss certification.
Only **Save Project** writes musical work to SD. No legacy project compatibility
is provided: old multi-file directories are not imported or overlaid.

## Compatibility and protecting existing work

**This is a deliberate format break, not an automatic migration.** QEONDA reads
`/projNN/project.qpr`; there is currently no importer or converter for old
multi-file projects, nor reverse compatibility with stock/older multi-file
firmware. A legacy folder without `project.qpr` appears **Empty** in browsing;
loading it initializes default RAM rather than importing or recovering old files.

**Retain the original card/backups untouched and use a separate FAT32 card for
QEONDA. Do not use your only legacy card for saving.** SafeStorage stages the new
project in `/projNNn`, renames an existing `/projNN` to `/projNNo`, publishes the
staging directory as `/projNN`, then removes the old directory and its contents.
Thus Save Project can replace a legacy slot and delete its multi-file work; it
does not promise to leave legacy folders unchanged. This is directory replacement,
not a format-aware merge. Staging is not power-failure-proof storage.

Kit, Pattern, Song and Globals Save affect RAM only; **Save Project** is the SD
durability action. See [saving and restart](USER-GUIDE.md#saving-and-restart).

## Why change the format

The goal is faster saving during playback with fewer tiny FAT operations. One
explicit, versioned project serializes the full RAM project through a buffered,
contiguous stream instead of many small slot files. “Contiguous” here describes
the logical stream, not a guarantee of contiguous physical allocation on the card.
It uses a 4096-byte buffer rather than a second project-sized RAM image.
There is no tmp-file overlay or second persistence model: RAM edits become durable
through one explicit Save Project operation.

The compatibility break is the tradeoff for that simpler persistence model and
reduced filesystem work. An importer is not currently implemented; that does not
mean conversion is impossible, and it is not a promise of future migration support.

### Local measurements, not universal guarantees

Earlier local implementation samples measured saves at **9.325–10.889 s** and
loads at **3.249–3.310 s**, with roughly **194 files** and **19,488 write calls**
per save. The single-file implementation writes a **255,118-byte** project with
**64 write calls** (including the boot-selection index byte) and loads with
**63 read calls**. Hardware samples recorded steady playing saves of
**642 / 655 / 793 ms**, a playing load of **375 ms**, and a boot load of **327 ms**.
The first new-format save took **3568 ms**, including legacy-directory cleanup
(195 unlinks), and is excluded from the steady-save figures.

These are small local samples of the earlier and single-file implementations,
not a stock-firmware benchmark, universal speed guarantee or worst-case timing
bound. Card, project, cleanup and workload matter; diagnostic report-writing time
was excluded. They do not certify audio/MIDI continuity for every workload,
concurrent-edit snapshots, media faults or power-loss recovery. The historical
[diagnostic description](PROJECT-MEASUREMENT.md) explains the retired measurement
mechanism; the current format and limitations are documented below.

## Runtime behavior

- Kit Save commits the edited sound buffer to the selected RAM kit, selects it as
  the loaded kit and assigns it to the active pattern (other patterns unchanged).
  Save Morph does not change these assignments. Project Save persists them. Pattern Save
  keeps/copies the edited RAM pattern and refreshes its internal backup buffer. Song
  Save As copies the current song to the selected RAM slot and selects it.
- Global UI edits and Globals Save remain RAM-only. There is no `glo.cfg` read or
  write, tmp recovery, dirty timer, periodic autosave, or slot-file persistence.
- Save Project captures the current edited kit and active-pattern shuffle,
  refreshes the internal pattern backup, then writes every RAM kit/pattern/song slot, names, 30 globals and four compressor
  controls. Unselected edited RAM patterns/songs are included too.
- `/projNN/project.qpr` is the one project file. Existing SafeStorage stages it in
  `/projNNn`, checks the stream and file close, then publishes by directory rename.
  The existing old-directory recovery and cleanup-warning semantics are retained.
- After successful publication, `/proj.idx` records the last **saved** project.
  Loading another project does not change that selection. An index-write failure
  is a post-commit warning, not a claim that the project file was not saved.
- Boot checks the actual load result. Missing index selects slot 0; a missing
  project initializes default RAM without creating/saving files. Other errors
  are reported, not silently converted to successful loads. No tmp overlay runs.
- Name browsing reads the project header/name without changing the working
  directory or loading musical slots. Missing/incompatible files display Empty.
- Reload restores sounds from the RAM kit only; it does not restore pattern data
  or read the SD project.
  Playback is not automatically stopped. Both save/load and diagnostic reporting
  retain balanced background-audio ownership. No new timeout or lockout is added.

The stream uses one static 4096-byte buffer, not a second project-sized image.
Decoded kit caches retain ingress FX dry/wet clamping at 100 and modulation-target
normalization before activation. Compressor controls are published together at
successful load completion. Playback state, UI selection and live filter controls
are not persisted.

A load is **not transactional**. Header and exact length are checked before
modifying RAM, but later I/O failure may leave partially loaded RAM. Concurrent
recording/edits during streaming are not an atomic project snapshot. Staged saves
do not guarantee arbitrary power-failure atomicity on FAT/card hardware. Existing
failed-write-close ownership and explicit-unmount invalidation remain in place.

## Codec version 1

`Core/Inc/Preset/ProjectCodec.h` describes a borrowed view of existing project RAM;
it does not allocate a second project. The caller supplies the existing stream,
file lifetime and current edit-buffer capture. No raw structs are written.

The 36-byte header contains:

- Eight-byte magic `QEONDAPR`.
- Twelve little-endian 16-bit values: version (1), header size (36), slots (64),
  tracks (7), steps (64), bars (4), sound parameters (247), song length (64),
  globals (30), name length (8), step fields (7), timing bytes (1).
- Little-endian 32-bit payload length (255082).

The exact file length is **255118 bytes**. Reader rejects any header mismatch or
file length mismatch before modifying project RAM. It rejects old formats rather
than guessing. I/O failures after validation can leave partially loaded RAM;
there is no transactional load guarantee or retry.

Payload order:

1. Project name (8), global parameters (30), compressor threshold/ratio/attack/
   release (4).
2. For each slot, kit name (8), sound parameters (247), pattern name (8), pattern
   fields below, song name (8), song entries (64).
3. Pattern fields: for each track, 64 explicit seven-byte steps (volume,
   probability, note, automation target/value 1 and 2), then 64 timing bytes
   (flam low nibble, shift high nibble). Track-major/bar-minor main hits are LE16.
   Shuffle, seven lengths, associated kit and sticky occupancy follow.

All seven step fields and both timing nibbles retain their full existing byte/
nibble representations. Silent-used occupancy is retained independently of hits.
`PatternSetting`, `changeBar` and `nextPattern` are commented out in the actual
`PatternSet` and chaining implementation; they are not active state to persist.
Song chaining remains represented by the song entries. Playback state, backup
buffers, queues and UI selection are not codec fields.

## Verification

The following verification account is a 2026-11-10 pre-commit snapshot.
Its no-commit/no-install statements describe that stage, not later acceptance.

`test_project_codec` checks all slots/fields and exact wire bytes, header mutations,
length rejection, truncation and I/O errors. `test_master_comp_persistence` and
`test_master_comp_save` now run `test_project_runtime.py`: extracted **production
project APIs**, linked production SafeStorage/ProjectStream/ProjectCodec, with
byte-backed file/directory endpoints. They cover RAM-only save APIs, current-kit
capture, live shuffle edit/dispatch then project save without pad-save (active slot
only, nonactive slot unchanged), full project round-trip, compressor publication, names, boot selection,
missing/default initialization, incompatible files, read errors, 85 injected
filesystem-call faults, 64 short-write positions and retained failed close/retry.
The fake distinguishes absent parents (`FR_NO_PATH`) from absent leaf files
(`FR_NO_FILE`), denies unlink of an open file and models the single FatFs lock
slot for directory opens. A failed retained-close retry must be the only FS call;
a successful retry must release that lock before staging cleanup.
`test_project_callsites` checks boot/control wiring, absence of tmp/autosave/slot
I/O calls, no storage transport stop, and executes the literal song Save-As and
interactive project-load branches (both missing-file/path fallbacks, other errors
reported without creating a project).
Reload, occupancy, MIDI transport and audio-scheduling regressions remain enabled.

These tests substitute engine/UI/timer or filesystem endpoints; they are not
hardware timing, audible, stack-margin, concurrent recording or SD-media/power-loss
certification. No commits, card writes or installation were performed.

## Historical verification snapshots (2026-11-10)

The working-tree identities, test counts and no-commit/no-card/no-hardware
statements below record the pre-commit verification stage, not current status.
They were superseded by storage commit `38cf955` and subsequent hardware feedback.
Later `8a81f1c` added Save Kit assignment and navigation; the runtime description
above includes its assignment behavior. Historical image identities remain unchanged.

## Final integration build evidence (historical)

The OFF/ON diagnostic comparison below is historical, before ProjectMeasure was
removed. The measurement build and its two dedicated tests are retired; see
[retired diagnostic evidence](PROJECT-MEASUREMENT.md).

Uncommitted working tree based on development
`01fefe977069143473e2fb899a6e7b7e7e0b3b92`; version remains **LXR QEONDA 0.1**.
After the missing-directory, retained-close ordering and live-shuffle review fixes,
Apple Clang 17 native suites: **51/51 passed** with the diagnostic option OFF and
ON. ARM GCC **14.3.1** normal and measurement builds passed, as did both FM codegen
checks (the accepted unsigned conversion remains, no negative clamp). Normal
release verification and diagnostic header/checksum/BIN comparison passed.

| Build | Payload bytes | Image SHA-256 |
|---|---:|---|
| Normal | 295928 | `a0e501aa36e5cbb51270fb7ff0c286dc356414fff3165632a6f5b2d7b5fb71e0` |
| Project measurement | 299536 | `e7db2e2da00a0160baf64e05e81ed9965ff74d1a1d233f3173e652c44af88c76` |

Static placement: ITCM 15336/16384, DTCM 107392/131072; normal RAM
276476/393216, measurement RAM 277492/393216 bytes. Firmware CRLF preservation
and `git -c core.whitespace=cr-at-eol diff --check` passed. These figures are not
measured CPU cycles, storage latency, deadline or stack-margin certification.

## Instrumentation removal verification

ProjectMeasure was removed at user request; project codec, stream and storage
behavior are unchanged. Normal ARM GCC 14.3.1 Release configure/build passed;
`python3 tests/check_fm_arm_codegen.py build/release` and
`python3 cmake/tools/verify_release.py build/release` passed. Native Clang
`cmake --preset host-tests`, build and `ctest --preset host-tests`: **49/49 passed**
(the two measurement-only tests were removed). Existing sprintf deprecation
warnings remain. Firmware line endings were preserved and
`git -c core.whitespace=cr-at-eol diff --check` passed.

Both normal BIN and update image compare byte-identical (`cmp`) with copies
retained immediately before removal. Payload remains 295928 bytes. SHA-256:

- BIN: `941fc029e59aedbbf3812746fb6a7c348ad6f7fd9c37319f98527cfad6be5e5b`
- Image: `a0e501aa36e5cbb51270fb7ff0c286dc356414fff3165632a6f5b2d7b5fb71e0`
- ELF: `2a92c4b4fced69798a51a1ade4a16d0a5a05362438b5a5e04c9ec49169c9c9fb`

No commits, card writes or hardware tests. Prior hardware verification gaps remain.

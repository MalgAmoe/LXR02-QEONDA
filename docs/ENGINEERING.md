# Engineering notes for contributors and coding agents

Read [AGENTS.md](../AGENTS.md) first. This document is a map of the application and
its design constraints, not a replacement for inspecting current source. Controls
belong in [USER-GUIDE](USER-GUIDE.md), tooling in [BUILD](BUILD.md), test mechanics
and coverage in [tests/README](../tests/README.md). Do not infer hardware acceptance
from an example, old test result or successful build.

## 1. Instrument vocabulary and source map

A **voice/track** is a musical lane, not necessarily an independent synth engine:
there are seven tracks and six synthesis engines, with shared hi-hat resources.
A **kit** supplies sounds; a **pattern** supplies sequenced events, lengths and
associated settings; a **project** groups saved material and project controls.
A selected/shown pattern can differ from the currently playing or pending pattern.
A **step lock** temporarily applies parameter automation, not a permanent kit edit.

Paths in this table are relative to the repository root:

| Area | Start reading here | Questions to answer |
|---|---|---|
| Startup, foreground service | `Core/Src/main.c` | What runs between input, display, storage and audio service? |
| Interrupts | `Core/Src/stm32f7xx_it.c` | Which work can preempt this operation? |
| Audio scheduling/render | `Core/Src/Soundengine/Soundengine.c`, `Core/Inc/Soundengine/config.h` | Who owns each requested DMA half? |
| Mixing and effects | `Core/Src/Soundengine/DSPAudio/mixer.c`, `Core/Src/Soundengine/FxBus.c`, `Core/Src/Soundengine/DSPAudio/` | Where do gain, clipping, filtering and routing occur? |
| Sequence and synchronization | `Core/Src/Soundengine/Sequencer/sequencer.c`, `clockSync.c` in the same directory | Is this real transport, audible playback, or an edit coordinate? |
| Buttons/menu/LEDs | `Core/Src/buttonHandler.c`, `Core/Src/menu/menu.c`, `Core/Src/ledHandler.c` | Who owns press, release and repaint? |
| Physical inputs | `Core/Src/IO/DIO.c`, `Core/Src/encoder.c` | Is it shift-register, GPIO or decoded encoder input? |
| Parameter definitions | `Core/Inc/Parameters.h`, `Core/Inc/menu/menuPages.h` | What range, slot, engine and dispatch path does this use? |
| MIDI and panel dispatch | `Core/Src/Soundengine/MIDI/`, `Core/Src/frontPanelParser.c` | Is this a sound parameter, transport command or panel-only action? |
| Kits, projects, storage | `Core/Src/Preset/`, `FATFS/Target/` | What is in RAM, staged on disk, or already adopted? |
| Placement and toolchain | `STM32F765VGTX_FLASH.ld`, `cmake/`, `CMakeLists.txt` | Which memory region and compile flags actually apply? |

## 2. Audio scheduling and memory

The target is STM32F765 Cortex-M7. Current configuration uses 64-sample rendering
blocks and a nominal `REAL_FS` of 44140 Hz: roughly 1.45 ms per block. This is a
scheduling interval, **not spare CPU time**. Inspect configuration and generated
commands rather than assuming these values for another build.

Audio DMA callbacks and rendering share buffer/request state. The renderer uses
request-generation ownership checks; preserve them when changing scheduling.
Audio/sequence work can run in interrupt context, and foreground operations also
service audio. A call that looks like an ordinary function can therefore touch
state shared with MIDI, timers and DMA. Trace the actual configuration and caller
chain before choosing a critical section.

ITCM, DTCM and ordinary RAM have separate capacities and access constraints.
`IN_ITCM_RAM`, `INDTCM` and `INDTCMZ` are placement attributes, not decoration.
Check the final ELF/map and peripheral access requirements before moving buffers.
A free-space total across all regions cannot justify overflowing one region.
Avoid large automatic arrays on interrupt stacks. Static fit is not stack-margin
measurement; report exact build identity for any memory/timing evidence.

## 3. Sound changes are behavior changes

Preserve synthesis order, types, endpoints and smoothing unless the change explicitly
calls for a different sound. In particular:

- MOD decay127 is intentional infinite hold. Slope127 endpoint, wavetable wrapping
  and integer PWM phase corrections are intentional too.
- FM relies on the accepted ARM `vcvt.u32.f32` negative-to-zero behavior. Do not add
  per-sample negative clamps simply because native host casts behave differently.
  Run `tests/check_fm_arm_codegen.py` after relevant compiler/flag/context changes;
  label host conversion substitutes as models.
- Transient signed-shift code has target-specific history; a sanitizer finding alone
  does not justify a sound change. Establish actual target behavior first.
- Snare musical clipping occurs after combined tone/noise/transient, before envelope,
  velocity, voice volume and fader. MIX drive is downstream. Preserve exceptional-range
  final conversion bounds and intentional mono-compressor saturation.
- Fader targets are cached per rendered voice block; smoothing remains per sample.
  Caching a target is not permission to update the smoother only once per block.
- FX dry/wet accepts0–100 and clamps at ingress, without rescaling to127 or adding
  checks in the audio loop.

The master filters and compressor act on **St1 only**, after FX; hardware/code output
names are not intuitive (`output2` / `dma_buffer2` / SPI2 correspond to St1). Verify
routing through the mixer and DMA path, not variable names alone. Independent HP/LP
are session state. Compressor settings are project state. Accepted makeup is
`R - 4R/(R + 12)` dB, with R the predicted reduction at0dBFS—not the ratio. It is
neither half compensation nor a +12dB cap. Ratio1 settles to true bypass. Neither
filters nor compressor constitute a guaranteed limiter.

## 4. Controls, sequencing and Looping

Mode and visible page are distinct. Pattern selection can retain a voice/FX/PERF
page while pads select patterns rather than edit steps or play rolls. Gate new
shortcuts on intended mode **and** page/context, not just what appears on screen.

Modifiers have existing priority and side effects. Inspect both press and release:
a pad pressed under one mode/modifier may be released under another. Copy can enter
track-copy mode; Shift+Copy can arm Clear or live erase. Do not hijack those paths
by adding a late switch case. Encoder clicks and turns are separate actions.

Play and bar buttons use immediate press/stable20ms-release rearming. Page Down
is a separate GPIO, not another index into the shift-register array. The encoder
has its own decoding; simulated menu increments do not test physical detents.

Step data comprises the complete `Step`, `StepTiming` and main hit bits. Rotation
must move all three together and preserve inactive tail data. Seven track lengths
may differ. Never assume the displayed bar defines the playback length.

**Looping is an audible read mapping, not an audio recording or transport rewind.**
Real step indices continue for synchronization, pattern/song progression, recording
and LED chase. Source indices used for programmed hits can differ during a loop.
Manual rolls and momentary pattern mute remain separate controls.

Microshift/flams read previous/current/next source events across24 pulses per step.
Negative shift can sound an event before its nominal boundary. Probability histories
are gated by existing active/mute/erase logic, so one play/skip bit for an entire
step occurrence is not generally sufficient. Current Looping caches role outcomes
and observes the real timeline separately. Source indices alone do not identify
occurrences on short tracks. Writes/erase must invalidate cached aliases correctly.

Use explicit audible source selection for looped automation; do not globally remap
manual/MIDI triggers. Preserve ordinary no-loop behavior, including existing quirks,
unless a separate fix is agreed. Entry/release/handover preserve substep phase, do
not synthesize hits and do not forcibly reset voices or effects. Ordinary note-offs
continue. Recording and erase remain on the real timeline: do not silently lock
them out or redirect them to the loop. See the user guide for ownership/cancellation.

## 5. Parameter layers and persistence

`activeParameters` holds editable values; `mainParameters` contains RAM kit bases.
Morph reads source and destination and applies interpolated values asynchronously.
Engine-effective values can also include temporary automation/modulation. Copying
one array is not necessarily capturing the audible sound.

Follow each parameter through menu -> dispatch -> DSP, and separately through
save/load. Internal IDs, CC numbers and NRPN addresses are not equivalent. Some
controls bypass MIDI/step capture deliberately: master filters and master compressor
are examples. Bulk Shift+knob follows **same menu slot**, not semantic remapping,
with per-engine bounds/shared-hat deduplication and no step-lock writing.

Shift+Reload resets morph and master filters and restores the selected kit from RAM,
not directly from disk; compressor settings remain. Pattern activation and linked-kit
behavior still follow their own timing. Do not describe this as an atomic all-state
reset or assume it discards every project change.

Continuous playback during project load/save is required. Preserve staged-save
safeguards and the **Finalizing** UI phase. Do not add automatic transport stops,
blanket reload-required lockouts or a transactional loader redesign as incidental
hardening. Partial loads and temporary-file ownership require explicit policies;
the current implementation must not be advertised as full rollback.

Do not introduce arbitrary readiness/transfer deadlines. Persistent BUSY can wait
indefinitely under current policy. Preserve explicit terminal card errors,
initialization retry, explicit-unmount stale-handle invalidation and same-mount
failed-close ownership. Never replay a stale handle onto a replacement card.
File layouts and optional extensions affect older firmware: validate defaults,
truncation and round trips, and explain compatibility changes before editing formats.

## 6. MIDI boundaries

DIN and USB parsing/queues are separate; output serialization protects message
boundaries. Keep static buffers and explicit ownership. SysEx owns an output until
end/interruption or route removal; realtime may interleave. There is no inactivity
expiry; an abandoned stream can block competing traffic until routing is reset.
Do not add a timeout without an agreed behavioral change.

Received Start resets, Stop preserves position, Continue resumes on incoming clock.
Front-panel transport is distinct. Song Position Pointer is not implemented; do not
claim general DAW-seek compliance. USB MIDI consumption can be starved during project
storage operations even while DIN/audio service continues. Preserve that documented
limitation rather than claiming storage tests establish universal USB timing.

## 7. Evidence that is useful to a maintainer

For a change, report:

1. User-visible goal and behavior intentionally preserved/changed.
2. Touched input, DSP, shared-state and persistence paths.
3. Exact test commands/results, including extracted code versus modeled endpoints.
4. Source revision, compiler/flags, image hash and relevant static memory deltas.
5. Hardware checks actually performed, and remaining timing/listening/storage gaps.

Use independent expected results, representative musical cases and regression tests
that fail for the reported defect. Do not weaken an assertion simply because gain
or output changed; derive the new expectation from the approved behavior. Test
modifier release order, mute/roll interactions and save/load when relevant—not only
isolated helper math. Fresh CMake configuration matters when registering tests.

Regression fixtures may retain old implementation fragments to detect unintended
changes. Their role is an oracle, never the firmware source selected for release.
Keep attribution and a full revision identity; no runtime `git show` dependency.
The manual release workflow builds its selected source SHA. A test pass, image copy,
installation and musical acceptance are different evidence levels.

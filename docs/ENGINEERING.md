# Engineering notes for contributors and coding agents

Read [AGENTS.md](../AGENTS.md) first. This document is a map of the application and
its current implementation, not a specification that future designs must preserve.
Use it to locate dependencies and make intentional changes, then update it as the
architecture evolves. Controls
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
request-generation ownership checks so completion of an older render does not
erase a newer DMA request.
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

## 3. Signal flow and DSP details

The mixer renders the drum, snare, cymbal and shared hi-hat engines, routes their
samples to the outputs/FX bus, then calls `FxBus_process`. Start with
`mixer_calcNextSampleBlock` to follow the actual processing order and active compile
options. Gain and saturation exist at multiple stages; moving a nonlinear stage
across an envelope or gain changes the sound, even if maximum levels are unchanged.

Useful implementation details when extending this path:

- Fader targets are cached per rendered voice block; smoothing still runs per sample.
  Changing smoothing rate changes the time response unless its coefficients change too.
- Snare clipping follows combined tone/noise/transient and precedes envelope,
  velocity, voice volume and fader. MIX drive is a later stage.
- MOD decay 127 represents infinite hold rather than simply a longer finite decay.
  Endpoint values can have special semantics; check the receiving DSP function.
- FX dry/wet uses 0–100, clamped at ingress. MIDI's 7-bit container does not mean
  every parameter uses a 0–127 scale.
- FM float-to-unsigned conversion currently relies on ARM `vcvt.u32.f32`
  negative-to-zero behavior. `tests/check_fm_arm_codegen.py` checks that dependency.
  Host conversion models are not proof of identical target behavior, and compiler
  changes require rechecking the generated instructions.

Master filters and compressor process **St1 only**, after FX. The code/hardware
names are not intuitive: `output2` / `dma_buffer2` / SPI2 correspond to St1.
Independent HP/LP settings are session state; compressor settings are project state.
The current makeup calculation is `R - 4R/(R + 12)` dB, where R is predicted gain
reduction at 0 dBFS, not the ratio. Ratio 1 settles to bypass. These stages are not
a guaranteed output limiter. Treat equations, placement and persistence as separate
integration concerns when developing a different processor.

## 4. Controls, sequencing and Looping

Mode and visible page are distinct. Pattern selection can retain a voice/FX/PERF
page while pads select patterns rather than edit steps or play rolls. Gate new
shortcuts on intended mode **and** page/context, not just what appears on screen.

Modifiers have existing priority and side effects. Inspect both press and release:
a pad pressed under one mode/modifier may be released under another. Copy can enter
track-copy mode; Shift+Copy can arm Clear or live erase. A new shortcut may need handling before those side effects occur, rather than
only a new case in the final dispatcher. Encoder clicks and turns are separate actions.

Play and bar buttons use immediate press/stable 20ms-release rearming. Page Down
is a separate GPIO, not another index into the shift-register array. The encoder
has its own decoding; simulated menu increments do not test physical detents.

Step data comprises the complete `Step`, `StepTiming` and main hit bits. A whole-step editing operation needs to account for all three, as well as data
outside the current active length. Seven track lengths
may differ. Never assume the displayed bar defines the playback length.

**Looping is an audible read mapping, not an audio recording or transport rewind.**
Real step indices continue for synchronization, pattern/song progression, recording
and LED chase. Source indices used for programmed hits can differ during a loop.
Manual rolls and momentary pattern mute remain separate controls.

Microshift/flams read previous/current/next source events across 24 pulses per step.
Negative shift can sound an event before its nominal boundary. Probability histories
are gated by existing active/mute/erase logic, so one play/skip bit for an entire
step occurrence is not generally sufficient. Current Looping caches role outcomes
and observes the real timeline separately. Source indices alone do not identify
occurrences on short tracks. Writes/erase must invalidate cached aliases correctly.

Looped automation uses explicit audible source selection; manual/MIDI triggers
follow their own paths. Entry, release and handover retain substep phase without
synthetic hits or forced voice/FX resets. Recording and erase use the real timeline.
These distinctions matter when adding alternative playback transformations: decide
which timeline owns each operation and test automation, note-offs and edits together.
See the user guide for current Looping controls and cancellation behavior.

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

Project loads/saves currently coexist with playback. Storage work therefore interacts
with audio servicing and interrupt latency, not only file correctness. The save path
uses staged writes; the load path does not provide full rollback on partial failure.
Read `Core/Src/Preset/SafeStorage.c`, `SlotFiles.c` and `presetManager.c` together
before changing ownership, commit order or error recovery.

The card layer distinguishes terminal errors from BUSY; persistent BUSY can wait
indefinitely. Explicit unmount invalidates stale handles, and failed-close ownership
is retained on the same mount. Recovery changes need to distinguish a retry on the
same card from access to a replacement card. Define failure and recovery behavior
alongside the successful path rather than assuming file operations are atomic.

File layouts and optional extensions affect older firmware: investigate field widths,
ordering, defaults and readers as well as writers. Test existing files, missing or
truncated optional data and save/load round trips. Document any format migration or
loss of backward compatibility.

## 6. MIDI boundaries

DIN and USB parsing/queues are separate; output serialization protects message
boundaries. Keep static buffers and explicit ownership. SysEx owns an output until
end/interruption or route removal; realtime may interleave. There is no inactivity
expiry; an abandoned stream can block competing traffic until routing is reset.
Changing stream expiry would change how incomplete transfers and competing
messages are handled; test those cases together.

Received Start resets, Stop preserves position, Continue resumes on incoming clock.
Front-panel transport is distinct. Song Position Pointer is not implemented; do not
claim general DAW-seek compliance. USB MIDI consumption can be starved during project
storage operations even while DIN/audio service continues. This is an existing limitation, not a required behavior. Improvements need tests
that exercise USB input during storage work, not only ordinary idle reception.

## 7. Extending the instrument

These are investigation checklists, not mandatory changes to every layer. Find a
similar existing feature and trace its actual call sites first.

### Add a sound parameter

1. Define its meaning, units, range, default and any special endpoint values.
2. Locate parameter IDs and menu entries in `Core/Inc/Parameters.h` and
   `Core/Inc/menu/menuPages.h`. Trace panel dispatch through `frontPanelParser.c`
   and the MIDI/Cortex parser code to the destination engine.
3. Decide where the value lives: editable kit state, temporary performance state,
   per-step automation or project settings. Check array bounds, initialization,
   morph interpolation and shared-engine handling where applicable.
4. Implement conversion/smoothing at the appropriate rate. Check extreme inputs and
   rapid movement as well as static values.
5. If MIDI exposure is wanted, allocate and document an address explicitly; internal
   IDs are not a ready-made external mapping. Check channel and value-range handling.
6. If persistent, update serialization/defaults and round-trip tests. Test the menu,
   dispatch and DSP together so a visible value actually controls the intended sound.

### Add a gesture or sequencer feature

- Follow input acquisition -> button/encoder decoding -> mode handling -> state
  update -> LED/display feedback. Input sources are not all electrically identical.
- Decide press/release ownership, modifier priority, mode exit and transport behavior.
- Distinguish display position, real transport position and audible event source.
  Account for different track lengths, early/late events and pattern transitions.
- Test stopped and running operation, overlapping gestures, automation, manual hits
  and any recording/editing interaction introduced by the feature.

### Add an effect or change rendering

- Locate routing and buffer format first. Establish channel layout, numerical range,
  gain staging, sample rate and where state resets.
- Budget per-sample/block work, persistent state and stack temporaries. Inspect the
  linked memory regions and generated ARM code, then measure on hardware when timing
  is material. A short source expression can compile into expensive operations.
- Test bypass/activation transitions, silence, sustained signals, rapid changes and
  high-level input. Listen as well as measure: clicks, aliasing and altered dynamics
  may not appear in simple bounds tests.

### Extend saved state

- Trace defaults -> in-memory owner -> serializer -> loader -> runtime application.
  Writing a value is insufficient if loading never reapplies it to the engine.
- Decide kit/pattern/project/session lifetime explicitly. Check reload and project
  switching, compatibility with existing files and interruption/error handling.
- Test with representative stored material as well as freshly created defaults.

## 8. Verification reference

Use [BUILD](BUILD.md) for reproducible commands and [tests/README](../tests/README.md)
for harness details. Tests include native code, extracted production functions and
hardware substitutes; understand which boundaries each test actually covers.
Regression fixtures are test oracles, not firmware sources selected for release.
Keep their provenance and avoid runtime dependencies on historical Git objects.

For a useful handoff, describe the intended result, affected paths and tests run.
Include source/compiler/image identity for hardware results and relevant memory
changes for firmware work. Explicitly separate host checks, static fit, measured
timing and listening tests. Test modifier order, clock/storage traffic and save/load
when relevant rather than treating isolated DSP math as full-system coverage.

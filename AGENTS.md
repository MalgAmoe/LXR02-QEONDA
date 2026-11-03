# Working on LXR QEONDA

This is firmware for a **live musical instrument**, not a general-purpose service.
Preserve its sound, timing, playable controls and users' saved work. A technically
neater implementation is not an improvement if it changes the groove or makes a
performance gesture harder.

## Read before changing code

1. Read the task and inspect the current branch, working tree and relevant source.
   Preserve unrelated edits. A request to investigate is not permission to implement.
2. Read [controls and compatibility](docs/USER-GUIDE.md) for intended behavior.
3. Use [engineering notes](docs/ENGINEERING.md) for architecture, ownership and
   sensitive boundaries; [build instructions](docs/BUILD.md) and
   [test guide](tests/README.md) own commands and test limitations.
4. Treat old comments, disabled code, historical reports and prior proposals as
   clues, not proof of active behavior or permission to revive a design.

**QEONDA 0.1 is feature-frozen.** Unless explicitly reopened, scope is documentation,
release preparation and fixes for demonstrated bugs. Keep the displayed version
0.1; distinguish builds by source revision and image hash. Snapshots/scenes are not
implemented features. Follow the maintainer's branch instructions; do not switch,
merge or publish branches merely to make your environment convenient.

## Musical and engineering judgment

- Establish the actual symptom, realistic use case and existing recovery. Explain
  proposed changes in musician-facing terms before changing behavior.
- Prefer the smallest coherent fix at the responsible layer. No opportunistic
  cleanup, new framework, generic event bus or loader redesign.
- Do not silently add limiting, clipping, gain caps, transport stops, recording
  lockouts or arbitrary timeouts as "safety." These alter musical behavior. Conversely,
  do not remove existing bounds or saturation without understanding their purpose.
- Distortion can be intentional; so can infinite envelopes and wraparound. Ask
  whether a change should sound different. Keep controllable compression and
  optional distortion, not forced quietness or forced distortion.
- Preserve the user guide's modifier, release, reload, persistence and routing
  semantics. A knob's menu position, internal parameter ID, MIDI address and DSP
  function are not interchangeable concepts.
- Consider CPU, RAM, flash, stack, latency, compatibility and control complexity.
  Avoid per-sample work for a setting that can be handled at ingress or update time.

## Code and real-time discipline

- Match nearby C style and preserve existing line endings, especially firmware
  CRLF. Do not reformat unrelated files. Check with:
  `git -c core.whitespace=cr-at-eol diff --check`.
- Trace callers and execution contexts before editing shared state. `volatile`
  does not make a multi-field update atomic. Keep explicit ownership, fixed buffers
  and short transactions that save and restore PRIMASK; never blindly enable IRQs.
- No SD/file operations, kit loads, large DSP work or logging inside masked sections.
  Do not add dynamic allocation to audio/clock paths.
- Preserve per-sample smoothing and operation order in DSP. A block-rate shortcut
  can change sound even when endpoints are identical. Inspect actual ARM codegen
  for DSP/compiler/flag changes, not only host output.
- Preserve licence/copyright notices and third-party boundaries. Do not copy code
  from another firmware without checking its licence and attribution requirements.

## Verification and completion

- Reproduce a reported bug with a focused test where practical; test real production
  code, not just a separately rewritten algorithm. Label mocked hardware and models.
- Tests must run from the checked-out tree, including shallow clones/source archives.
  Do not require private files or historical Git objects at runtime. Frozen regression
  fixtures need provenance and must not be refreshed just to make a failure pass.
- Run proportionate checks from [BUILD](docs/BUILD.md): Clang host tests, ARM build,
  FM codegen check and image verifier when firmware is affected. Reconfigure CMake
  after changing test registration; inspect the enumerated suite, not an old count.
- Passing host tests/static memory fit does **not** certify device timing, stack
  margin, storage faults, MIDI interoperability or audible behavior. Instruction
  counts are not measured cycles. Report what actually ran and what remains untested.
- Update the owning documentation, not parallel copies of a status diary. Keep
  public docs useful in a standalone clone; no private paths or hardware identifiers.
- Before finishing, personally inspect important diffs, check the original request,
  and distinguish changed, committed, pushed, built, copied and installed states.

## External actions

Obtain task-specific authorization before installing dependencies, destructive
operations, changing sensitive configuration, pushing/publishing, writing an SD
card, flashing via a probe or touching the bootloader. A normal application change
is not bootloader authorization. For an authorized card update, identify the card,
validate the exact image, verify readback and safely eject; copying is not installation.
Never delete backups without permission or create routine full-card backups without
an agreed reason.

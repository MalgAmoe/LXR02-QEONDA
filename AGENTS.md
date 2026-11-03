# Developing LXR QEONDA

This is firmware for a live musical instrument. Good results combine clear C code,
reliable timing, intentional sound and controls that make sense while playing.
This guide supports fixes, experiments and new features; it does not prescribe a
roadmap or require future versions to retain every current design choice.

## Find your starting point

- Read the requested goal, relevant source and current diff before editing. Preserve
  unrelated work and keep changes focused on the task.
- [USER-GUIDE](docs/USER-GUIDE.md) describes the current instrument and controls.
- [ENGINEERING](docs/ENGINEERING.md) maps the code, runtime and extension points.
- [BUILD](docs/BUILD.md) owns toolchain/build commands; [tests/README](tests/README.md)
  explains test harnesses and their limits.
- Verify old comments and examples against active code and compile options. Existing
  behavior is a starting point to understand, not a prohibition on changing it.

## A useful development loop

1. Describe the feature or problem in musician-facing terms. Identify what should
   change and what should remain unaffected, including sound and saved projects.
2. Trace a similar existing feature end to end: input, dispatch, state, DSP or
   sequencing, display, persistence and MIDI where applicable.
3. Choose a simple, coherent implementation with explicit state ownership. Consider
   CPU, RAM, flash, stack, latency and interaction complexity—not only code size.
4. Add focused tests for the intended behavior and surrounding interactions. For a
   bug, capture a reproducer; for a feature, test normal use and meaningful boundaries.
5. Build and check on the target where relevant, then document behavior, compatibility
   and verification gaps. Review the final diff against the original goal.

## Code style and musical behavior

- Follow nearby naming, C formatting and module conventions. Preserve existing line
  endings (firmware commonly uses CRLF); avoid unrelated reformatting. Check with
  `git -c core.whitespace=cr-at-eol diff --check`.
- Prefer explicit, readable control flow and small cohesive functions. Introduce
  abstractions when they simplify actual use cases, not hypothetical expansion.
- Explain units, ranges, ownership and non-obvious reasons in comments. Keep headers
  and public interfaces consistent with their implementations.
- Treat smoothing rate, clipping placement, gain, parameter scaling and event order
  as audible behavior. Changes may be desirable; make them intentional and test them.
- Distortion, infinite envelopes and wraparound can be musical features rather than
  faults. Conversely, existing behavior is not automatically correct. Evaluate the
  actual symptom, target execution and musical result.
- Consider gestures as sequences: press, hold, modifier changes, release, mode change
  and feedback. Test interactions, not just each button in isolation.
- Preserve licence and attribution notices; check compatibility before importing code.

## Real-time implementation

- Trace caller contexts before changing shared state. `volatile` alone does not make
  multi-field updates atomic. Use explicit ownership and short critical sections
  that save and restore PRIMASK rather than blindly enabling interrupts afterward.
- Keep blocking I/O, allocation, logging and long computations out of audio/clock
  critical paths and interrupt-masked sections. Fixed buffers and bounded work make
  timing easier to reason about.
- Calculate control-dependent values at update/block rate where appropriate, while
  retaining sample-rate processing where it determines the intended sound.
- Inspect actual ARM codegen when DSP, compiler or optimization changes matter.
  Host floating-point behavior and sanitizer models can differ from the target.
- Check memory placement, stack use and DMA accessibility, not just total free RAM.

## Verification and handoff

- Use the commands in BUILD for Clang host tests, ARM builds, target-codegen checks
  and image verification as relevant. Reconfigure after adding registered tests.
- Prefer tests exercising production code. Label hardware substitutes and models;
  keep fixtures attributable and runnable from shallow clones/source archives without
  private files or historical Git objects.
- Derive expectations from intended behavior. A changed test expectation should have
  a reason beyond making the test pass.
- Host tests and static memory fit do not establish hardware timing, stack margin,
  audible quality or MIDI/storage interoperability. Report checks actually performed.
- Update the relevant reference documentation when behavior or architecture changes.
  Keep it useful in a standalone clone, with repository-relative links.
- Summarize the change, tradeoffs and remaining checks. Record source revision,
  compiler and image hash when reporting firmware measurements or distributing builds.
- Confirm scope before destructive operations, publishing or writing to hardware.
  Building an image, copying it to a card and installing it are separate actions.

# QEONDA 0.1 — controls and compatibility

A supplement to the stock desktop LXR manual. For downloads and installation, see
[the README](../README.md#download-and-install).

## Performance banks

Repeated PERF presses cycle A → B → C → A. The four knobs address the current bank;
encoder selection traverses all twelve controls.

| Bank | Controls, left to right |
|---|---|
| A | BPM / roll speed / morph / sample-rate reduction |
| B | Shuffle / HP / LP / shared resonance |
| C | Compressor threshold / ratio / attack / release |

Buttons 1–7 play rolls. **Momentary pattern mute:** holding button 8 suppresses programmed hits while leaving
manual rolls available. The sequencer keeps running; release brings the pattern back in, still in time.
Leaving PERF or Stop also cancels this mute. Existing
armed roll recording remains available.

**Looping:** while running in PERF, hold step buttons **9 / 10 / 11 / 12**
for a **2 / 4 / 6 / 8-step loop** across all tracks. The first held
button owns the loop; later held buttons wait in press order. Releasing the
owner starts the next held window freshly from the real playhead, not from the
audible loop. Releasing all buttons returns to the continuing real timeline.
The owner LED stays lit; the chase still shows the real playhead.

Only plain presses acquire a loop: Shift, Load, Save and Copy/clear retain their
existing functions. Releases remain owned even if modifiers or mode change.
Stopped presses do nothing. Stop, transport reset, leaving PERF, project load,
and actual pattern activation/reload cancel the owner and all waiters; press
again to start another loop. Merely queuing a pattern change does not cancel.
Switches preserve the current sub-step phase and do not inject a hit or reset
sounds/FX. Sound controls, armed recording and erase remain live; recording
still writes the real timeline, and changed/erased steps are reflected by future
loop evaluations. This is a momentary playback effect, not saved pattern data.

### Combining loops and momentary pattern mute

Keep a loop button held and hold **8** to silence its programmed hits without
cancelling the loop. Release **8** to hear the loop again; release the loop button
to return to the advancing real timeline. Manual rolls remain available.

The loop reads existing pattern steps rather than recording audio. Probability
outcomes are remembered as encountered and reused on repeats; recording or erase
can still change referenced steps. Sound controls remain live.

## Pattern selection without losing controls

Shift+Pattern or Load+Pattern keeps the current voice, FX or PERF controls visible
and usable. Entering from any other screen opens PERF bank A. The step buttons select
patterns and the bar buttons select pattern banks; LEDs show playing/pending selection.
Voice or PERF exits selection without an extra step-edit toggle or PERF bank change
when returning to the same control page. The current page and selected parameter are
retained; knobs and encoder continue editing those controls. Copy does not exit this
view, and subpage buttons are inactive while selecting patterns. Step buttons select
patterns rather than playing PERF rolls or momentarily muting programmed hits.
Pattern saving remains a separate operation.
Kit autoload still replaces sound settings, including the displayed FX type. Ordinary
knob recording still targets the playing pattern, not a pending selection.

## Selected-track rotation

In ordinary **Voice mode**, hold **Shift** and turn the data encoder to rotate the
selected voice track in the shown/edited pattern: positive increments move events
right, negative increments left, one step per increment, wrapping within the track's
active length (1–64). Hits, velocity, notes, probability, both automation lanes,
flam and microshift move together. Steps beyond the active length are untouched.

Other tracks, track length, viewed bar, selected parameter and playback position stay
unchanged. Playback continues. Rotation is not available in pattern selection/live,
other modes, dialogs or Copy/Clear; their encoder behavior is unchanged. Encoder
click is unchanged. Recording continues at the current playhead. Already-issued triggers are not
retracted; subsequent sequencer reads use the rotated data. Save the pattern normally
to commit it to a RAM slot; save the project to keep it across power-off.

## Master filters

HP and LP are independent, after FX on **St1 only**. Other outputs are unaffected.
HP0 and LP127 are bypass endpoints. Active HP spans 20 Hz–8 kHz; active LP spans
40 Hz–18 kHz. Both display 0–127. Shared resonance spans Q approximately 0.707–3.
Crossed cutoffs are allowed: there is no automatic cutoff ordering.

Startup and Shift+Reload restore HP0 / LP127 / resonance0. Ordinary loads, Stop and
page changes retain these settings. Filters are temporary session controls, not saved
project parameters.

## Master compressor

The compressor follows the filters on St1 only.

| Control | Range | Default |
|---|---|---|
| Threshold | −48…0 dBFS | −12 dBFS |
| Ratio | 1:1…20:1 | 1:1, bypass |
| Attack | 0.1…100 ms | Approximately 5 ms |
| Release | 10…500 ms | Approximately 100 ms |

Attack/release use logarithmic steps. Automatic makeup follows the predicted reduction R at 0 dBFS minus a gradually growing margin: R - 4R/(R + 12) dB (up to +42.43 dB); ratio1
returns to bypass through a short transition. **This is not a limiter**: transients
can pass through the attack and final output conversion can clip.

These controls belong to the project, not the kit or morph. Editing them does not
record step locks or automatically save the kit. Save the project explicitly.

| Action | Filters | Compressor |
|---|---|---|
| Startup | Reset to bypass | Defaults to bypass before project settings load |
| Kit/pattern load or ordinary Reload | Retained | Retained |
| Shift+Reload | Reset to bypass | Retained |
| Project load | Retained | Loaded from the saved project |
| Project save | Not stored | Stored |

### Saving and restart

Kit, Pattern and Song Save store/copy slots **in RAM only**. Global changes also
remain in RAM. **Save Project** is the disk-save action: it includes the current
edited kit, every RAM kit/pattern/song slot, names and project/global controls.
Song Save As copies the current song into the chosen RAM slot and selects it.

Boot restores the last explicitly saved project, not the last project you merely
loaded. A missing project starts initialized RAM without automatically saving it.
There is no temporary-file recovery or background autosave: power-off discards
changes since Project Save. Reload is unchanged and is not a disk-project reload.

Projects use a new single-file format (`/projNN/project.qpr`). Old multi-file
projects and tmp/global files are not imported. Save/load do not automatically
stop playback. **Saving Project** remains displayed until completion; a post-save warning
can mean cleanup or the boot-selection index could not be updated even though
the project file was published.

A failed project load is not an all-or-nothing rollback: depending on where it fails,
previous or target compressor settings may remain. Reload the intended project
successfully, or select ratio1 to bypass compression. Do not assume temporary files
provide automatic recovery of unsaved settings.

## Empty and used patterns

In live pattern selection (Shift+Pattern or Load+Pattern), used slots are
steadily lit and empty slots are dark. The current pattern flashes fast; a
queued, different pattern flashes at half that rate. These markers override
occupancy even for empty slots, and only appear in the displayed bank. Flashing
follows the existing sequencer LED clock. Bank changes redraw the slots; leaving
selection restores the normal step LEDs/chase. Save+Pattern LEDs are unchanged.

New pattern slots are empty. Selecting an empty slot keeps the current kit and
unsaved sound edits, without reloading sounds, and associates that slot with the
currently loaded kit. Enabling its first step makes it **used**. Removing the last
hit individually, clearing tracks, or replacing generated hits does not
make a used pattern empty: silent used patterns keep ordinary kit-change behavior.
Only an explicit whole-pattern erase resets a slot to empty.

Whole-pattern copy carries the source's empty/used status, including a silent used
source. Track/bar copies and recording/generation that add hits make an empty
pattern used. Automation alone does not mark a pattern used.

Project saving retains this status, including silent-used history.
Unsaved sound edits need **Save Project** for disk persistence.

## Shift+Reload

Clears morph, resets filters, cancels Looping, and reloads the selected kit from
**RAM, not disk**. Pattern data, sequencer position and any queued pattern are unchanged.
PERF is refreshed. A queued pattern still activates normally: used patterns follow
their kit link; empty patterns retain the sounds present at activation.

Pattern edits remain in RAM across pattern switches. Save-as copies edits to the new
slot and retains them in the source slot. Save the project to retain edits on disk.
This is not an atomic reset of every setting; compressor controls are retained.

## Shift+knob change-all

On ordinary voice pages, Shift plus a knob changes that same subpage/bank/slot across
the seven tracks. It follows **slot position**, not function names: different engines
may change different functions. Each parameter moves relative to its original kit
value and clamps independently. A selected parameter at its limit does not stop peers.

Shared hi-hat parameters move once; separate closed/open decays remain separate.
Empty/non-sound entries are skipped; an empty selected slot can still affect peers.
The gesture does not write step locks, including when steps are held. Releasing Shift
keeps edits. Use Reload to restore the kit; subsequent ordinary edits can record normally.

## MIDI and storage limits

USB-clock playback can be interrupted during project save/load: USB MIDI consumption
is delayed and queued clocks can be lost. Prefer internal or DIN clock when playback
must continue through storage operations. A tested DIN-clock save/load session retained
audio continuity without new missed-ready events or MIDI losses; this is not universal
certification of all projects, cards or MIDI traffic.

Received MIDI Stop preserves position; Continue resumes on incoming clocks; Start
resets position. Front-panel transport behavior is distinct. Song Position Pointer
is not implemented.

## Button response

Play and both bar/bank buttons respond immediately. Each rearms independently
after 20 ms of stable release, suppressing contact-bounce repeats in all modes.

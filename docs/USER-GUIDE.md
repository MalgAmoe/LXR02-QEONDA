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

## Pattern selection without losing controls

Shift+Pattern or Load+Pattern keeps the current voice, FX or PERF controls visible
and usable. Entering from any other screen opens PERF bank A. The step buttons select
patterns and the bar buttons select pattern banks; LEDs show playing/pending selection.
Voice or PERF exits selection without an extra step-edit toggle or PERF bank change
when returning to the same control page. Pattern saving remains a separate operation.
Kit autoload still replaces sound settings, including the displayed FX type. Ordinary
knob recording still targets the playing pattern, not a pending selection.

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
| Project load | Retained | Loaded from project, or bypass defaults for older files |
| Project save | Not stored | Stored |

### Project compatibility

Compressor settings use an eight-byte extension after the legacy 30-byte globals
file. Older firmware ignores the extension; saving globals with older firmware
removes it. Loading that rewritten project in QEONDA restores compressor defaults
with ratio1 bypass. Missing or invalid extensions also use bypass defaults.

A failed project load is not an all-or-nothing rollback: depending on where it fails,
previous or target compressor settings may remain. Reload the intended project
successfully, or select ratio1 to bypass compression. Do not assume temporary files
provide automatic recovery of unsaved settings.

## Shift+Reload

Clears morph, requests current-pattern reload, resets filters, and reloads the selected
kit from **RAM, not disk**. Pattern activation follows existing running/stopped timing;
a linked pattern kit may subsequently replace the selected kit. PERF is refreshed.
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

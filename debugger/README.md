# Musical debugger

Start the local debugger after installing SONATA:

```sh
sonata debug examples/sum.son --open
```

The default address is `http://127.0.0.1:8765`. Add `--port 8976` to use another
port. The interface uses packaged HTML, CSS, JavaScript, and original synthesis;
it does not fetch fonts, scripts, or audio from another site.

SONATA executes a bounded program first, then lets you navigate its recorded
trace. A breakpoint pauses playback before an event at that line. It does not
suspend a live interpreter, and editing a variable during playback is not
supported.

## Your first listening session

1. Choose `sum.son` from the example menu. The program runs automatically and
   returns `15`.
2. Press **Play**. Source highlighting, the selected event, variables, and call
   stack follow the sound.
3. Press **Step** to advance one event and audition its notes. The **Inspect
   event** slider also selects events, including events muted by a filter.
4. Click a note to inspect the source statement and state that produced it.
   Click source text to select the first event from that line, then use the
   previous/next controls under the editor to visit its other events.
5. Click a line number to set a breakpoint. Playback pauses before the next
   event on that line. Press Play to continue. A line can produce several events.
6. Change the source and press **Run source**. The old trace and export actions
   clear as soon as the text changes.

**Rewind** returns to beat zero and execution event zero, even when the opening
events are muted. After a completed performance, Play starts again.
Speed changes audition speed without changing recorded note times or
program semantics. Palette changes run the program again with the selected
sound palette. Responses from an earlier source or fixture are discarded.

## Inputs and selective listening

Open **Inputs and listening settings**. Input fixture A is a JSON array; the
program reads entries with `input(index)`. For example, enter `[5]` and run:

```sonata
let n = input(0);
let total = 0;
for i in 1..n+1 {
  total = total + i;
}
return total;
```

Fixture text is sent directly to Python before parsing, so an integer such as
`9007199254740993` retains its value. Large integers in the trace and output are
also displayed exactly. An example with an adjacent fixture file loads that
fixture automatically.

The default **Stable semantic motifs** mapping follows event, function, and
variable identities. **Original line motifs** retains the prototype's mapping.
Changing source formatting alone should be compared using the semantic mapping.

Enter comma-separated event kinds, function names, or variable names to focus
the sound. An empty field means all. Filters intersect: `assign` plus variable
`total` keeps assignments affecting `total`. Variable filters also retain events
where the watched value changes, including array mutations. All execution
events remain available in the inspector. Their original IDs and beat positions
remain unchanged, so a filtered passage may contain silence.

Set a variable name and numerical range to map that range into the melodic
vocabulary. Use `*` as the fallback range for numeric events without a named
range. An out-of-range value adds a chromatic cue; the inspector retains the
exact value. The browser accepts range endpoints that are safe JavaScript
integers and rejects larger values instead of rounding them. The Python profile
API supports signed 64-bit endpoints.

Press **Run with these settings** after changing the fixture or listening
fields. Editing them immediately invalidates the previous score. This prevents
a download or audition from silently using older settings.

## Compare two executions

Open **Compare two executions**, then press **Copy A to B**. This copies the
source and its fixture. Edit program B, its fixture, or both, and press
**Compare A and B**. Both runs use the same palette and listening profile.

Try changing the sum's loop from `1..n+1` to `1..n`. With fixture `[5]`, A returns
`15` and B returns `10`.

The comparison shows both sources, return values, and the first differing
semantic event. Source position changes alone do not count as a difference.
**Go to first divergence** selects that event, highlights its source lines,
and places a suggested region around it. A pink line marks the divergence in
the execution timeline.

**Listen to A** and **Listen to B** preserve the current beat, so you can switch
between the two executions at the same point. If playback is running, switching
sides resumes it. The source panel, variables, stack, output, and export buttons
follow the selected side. Program B is read-only in the main source panel;
edit it in the comparison panel. Each side has its own line breakpoints.

Enable **Loop region** to repeatedly hear the chosen passage. Type start and
end beats, or seek to a point and press **Set start** / **Set end**. The region
must fit in the score and have a positive length. The end is exclusive: notes
starting there are not scheduled in that repetition. Playback stops sustained
voices at the boundary and starts the region again. Breakpoints still pause
playback inside the region.

This comparison aligns executions by event position. It is useful for small
changes, but does not attempt to align differently structured algorithms or
prove that two programs are equivalent for every possible input.

## Compose an executable score

Switch from **Execution** to **Executable score**. The source panel shows the
canonical program, while the piano roll shows its reversible SC1 encoding.
Reserved operations have specified pitches; names and literals occupy sequences
of notes. Framing and checksum notes are also audible.

Below the piano roll, musical token cells show the token text and a small view
of its actual encoded pitches. Select a cell to seek to its notes. Long programs
use pages of 48 cells.

1. Select a cell such as the numeral `5`.
2. Enter `6` in **Token text** and press **Replace**. You can also insert a cell
   before or after the selection, or delete it.
3. Press **Validate and run score**. SONATA checks the token stream against its
   grammar, rebuilds framing and checksum notes, executes the result, and updates
   the source and score together.
4. If the draft is invalid, repair it or press **Discard edits**. The previous
   accepted source remains intact. Playback and exports stay disabled while a
   draft is unvalidated.

Each cell contains one token. A negative number uses separate `-` and numeral
cells. Editing B's score is done through Program B in the comparison panel.
Applying edits to A clears the old comparison because its result is now stale.

This editor works with SONATA's reserved musical grammar. Arbitrary songs and
ordinary MIDI recordings are not executable SONATA programs.

## Save the selected performance

| Button | Contents |
| --- | --- |
| WAV | Runtime performance with the selected palette and listening profile, as mono 16-bit PCM. |
| Runtime MIDI | The selected run's audible events, including filtering and range cues. |
| Executable MIDI | The full program encoded as an SC1 musical score. Runtime listening filters do not remove source instructions. |

When a comparison is open, exports use the currently selected A or B source and
fixture. Playback speed changes audition only; exports use the original
120 BPM timing. Browser audition uses Web Audio oscillators, while WAV export
uses the NumPy synthesizer. The pitches and timing correspond, but their timbres
differ.

## Keyboard and nonvisual controls

| Key or control | Action |
| --- | --- |
| Ctrl+Enter / Cmd+Enter | Run program A with the current settings. |
| Space outside form controls | Play or pause. |
| Right / Left Arrow outside form controls | Step forward / backward. |
| Home outside form controls | Rewind. |
| Escape | Pause, including while an editor is focused. |
| Tab / Shift+Tab | Move between controls and leave text editors. |
| Ctrl+] / Cmd+] in the source editor | Insert two spaces. |
| Inspect event slider | Select any execution event without clicking the piano roll. |

Buttons, line breakpoints, token cells, and inputs have keyboard focus states
and text labels. A skip link moves directly to the source editor. The event
slider, source, and state text provide alternatives to canvas interaction.
Hiding the browser tab pauses audio. Reduced-motion preferences are respected.
These features have automated state coverage; they do not establish that the
interface meets a particular accessibility standard or works with every screen
reader. User testing remains necessary.

## Bounds and verification

The browser uses execution limits suitable for interactive examples. A runtime
error retains its partial trace. The server validates inputs and settings and
accepts loopback requests only. Source and state use DOM text nodes.

Browser playback stops with a message if more than 512 oscillators would be
active together. WAV rendering has separate duration, note-count, and synthesis
work limits. A filtered trace can be completely silent; use Step or Inspect
event to examine it, or broaden the listening filters.

Run the browser state regression harness with:

```sh
python -m pytest -q tests/test_web_v1.py
```

It uses Node with DOM/audio stubs to test exact fixture transport, profile
validation, A/B source ownership and breakpoints, stale-response rejection,
score-edit failure and recovery, and loop scheduling boundaries. It skips when
Node is unavailable. It cannot verify layout, actual browser audio, or screen
reader behavior. The release verification records separate real-browser checks.

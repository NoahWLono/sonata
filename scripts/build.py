"""Rebuild recordings, verification reports and the self-contained showcase."""
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sonata.audio import render_wav
from sonata.codec import compile_program, import_program
from sonata.language import parse, canonical, format_source
from sonata.midi import write_midi
from sonata.music import sonify
from sonata.runtime import execute, Limits
from sonata.validation import verify


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def score_svg(notes, path):
    width, height = 1440, 330
    end = max(n["start"] + n["duration"] for n in notes)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Executable SONATA note score">', '<rect width="100%" height="100%" fill="#101b24"/>', '<text x="24" y="28" fill="#e9dcb8" font-family="monospace" font-size="16">SC1 / EXECUTABLE NOTE SCORE — operations · operand melodies · checksum</text>']
    for pitch in range(36, 109, 12):
        y = 285 - (pitch - 36) * 3
        parts.append(f'<path d="M50 {y} H1410" stroke="#2e4653"/><text x="12" y="{y+4}" fill="#889eaa" font-size="12">{pitch}</text>')
    for note in notes:
        x = 50 + note["start"] / end * 1350
        y = 285 - (note["pitch"] - 36) * 3
        color = ["#deb975", "#72c5b4", "#d19ad6"][note["channel"] % 3]
        parts.append(f'<rect x="{x:.3f}" y="{y}" width="{max(1.5,note["duration"]/end*1350):.3f}" height="4" fill="{color}"><title>{html.escape(str(note.get("token") or "framing"))} / MIDI {note["pitch"]} / beat {note["start"]}</title></rect>')
    parts.append(f'<text x="50" y="318" fill="#b5c6ce" font-family="monospace" font-size="12">{len(notes)} audible notes · {end:.2f} beats · quarter-note grid / 30720 PPQ · no program metadata</text></svg>')
    path.write_text("".join(parts))


def showcase(demos):
    out = ROOT / "audio" / "showcase"
    out.mkdir(exist_ok=True)
    a, b = demos["sum"], demos["off_by_one"]
    signature = lambda e: (e["kind"], e["depth"], e["data"], e["variables"])
    divergence = next((i for i, (x,y) in enumerate(zip(a["result"]["trace"], b["result"]["trace"])) if signature(x) != signature(y)), min(len(a["notes"]),len(b["notes"])))
    save_json(out / "comparison.json", {"first_divergent_event": divergence, "time_seconds": divergence * .125, "correct_result": 15, "defective_result": 10, "criterion": "First unequal kind, depth, event data or variable snapshot"})
    score_svg(a["code_notes"], out / "executable-score.svg")
    panels = []
    for index, (name, run) in enumerate((("sum", a), ("off_by_one", b))):
        source = (ROOT / "examples" / (name + ".son")).read_text()
        panels.append(f'<section><h2>{"Correct / 15" if index == 0 else "Off-by-one / 10"}</h2><pre>{html.escape(source)}</pre><audio id="audio{index}" controls src="../demos/{name}/execution.wav"></audio><p><a href="../demos/{name}/execution.mid">Execution MIDI</a> · <a href="../demos/{name}/code.mid">Executable source MIDI</a></p><canvas id="roll{index}" width="1000" height="230"></canvas><pre id="event{index}"></pre></section>')
    payload = json.dumps([{ "trace": d["result"]["trace"], "notes": d["notes"]} for d in (a,b)]).replace("</", "<\\/")
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>SONATA / One algorithm, three representations</title><style>
body{background:#101b24;color:#e9e4d7;font:16px system-ui;max-width:1400px;margin:40px auto;padding:20px}h1{font:48px Georgia}h2{color:#dec08a}a{color:#72c5b4}main{display:grid;grid-template-columns:1fr 1fr;gap:28px}pre{white-space:pre-wrap;font:14px monospace;background:#162631;padding:18px;min-height:130px}canvas{width:100%;background:#162631}audio{width:100%}button{padding:12px 22px;background:#dec08a;border:0;border-radius:5px;cursor:pointer}img{width:100%}@media(max-width:800px){main{grid-template-columns:1fr}}
</style><h1>One algorithm. Three representations.</h1><p>SONATA / source → executable note score → the sound of actual execution.</p><p>The upper bound changes from 6 to 5. The fifth addition disappears. A synchronized cursor follows each real recording.</p><button id="play">Play both from beginning</button><button id="pause">Pause both</button><p id="divergence"></p><main>''' + "".join(panels) + '''</main><h2>Executable musical notation</h2><p>This complete SC1 piano roll carries the source program in notes. Download the executable source MIDI above, then use <code>sonata decode</code> to recover and run it. Hover notes in <a href="executable-score.svg">the SVG score</a> for token labels. Gold: syntax; green: operands; violet: checksum.</p><img src="executable-score.svg" alt="Complete executable source note score"><p>Runtime sonification is intentionally lossy; source-code MIDI round trips preserve the canonical AST. Automated differences establish signal differences, not a human debugging benefit.</p><script>
const runs=PAYLOAD; const divergence=DIVERGENCE;
const players=[document.querySelector('#audio0'),document.querySelector('#audio1')];
document.querySelector('#play').onclick=()=>players.forEach(p=>{p.currentTime=0;p.play()});document.querySelector('#pause').onclick=()=>players.forEach(p=>p.pause());
function draw(){runs.forEach((run,i)=>{const canvas=document.querySelector('#roll'+i),c=canvas.getContext('2d');c.clearRect(0,0,1000,230);let duration=Math.max(...run.notes.map(n=>(n.start+n.duration)*.5));for(const n of run.notes){c.fillStyle=n.event_id>=divergence?'#da907e':'#72c5b4';c.fillRect(n.start*.5/duration*1000,210-(n.pitch-30)*3,Math.max(2,n.duration*.5/duration*1000),4)}c.fillStyle='#fff';c.fillRect(players[i].currentTime/duration*1000,0,2,230);const e=run.trace[Math.min(run.trace.length-1,Math.floor(players[i].currentTime/.125))];document.querySelector('#event'+i).textContent=JSON.stringify({event:e.id,line:e.line,kind:e.kind,variables:e.variables},null,2)});document.querySelector('#divergence').textContent='First differing execution event: '+divergence+' ('+(divergence*.125).toFixed(3)+' s). Orange notes follow the divergence.';requestAnimationFrame(draw)}draw();
</script></html>'''
    (out / "index.html").write_text(document.replace("PAYLOAD",payload).replace("DIVERGENCE",str(divergence)))


def build():
    demos, summaries = {}, {}
    for source_path in sorted((ROOT / "examples").glob("*.son")):
        name, source = source_path.stem, source_path.read_text()
        out = ROOT / "audio" / "demos" / name
        out.mkdir(parents=True, exist_ok=True)
        ast = parse(source)
        fixture = source_path.with_suffix(".json")
        inputs = json.loads(fixture.read_text()) if fixture.is_file() else None
        result = execute(ast, Limits(max_depth=12), inputs=inputs)
        notes = sonify(result["trace"])
        save_json(out / "trace.json", result)
        save_json(out / "notes.json", notes)
        code_notes = compile_program(ast, out / "code.mid")
        restored = import_program(out / "code.mid")
        assert canonical(ast) == canonical(restored)
        (out / "decoded.son").write_text(format_source(restored))
        write_midi(notes, out / "execution.mid")
        audio = render_wav(notes, out / "execution.wav")
        if name == "infinite_recursion":
            assert result["error"]["kind"] == "DepthLimit"
            save_json(out / "verification.json", {"bounded_demo": True, "error": result["error"], "max_depth": max(e["depth"] for e in result["trace"]), "canonical_ast_roundtrip": True, "independent_success_verification": "not applicable to intentional resource error"})
        else:
            report = verify(source, inputs=inputs)
            assert report["passed"], (name, report)
            save_json(out / "verification.json", report)
        summaries[name] = {"result": result["return_value"], "error": result["error"], "events": len(result["trace"]), "notes": len(notes), "audio": audio}
        demos[name] = {"result":result,"notes":notes,"code_notes":code_notes}
        print(f"Recorded {name}: {len(notes)} notes, {audio['duration']:.2f}s", flush=True)
    for palette in ("classical","electronic","ambient"):
        out = ROOT / "audio" / "palettes"
        out.mkdir(exist_ok=True)
        notes = sonify(demos["sum"]["result"]["trace"],palette)
        render_wav(notes,out/f"sum-{palette}.wav",palette=palette)
        write_midi(notes,out/f"sum-{palette}.mid",palette=palette)
    sorting = [e for e in demos["bubble_sort"]["result"]["trace"] if e["kind"] == "output"]
    for label,event in (("unsorted",sorting[0]),("intermediate",sorting[1]),("sorted",sorting[-1])):
        notes = sonify([dict(event,id=0)])
        out = ROOT / "audio" / "demos" / "bubble_sort"
        render_wav(notes,out/f"{label}.wav",bpm=30)
        write_midi(notes,out/f"{label}.mid",bpm=30)
    showcase(demos)
    save_json(ROOT / "audio" / "manifest.json",summaries)
    return demos


if __name__ == "__main__":
    build()

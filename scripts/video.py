"""Optional FFmpeg showcase with original execution audio and synchronized labels."""
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("fc-match"):
        print("Optional video skipped: FFmpeg/fontconfig unavailable; HTML showcase remains playable.")
        return
    out = ROOT / "audio" / "showcase"
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "audio" / "manifest.json").read_text())
    first = manifest["sum"]["audio"]["duration"] + 1
    duration = first + manifest["off_by_one"]["audio"]["duration"] + 1
    for name in ("sum", "off_by_one"):
        (out / f"{name}.txt").write_text((ROOT / "examples" / f"{name}.son").read_text())
    font = subprocess.check_output(["fc-match", "-f", "%{file}", "monospace"], text=True).strip()
    # Filter paths are repo-relative to avoid host path and filter escaping issues.
    graph = (
        "[0:a]adelay=1000[a0];[1:a]adelay=1000[a1];[a0][a1]concat=n=2:v=0:a=1[a];"
        "[a]asplit=2[aout][view];[view]showwaves=s=1280x180:mode=line:rate=30:colors=0x72c5b4,format=rgba[w];"
        f"color=c=0x101b24:s=1280x720:r=30:d={duration}[bg];[bg][w]overlay=0:480:shortest=1,"
        f"drawtext=fontfile={font}:text='SONATA / THE PROGRAMMING LANGUAGE YOU CAN HEAR':x=35:y=28:fontsize=26:fontcolor=0xdec08a,"
        f"drawtext=fontfile={font}:text='SOURCE - EXECUTABLE NOTES - ACTUAL EXECUTION AUDIO':x=35:y=72:fontsize=17:fontcolor=white,"
        f"drawtext=fontfile={font}:textfile=audio/showcase/sum.txt:x=35:y=150:fontsize=18:fontcolor=0x72c5b4,"
        f"drawtext=fontfile={font}:textfile=audio/showcase/off_by_one.txt:x=655:y=150:fontsize=18:fontcolor=0xda907e,"
        f"drawtext=fontfile={font}:text='NOW PLAYING - CORRECT / RESULT 15 / FIVE ADDITIONS':x=35:y=415:fontsize=22:fontcolor=0x72c5b4:enable='lt(t,{first})',"
        f"drawtext=fontfile={font}:text='NOW PLAYING - DEFECT / RESULT 10 / FOUR ADDITIONS':x=35:y=415:fontsize=22:fontcolor=0xda907e:enable='gte(t,{first})',"
        f"drawtext=fontfile={font}:text='Measured musical difference. Human debugging benefit remains untested.':x=35:y=680:fontsize=16:fontcolor=white[v]"
    )
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", "audio/demos/sum/execution.wav", "-i", "audio/demos/off_by_one/execution.wav", "-filter_complex", graph, "-map", "[v]", "-map", "[aout]", "-t", str(duration), "-c:v", "libx264", "-threads", "1", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "audio/showcase/sonata-demo.mp4"]
    subprocess.run(args, cwd=ROOT, check=True)
    print(f"Created audio/showcase/sonata-demo.mp4 ({duration:.3f}s)")


if __name__ == "__main__":
    main()

"""Buat narasi suara + timing per kata dari story JSON (pakai edge-tts, butuh internet).
Output: build/<nama>/scene_N.mp3 dan scene_N.json (daftar kata + waktu)."""
import asyncio, json, sys, pathlib
import edge_tts

async def one(text, voice, mp3, js):
    comm = edge_tts.Communicate(text, voice, boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7
                words.append({"text": ch["text"], "start": s, "end": s + ch["duration"] / 1e7})
    js.write_text(json.dumps(words, ensure_ascii=False))

async def main(path):
    story = json.loads(pathlib.Path(path).read_text())
    out = pathlib.Path("build") / pathlib.Path(path).stem
    out.mkdir(parents=True, exist_ok=True)
    voice = story.get("voice", "id-ID-ArdiNeural")
    items = [s["narration"] for s in story["scenes"]]
    if story.get("choices", {}).get("narration"):
        items.append(story["choices"]["narration"])
    for i, t in enumerate(items):
        await one(t, voice, out / f"scene_{i}.mp3", out / f"scene_{i}.json")
        print("tts", i, t[:40])

asyncio.run(main(sys.argv[1]))

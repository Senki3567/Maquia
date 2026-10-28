import json, glob, time, asyncio, httpx, re, os, sys

def get_headers():
    for pid in glob.glob("/proc/[0-9]*/environ"):
        try:
            with open(pid, "rb") as f:
                content = f.read()
                if b"OPENAPI_MCP_HEADERS" in content:
                    for item in content.split(b"\x00"):
                        if item.startswith(b"OPENAPI_MCP_HEADERS="):
                            return json.loads(item.decode("utf-8").split("=", 1)[1])
        except Exception:
            continue
    raise RuntimeError("Notion headers not found")

DB_ID = "405ea784-2f74-81a8-af66-c2baabef3e6d"
CHECKPOINT_FILE = "/tmp/notion_dialogue_checkpoint_v2.json"

def load_dialogues():
    with open("Maquia.vi.ass", "r", encoding="utf-8-sig", errors="ignore") as f:
        lines = [l.strip() for l in f if l.strip()]

    events = [e for e in lines if (e.startswith("Dialogue:") or e.startswith("Comment:")) and e.split(",", 4)[3] in ("Dialouge", "Dialouge - bord")]
    rows = []
    for idx, e in enumerate(events):
        parts = e.split(",", 9)
        start_time = parts[1].strip()
        end_time = parts[2].strip()
        actor = parts[4].strip() or " "
        m = re.match(r"^((?:\{[^}]*\})+)(.*)$", parts[9])
        tags = m.group(1) if m else ""
        dialogue = m.group(2) if m else parts[9]
        rows.append({
            "idx": idx,
            "stt": str(idx + 1),
            "actor": actor,
            "start": start_time,
            "end": end_time,
            "tag": tags,
            "dialogue": dialogue
        })
    return rows

async def main():
    headers = get_headers()
    dialogues = load_dialogues()
    total = len(dialogues)
    print(f"Loaded {total} dialogue lines.")

    completed_indices = set()
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r") as f:
                completed_indices = set(json.load(f))
            print(f"Resuming from checkpoint: {len(completed_indices)} rows already inserted.")
        except Exception:
            pass

    # Pacing: 2 workers, each sleeping 0.35s -> ~2.8 req/sec
    sem = asyncio.Semaphore(2)
    lock = asyncio.Lock()
    client = httpx.AsyncClient(headers=headers, timeout=60.0, limits=httpx.Limits(max_keepalive_connections=5, max_connections=10))

    async def insert_one(row):
        idx = row["idx"]
        if idx in completed_indices:
            return True

        payload = {
            "parent": {"database_id": DB_ID},
            "properties": {
                "STT": {"title": [{"text": {"content": row["stt"]}}]},
                "Actor": {"rich_text": [{"text": {"content": row["actor"]}}]},
                "Start": {"rich_text": [{"text": {"content": row["start"]}}]},
                "End": {"rich_text": [{"text": {"content": row["end"]}}]},
                "Tag": {"rich_text": [{"text": {"content": row["tag"]}}]},
                "Thoại": {"rich_text": [{"text": {"content": row["dialogue"]}}]}
            }
        }

        retries = 8
        backoff = 2.0
        while retries > 0:
            async with sem:
                try:
                    resp = await client.post("https://api.notion.com/v1/pages", json=payload)
                    if resp.status_code == 200:
                        async with lock:
                            completed_indices.add(idx)
                            if len(completed_indices) % 50 == 0 or len(completed_indices) == total:
                                print(f"Progress: {len(completed_indices)}/{total} rows inserted ({(len(completed_indices)/total)*100:.1f}%)", flush=True)
                                with open(CHECKPOINT_FILE, "w") as cf:
                                    json.dump(list(completed_indices), cf)
                        # Pacing
                        await asyncio.sleep(0.35)
                        return True
                    elif resp.status_code == 429:
                        try:
                            err_data = resp.json()
                            retry_after = float(err_data.get("additional_data", {}).get("retry_after", resp.headers.get("Retry-After", 5.0)))
                        except Exception:
                            retry_after = float(resp.headers.get("Retry-After", 5.0))
                        print(f"Row {idx}: Rate limited (429). Backing off {retry_after}s...", flush=True)
                        await asyncio.sleep(retry_after + 1.0)
                        retries -= 1
                    else:
                        print(f"Row {idx} error {resp.status_code}: {resp.text}", flush=True)
                        await asyncio.sleep(backoff)
                        backoff *= 1.5
                        retries -= 1
                except Exception as err:
                    print(f"Row {idx} exception: {err}", flush=True)
                    await asyncio.sleep(backoff)
                    backoff *= 1.5
                    retries -= 1
        return False

    t0 = time.time()
    chunk_size = 50
    for i in range(0, total, chunk_size):
        chunk = dialogues[i:i + chunk_size]
        results = await asyncio.gather(*[insert_one(r) for r in chunk])
        if not all(results):
            print(f"Warning: Some rows in chunk {i}-{i+len(chunk)} failed.", flush=True)

    elapsed = time.time() - t0
    print(f"All done! Inserted {len(completed_indices)}/{total} rows in {elapsed:.1f} seconds.", flush=True)
    await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())

import asyncio, base64, json
import sounddevice as sd
import numpy as np
import websockets

WS_URL = "ws://127.0.0.1:8001/v1/language/ws/ingest-voice"

SAMPLE_RATE = 16000
CHUNK_MS = 200
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)

USER_ID = "test_user"
SESSION_ID = "test_session_ws_001"

def float32_to_pcm16_bytes(x: np.ndarray) -> bytes:
    x = np.clip(x, -1.0, 1.0)
    pcm16 = (x * 32767).astype(np.int16)
    return pcm16.tobytes()

async def main():
    recv_task = None
    try:
        async with websockets.connect(WS_URL) as ws:
            await ws.send(json.dumps({
                "type": "start",
                "user_id": USER_ID,
                "session_id": SESSION_ID,
                "lang": "auto",
                "channel": "voice",
                "confidence_threshold": 0.3
            }))
            print("✅ Sent start. Speak now... (Ctrl+C to stop)")

            async def receiver():
                try:
                    async for msg in ws:
                        data = json.loads(msg)
                        t = data.get("type")
                        if t in ("stt_partial", "stt_final"):
                            print(f"[{t}] {data.get('text')}")
                        elif t == "orchestrator":
                            print("[orchestrator] got response keys:", list(data.get("payload", {}).keys()))
                        else:
                            print("[ws]", data)
                except asyncio.CancelledError:
                    # normal on shutdown
                    return

            recv_task = asyncio.create_task(receiver())

            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as stream:
                while True:
                    audio, _ = stream.read(CHUNK_SAMPLES)
                    chunk_bytes = float32_to_pcm16_bytes(audio[:, 0])
                    b64 = base64.b64encode(chunk_bytes).decode("utf-8")
                    await ws.send(json.dumps({"type": "audio", "audio_b64": b64}))

    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
    except asyncio.CancelledError:
        # also normal sometimes
        print("\n🛑 Cancelled (shutdown).")
    finally:
        if recv_task:
            recv_task.cancel()
            await asyncio.gather(recv_task, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())

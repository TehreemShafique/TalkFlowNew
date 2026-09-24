# ruff: noqa
import csv
import os
import random
import socket
import time
import uuid

import numpy as np
import soundfile as sf


def send_audiosocket(sock, msg_type, payload=b""):
    if len(payload) > 65535:
        raise ValueError("Payload too large")
    header = bytes([msg_type]) + len(payload).to_bytes(2, "big")
    sock.sendall(header + payload)

def float32_to_pcm16le(audio):
    audio = np.clip(audio, -1.0, 1.0)
    audio = (audio * 32767).astype(np.int16)
    return audio.tobytes()

def main():
    manifest_path = "/app/scripts/test_set/review.csv"
    utterances = []
    with open(manifest_path, "r", encoding="cp1252") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["expected_text"].strip():
                utterances.append(row)
                
    random.seed(42)
    target_count = int(os.environ.get("CALL_COUNT", "500"))
    if len(utterances) >= target_count:
        selected = random.sample(utterances, target_count)
    else:
        selected = [random.choice(utterances) for _ in range(target_count)]
    
    print(f"Testing {len(selected)} live utterances via AudioSocket...")
    
    port = int(os.environ.get("AUDIOSOCKET_PORT", "9019"))
    
    for i, item in enumerate(selected):
        wav_path = f"/app/scripts/test_set/{item['file']}"
        print(f"[{i+1}/{len(selected)}] Streaming {wav_path} (Expected: {item['expected_text']})")
        
        audio, sr = sf.read(wav_path)
        if sr == 16000:
            audio = audio[::2]
        elif sr != 8000:
            raise ValueError(f"Unsupported sample rate {sr}")
            
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", port))
        
        call_uuid = uuid.uuid4().bytes
        send_audiosocket(sock, 0x01, call_uuid) # UUID
        
        # Inject artificial silence in the middle of 30% of calls to trigger SPEECH_PENDING_END and RESUME
        inject_pause = random.random() < 0.3
        split_point = len(audio) // 2
        
        chunk_size = 320 # 40ms of 8kHz
        
        for idx in range(0, len(audio), chunk_size):
            chunk = audio[idx:idx+chunk_size]
            payload = float32_to_pcm16le(chunk)
            send_audiosocket(sock, 0x10, payload) # PCM_8K
            
            if inject_pause and idx < split_point and (idx + chunk_size) >= split_point:
                # We reached the middle, send 800ms of silence
                print(" -> Injecting 1500ms pause...")
                silence_chunk = np.zeros(chunk_size, dtype=np.float32)
                silence_payload = float32_to_pcm16le(silence_chunk)
                for _ in range(int(1500 / 40)):
                    send_audiosocket(sock, 0x10, silence_payload)
                    time.sleep(0.04)
                    
            time.sleep(0.04) # Realtime streaming
            
        # Send a bit of silence at the end to trigger natural VAD speech_end
        silence_chunk = np.zeros(chunk_size, dtype=np.float32)
        silence_payload = float32_to_pcm16le(silence_chunk)
        for _ in range(int(1500 / 40)):
            send_audiosocket(sock, 0x10, silence_payload)
            time.sleep(0.04)
            
        send_audiosocket(sock, 0x00) # TERMINATE
        sock.close()
        
        time.sleep(1) # Gap between calls

if __name__ == "__main__":
    main()


from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import numpy as np
import time
import anyio
import torch
import json
from model.guitar_model import TabCNN
from utils.tab_translation import tabs_to_front, make_preds_json
from utils.audio_preprocessing import AudioBuffer, preprocess_audio
from utils.create_message import create_response
from utils.simple_hueristics import get_most_likely_tab
from collections import deque
from utils.session_state_class import SessionState

app = FastAPI()
@app.get("/")
async def health_check():
    return {"status": "healthy"}

model = TabCNN()
checkpoint = torch.load("model/weights.pth", map_location="cpu")
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()

global_mean = np.load("global_mean.npy")
global_std = np.load("global_std.npy")

client_sample_rate = 44100
rolling_buffer = AudioBuffer(max_samples=(int(client_sample_rate*2.5)))

json_path = "test_logits.json"

@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    print("Accepted Client")
    try:
        print(global_mean)
        print(global_std)
        ## tab format = [(,), (,)]
        session = SessionState()
        prev_tab = []
        total_samples_processed = 0
        while True:
            message = await ws.receive()

            if "text" in message:
                data = json.loads(message["text"])
                if data.get("type") == "config":
                    client_sample_rate = data.get("sample_rate")
                    print("recieved config", client_sample_rate)
                    rolling_buffer.update_max_samples(int(client_sample_rate*2.5))
                    total_samples_processed = 0
                if data.get("type") == "end_stream":
                    front_json = tabs_to_front([])
                    print("FINISHED STREAM")
                    await ws.send_json(create_response(preds=make_preds_json([], []), notes=front_json, stream_end=True))
                    session = SessionState()
            elif "bytes" in message:
                try:                
                    chunk = np.frombuffer(message["bytes"], dtype=np.float32)
                    rolling_buffer.add_chunk(chunk)

                    total_samples_processed += len(chunk)
                    current_ms = int((total_samples_processed / client_sample_rate) * 1000)

                    if rolling_buffer.is_ready():
                        X = rolling_buffer.get_window()

                        processed_data = preprocess_audio(X, client_sr=client_sample_rate, global_mean=global_mean, global_std=global_std, session=session)
                        if torch.is_tensor(processed_data):
                            notes_output, strings_output = await anyio.to_thread.run_sync(lambda: model(processed_data.unsqueeze(0)))
                            likely_tab = get_most_likely_tab(note_logits=notes_output, string_logits=strings_output, prev_tab=prev_tab)
                            preds_json = make_preds_json(notes_output.tolist(), strings_output.tolist())
                            with open(json_path, "a") as f:
                                json.dump({"data" : preds_json, "timestamp" : current_ms}, f)
                                f.write("\n")
                            ## [(1, 3), (3, 5)]
                            if likely_tab:
                                front_json = tabs_to_front(likely_tab)
                                prev_tab = likely_tab
                                print(front_json)
                                await ws.send_json(create_response(preds=preds_json, notes=front_json))
                            else:
                                front_json = tabs_to_front([])
                                await ws.send_json(create_response(preds=preds_json, notes=front_json))
                        elif processed_data == None:
                            front_json = tabs_to_front([])
                            await ws.send_json(create_response(preds=make_preds_json([], []), notes=front_json))
                        else:
                            print("PREPROCESSING ERROR")
                            await ws.send_json(create_response(error="preprocessing"))
                except Exception as e:
                    print("No bytes")
                    await ws.send_json(create_response(error=e))

    except WebSocketDisconnect:
        print("Socket Disconnected")


def save_tensor_debug(X_numpy, label="hum"):
    # X_numpy should be your final processed shape (4, 51, 144)
    timestamp = int(time.time())
    filename = f"debug_{label}_{timestamp}.json"
    
    debug_data = {
        "label": label,
        "shape": X_numpy.shape,
        "min": float(X_numpy.min()),
        "max": float(X_numpy.max()),
        "mean": float(X_numpy.mean()),
        "data": X_numpy.tolist() # This makes it a nested list
    }
    
    with open(filename, "w") as f:
        json.dump(debug_data, f)
    print(f"--- Debug Tensor Saved: {filename} ---")
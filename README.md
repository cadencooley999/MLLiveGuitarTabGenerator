https://liveguitarmirror.web.app/ 

# Guitar Mirror

Guitar Mirror is a real-time AI-powered guitar transcription system that listens to live audio input and predicts guitar tabs as you play. It combines deep learning, streaming audio processing, and low-latency WebSocket communication to deliver near real-time musical feedback directly in the browser.

---

## Overview

Guitar Mirror captures audio from a user's microphone in the browser, streams it to a cloud-hosted inference API, and returns predicted guitar tab positions in real time.

The system is designed for:
- Live guitar practice feedback
- Learning and transcription assistance
- Real-time musical analysis

---

## Core Capabilities

### Real-Time Audio Streaming
- Audio is captured in small chunks from the browser
- Streams continuously over a WebSocket connection
- Supports configurable sample rates and buffering

### Deep Learning Inference
- Uses a custom PyTorch model (`TabCNN`)
- Processes spectrogram-like features derived from raw audio
- Outputs:
  - Note predictions
  - String predictions
  - Tab positions over time

### Low-Latency Cloud Inference
- Backend deployed on **Google Cloud Run**
- FastAPI WebSocket server handles streaming input
- Model runs on CPU with optimized batching
- Designed for continuous inference on rolling audio windows

---

## System Architecture

### Frontend
- Built with React + TypeScript (Vite)
- Captures microphone input using Web Audio API
- Sends Float32 audio buffers via WebSocket
- Renders live tab predictions in UI

### Backend
- FastAPI WebSocket server (`/ws`)
- PyTorch inference pipeline
- Rolling audio buffer system for temporal context
- Preprocessing pipeline:
  - Normalization
  - Feature extraction
  - Session-aware state tracking

### Deployment
- Containerized using Docker
- Hosted on Google Cloud Run
- Auto-scaling with per-request instances

---

## Model Architecture

The core model is a hybrid CNN + GRU + Attention network:

### Feature Extractor (CNN)
- 4-layer convolutional network
- Batch normalization + dropout
- Max pooling for temporal compression

### Temporal Modeling (GRU)
- Bidirectional GRU (hidden size 160)
- Captures time-based musical patterns

### Attention Layer
- Learns importance over time steps
- Produces weighted aggregation of sequence features

### Output Heads
- Note classification head (64 classes)
- String classification head (6 guitar strings)

---

## Training Pipeline (Summary)

The model was trained on labeled guitar audio data:

### Data Processing
- Raw audio converted into structured feature tensors
- Normalized using global mean and standard deviation
- Segmented into rolling windows

### Labels
- Guitar note positions (fret + string combinations)
- Temporal alignment with audio frames

### Training Strategy
- Cross-entropy loss for multi-head outputs
- Regularization:
  - Dropout (CNN + GRU + dense layers)
  - Batch normalization
- Optimization on GPU (training-time only)

---

## Real-Time Inference Flow

1. Browser captures microphone audio
2. Audio streamed via WebSocket to backend
3. Backend stores rolling buffer (2–3 seconds)
4. Audio chunk is preprocessed:
   - normalization
   - feature extraction
5. Model runs inference on CPU thread
6. Predictions are post-processed into tab format
7. Results streamed back to frontend UI

## Deployment Details

- Backend: Google Cloud Run (Python 3.11 + FastAPI)
- Frontend: Vite React app (Firebase Hosting ready)
- Model files included in container image
- WebSocket endpoint: ----

## Notes & Limitations

- CPU inference (no GPU acceleration yet)
- Latency depends on Cloud Run cold starts
- Performance varies with audio quality and noise
- Designed for real-time guidance, not studio-grade transcription

---

## Future Improvements

- GPU-enabled inference (Cloud Run GPU or Vertex AI)
- Streaming smoothing / debounce for stable tab output
- Multi-instrument support
- Improved dataset diversity
- Edge deployment for ultra-low latency
- User feedback loop for model fine-tuning

---

## Tech Stack

- **Frontend:** React, TypeScript, Vite
- **Backend:** FastAPI, WebSockets
- **ML:** PyTorch, NumPy, librosa
- **Infra:** Docker, Google Cloud Run
- **Realtime:** WebSockets, rolling buffers

---

## Summary

Guitar Mirror is a real-time musical intelligence system that listens, interprets, and visualizes guitar playing as live tablature using deep learning and cloud inference. It bridges signal processing and modern web infrastructure to create an interactive learning tool for musicians.

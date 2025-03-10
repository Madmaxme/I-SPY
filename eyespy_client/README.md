# EyeSpy Client

Face detection client component of the EyeSpy system. This client captures faces from your screen and sends them to the EyeSpy backend for processing.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure the backend server is running (see eyespy_server directory)

## Usage

Run the client:
```bash
python FotoRec_client.py
```

Options:
- `--url`: URL to open in Chrome (default: about:blank)
- `--skip-chrome`: Skip opening Chrome
- `--server`: Backend server URL (default: http://localhost:8000)

## Features

- Real-time face detection using screen capture
- Local face database to avoid duplicate uploads
- Backend connectivity checking
- Face image storage in the detected_faces directory

## Stopping

Press 'q' in the face monitoring window to stop the client.
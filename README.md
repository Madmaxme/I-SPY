# EyeSpy

A face detection and identity search system that monitors your screen for faces, saves them, and searches for their identities online.

## Client-Server Architecture

The system has been reorganized into a client-server architecture with separate directories:

- **eyespy_client/** - Contains the face detection client that captures faces from your screen
- **eyespy_server/** - Contains the backend processing server that handles face recognition and identity search

Each directory has its own README with detailed setup and usage instructions.

## Features

- **Screen Monitoring**: Capture faces from any part of your screen
- **Face Detection**: Automatically detect and save unique faces
- **Identity Search**: Search for identities on the web using FaceCheckID
- **Client-Server Architecture**: Separate client for face detection and server for processing
- **Duplicate Avoidance**: Client maintains local database of known faces
- **Multi-threaded Processing**: Server processes faces in background threads

## Requirements

- Python 3.7+
- API Keys:
  - FaceCheckID API key 
  - Firecrawl API key (optional)
  - OpenAI API key (for bio generation, optional)
  - Records API key (for record checking, optional)

## Directory Structure

```
EyeSpy/
├── README.md                # Main README with overview
├── eyespy_client/           # Client component
│   ├── FotoRec_client.py    # Client application
│   ├── README.md            # Client-specific instructions
│   ├── requirements.txt     # Client dependencies
│   └── detected_faces/      # Client's face storage (created on first run)
├── eyespy_server/           # Server component
│   ├── FaceUpload.py        # Face identity search
│   ├── backend_server.py    # Flask API server
│   ├── bio_integration.py   # Bio generation integration
│   ├── BioGenerator.py      # Bio generation functionality
│   ├── record_integration.py# Record checking integration
│   ├── RecordChecker.py     # Record checking functionality
│   ├── README.md            # Server-specific instructions
│   ├── requirements.txt     # Server dependencies
│   ├── uploaded_faces/      # Server's uploaded face storage (created on first run)
│   └── face_search_results/ # Server's results storage (created on first run)
```

## Quick Start Guide

1. Set up and start the server:
```bash
cd eyespy_server
pip install -r requirements.txt
python backend_server.py --port 5001
```

2. In a new terminal, set up and start the client:
```bash
cd eyespy_client
pip install -r requirements.txt
python FotoRec_client.py --server http://localhost:5001
```

## Data Flow

1. **Client**: Detects faces from screen captures
2. **Client**: Saves new unique faces locally in `eyespy_client/detected_faces/`
3. **Client**: Uploads new faces to the server
4. **Server**: Receives faces and saves them in `eyespy_server/uploaded_faces/`
5. **Server**: Processes faces to find identity matches
6. **Server**: Stores results in `eyespy_server/face_search_results/`

## Getting Started

See the README files in the respective directories for detailed setup and usage instructions:

- [Client Setup and Usage](eyespy_client/README.md)
- [Server Setup and Usage](eyespy_server/README.md)

## Testing

To test the system:
1. Start the server first, noting the port number
2. Start the client, pointing it to the server URL
3. Position a face on your screen
4. The client will detect faces, save them locally, and upload them to the server
5. The server will process the faces and save results
6. Check the output directories to verify results

## Deployment Options

### Local Development
- Run both client and server on the same machine
- Client connects to http://localhost:5001 (or whichever port you choose)

### Production Deployment
- Host the backend server on a cloud service
- Configure clients to connect to the remote server URL
- Set EYESPY_BACKEND_URL environment variable on clients

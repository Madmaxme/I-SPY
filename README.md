# EyeSpy

A face detection and identity search system that monitors your screen for faces, saves them, and searches for their identities online.

## Features

- **Screen Monitoring**: Capture faces from any part of your screen
- **Face Detection**: Automatically detect and save unique faces
- **Identity Search**: Search for identities on the web using FaceCheckID
- **Integrated System**: Combined face detection and processing pipeline
- **Queue Management**: Dynamic queue system to handle any volume of faces
- **Graceful Shutdown**: Proper shutdown sequence to ensure no faces are lost
- **Multi-threaded Processing**: Parallel processing for efficiency

## Requirements

- Python 3.7+
- Required packages: OpenCV, face_recognition, PIL, requests, etc.
- API Keys:
  - FaceCheckID API key 
  - Firecrawl API key (optional)

> **Note on FireCrawl Errors**: The system will work correctly even if you see FireCrawl errors like "Rate limit exceeded" or "website no longer supported". These errors just mean that some additional information about the identified people couldn't be scraped, but the face matching and organization will still work properly.

## Setup

1. Create a `.env` file with your API keys:
```
FACECHECK_API_TOKEN=your_facecheck_api_token
FIRECRAWL_API_KEY=your_firecrawl_api_key
```

2. Install required packages:
```
pip install opencv-python face_recognition pillow requests python-dotenv firecrawl-py
```

## Running the System

There are three ways to run the system:

### 1. Full System (Recommended)

Run the controller to manage both face detection and processing:

```bash
python controller.py --queue-size 100 --workers 2
```

Options:
- `--queue-size`: Maximum number of faces in the processing queue
- `--workers`: Number of parallel face processing workers

### 2. Face Detection Only

Run only the face detection component:

```bash
python FotoRec.py
```

This will capture faces but not search for identities.

### 3. Face Processing Only

Process previously detected faces:

```bash
python FaceUpload.py
```

Options:
- `--dir`: Directory containing face images
- `--limit`: Maximum number of faces to process
- `--force`: Process all faces, even if previously processed
- `--file`: Process a specific face file

## Stopping the System

The system handles graceful shutdown for proper termination:

1. Press `q` in the face monitoring window or Ctrl+C in the terminal
2. The system will:
   - Stop face detection first
   - Process any remaining faces in the queue
   - Shut down completely

## Architecture

The system consists of three main components:

1. **FotoRec**: Face detection from screen captures
2. **FaceUpload**: Face identity search using FaceCheckID
3. **Controller**: Manages communication between components

These are connected through a thread-safe queue system that ensures efficient processing.

## Output

- Detected faces are saved in `detected_faces/`
- Search results are organized by person in `face_search_results/`
  - Each person gets their own directory (named after them if possible)
  - Each person directory contains:
    - JSON result files with search details
    - An `images/` subfolder with all matching images
- Unknown faces or faces without clear identities go to `face_search_results/unknown/`

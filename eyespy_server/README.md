# EyeSpy Server

Backend server component of the EyeSpy system. This server receives face images from clients, processes them to find matches, and stores results.

## Setup (Local Installation)

1. Copy or symlink the following files from the root EyeSpy directory into this directory:
```
FaceUpload.py
bio_integration.py
record_integration.py
BioGenerator.py
RecordChecker.py
```

2. Create a `.env` file with your API keys:
```
FACECHECK_API_TOKEN=your_facecheck_api_token
FIRECRAWL_API_KEY=your_firecrawl_api_key
OPENAI_API_KEY=your_openai_api_key
RECORDS_API_KEY=your_records_api_key
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Docker Setup

1. Create a `.env` file with your API keys (see above) or copy from `.env.example`

2. Build and run with Docker Compose:
```bash
# Build the image
docker-compose build

# Start the server
docker-compose up -d

# View logs
docker-compose logs -f
```

3. Stop the server:
```bash
docker-compose down
```

## Usage (Local)

Run the server:
```bash
python backend_server.py
```

Options:
- `--token`: FaceCheckID API token (overrides .env file)
- `--firecrawl-key`: Firecrawl API key (overrides .env file)
- `--port`: Server port (default: 8000)

## API Endpoints

- `GET /api/health` - Health check endpoint
- `POST /api/upload_face` - Upload a face image for processing

## Features

- RESTful API for face upload
- Background processing of face images
- Integrations for bio generation and record checking
- Result storage in face_search_results directory

## Stopping

- Local: Use Ctrl+C in the terminal to stop the server
- Docker: Run `docker-compose down`
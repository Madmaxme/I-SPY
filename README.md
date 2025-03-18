# EyeSpy: AI-Powered Face Detection and Identity Search System

EyeSpy is a powerful face detection and identity search system that utilizes computer vision and web scraping to automatically detect faces from your screen (either from webcam or video files), save them locally, upload them to a backend server for processing, and search for potential identities online.

## 🔍 Key Features

- **Dual Detection Methods**: Monitor your screen in real-time or analyze recorded videos
- **AI-Powered Face Detection**: Uses AWS Rekognition for accurate face detection and indexing
- **Identity Search**: Integrates with FaceCheckID for online face matching
- **Scraping Capabilities**: Extracts information from matching web profiles
- **Bio Generation**: Creates AI-generated biographical summaries using OpenAI
- **Public Records Integration**: Optional records search capabilities
- **Client-Server Architecture**: Scalable design with database storage
- **Docker Support**: Easy deployment with containerization
- **Multi-threaded Processing**: Efficient background processing

## 🏗️ Architecture

EyeSpy uses a client-server architecture with two main components:

### 📱 Client Component (`eyespy_client/`)

- Captures screen content or processes video files
- Detects faces using AWS Rekognition
- Stores detected faces locally to avoid duplicates
- Uploads new faces to the backend server

### 🖥️ Server Component (`eyespy_server/`)

- Receives uploaded faces from clients
- Processes faces to find identity matches using FaceCheckID
- Optionally searches for public records
- Generates biographical information using OpenAI GPT-4
- Stores all results in a PostgreSQL database
- Provides RESTful API endpoints

## 🧰 Tech Stack

### Client
- **Python 3.9+**
- **OpenCV**: For image processing
- **AWS Rekognition**: For face detection and recognition
- **Boto3**: AWS SDK for Python
- **Requests**: For HTTP communication with the server

### Server
- **Python 3.9+**
- **Flask**: Web framework for the API
- **PostgreSQL**: Database for storing results
- **Docker & Docker Compose**: Containerization
- **Gunicorn**: WSGI HTTP Server
- **OpenAI API**: For bio generation
- **FaceCheckID API**: For face search
- **Firecrawl**: For web scraping

## 🔧 Setup and Installation

### Prerequisites

1. Python 3.9+
2. AWS Account with Rekognition access
3. API Keys:
   - AWS credentials (for the client)
   - FaceCheckID API key (for the server)
   - OpenAI API key (optional, for bio generation)
   - Firecrawl API key (optional, for enhanced web scraping)
   - Records API key (optional, for public records search)
4. PostgreSQL database (or use the included Cloud SQL Proxy)

### Client Setup

1. Navigate to the client directory:
   ```bash
   cd eyespy_client
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables (create a `.env` file):
   ```
   AWS_ACCESS_KEY=your_aws_access_key
   AWS_SECRET_KEY=your_aws_secret_key
   AWS_REGION=eu-west-1
   EYESPY_BACKEND_URL=http://localhost:8080
   ```

### Server Setup

#### Local Installation

1. Navigate to the server directory:
   ```bash
   cd eyespy_server
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables (create a `.env` file):
   ```
   FACECHECK_API_TOKEN=your_facecheck_api_token
   OPENAI_API_KEY=your_openai_api_key
   FIRECRAWL_API_KEY=your_firecrawl_api_key
   RECORDS_API_KEY=your_records_api_key
   
   # Database configuration
   DATABASE_URL=postgresql://username:password@localhost:5432/eyespy
   # OR individual settings
   DB_USER=your_db_user
   DB_PASS=your_db_password
   DB_NAME=eyespy
   DB_HOST=localhost
   DB_PORT=5432
   ```

#### Docker Installation

1. Navigate to the server directory:
   ```bash
   cd eyespy_server
   ```

2. Create a `.env` file with the same variables as above.

3. Build and start the containers:
   ```bash
   docker-compose build
   docker-compose up -d
   ```

## 🚀 Usage

### Running the Server

#### Local Mode

```bash
cd eyespy_server
python backend_server.py --port 8080
```

#### Docker Mode

```bash
cd eyespy_server
docker-compose up -d
```

### Running the Client

#### Photo Capture Mode

```bash
cd eyespy_client
python FotoRec_client.py --server http://localhost:8080
```

#### Video Analysis Mode

```bash
cd eyespy_client
python VideoRec_client.py --server http://localhost:8080 --video path/to/video.mp4
```

### Client Controls

- Press 'q' to quit
- Press 'p' to pause/resume processing
- Press 's' to take a screenshot
- Press '+'/'-' to increase/decrease video playback speed
- Press 'd'/'f' to decrease/increase face indicator display time

## 🗄️ Data Flow

1. **Client**: Detects faces from screen or video
2. **Client**: Checks if the face is new using AWS Rekognition
3. **Client**: Saves new unique faces locally
4. **Client**: Uploads new faces to the server
5. **Server**: Processes faces to find identity matches using FaceCheckID
6. **Server**: Scrapes information from matching websites
7. **Server**: Optionally performs public records search
8. **Server**: Generates biographical summaries using OpenAI
9. **Server**: Stores all results in PostgreSQL database

## 🔌 API Endpoints

- **GET /api/health**: Health check endpoint
- **GET /**: Root endpoint returning server status
- **POST /api/upload_face**: Upload a face image for processing

## 📦 Directory Structure

```
EyeSpy/
├── README.md                # Main README with overview
├── eyespy_client/           # Client component
│   ├── FotoRec_client.py    # Screen monitoring client
│   ├── VideoRec_client.py   # Video analysis client
│   ├── README.md            # Client-specific instructions
│   ├── requirements.txt     # Client dependencies
│   └── detected_faces/      # Local face storage
├── eyespy_server/           # Server component
│   ├── backend_server.py    # Flask API server
│   ├── FaceUpload.py        # Face identity search
│   ├── bio_integration.py   # Bio generation integration
│   ├── BioGenerator.py      # Bio generation functionality
│   ├── NameResolver.py      # Name resolution logic
│   ├── record_integration.py# Record checking integration
│   ├── RecordChecker.py     # Record checking functionality
│   ├── db_connector.py      # Database connectivity
│   ├── Dockerfile           # Server containerization
│   ├── docker-compose.yml   # Container orchestration
│   ├── startup.sh           # Server startup script
│   ├── README.md            # Server-specific instructions
│   ├── requirements.txt     # Server dependencies
│   └── face_search_results/ # Server's results storage
```

## 🚨 Security and Privacy Considerations

- All data is stored locally or in your controlled database
- API keys should be kept secure and never committed to repositories
- Face data processing should comply with applicable privacy laws
- Use appropriate access controls for the database and API endpoints
- Consider implementing authentication for production deployments

## 📋 Deployment Options

### Development

- Run both client and server on the same machine
- Use local PostgreSQL or SQLite database
- Point client to http://localhost:8080

### Production

- Host the backend server on a cloud service (Google Cloud Run, AWS, etc.)
- Use a managed database service
- Set up proper authentication and HTTPS
- Configure clients to connect to the secure endpoint

## 🔧 Troubleshooting

- **Client-Server Connection Issues**: Verify the server URL and network connectivity
- **Database Connection Issues**: Check database credentials and connection string
- **AWS Authentication Errors**: Verify AWS credentials and permissions
- **Face Detection Problems**: Ensure adequate lighting and face visibility
- **API Rate Limiting**: Some APIs (FaceCheckID, OpenAI) have rate limits

## ⚖️ License

This project is intended for educational and research purposes only. Use of this software must comply with applicable laws and terms of service for all integrated APIs and services.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests with improvements or bug fixes.
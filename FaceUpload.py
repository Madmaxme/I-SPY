import os
import time
import json
import base64
import requests
import argparse
import glob
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import urllib.parse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Try importing firecrawl, provide installation instructions if not found
try:
    from firecrawl import FirecrawlApp
    FIRECRAWL_AVAILABLE = True
    print("Firecrawl module found and imported successfully")
except ImportError:
    FIRECRAWL_AVAILABLE = False
    print("Firecrawl package not found. Please install using: pip install firecrawl-py")
    print("Continuing without Firecrawl integration...")

# FaceCheckID API Configuration
TESTING_MODE = False  # Set to False for production use
APITOKEN = os.getenv('FACECHECK_API_TOKEN')

# Firecrawl API Configuration
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')

# Default directory for detected faces (should match FotoRec.py save_dir)
DEFAULT_FACES_DIR = "detected_faces"

# Directory to store search results
RESULTS_DIR = "face_search_results"

# File to track processed faces
PROCESSED_FACES_FILE = "processed_faces.json"

def setup_directories():
    """Create necessary directories if they don't exist"""
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)
        print(f"Created results directory: {RESULTS_DIR}")
    
    # Create a temporary directory for storing images before organizing
    temp_images_dir = os.path.join(RESULTS_DIR, "temp_images")
    if not os.path.exists(temp_images_dir):
        os.makedirs(temp_images_dir)
        
    # Create an 'unknown' directory for results that don't match anyone
    unknown_dir = os.path.join(RESULTS_DIR, "unknown")
    if not os.path.exists(unknown_dir):
        os.makedirs(unknown_dir)
        
    unknown_images_dir = os.path.join(unknown_dir, "images")
    if not os.path.exists(unknown_images_dir):
        os.makedirs(unknown_images_dir)
        
    return temp_images_dir

def load_processed_faces():
    """Load the list of already processed face files"""
    if os.path.exists(PROCESSED_FACES_FILE):
        try:
            with open(PROCESSED_FACES_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading processed faces file: {e}")
    
    return []

def save_processed_faces(processed_faces):
    """Save the updated list of processed face files"""
    try:
        with open(PROCESSED_FACES_FILE, 'w') as f:
            json.dump(processed_faces, f)
    except Exception as e:
        print(f"Error saving processed faces file: {e}")

def get_unprocessed_faces(faces_dir, processed_faces):
    """Get list of face image files that haven't been processed yet"""
    # Get all image files in the faces directory
    image_files = glob.glob(os.path.join(faces_dir, "face_*.jpg"))
    
    # Filter out already processed files
    unprocessed = [file for file in image_files if file not in processed_faces]
    
    return unprocessed

def search_by_face(image_file, timeout=300):
    """
    Search FaceCheckID API using a face image
    
    Args:
        image_file: Path to the image file
        timeout: Maximum time in seconds to wait for search (default: 5 minutes)
    
    Returns:
        Tuple of (error_message, search_results)
    """
    mode_message = "****** TESTING MODE search, results are inaccurate, and queue wait is long, but credits are NOT deducted ******" if TESTING_MODE else "PRODUCTION MODE: Credits will be deducted for this search"
    print(f"\n{mode_message}")
    
    site = 'https://facecheck.id'
    headers = {'accept': 'application/json', 'Authorization': APITOKEN}
    
    # Step 1: Upload the image
    try:
        with open(image_file, 'rb') as img_file:
            files = {'images': img_file, 'id_search': None}
            response = requests.post(site + '/api/upload_pic', headers=headers, files=files).json()
    except Exception as e:
        return f"Error uploading image: {str(e)}", None
    
    if response.get('error'):
        return f"{response['error']} ({response['code']})", None
    
    id_search = response['id_search']
    print(response['message'] + ' id_search=' + id_search)
    
    # Step 2: Run the search with timeout
    json_data = {
        'id_search': id_search,
        'with_progress': True,
        'status_only': False,
        'demo': TESTING_MODE
    }
    
    start_time = time.time()
    last_progress = -1
    
    while True:
        # Check if timeout exceeded
        if time.time() - start_time > timeout:
            return f"Search timed out after {timeout} seconds", None
        
        try:
            response = requests.post(site + '/api/search', headers=headers, json=json_data).json()
        except Exception as e:
            return f"Error during search: {str(e)}", None
        
        if response.get('error'):
            return f"{response['error']} ({response['code']})", None
        
        if response.get('output'):
            return None, response['output']['items']
        
        # Only print progress if it's changed
        current_progress = response.get('progress', 0)
        if current_progress != last_progress:
            print(f"{response['message']} progress: {current_progress}%")
            last_progress = current_progress
        
        # Sleep for a bit to avoid hammering the API
        time.sleep(1)

def save_thumbnail_from_base64(base64_str, filename):
    """Save Base64 encoded image to file"""
    try:
        # Extract the actual base64 content (after the comma)
        if ',' in base64_str:
            base64_content = base64_str.split(',', 1)[1]
        else:
            base64_content = base64_str
        
        # Decode and save
        image_data = base64.b64decode(base64_content)
        with open(filename, 'wb') as f:
            f.write(image_data)
        return True
    except Exception as e:
        print(f"Error saving thumbnail: {e}")
        return False

def collect_fallback_urls(search_results: List[Dict], primary_index: int) -> List[str]:
    """
    Collect fallback URLs from search results that aren't the primary one
    
    Args:
        search_results: List of search results from FaceCheckID
        primary_index: Index of the primary result being processed
        
    Returns:
        List of fallback URLs to try
    """
    fallback_urls = []
    
    try:
        # Skip the primary URL we already tried
        for i, result in enumerate(search_results):
            if i != primary_index and result.get('url'):
                fallback_urls.append(result.get('url'))
    except Exception as e:
        print(f"Error collecting fallback URLs: {e}")
    
    return fallback_urls

def scrape_with_firecrawl(url: str, fallback_urls: List[str] = None) -> Optional[Dict[str, Any]]:
    """
    Scrape a URL using Firecrawl to extract information about the person.
    If scraping fails and fallback_urls are provided, attempts to scrape those.
    
    Args:
        url: The primary URL to scrape
        fallback_urls: A list of alternative URLs to try if the primary fails
        
    Returns:
        Dictionary containing the scraped information or None if all scraping failed
    """
    global FIRECRAWL_AVAILABLE
    
    if not FIRECRAWL_AVAILABLE:
        print("Firecrawl not available. Skipping web scraping.")
        return None
    
    # Skip if the API key isn't set
    if not FIRECRAWL_API_KEY or FIRECRAWL_API_KEY == 'YOUR_FIRECRAWL_API_KEY':
        print("Firecrawl API key not set. Skipping web scraping.")
        return None
    
    # Initialize a list of URLs to try, starting with the primary URL
    urls_to_try = [url]
    
    # Add any fallback URLs if provided
    if fallback_urls:
        urls_to_try.extend(fallback_urls)
    
    # Try each URL in sequence until one succeeds
    for current_url in urls_to_try:
        try:
            # Skip empty or invalid URLs
            if not current_url or not current_url.startswith(('http://', 'https://')):
                continue
                
            print(f"Scraping {current_url} with Firecrawl...")
            
            # Initialize Firecrawl
            firecrawl_app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
            
            # Define the extraction prompt rather than using a schema
            # This approach is more flexible and works better with Firecrawl
            extraction_prompt = """
            Extract the following information about the person featured in this page:
            - Full name of the person
            - Description or bio
            - Job, role, or occupation
            - Location information
            - Social media handles or usernames
            - Age or birthdate information
            - Organizations or companies they're affiliated with
            
            If the page is a social media profile, extract the profile owner's information.
            If the page is a news article or blog post, extract information about the main person featured.
            If certain information isn't available, that's okay.
            """
            
            # Parameters for scraping with prompt-based extraction
            params = {
                'formats': ['json', 'markdown'],
                'jsonOptions': {
                    'prompt': extraction_prompt
                }
            }
            
            result = firecrawl_app.scrape_url(current_url, params)
            
            if result and 'json' in result and result['json']:
                print(f"Successfully scraped person information from {current_url}")
                return {
                    'person_info': result.get('json', {}),
                    'page_content': result.get('markdown', ''),
                    'metadata': result.get('metadata', {}),
                    'source_url': current_url  # Track which URL was actually used
                }
            else:
                print(f"No structured data returned from Firecrawl for {current_url}, trying next URL if available")
                
        except Exception as e:
            print(f"Error scraping {current_url} with Firecrawl: {e}")
            # Continue to the next URL
    
    # If we get here, all URLs failed
    print("All scraping attempts failed")
    return None

def analyze_search_result(result: Dict[str, Any], result_index: int, temp_images_dir: str = None, fallback_urls: List[str] = None) -> Dict[str, Any]:
    """
    Analyze a single search result to extract identity information
    
    Args:
        result: Single result from FaceCheckID
        result_index: Index number of this result
        temp_images_dir: Directory to temporarily save images (will be moved later)
        fallback_urls: A list of fallback URLs to try if scraping the primary URL fails
        
    Returns:
        Dictionary with enriched information
    """
    url = result.get('url', '')
    score = result.get('score', 0)
    
    # Save the thumbnail image
    base64_str = result.get('base64', '')
    thumbnail_path = None
    
    if base64_str:
        # If no specific directory is provided, use the default temporary directory
        if not temp_images_dir:
            # Make sure the images directory exists
            temp_images_dir = os.path.join(RESULTS_DIR, "temp_images")
            if not os.path.exists(temp_images_dir):
                os.makedirs(temp_images_dir)
            
        thumbnail_filename = f"result_{result_index}_{result.get('guid', 'unknown')}.webp"
        thumbnail_path = os.path.join(temp_images_dir, thumbnail_filename)
        if save_thumbnail_from_base64(base64_str, thumbnail_path):
            print(f"Saved temporary thumbnail image")
    
    # Get identity sources
    sources = get_identity_sources(url)
    source_type = sources[0] if sources else "Unknown source"
    
    # Scrape the URL if Firecrawl is available, with fallbacks
    scraped_data = scrape_with_firecrawl(url, fallback_urls)
    
    # Combine all information
    analysis = {
        'url': url,
        'score': score,
        'source_type': source_type,
        'thumbnail_path': thumbnail_path,
        'scraped_data': scraped_data
    }
    
    return analysis

def get_identity_sources(url: str) -> List[str]:
    """
    Determine possible identity sources based on the URL
    
    Args:
        url: The URL to analyze
        
    Returns:
        List of potential identity source types
    """
    domain = extract_domain(url).lower()
    
    sources = []
    
    # Social media platforms
    if any(sm in domain for sm in ['facebook', 'fb.com']):
        sources.append('Facebook profile')
    elif 'instagram' in domain:
        sources.append('Instagram profile')
    elif 'twitter' in domain or 'x.com' in domain:
        sources.append('Twitter/X profile')
    elif 'linkedin' in domain:
        sources.append('LinkedIn profile')
    elif 'tiktok' in domain:
        sources.append('TikTok profile')
    elif 'youtube' in domain:
        sources.append('YouTube channel')
    
    # News and media
    if any(news in domain for news in ['news', 'article', 'post', 'blog', 'thesun', 'daily', 'times', 'herald', 'cnn', 'bbc']):
        sources.append('News article')
    
    # Default if none matched
    if not sources:
        sources.append('Web page')
    
    return sources

def extract_domain(url: str) -> str:
    """Extract the main domain from a URL"""
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc
        return domain
    except:
        return url

def process_single_face(image_file, timeout=300):
    """
    Process a single face image
    
    Args:
        image_file: Path to the face image file
        timeout: Maximum time to wait for search results
        
    Returns:
        True if processing was successful, False otherwise
    """
    if not os.path.exists(image_file):
        print(f"Error: Face file '{image_file}' does not exist!")
        return False
    
    print(f"Processing: {os.path.basename(image_file)}")
    
    try:
        # Set up directories and get temp directory
        temp_images_dir = setup_directories()
        
        # Search for the face with timeout
        error, search_results = search_by_face(image_file, timeout=timeout)
        
        if search_results:
            # Print the search results summary
            print(f"Found {len(search_results)} potential matches")
            
            # Process each result to get identity information
            identity_analyses = []
            
            # Process top 5 results (original limit) with fallback functionality
            for j, result in enumerate(search_results[:5], 1):  # Process top 5 results
                # Collect fallback URLs from other results
                fallback_urls = collect_fallback_urls(search_results, j-1)
                
                # Analyze this result with temp directory and fallback URLs
                analysis = analyze_search_result(result, j, temp_images_dir, fallback_urls)
                identity_analyses.append(analysis)
            
            # Save the results with enhanced information
            results_data = {
                "source_image": image_file,
                "search_timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "original_results": search_results,
                "identity_analyses": identity_analyses
            }
            
            # Extract the basename without extension and path - this will be our directory name
            base_image_name = os.path.basename(image_file)
            base_image_name = os.path.splitext(base_image_name)[0]  # Remove extension
            
            # Create a simple directory based only on the input file name
            person_dir = os.path.join(RESULTS_DIR, base_image_name)
            if not os.path.exists(person_dir):
                os.makedirs(person_dir)
                print(f"Created results directory: {person_dir}")
            
            # Create an images subfolder for the results
            images_dir = os.path.join(person_dir, "images")
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)
            
            # Move result thumbnails to the folder
            for i, analysis in enumerate(identity_analyses):
                if analysis.get('thumbnail_path'):
                    # Copy the thumbnail to the folder
                    original_thumb = analysis['thumbnail_path']
                    if os.path.exists(original_thumb):
                        new_thumb_name = f"match_{i+1}_{os.path.basename(original_thumb)}"
                        new_thumb_path = os.path.join(images_dir, new_thumb_name)
                        try:
                            import shutil
                            shutil.copy2(original_thumb, new_thumb_path)
                            # Update the path in the analysis
                            analysis['thumbnail_path'] = new_thumb_path
                        except Exception as e:
                            print(f"Error copying thumbnail: {e}")
            
            # Generate result filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = os.path.join(person_dir, f"results_{timestamp}.json")
            
            # Save to file
            with open(results_file, 'w') as f:
                json.dump(results_data, f, indent=2)
            print(f"Results saved to {results_file} (Directory: {base_image_name})")
            
            # Mark as processed
            processed_faces = load_processed_faces()
            if image_file not in processed_faces:
                processed_faces.append(image_file)
                save_processed_faces(processed_faces)
            
            # Clean up temp directory if it exists
            try:
                import shutil
                if os.path.exists(temp_images_dir):
                    shutil.rmtree(temp_images_dir)
                    # Recreate it for future use
                    os.makedirs(temp_images_dir)
            except Exception as e:
                print(f"Warning: Could not clean up temporary files: {e}")
                
            return True
        else:
            print(f"Search failed: {error}")
            return False
    
    except Exception as e:
        print(f"Error processing face {os.path.basename(image_file)}: {e}")
        return False

def process_faces(faces_dir, limit=None, force=False, timeout=300):
    """Process face images and search for matches
    
    Args:
        faces_dir: Directory containing face images
        limit: Maximum number of faces to process
        force: Process all faces even if previously processed
        timeout: Maximum time in seconds to wait for each search
    """
    processed_faces = [] if force else load_processed_faces()
    
    # Get unprocessed face images
    unprocessed_files = get_unprocessed_faces(faces_dir, processed_faces)
    
    if not unprocessed_files:
        print("No new faces to process.")
        return
    
    print(f"Found {len(unprocessed_files)} unprocessed face images.")
    
    # Apply limit if specified
    if limit and limit > 0:
        unprocessed_files = unprocessed_files[:limit]
        print(f"Processing first {limit} images...")
    
    for i, image_file in enumerate(unprocessed_files, 1):
        print(f"\n[{i}/{len(unprocessed_files)}] Processing: {os.path.basename(image_file)}")
        
        try:
            # Process single face with the new method
            success = process_single_face(image_file, timeout=timeout)
            
            if not success:
                print(f"Failed to process: {image_file}")
            
        except KeyboardInterrupt:
            print("\nProcess interrupted by user. Saving progress...")
            # Save progress before exiting
            if image_file not in processed_faces:
                processed_faces.append(image_file)
                save_processed_faces(processed_faces)
            print("You can resume processing later.")
            raise

def queue_worker(face_queue, shutdown_event=None, timeout=300):
    """
    Worker function that processes faces from a queue
    
    Args:
        face_queue: Queue to get face images from
        shutdown_event: Event to signal shutdown
        timeout: Search timeout in seconds
    """
    print(f"[FACEUPLOAD] Face processing worker started")
    print(f"[FACEUPLOAD] Worker ready to process faces")
    
    # Set up necessary directories
    setup_directories()
    
    try:
        while True:
            # Check if shutdown is requested and queue is empty
            if shutdown_event and shutdown_event.is_set() and face_queue.is_empty():
                print("[FACEUPLOAD] Shutdown requested and queue empty, stopping worker...")
                break
                
            try:
                # Get a face from the queue (with timeout to check for shutdown)
                print("[FACEUPLOAD] Checking queue for faces...")
                face_path = face_queue.get(block=True, timeout=2.0)
                
                # Process the face
                try:
                    print(f"[FACEUPLOAD] Processing face from queue: {os.path.basename(face_path)}")
                    success = process_single_face(face_path, timeout=timeout)
                    
                    # Mark the task as done regardless of success
                    face_queue.task_done()
                    
                    if success:
                        print(f"[FACEUPLOAD] Successfully processed: {os.path.basename(face_path)}")
                    else:
                        print(f"[FACEUPLOAD] Failed to process: {os.path.basename(face_path)}")
                        
                except Exception as e:
                    print(f"[FACEUPLOAD] Error processing face from queue: {e}")
                    face_queue.task_done()
            except queue.Empty:
                # Queue.get timed out, which is expected for the polling loop
                print("[FACEUPLOAD] No faces in queue, waiting...")
                # Sleep a bit longer to reduce log spam
                time.sleep(2.0)
            
    except KeyboardInterrupt:
        print("Worker interrupted by user")
        
    except Exception as e:
        print(f"Worker encountered an error: {e}")
        
    finally:
        print("Face processing worker stopped")

def main(face_queue=None, shutdown_event=None):
    """
    Main function to run the face upload and search tool
    
    Args:
        face_queue: Optional queue to get faces from (for worker mode)
        shutdown_event: Optional event to signal shutdown
    """
    # Skip argument parsing if we're called with a queue (worker mode)
    if face_queue:
        print(f"Running in worker mode with provided queue (Queue object type: {type(face_queue).__name__})")
        print(f"Queue size: {face_queue.queue.qsize()}")
        # Set up necessary directories
        setup_directories()
        # Start the worker
        queue_worker(face_queue, shutdown_event, timeout=300)
        return

    # Only parse arguments when running standalone
    parser = argparse.ArgumentParser(description='Upload detected faces to FaceCheckID and search for matches')
    parser.add_argument('--dir', default=DEFAULT_FACES_DIR, help='Directory containing face images')
    parser.add_argument('--limit', type=int, help='Limit the number of faces to process')
    parser.add_argument('--force', action='store_true', help='Process all faces, even if previously processed')
    parser.add_argument('--token', help='FaceCheckID API token')
    parser.add_argument('--firecrawl-key', help='Firecrawl API key')
    parser.add_argument('--timeout', type=int, default=300, help='Search timeout in seconds (default: 300)')
    parser.add_argument('--skip-scrape', action='store_true', help='Skip web scraping even if Firecrawl is available')
    parser.add_argument('--file', help='Process a specific face file instead of all unprocessed faces')
    parser.add_argument('--worker', action='store_true', help='Run in worker mode (requires parent process)')
    args = parser.parse_args()
    
    # Set up the API tokens
    global APITOKEN, FIRECRAWL_API_KEY, FIRECRAWL_AVAILABLE
    if args.token:
        APITOKEN = args.token
    if args.firecrawl_key:
        FIRECRAWL_API_KEY = args.firecrawl_key
    
    # Override Firecrawl availability if requested
    if args.skip_scrape:
        FIRECRAWL_AVAILABLE = False
        print("Web scraping disabled by command line argument")
    
    # Set up necessary directories
    setup_directories()
    
    # If worker mode requested but no queue provided, error out
    if args.worker:
        print("Worker mode requested but no queue provided. This mode should only be used from controller.py")
        return
    
    # Handle single file processing if specified
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: Specified file '{args.file}' does not exist!")
            return
        
        process_single_face(args.file, args.timeout)
        return
    
    # Check if faces directory exists for batch processing
    if not os.path.exists(args.dir):
        print(f"Error: Faces directory '{args.dir}' does not exist!")
        print(f"Make sure FotoRec.py has run and saved faces, or specify a different directory with --dir")
        return
    
    # Process face images
    process_faces(args.dir, args.limit, args.force, args.timeout)
    
    print("\nProcessing complete!")
    print(f"Results have been saved to the '{RESULTS_DIR}' directory.")

if __name__ == "__main__":
    # When run directly, no queue is provided
    main(face_queue=None, shutdown_event=None)
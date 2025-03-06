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
    
    # Create a directory for storing extracted images
    images_dir = os.path.join(RESULTS_DIR, "images")
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)
        print(f"Created images directory: {images_dir}")

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

def scrape_with_firecrawl(url: str) -> Optional[Dict[str, Any]]:
    """
    Scrape a URL using Firecrawl to extract information about the person
    
    Args:
        url: The URL to scrape
    
    Returns:
        Dictionary containing the scraped information or None if scraping failed
    """
    global FIRECRAWL_AVAILABLE
    
    if not FIRECRAWL_AVAILABLE:
        print("Firecrawl not available. Skipping web scraping.")
        return None
    
    # Skip if the API key isn't set
    if FIRECRAWL_API_KEY == 'YOUR_FIRECRAWL_API_KEY':
        print("Firecrawl API key not set. Skipping web scraping.")
        return None
    
    try:
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
        
        print(f"Scraping {url} with Firecrawl...")
        result = firecrawl_app.scrape_url(url, params)
        
        if result and 'json' in result:
            print("Successfully scraped person information")
            return {
                'person_info': result.get('json', {}),
                'page_content': result.get('markdown', ''),
                'metadata': result.get('metadata', {})
            }
        else:
            print("No structured data returned from Firecrawl")
            return None
            
    except Exception as e:
        print(f"Error scraping with Firecrawl: {e}")
        return None

def extract_domain(url: str) -> str:
    """Extract the main domain from a URL"""
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc
        return domain
    except:
        return url

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

def analyze_search_result(result: Dict[str, Any], result_index: int) -> Dict[str, Any]:
    """
    Analyze a single search result to extract identity information
    
    Args:
        result: Single result from FaceCheckID
        result_index: Index number of this result
        
    Returns:
        Dictionary with enriched information
    """
    url = result.get('url', '')
    score = result.get('score', 0)
    
    # Save the thumbnail image
    base64_str = result.get('base64', '')
    thumbnail_path = None
    
    if base64_str:
        thumbnail_filename = f"result_{result_index}_{result.get('guid', 'unknown')}.webp"
        thumbnail_path = os.path.join(RESULTS_DIR, "images", thumbnail_filename)
        if save_thumbnail_from_base64(base64_str, thumbnail_path):
            print(f"Saved thumbnail image to {thumbnail_path}")
    
    # Get identity sources
    sources = get_identity_sources(url)
    source_type = sources[0] if sources else "Unknown source"
    
    # Scrape the URL if Firecrawl is available
    scraped_data = scrape_with_firecrawl(url)
    
    # Combine all information
    analysis = {
        'url': url,
        'score': score,
        'source_type': source_type,
        'thumbnail_path': thumbnail_path,
        'scraped_data': scraped_data
    }
    
    return analysis

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
            # Search for the face with timeout
            error, search_results = search_by_face(image_file, timeout=timeout)
            
            if search_results:
                # Print the search results summary
                print(f"Found {len(search_results)} potential matches:")
                
                # Process each result to get identity information
                identity_analyses = []
                
                for j, result in enumerate(search_results[:5], 1):  # Process top 5 results
                    score = result['score']
                    url = result['url']
                    
                    print(f"\n  {j}. Score: {score} | URL: {url}")
                    print(f"  Analyzing source to determine identity...")
                    
                    # Analyze this result
                    analysis = analyze_search_result(result, j)
                    identity_analyses.append(analysis)
                    
                    # Print scraped information if available
                    if analysis.get('scraped_data') and analysis['scraped_data'].get('person_info'):
                        person_info = analysis['scraped_data']['person_info']
                        # Handle different possible data structures
                        if isinstance(person_info, dict):
                            if 'full_name' in person_info:
                                print(f"  → Name: {person_info['full_name']}")
                            elif 'name' in person_info:
                                print(f"  → Name: {person_info['name']}")
                                
                            if 'profession' in person_info:
                                print(f"  → Profession: {person_info['profession']}")
                            elif 'occupation' in person_info:
                                print(f"  → Profession: {person_info['occupation']}")
                        else:
                            # If it's a string or other non-dict format
                            print(f"  → Info: {str(person_info)[:100]}")
                    
                    print(f"  → Source type: {analysis['source_type']}")
                
                if len(search_results) > 5:
                    print(f"\n  ... and {len(search_results) - 5} more results")
                    
                # Save the results with enhanced information
                results_data = {
                    "source_image": image_file,
                    "search_timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                    "original_results": search_results,
                    "identity_analyses": identity_analyses
                }
                
                # Generate a filename based on the original image
                base_filename = os.path.basename(image_file).replace(".jpg", "")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                results_file = os.path.join(RESULTS_DIR, f"{base_filename}_results_{timestamp}.json")
                
                # Save to file
                try:
                    with open(results_file, 'w') as f:
                        json.dump(results_data, f, indent=2)
                    print(f"\nResults saved to {results_file}")
                except Exception as e:
                    print(f"Error saving results: {e}")
            else:
                print(f"Search failed: {error}")
            
            # Mark as processed
            processed_faces.append(image_file)
            save_processed_faces(processed_faces)
        
        except KeyboardInterrupt:
            print("\nProcess interrupted by user. Saving progress...")
            # Save progress before exiting
            if image_file not in processed_faces:
                processed_faces.append(image_file)
                save_processed_faces(processed_faces)
            print("You can resume processing later.")
            raise

def main():
    """Main function to run the face upload and search tool"""
    parser = argparse.ArgumentParser(description='Upload detected faces to FaceCheckID and search for matches')
    parser.add_argument('--dir', default=DEFAULT_FACES_DIR, help='Directory containing face images')
    parser.add_argument('--limit', type=int, help='Limit the number of faces to process')
    parser.add_argument('--force', action='store_true', help='Process all faces, even if previously processed')
    parser.add_argument('--token', help='FaceCheckID API token')
    parser.add_argument('--firecrawl-key', help='Firecrawl API key')
    parser.add_argument('--timeout', type=int, default=300, help='Search timeout in seconds (default: 300)')
    parser.add_argument('--skip-scrape', action='store_true', help='Skip web scraping even if Firecrawl is available')
    parser.add_argument('--file', help='Process a specific face file instead of all unprocessed faces')
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
    
    # Handle single file processing if specified
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: Specified file '{args.file}' does not exist!")
            return
        
        print(f"Processing single file: {args.file}")
        
        error, search_results = search_by_face(args.file, timeout=args.timeout)
        if search_results:
            # Process and save results for this single file
            identity_analyses = []
            for j, result in enumerate(search_results[:5], 1):
                analysis = analyze_search_result(result, j)
                identity_analyses.append(analysis)
                
            results_data = {
                "source_image": args.file,
                "search_timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "original_results": search_results,
                "identity_analyses": identity_analyses
            }
            
            base_filename = os.path.basename(args.file).replace(".jpg", "").replace(".jpeg", "").replace(".png", "")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = os.path.join(RESULTS_DIR, f"{base_filename}_results_{timestamp}.json")
            
            with open(results_file, 'w') as f:
                json.dump(results_data, f, indent=2)
            print(f"\nResults saved to {results_file}")
        else:
            print(f"Search failed: {error}")
        
        return
    
    # Check if faces directory exists for batch processing
    if not os.path.exists(args.dir):
        print(f"Error: Faces directory '{args.dir}' does not exist!")
        print(f"Make sure FotoRec.py has run and saved faces, or specify a different directory with --dir")
        return
    
    # Process face images
    process_faces(args.dir, args.limit, args.force)
    
    print("\nProcessing complete!")
    print(f"Results have been saved to the '{RESULTS_DIR}' directory.")

if __name__ == "__main__":
    main()
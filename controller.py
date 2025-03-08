import os
import time
import threading
import logging
import signal
import sys
import FotoRec
import FaceUpload
from bio_integration import integrate_with_controller as integrate_bio
from record_integration import integrate_records_with_controller as integrate_records

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Controller")

class DirectFaceProcessor:
    """
    Simple face processor that directly processes new faces
    """
    def __init__(self):
        self.shutdown_event = threading.Event()
        
    def process_face(self, face_path):
        """Process a single face - called directly from FotoRec"""
        print(f"\n[PROCESSOR] New face detected: {os.path.basename(face_path)}")
        thread = threading.Thread(
            target=self._process_face_thread,
            args=(face_path,),
            daemon=True
        )
        thread.start()
        
    def _process_face_thread(self, face_path):
        """Process a face in a background thread"""
        print(f"[PROCESSOR] Starting processing for: {os.path.basename(face_path)}")
        try:
            success = FaceUpload.process_single_face(face_path)
            if success:
                print(f"[PROCESSOR] Successfully processed: {os.path.basename(face_path)}")
            else:
                print(f"[PROCESSOR] Failed to process: {os.path.basename(face_path)}")
        except Exception as e:
            print(f"[PROCESSOR] Error processing face: {str(e)}")

class EyeSpyController:
    """Main controller for the EyeSpy system"""
    
    def __init__(self):
        """Initialize the controller"""
        self.shutdown_event = threading.Event()
        self.face_processor = DirectFaceProcessor()
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Initialize components
        self._initialize_components()
        
        logger.info("EyeSpy controller initialized")
    
    def _initialize_components(self):
        """Initialize all system components"""
        components_status = {
            "bio_generation": False,
            "record_checking": False
        }
        
        # Initialize bio generation if available
        try:
            # Check if OPENAI_API_KEY is set in environment
            if not os.getenv("OPENAI_API_KEY"):
                print("[CONTROLLER] Warning: OPENAI_API_KEY not set. Bio generation will be disabled.")
            else:
                # Integrate bio generation
                components_status["bio_generation"] = integrate_bio()
                print("[CONTROLLER] Bio generation enabled and integrated.")
        except Exception as e:
            print(f"[CONTROLLER] Error initializing bio generation: {e}")
        
        # Initialize record checking if available
        try:
            # Check if RECORDS_API_KEY is set in environment
            if not os.getenv("RECORDS_API_KEY"):
                print("[CONTROLLER] Warning: RECORDS_API_KEY not set. Record checking will be disabled.")
            else:
                # Integrate record checking
                components_status["record_checking"] = integrate_records()
                print("[CONTROLLER] Record checking enabled and integrated.")
        except Exception as e:
            print(f"[CONTROLLER] Error initializing record checking: {e}")
        
        # Print component status summary
        print("\n[CONTROLLER] System Components Status:")
        for component, status in components_status.items():
            status_str = "ENABLED" if status else "DISABLED"
            print(f"  - {component}: {status_str}")
        print("")
    
    def signal_handler(self, sig, frame):
        """Handle termination signals"""
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        self.shutdown()
    
    def start_fotorec(self):
        """
        Start the FotoRec face detection in the main thread
        This is because OpenCV window functions must run in the main thread
        """
        logger.info("Starting FotoRec in main thread...")
        return FotoRec.main(face_processor=self.face_processor, shutdown_event=self.shutdown_event)
    
    def shutdown(self):
        """Initiate a graceful shutdown of all components"""
        logger.info("Initiating system shutdown...")
        # Set the shutdown event to signal components
        self.shutdown_event.set()
        logger.info("Shutdown complete")
    
    def run(self):
        """Run the complete EyeSpy system"""
        try:
            # Start FotoRec in the main thread (OpenCV windows must run in main thread)
            self.start_fotorec()
            
            # If FotoRec exited, initiate shutdown if not already done
            if not self.shutdown_event.is_set():
                logger.info("FotoRec has exited, initiating shutdown...")
                self.shutdown()
            
        except KeyboardInterrupt:
            logger.info("Interrupted by user, shutting down...")
            self.shutdown()
        
        except Exception as e:
            logger.error(f"Controller encountered an error: {e}")
            self.shutdown()

def main():
    """Main function to start the EyeSpy system"""
    # Parse token arguments if provided
    token = None
    firecrawl_key = None
    
    # Parse command line arguments manually for tokens only
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--token' and i+1 < len(args):
            token = args[i+1]
            i += 2
        elif args[i] == '--firecrawl-key' and i+1 < len(args):
            firecrawl_key = args[i+1]
            i += 2
        else:
            i += 1
    
    # Print banner
    print("""
    ╔═════════════════════════════════════════════╗
    ║                 EYE SPY                     ║
    ║       Face Detection & Identity Search      ║
    ╚═════════════════════════════════════════════╝
    """)
    
    # Update API keys in environment if provided
    if token:
        os.environ['FACECHECK_API_TOKEN'] = token
    if firecrawl_key:
        os.environ['FIRECRAWL_API_KEY'] = firecrawl_key
    
    # Create and run the controller
    controller = EyeSpyController()
    controller.run()

if __name__ == "__main__":
    main()
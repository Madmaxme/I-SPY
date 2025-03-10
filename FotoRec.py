import cv2
import numpy as np
import face_recognition
import pyautogui
import time
import os
import pickle
import webbrowser
import threading
from datetime import datetime
from queue import Queue, Full, Empty

# Create directory to save face screenshots if it doesn't exist
save_dir = "detected_faces"
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

# File to store face encodings
face_encodings_file = os.path.join(save_dir, "known_face_encodings.pkl")

# Initialize variables
known_face_encodings = []

# Load previously seen face encodings if the file exists
if os.path.exists(face_encodings_file):
    try:
        with open(face_encodings_file, 'rb') as f:
            known_face_encodings = pickle.load(f)
        print(f"Loaded {len(known_face_encodings)} previously detected faces")
    except Exception as e:
        print(f"Error loading known faces: {e}")
        known_face_encodings = []

def open_chrome(url="about:blank"):
    """Open a Chrome window with the specified URL"""
    print(f"Opening Chrome with URL: {url}")
    try:
        webbrowser.get('chrome').open_new(url)
        time.sleep(2)  # Give Chrome time to open
        return True
    except Exception as e:
        print(f"Error opening Chrome: {e}")
        return False

class LiveFeedCapture:
    """Class to manage continuous screen capture as a live feed"""
    def __init__(self, max_fps=30):
        self.frame_queue = Queue(maxsize=2)  # Small queue to ensure fresh frames
        self.running = False
        self.thread = None
        self.last_frame_time = time.time()
        self.frame_count = 0
        self.fps = 0
        self.max_fps = max_fps
        self.min_frame_time = 1.0 / max_fps
    
    def start(self):
        """Start the continuous capture thread"""
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print("Live feed started")
    
    def stop(self):
        """Stop the continuous capture thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        print("Live feed stopped")
    
    def _capture_loop(self):
        """Continuously capture screen frames"""
        while self.running:
            try:
                # Throttle capture rate to target FPS
                current_time = time.time()
                elapsed = current_time - self.last_frame_time
                if elapsed < self.min_frame_time:
                    time.sleep(self.min_frame_time - elapsed)
                
                # Capture screen
                screenshot = pyautogui.screenshot()
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # Update queue, replacing oldest frame if full
                try:
                    if self.frame_queue.full():
                        self.frame_queue.get_nowait()  # Remove oldest frame
                    self.frame_queue.put_nowait(frame)
                    
                    # Update stats
                    self.frame_count += 1
                    if self.frame_count >= 30:  # Calculate FPS every 30 frames
                        now = time.time()
                        self.fps = self.frame_count / (now - self.last_frame_time)
                        self.frame_count = 0
                        self.last_frame_time = now
                        
                except (Full, Empty):
                    pass  # Ignore queue errors
                
            except Exception as e:
                print(f"Capture error: {e}")
                time.sleep(0.1)  # Brief pause after error
    
    def get_frame(self):
        """Get the most recent frame"""
        try:
            return self.frame_queue.get_nowait()
        except Empty:
            return None
    
    def get_fps(self):
        """Get the current frames per second rate"""
        return self.fps

def is_new_face(face_encoding, tolerance=0.6):
    """Check if face is new by comparing with known faces"""
    if not known_face_encodings:
        return True
    
    # Compare against all known faces
    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
    return min(face_distances) > tolerance

def save_face(frame, face_location, face_encoding, face_processor=None):
    """Save a detected face if it's new"""
    global known_face_encodings
    
    # Check if this is a new face
    if not is_new_face(face_encoding):
        return None
    
    # Extract face coordinates
    top, right, bottom, left = face_location
    
    # Add margin to face crop
    margin = 30
    top = max(0, top - margin)
    bottom = min(frame.shape[0], bottom + margin)
    left = max(0, left - margin)
    right = min(frame.shape[1], right + margin)
    
    # Extract face image
    face_image = frame[top:bottom, left:right]
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    face_id = hash(tuple(face_encoding))
    filename = f"{save_dir}/face_{timestamp}_{face_id}.jpg"
    
    # Save face image
    cv2.imwrite(filename, face_image)
    print(f"New face saved: {filename}")
    
    # Add to known faces
    known_face_encodings.append(face_encoding)
    
    # Save updated known faces
    with open(face_encodings_file, 'wb') as f:
        pickle.dump(known_face_encodings, f)
    
    # Process the face if processor provided
    if face_processor:
        try:
            face_processor.process_face(filename)
        except Exception as e:
            print(f"Error processing face: {e}")
    
    return filename

def main(face_processor=None, shutdown_event=None, url="about:blank", skip_chrome=False):
    """Main function for face monitoring"""
    print("\n==== Chrome Face Monitor (Live Feed) ====")
    
    # Open Chrome if not skipped
    if not skip_chrome:
        open_chrome(url)
        print("Chrome opened. Starting live feed monitoring...")
    else:
        print("Skipping Chrome window, starting live feed monitoring of existing screen...")
    
    # Create monitoring window
    cv2.namedWindow("Face Monitoring", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Face Monitoring", 800, 600)
    
    # Start live feed capture
    capture = LiveFeedCapture(max_fps=30)
    capture.start()
    
    # Variables for processing
    process_every_other = True
    current_faces = []
    
    try:
        # Main monitoring loop
        running = True
        while running:
            # Check if shutdown requested
            if shutdown_event and shutdown_event.is_set():
                print("Shutdown requested")
                break
            
            # Get frame from live feed
            frame = capture.get_frame()
            
            if frame is None:
                # No frame available yet
                time.sleep(0.01)  # Very short delay
                continue
                
            # Process faces every other frame to improve performance
            if process_every_other:
                # Resize for faster processing
                small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                
                # Find faces
                face_locs = face_recognition.face_locations(small_frame)
                
                # Reset current faces
                current_faces = []
                
                if face_locs:
                    # Get face encodings
                    face_encodings = face_recognition.face_encodings(small_frame, face_locs)
                    
                    # Process each face
                    for i, (top, right, bottom, left) in enumerate(face_locs):
                        # Scale coordinates back up
                        scaled_loc = (top*4, right*4, bottom*4, left*4)
                        current_faces.append(scaled_loc)
                        
                        # Save if it's a new face
                        if i < len(face_encodings):
                            save_face(frame, scaled_loc, face_encodings[i], face_processor)
            
            # Toggle processing flag
            process_every_other = not process_every_other
            
            # Draw rectangles around faces
            display_frame = frame.copy()
            for (top, right, bottom, left) in current_faces:
                cv2.rectangle(display_frame, (left, top), (right, bottom), (0, 255, 0), 2)
            
            # Add status text
            cv2.putText(display_frame, f"LIVE | FPS: {capture.get_fps():.1f} | Faces: {len(current_faces)}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(display_frame, f"Tracking {len(known_face_encodings)} unique faces", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(display_frame, "Press 'q' to quit", 
                       (10, display_frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
            
            # Resize for display
            h, w = display_frame.shape[:2]
            if w > 800:
                display_frame = cv2.resize(display_frame, (800, int(800 * h / w)))
                
            # Show frame
            cv2.imshow("Face Monitoring", display_frame)
            
            # Check for key press
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("Quit requested")
                running = False
                if shutdown_event:
                    shutdown_event.set()
    
    except KeyboardInterrupt:
        print("Monitoring stopped by user")
    except Exception as e:
        print(f"Error during monitoring: {e}")
        if shutdown_event:
            shutdown_event.set()
    finally:
        # Stop capture
        capture.stop()
        cv2.destroyAllWindows()
        print("\nMonitoring stopped")
        print(f"- Faces saved to: {os.path.abspath(save_dir)}")
        print(f"- {len(known_face_encodings)} unique faces detected")

if __name__ == "__main__":
    main(url="about:blank")
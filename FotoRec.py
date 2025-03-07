import cv2
import numpy as np
import face_recognition
import pyautogui
import time
import os
import subprocess
import re
import pickle
from datetime import datetime
from PIL import ImageGrab

# Create directory to save face screenshots if it doesn't exist
save_dir = "detected_faces"
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

# File to store face encodings
face_encodings_file = os.path.join(save_dir, "known_face_encodings.pkl")

# Initialize variables
face_locations = []
process_this_frame = True
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

def get_running_apps_macos():
    """Get list of running applications on macOS"""
    try:
        # Get list of all running applications using AppleScript
        script = 'tell application "System Events" to get name of every application process whose background only is false'
        result = subprocess.check_output(["osascript", "-e", script], universal_newlines=True)
        
        # Process the result into a list
        apps = result.strip().split(", ")
        
        # Filter out system processes and sort alphabetically
        filtered_apps = sorted([app for app in apps if not app.startswith("com.") and len(app) > 1])
        
        return filtered_apps
    except Exception as e:
        print(f"Error getting running applications: {e}")
        return []

def get_app_window_bounds(app_name):
    """Get the window bounds of a specific application on macOS"""
    try:
        # AppleScript to get position and size of app window
        script = f'''
        tell application "System Events"
            set frontApp to first application process whose name is "{app_name}"
            set frontWindow to first window of frontApp
            set appPosition to position of frontWindow
            set appSize to size of frontWindow
            return appPosition & appSize
        end tell
        '''
        
        result = subprocess.check_output(["osascript", "-e", script], universal_newlines=True)
        
        # Parse coordinates from result (format is typically "x, y, width, height")
        coords = [int(x.strip()) for x in result.strip().split(',')]
        
        # Extract bounds - some apps might return different formats, so check length
        if len(coords) >= 4:
            x, y, width, height = coords[:4]
            return (x, y, x + width, y + height)
        else:
            print(f"Unexpected coordinates format for {app_name}: {coords}")
            return None
            
    except Exception as e:
        print(f"Error getting window bounds for {app_name}: {e}")
        return None

def select_app_to_monitor():
    """Terminal interface to select which app to monitor"""
    print("\n==== Instagram Face Capture Tool ====")
    print("Select an application to monitor for faces:\n")
    
    # Get list of running applications
    apps = get_running_apps_macos()
    
    if not apps:
        print("No suitable applications found running. Using full screen instead.")
        return None
    
    # Display applications with numbers
    for i, app in enumerate(apps, 1):
        print(f"{i}. {app}")
    
    print("\nF. Monitor full screen")
    print("C. Custom region selection")
    
    # Get user selection
    while True:
        try:
            choice = input("\nEnter the number of the application to monitor: ").strip()
            
            if choice.lower() == 'f':
                print("Selected: Full Screen")
                return None
            elif choice.lower() == 'c':
                print("Selected: Custom Region")
                return "custom"
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(apps):
                selected_app = apps[choice_num - 1]
                print(f"Selected: {selected_app}")
                return selected_app
            else:
                print(f"Please enter a number between 1 and {len(apps)}, 'F' for full screen, or 'C' for custom region.")
        except ValueError:
            print("Please enter a valid number or letter.")

def custom_region_selector():
    """Simple region selector for custom mode"""
    # Take a screenshot for selection
    screenshot = pyautogui.screenshot()
    screenshot_np = np.array(screenshot)
    canvas = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
    
    # Get screen dimensions
    screen_width, screen_height = pyautogui.size()
    
    # Create a window
    cv2.namedWindow("Select Custom Region", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Select Custom Region", 1024, 768)
    
    # Add instructions
    cv2.putText(canvas, "Click and drag to select a region to monitor", 
                (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(canvas, "Press ENTER to confirm or ESC to cancel", 
                (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    
    # Region variables
    region = {"start_x": 0, "start_y": 0, "end_x": 0, "end_y": 0, "drawing": False, "complete": False}
    selection_confirmed = False
    
    # Mouse callback function
    def mouse_callback(event, x, y, flags, param):
        nonlocal canvas, screenshot_np
        
        # Scale coordinates
        window_width, window_height = cv2.getWindowImageRect("Select Custom Region")[2:4]
        scale_x = screen_width / window_width
        scale_y = screen_height / window_height
        screen_x, screen_y = int(x * scale_x), int(y * scale_y)
        
        if event == cv2.EVENT_LBUTTONDOWN:
            region["start_x"], region["start_y"] = screen_x, screen_y
            region["drawing"] = True
            # Reset canvas
            canvas = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
            cv2.putText(canvas, "Click and drag to select a region", 
                        (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
        elif event == cv2.EVENT_MOUSEMOVE and region["drawing"]:
            region["end_x"], region["end_y"] = screen_x, screen_y
            # Create a copy for drawing
            temp = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
            cv2.putText(temp, "Click and drag to select a region", 
                       (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.rectangle(temp, (region["start_x"], region["start_y"]), 
                         (screen_x, screen_y), (0, 255, 0), 2)
            canvas = temp
            cv2.imshow("Select Custom Region", canvas)
            
        elif event == cv2.EVENT_LBUTTONUP:
            region["end_x"], region["end_y"] = screen_x, screen_y
            region["drawing"] = False
            region["complete"] = True
            
            # Ensure start < end
            if region["start_x"] > region["end_x"]:
                region["start_x"], region["end_x"] = region["end_x"], region["start_x"]
            if region["start_y"] > region["end_y"]:
                region["start_y"], region["end_y"] = region["end_y"], region["start_y"]
                
            # Final rectangle
            temp = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
            cv2.putText(temp, "Press ENTER to confirm selection", 
                       (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.rectangle(temp, (region["start_x"], region["start_y"]), 
                         (region["end_x"], region["end_y"]), (0, 255, 0), 2)
            canvas = temp
            cv2.imshow("Select Custom Region", canvas)
    
    # Set callback and show window
    cv2.setMouseCallback("Select Custom Region", mouse_callback)
    cv2.imshow("Select Custom Region", canvas)
    
    # Wait for confirmation
    while not selection_confirmed:
        key = cv2.waitKey(1) & 0xFF
        if key == 13 and region["complete"]:  # Enter key
            selection_confirmed = True
        elif key == 27:  # Escape key
            cv2.destroyAllWindows()
            return None
    
    cv2.destroyAllWindows()
    return (region["start_x"], region["start_y"], region["end_x"], region["end_y"])

def get_monitor_region():
    """Get the region to monitor based on user selection"""
    selected_app = select_app_to_monitor()
    
    if selected_app is None:
        # Full screen
        width, height = pyautogui.size()
        print(f"Monitoring full screen ({width}x{height})")
        return (0, 0, width, height)
    
    elif selected_app == "custom":
        # Custom region selection
        region = custom_region_selector()
        if region is None:
            # Fallback to full screen if custom selection is canceled
            width, height = pyautogui.size()
            print(f"Custom selection canceled. Monitoring full screen ({width}x{height})")
            return (0, 0, width, height)
        else:
            x1, y1, x2, y2 = region
            print(f"Monitoring custom region: ({x1},{y1}) to ({x2},{y2}) - {x2-x1}x{y2-y1} pixels")
            return region
    
    else:
        # App window region
        bounds = get_app_window_bounds(selected_app)
        if bounds:
            x1, y1, x2, y2 = bounds
            print(f"Monitoring {selected_app} window: ({x1},{y1}) to ({x2},{y2}) - {x2-x1}x{y2-y1} pixels")
            return bounds
        else:
            # Fallback if we can't get window bounds
            width, height = pyautogui.size()
            print(f"Could not determine window bounds for {selected_app}. Monitoring full screen ({width}x{height})")
            return (0, 0, width, height)

def get_screen_image(region=None):
    """Capture a portion of the screen"""
    if region:
        # Capture just the selected region
        x_start, y_start, x_end, y_end = region
        screenshot = ImageGrab.grab(bbox=(x_start, y_start, x_end, y_end))
    else:
        # Capture the full screen
        screenshot = ImageGrab.grab()
    
    # Convert to numpy array
    frame = np.array(screenshot)
    # Convert from RGB to BGR format for OpenCV
    return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

def is_new_face(face_encoding, tolerance=0.6):
    """Check if the face is new by comparing with all known face encodings"""
    global known_face_encodings
    
    if not known_face_encodings:
        return True
    
    # Compare with all known faces
    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
    
    # If the smallest distance is greater than tolerance, it's a new face
    return min(face_distances) > tolerance

def save_face(frame, face_location, face_encoding, region_offset=(0, 0), face_processor=None):
    """Save a detected face to disk if it's new"""
    global known_face_encodings
    
    # Check if this is a new face
    if not is_new_face(face_encoding):
        # Don't print message for skipped faces - too noisy
        return None
    
    # Extract face coordinates
    top, right, bottom, left = face_location
    
    # Add some margin to the face crop
    margin = 30
    top = max(0, top - margin)
    bottom = min(frame.shape[0], bottom + margin)
    left = max(0, left - margin)
    right = min(frame.shape[1], right + margin)
    
    # Extract the face from the frame
    face_image = frame[top:bottom, left:right]
    
    # Generate a unique face ID based on the encoding
    face_id = hash(tuple(face_encoding))
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{save_dir}/face_{timestamp}_{face_id}.jpg"
    
    # Save the face image
    cv2.imwrite(filename, face_image)
    print(f"New face saved to {filename}")
    
    # Add this face to our known faces
    known_face_encodings.append(face_encoding)
    
    # Save the updated known faces list
    with open(face_encodings_file, 'wb') as f:
        pickle.dump(known_face_encodings, f)
    
    # Process the face if a processor is provided
    if face_processor:
        try:
            face_processor.process_face(filename)
        except Exception as e:
            print(f"Error processing face: {str(e)}")
    
    return filename

def main(face_processor=None, shutdown_event=None):
    """
    Main face recognition function
    
    Args:
        face_processor: Optional processor for handling detected faces
        shutdown_event: Optional event to signal when the system should shut down
    """
    # Get the region to monitor
    monitor_region = get_monitor_region()
    
    if not monitor_region:
        print("No region selected. Exiting.")
        return
    
    x_start, y_start, x_end, y_end = monitor_region
    
    print("\nMonitoring started!")
    print(f"- Faces will be saved to: {os.path.abspath(save_dir)}")
    print(f"- Known faces database: {os.path.abspath(face_encodings_file)}")
    print(f"- Currently tracking {len(known_face_encodings)} unique faces")
    print("- Press 'q' in the monitoring window to quit")
    
    if face_processor:
        print(f"- Detected faces will be processed automatically")
    
    try:
        # Create a named window for monitoring
        cv2.namedWindow("Face Monitoring", cv2.WINDOW_NORMAL)
        
        running = True
        while running:
            # Check if shutdown was requested
            if shutdown_event and shutdown_event.is_set():
                print("Shutdown requested, stopping face detection...")
                break
                
            # Capture screen image (just the selected region)
            frame = get_screen_image(monitor_region)
            
            # Resize frame for faster face recognition processing
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            
            # Process every other frame to save resources
            global process_this_frame
            
            # Initialize scaled_face_locations for the display
            scaled_face_locations = []
            
            if process_this_frame:
                # Find all faces in the current frame
                face_locations = face_recognition.face_locations(small_frame)
                face_encodings = face_recognition.face_encodings(small_frame, face_locations)
                
                # Scale back the face locations
                scaled_face_locations = [(top * 4, right * 4, bottom * 4, left * 4) 
                                       for (top, right, bottom, left) in face_locations]
                
                # Process each detected face
                for (face_location, face_encoding) in zip(scaled_face_locations, face_encodings):
                    save_face(frame, face_location, face_encoding, (x_start, y_start), face_processor)
            
            process_this_frame = not process_this_frame
            
            # Display the frame with face rectangles
            debug_frame = frame.copy()
            for (top, right, bottom, left) in scaled_face_locations:
                cv2.rectangle(debug_frame, (left, top), (right, bottom), (0, 255, 0), 2)
            
            # Add status information
            status_text = f"Monitoring region: {x_end-x_start}x{y_end-y_start} pixels | Faces found: {len(scaled_face_locations)}"
            known_faces_text = f"Unique faces in database: {len(known_face_encodings)}"
            
            # Add processor status if available
            processor_text = ""
            if face_processor:
                processor_text = "Face processing: Enabled"
            
            cv2.putText(debug_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(debug_frame, known_faces_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            if processor_text:
                cv2.putText(debug_frame, processor_text, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            # Resize for display if too large
            h, w = debug_frame.shape[:2]
            if w > 800:
                display_width = 800
                display_height = int(h * (800 / w))
                debug_frame = cv2.resize(debug_frame, (display_width, display_height))
            
            cv2.imshow('Face Monitoring', debug_frame)
            
            # Check for quit command - MUST use cv2.waitKey(1) to catch keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("\n[FOTOREC] Quit requested via 'q' key, shutting down...")
                running = False
                # Also set shutdown event if available
                if shutdown_event:
                    print("[FOTOREC] Notifying controller of shutdown request...")
                    shutdown_event.set()
                    
                # Break out of the loop immediately to respond to quit
                break
                
            # Short delay to reduce CPU usage
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\nStopping face recognition...")
    
    finally:
        cv2.destroyAllWindows()
        print(f"\nFace monitoring stopped.")
        print(f"- Detected faces saved in {os.path.abspath(save_dir)}")
        print(f"- Database contains {len(known_face_encodings)} unique faces")
        
        # No queue signals needed - direct processing

if __name__ == "__main__":
    # When run directly, no processor is provided
    main(face_processor=None, shutdown_event=None)
#!/usr/bin/env python3
"""
record_integration.py - Integration module for adding record checking to the EyeSpy system
This should be imported in controller.py
"""

import os
from RecordChecker import RecordChecker, integrate_with_biogen

def integrate_records_with_controller():
    """
    Integrate record checking into the EyeSpy system
    This should be called from controller.py during initialization
    """
    try:
        # Check if RECORDS_API_KEY is set in environment
        if not os.getenv("RECORDS_API_KEY"):
            print("[RECORDS_INTEGRATION] Warning: RECORDS_API_KEY not set. Record checking will be disabled.")
            return False
            
        # Get optional provider setting
        provider = os.getenv("RECORDS_PROVIDER")
        if provider:
            print(f"[RECORDS_INTEGRATION] Using {provider} as records provider")
        
        # We don't call integrate_with_biogen here anymore
        # The workflow will now use bio_integration.py's process_directory_with_records_then_bio function
        # which properly handles the correct sequence (records first, then bio)
        
        print("[RECORDS_INTEGRATION] Record checking successfully integrated with the system")
        return True
            
    except Exception as e:
        print(f"[RECORDS_INTEGRATION] Error initializing record checking: {e}")
        return False

if __name__ == "__main__":
    # For testing the integration
    integrate_records_with_controller()
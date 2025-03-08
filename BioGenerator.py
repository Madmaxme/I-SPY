#!/usr/bin/env python3
import json
import os
import traceback
from datetime import datetime
import openai
from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
load_dotenv()

class BioGenerator:
    """Generate formatted bios from face search results using OpenAI API"""
    
    def __init__(self, api_key=None):
        """Initialize the BioGenerator with OpenAI API key"""
        # Use provided API key or get from environment
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Provide it as an argument or set OPENAI_API_KEY environment variable.")
        
        # Initialize the OpenAI client
        self.client = openai.OpenAI(api_key=self.api_key)
    
    def load_data(self, json_file):
        """Load and parse the JSON data file"""
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Check if the file has the expected structure
            if "identity_analyses" not in data:
                raise ValueError("Invalid JSON format: 'identity_analyses' key not found")
            
            return data
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON file: {json_file}")
        except FileNotFoundError:
            raise ValueError(f"File not found: {json_file}")
    
    def prepare_summarized_data(self, identity_analyses):
        """
        Create a focused version of the identity_analyses data by only including 
        entries that match the name of the first person found.
        This dramatically reduces token usage.
        """
        if not identity_analyses:
            return []
            
        first_person_name = None
        relevant_data = []
        
        # Find the first entry with person info to get the reference name
        for analysis in identity_analyses:
            person_name = None
            
            # Try to extract a name from person_info
            if analysis.get("scraped_data") and analysis["scraped_data"].get("person_info"):
                person_info = analysis["scraped_data"]["person_info"]
                
                # Check nested person object
                if "person" in person_info:
                    person_obj = person_info["person"]
                    if "fullName" in person_obj:
                        person_name = person_obj["fullName"]
                    elif "full_name" in person_obj:
                        person_name = person_obj["full_name"]
                    elif "name" in person_obj:
                        person_name = person_obj["name"]
                
                # Check flat structure
                if not person_name:
                    if "fullName" in person_info:
                        person_name = person_info["fullName"]
                    elif "full_name" in person_info:
                        person_name = person_info["full_name"]
                    elif "name" in person_info:
                        person_name = person_info["name"]
            
            # If we found a name, set it as the reference name and add this entry
            if person_name:
                if first_person_name is None:
                    first_person_name = person_name
                    print(f"[BIOGEN] Found first person: {first_person_name}")
                
                # Check if this entry is about the same person
                if first_person_name and self._is_same_person(person_name, first_person_name):
                    entry = self._extract_person_data(analysis)
                    if entry:
                        relevant_data.append(entry)
        
        print(f"[BIOGEN] Found {len(relevant_data)} entries matching the first person")
        return relevant_data
    
    def _is_same_person(self, name1, name2):
        """
        Simple comparison to check if two names likely refer to the same person
        We do a case-insensitive check if either name is a substring of the other
        """
        if not name1 or not name2:
            return False
            
        name1 = name1.lower()
        name2 = name2.lower()
        
        # Check if either name contains the other
        return name1 in name2 or name2 in name1
    
    def _extract_person_data(self, analysis):
        """
        Extract only the essential person data from an analysis entry
        Skip page_content inside scraped_data as requested
        """
        if not analysis:
            return None
            
        entry = {}
        
        # Basic match info
        entry["match_score"] = analysis.get("match_score", 0)
        entry["domain"] = analysis.get("domain", "unknown")
        
        # Extract person info
        if analysis.get("scraped_data") and analysis["scraped_data"].get("person_info"):
            person_info = analysis["scraped_data"]["person_info"]
            
            # Skip the page_content field as requested
            if "page_content" in person_info:
                del person_info["page_content"]
                
            # For nested person object
            if "person" in person_info:
                # Make a copy without page_content
                person_clean = {k: v for k, v in person_info["person"].items() 
                               if k != "page_content"}
                entry["person_info"] = {"person": person_clean}
            else:
                # Make a copy without page_content
                entry["person_info"] = {k: v for k, v in person_info.items() 
                                       if k != "page_content"}
        
        # Extract text content if available (excluding page_content)
        if analysis.get("scraped_data") and analysis["scraped_data"].get("text_content"):
            text = analysis["scraped_data"]["text_content"]
            # Skip if it's just raw page content
            if not text.startswith("<html") and len(text) < 1000:
                entry["text_content"] = text
        
        return entry
    
    def prepare_prompt(self, identity_analyses, record_analyses=None):
        """
        Prepare the prompt for OpenAI API using identity and record analyses
        
        Args:
            identity_analyses: List of identity analysis results from face search
            record_analyses: Optional record analysis data from RecordChecker
        
        Returns:
            Formatted prompt string
        """
        # Get data for only the first person and their matches
        person_data = self.prepare_summarized_data(identity_analyses)
        
        # Extract name for the prompt
        name = "the subject"
        if person_data and len(person_data) > 0:
            for entry in person_data:
                if entry.get("person_info"):
                    person_info = entry["person_info"]
                    if "person" in person_info and person_info["person"].get("fullName"):
                        name = person_info["person"]["fullName"]
                        break
                    elif person_info.get("fullName"):
                        name = person_info["fullName"]
                        break
                    elif person_info.get("full_name"):
                        name = person_info["full_name"]
                        break
        
        prompt = f"""
        You are a professional intelligence analyst creating a profile for {name} based on the following data.
        
        All entries in the data are about the same person. Synthesize the information to create a comprehensive profile.
        
        Create a well-formatted profile that includes:
        1. Full name and professional title
        2. Summary of who they are and what they're known for
        3. Current and past organizations/roles
        4. Notable achievements/work
        5. Location information
        6. Contact information (if available)
        7. Personal relationships and connections (if available)
        8. Any other relevant personal or professional details
        
        Format the report for mobile viewing with clear sections. Focus on factual information and present it in a professional tone.
        Do not include any AI-generated disclaimers or notes.
        """
        
        # Add the identity data section
        prompt += """
        
        Here is the IDENTITY MATCH data to analyze (all related to the same person):
        """
        
        # Add the person-specific data as a JSON string
        prompt += json.dumps(person_data, indent=2)
        
        # Add record data if available
        if record_analyses and record_analyses.get("personal_details"):
            prompt += """
            
            Here is additional PERSONAL RECORDS data found for this individual:
            """
            
            # Add the personal details from record search
            prompt += json.dumps(record_analyses["personal_details"], indent=2)
        
        # Return the prompt
        return prompt
    
    def generate_bio(self, identity_analyses, record_analyses=None):
        """
        Generate a bio using OpenAI's API with both identity and record data
        
        Args:
            identity_analyses: List of identity analysis results
            record_analyses: Optional record analysis data
            
        Returns:
            Generated biographical text
        """
        prompt = self.prepare_prompt(identity_analyses, record_analyses)
        
        try:
            # Estimate token count (rough approximation: 1 token ≈ 4 chars for English text)
            estimated_tokens = len(prompt) / 4
            
            # Log token estimate
            print(f"[BIOGEN] Estimated prompt tokens: {int(estimated_tokens)}")
            
            # If potentially too large, apply emergency fallback
            if estimated_tokens > 15000:  # Leave room for response
                print("[BIOGEN] Prompt too large, using emergency fallback...")
                
                # Take just the first match data and simplify prompt
                if identity_analyses and len(identity_analyses) > 0:
                    first_match = identity_analyses[0]
                    name = self.extract_name([first_match]) or "the subject"
                    
                    # Extract only the most critical info
                    critical_info = {
                        "name": name,
                        "source": first_match.get("domain", "unknown source")
                    }
                    
                    if first_match.get("scraped_data") and first_match["scraped_data"].get("person_info"):
                        person_info = first_match["scraped_data"]["person_info"]
                        if "occupation" in person_info:
                            critical_info["occupation"] = person_info["occupation"]
                        if "organization" in person_info:
                            critical_info["organization"] = person_info["organization"]
                    
                    # Add critical record info if available
                    if record_analyses and record_analyses.get("personal_details"):
                        details = record_analyses["personal_details"]
                        
                        # Add current address if available
                        if details.get("addresses") and len(details["addresses"]) > 0:
                            critical_info["address"] = details["addresses"][0]["address"]
                        
                        # Add phone if available
                        if details.get("phone_numbers") and len(details["phone_numbers"]) > 0:
                            critical_info["phone"] = details["phone_numbers"][0]["number"]
                    
                    # Very simplified prompt
                    prompt = f"""
                    Create a brief professional bio for {name} based on this limited data:
                    {json.dumps(critical_info, indent=2)}
                    
                    Format the bio for mobile viewing with clear sections.
                    """
                    
                    print(f"[BIOGEN] Emergency fallback prompt tokens: {int(len(prompt) / 4)}")
            
            # Call the OpenAI API with the appropriate prompt
            response = self.client.chat.completions.create(
                model="gpt-4-turbo", # or another appropriate model
                messages=[
                    {"role": "system", "content": "You are a professional intelligence analyst creating biographical profiles from search data."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more factual responses
                max_tokens=2000   # Adjust as needed for report length
            )
            
            # Extract and return the response text
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"[BIOGEN] Error while calling OpenAI API: {e}")
            traceback.print_exc()
            return None
    
    def save_report(self, bio, output_dir, filename="bio.txt"):
        """Save the generated bio to a text file in the specified directory"""
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Full path to the bio file
        filepath = os.path.join(output_dir, filename)
        
        # Save the report
        with open(filepath, 'w') as f:
            f.write(bio)
        
        return filepath
    
    def extract_name(self, identity_analyses):
        """Try to extract a person's name from the data for filename purposes"""
        for analysis in identity_analyses:
            # Look for name in scraped data
            if analysis.get('scraped_data') and analysis['scraped_data'].get('person_info'):
                person_info = analysis['scraped_data']['person_info']
                
                # Check if there's a 'person' key with 'fullName' or 'full_name'
                if 'person' in person_info:
                    if 'fullName' in person_info['person']:
                        return person_info['person']['fullName']
                    elif 'full_name' in person_info['person']:
                        return person_info['person']['full_name']
                
                # Direct keys in person_info
                if 'fullName' in person_info:
                    return person_info['fullName']
                elif 'full_name' in person_info:
                    return person_info['full_name']
        
        # If we couldn't find a name
        return None
    
    def process_result_directory(self, person_dir):
        """
        Process a face search result directory and generate a bio
        This is designed to be called from the FaceUpload module after results are saved
        
        Args:
            person_dir: Path to the person's result directory within face_search_results/
            
        Returns:
            filepath: Path to the generated bio file, or None if unsuccessful
        """
        print(f"[BIOGEN] Processing directory: {person_dir}")
        
        try:
            # Find the most recent results JSON file in the directory
            result_files = [f for f in os.listdir(person_dir) if f.startswith("results_") and f.endswith(".json")]
            if not result_files:
                print(f"[BIOGEN] No results files found in {person_dir}")
                return None
            
            # Sort by modification time (newest first)
            result_files.sort(key=lambda f: os.path.getmtime(os.path.join(person_dir, f)), reverse=True)
            json_file = os.path.join(person_dir, result_files[0])
            
            print(f"[BIOGEN] Using results file: {json_file}")
            
            # Load the data
            data = self.load_data(json_file)
            
            # Check if record_analyses is available
            record_analyses = data.get("record_analyses")
            if record_analyses:
                print(f"[BIOGEN] Found record analyses data from {record_analyses.get('provider', 'unknown')}")
            
            # Generate the bio with both identity and record data
            bio = self.generate_bio(data["identity_analyses"], record_analyses)
            
            if bio:
                # Save the report to the person directory
                filepath = self.save_report(bio, person_dir, "bio.txt")
                print(f"[BIOGEN] Bio generated and saved to: {filepath}")
                
                # Update the main JSON file to include the bio
                data["bio_text"] = bio
                data["bio_timestamp"] = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Write the updated JSON back to the file
                with open(json_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return filepath
            else:
                print("[BIOGEN] Failed to generate bio.")
                return None
                
        except Exception as e:
            print(f"[BIOGEN] Error processing directory {person_dir}: {e}")
            traceback.print_exc()
            return None
            
    def process_file(self, json_file):
        """
        Process a single results file and generate a bio
        
        Args:
            json_file: Path to the JSON file containing identity_analyses
            
        Returns:
            filepath: Path to the generated bio file, or None if unsuccessful
        """
        print(f"[BIOGEN] Processing file: {json_file}")
        
        try:
            # Get the directory containing the JSON file
            result_dir = os.path.dirname(json_file)
            
            # Load the data
            data = self.load_data(json_file)
            
            # Generate the bio
            bio = self.generate_bio(data["identity_analyses"])
            
            if bio:
                # Save the report in the same directory as the JSON file
                filepath = self.save_report(bio, result_dir, "bio.txt")
                print(f"[BIOGEN] Bio generated and saved to: {filepath}")
                return filepath
            else:
                print("[BIOGEN] Failed to generate bio.")
                return None
        
        except Exception as e:
            print(f"[BIOGEN] Error processing file {json_file}: {e}")
            traceback.print_exc()
            return None


# For command-line usage (not typically used in the controller integration)
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate bios from face search results using OpenAI API')
    parser.add_argument('path', help='Path to the JSON file or directory containing identity analyses')
    parser.add_argument('--api-key', help='OpenAI API key (optional if set in environment)')
    
    args = parser.parse_args()
    
    try:
        # Initialize the bio generator
        generator = BioGenerator(api_key=args.api_key)
        
        if os.path.isdir(args.path):
            # Process directory
            output_file = generator.process_result_directory(args.path)
        else:
            # Process single file
            output_file = generator.process_file(args.path)
        
        if output_file:
            print(f"[BIOGEN] Successfully generated bio. See {output_file}")
        
    except ValueError as e:
        print(f"[BIOGEN] Error: {e}")
    except Exception as e:
        print(f"[BIOGEN] Unexpected error: {e}")
        traceback.print_exc()
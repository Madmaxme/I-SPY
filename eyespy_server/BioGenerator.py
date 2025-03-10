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
        Create a focused version of the identity_analyses data by finding the most frequently
        occurring name and including entries that match this name.
        This approach ensures we identify the correct person while reducing token usage.
        """
        if not identity_analyses:
            return []
        
        # Step 1: Collect all names from all analyses
        all_names = []
        name_to_analysis = {}  # Maps names to original analysis objects
        name_to_score = {}     # Maps names to match scores (for weighting/tiebreaking)
        name_to_frequency = {} # Maps names to occurrence frequency
        
        for analysis in identity_analyses:
            match_score = analysis.get("score", 0)
            name_candidates = []
            
            # First, check for explicit candidate_names from Firecrawl
            if analysis.get("scraped_data") and analysis["scraped_data"].get("candidate_names"):
                candidate_names = analysis["scraped_data"]["candidate_names"]
                for candidate in candidate_names:
                    name_candidates.append(candidate["name"])
                    
                    # Track frequency of each name
                    norm_name = candidate["name"].lower().strip()
                    if norm_name not in name_to_frequency:
                        name_to_frequency[norm_name] = 0
                    name_to_frequency[norm_name] += 1
                
                print(f"[BIOGEN] Found {len(candidate_names)} explicit name candidates")
            
            # Fallback to old method if no explicit candidates
            if not name_candidates and analysis.get("scraped_data") and analysis["scraped_data"].get("person_info"):
                person_info = analysis["scraped_data"]["person_info"]
                
                # Check nested person object
                if "person" in person_info:
                    person_obj = person_info["person"]
                    if "fullName" in person_obj:
                        name_candidates.append(person_obj["fullName"])
                    elif "full_name" in person_obj:
                        name_candidates.append(person_obj["full_name"])
                    elif "name" in person_obj:
                        name_candidates.append(person_obj["name"])
                
                # Check flat structure
                if not name_candidates:
                    if "fullName" in person_info:
                        name_candidates.append(person_info["fullName"])
                    elif "full_name" in person_info:
                        name_candidates.append(person_info["full_name"])
                    elif "name" in person_info:
                        name_candidates.append(person_info["name"])
                
                # Update frequency for fallback names too
                for name in name_candidates:
                    if isinstance(name, str):
                        norm_name = name.lower().strip()
                        if norm_name not in name_to_frequency:
                            name_to_frequency[norm_name] = 0
                        name_to_frequency[norm_name] += 1
                    elif isinstance(name, list):
                        # Handle case where name is a list
                        for n in name:
                            if isinstance(n, str):
                                norm_name = n.lower().strip()
                                if norm_name not in name_to_frequency:
                                    name_to_frequency[norm_name] = 0
                                name_to_frequency[norm_name] += 1
            
            try:
                # Process all found names
                for person_name in name_candidates:
                    if not person_name:
                        continue
                        
                    # Handle both string and list cases
                    if isinstance(person_name, str):
                        # Normalize the name (lowercase, strip extra spaces)
                        norm_name = person_name.lower().strip()
                        all_names.append(norm_name)
                        
                        # Store analysis by name
                        if norm_name not in name_to_analysis:
                            name_to_analysis[norm_name] = []
                        name_to_analysis[norm_name].append(analysis)
                        
                        # Store highest score for this name
                        if norm_name not in name_to_score or match_score > name_to_score[norm_name]:
                            name_to_score[norm_name] = match_score
                    elif isinstance(person_name, list):
                        # Handle list of names
                        for name in person_name:
                            if isinstance(name, str) and name:
                                norm_name = name.lower().strip()
                                all_names.append(norm_name)
                                
                                # Store analysis by name
                                if norm_name not in name_to_analysis:
                                    name_to_analysis[norm_name] = []
                                name_to_analysis[norm_name].append(analysis)
                                
                                # Store highest score for this name
                                if norm_name not in name_to_score or match_score > name_to_score[norm_name]:
                                    name_to_score[norm_name] = match_score
            except Exception as e:
                print(f"[BIOGEN] Error processing name candidates: {e}")
                print(f"[BIOGEN] name_candidates type: {type(name_candidates).__name__}")
                print(f"[BIOGEN] name_candidates value: {name_candidates}")
            
            # Log the frequency counts
            print(f"[BIOGEN] Name frequency counts: {name_to_frequency}")
                    
        
        # Step 2: Group similar names (using our improved _is_same_person method)
        name_groups = []
        processed_names = set()
        
        for name in all_names:
            if name in processed_names:
                continue
                
            # Start a new group with this name
            current_group = [name]
            processed_names.add(name)
            
            # Find all similar names
            for other_name in all_names:
                if other_name not in processed_names and self._is_same_person(name, other_name):
                    current_group.append(other_name)
                    processed_names.add(other_name)
            
            # Add the group to our list of groups
            name_groups.append(current_group)
        
        # Step 3: Find the most common name group
        most_common_group = []
        highest_frequency = 0
        highest_score = 0
        
        for group in name_groups:
            # Calculate total frequency of this name group
            group_frequency = sum([name_to_frequency.get(name, 0) for name in group])
            
            # Find highest score in this group
            group_max_score = max([name_to_score.get(name, 0) for name in group])
            
            # Log group statistics
            print(f"[BIOGEN] Name group: {group}, Frequency: {group_frequency}, Max score: {group_max_score}")
            
            # Check if this group is more frequent, or equally frequent but higher scored
            if group_frequency > highest_frequency or (group_frequency == highest_frequency and group_max_score > highest_score):
                most_common_group = group
                highest_frequency = group_frequency
                highest_score = group_max_score
        
        # Step 4: Choose the canonical name from the most common group
        # Prefer the name with the highest frequency, using score as a tiebreaker
        canonical_name = None
        if most_common_group:
            # Sort the group by frequency first, then by score
            sorted_names = sorted(most_common_group, 
                                 key=lambda name: (name_to_frequency.get(name, 0), name_to_score.get(name, 0)), 
                                 reverse=True)
            
            # Get top name by frequency
            canonical_name = sorted_names[0]
            top_frequency = name_to_frequency.get(canonical_name, 0)
            
            # Log individual name frequencies
            for name in sorted_names[:5]:  # Log top 5 names
                print(f"[BIOGEN] Name candidate: {name}, Frequency: {name_to_frequency.get(name, 0)}, Score: {name_to_score.get(name, 0)}")
            
            # Get original case/format from name_to_analysis keys
            for original_name in name_to_analysis.keys():
                if original_name.lower() == canonical_name:
                    canonical_name = original_name
                    break
                    
            print(f"[BIOGEN] Selected canonical name: '{canonical_name}' with frequency: {top_frequency}")
        
        # If we couldn't find any names, return empty list
        if not canonical_name:
            print("[BIOGEN] No names found in any analysis")
            return []
            
        # Step 5: Collect all analyses that match the canonical name
        relevant_data = []
        for name in most_common_group:
            for analysis in name_to_analysis[name]:
                entry = self._extract_person_data(analysis)
                if entry:
                    relevant_data.append(entry)
        
        print(f"[BIOGEN] Found {len(relevant_data)} entries matching the canonical person")
        return relevant_data
    
    def _is_same_person(self, name1, name2):
        """
        Improved comparison to check if two names likely refer to the same person
        Uses a more sophisticated approach than simple substring matching
        """
        if not name1 or not name2:
            return False
            
        name1 = name1.lower().strip()
        name2 = name2.lower().strip()
        
        # Exact match
        if name1 == name2:
            return True
            
        # Split names into components
        name1_parts = name1.split()
        name2_parts = name2.split()
        
        # If one is a single name and the other has multiple parts
        if len(name1_parts) == 1 and len(name2_parts) > 1:
            # Check if the single name is in the multi-part name
            return name1_parts[0] in name2_parts
        elif len(name2_parts) == 1 and len(name1_parts) > 1:
            # Check if the single name is in the multi-part name
            return name2_parts[0] in name1_parts
            
        # For multi-part names, check if first and last names match
        if len(name1_parts) > 1 and len(name2_parts) > 1:
            # Check if first names match
            first_match = name1_parts[0] == name2_parts[0]
            # Check if last names match
            last_match = name1_parts[-1] == name2_parts[-1]
            
            # Return true if both first and last match
            return first_match and last_match
            
        # Fallback to old method if the above checks don't apply
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
        Uses the improved frequency-based name selection
        
        Args:
            identity_analyses: List of identity analysis results from face search
            record_analyses: Optional record analysis data from RecordChecker
        
        Returns:
            Formatted prompt string
        """
        # Get data for the most frequently occurring person and their matches
        person_data = self.prepare_summarized_data(identity_analyses)
        
        # Extract the canonical name using our improved approach
        canonical_name = self.extract_name(identity_analyses)
        name = canonical_name if canonical_name else "the subject"
        
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
                
                # Use our canonical name approach even for the fallback
                name = self.extract_name(identity_analyses) or "the subject"
                # Take just the highest scored match for the fallback
                if identity_analyses and len(identity_analyses) > 0:
                    # Sort matches by score (highest first)
                    sorted_matches = sorted(identity_analyses, key=lambda x: x.get("score", 0), reverse=True)
                    first_match = sorted_matches[0]
                    
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
        """
        Extract the most frequently occurring person's name from the data
        This now uses the frequency-based approach for consistent naming
        """
        try:
            # Use our existing frequency-based approach
            summarized_data = self.prepare_summarized_data(identity_analyses)
            
            # If we found data, try to extract name from the first entry
            # (the prepare_summarized_data method guarantees these are for the canonical person)
            if summarized_data and len(summarized_data) > 0:
                for entry in summarized_data:
                    if entry.get("person_info"):
                        person_info = entry["person_info"]
                        
                        # Check nested person object
                        if "person" in person_info:
                            person_obj = person_info["person"]
                            if "fullName" in person_obj and isinstance(person_obj["fullName"], str):
                                return person_obj["fullName"]
                            elif "full_name" in person_obj and isinstance(person_obj["full_name"], str):
                                return person_obj["full_name"]
                            elif "name" in person_obj and isinstance(person_obj["name"], str):
                                return person_obj["name"]
                        
                        # Direct keys in person_info
                        if "fullName" in person_info and isinstance(person_info["fullName"], str):
                            return person_info["fullName"]
                        elif "full_name" in person_info and isinstance(person_info["full_name"], str):
                            return person_info["full_name"]
                        elif "name" in person_info and isinstance(person_info["name"], str):
                            return person_info["name"]
        except Exception as e:
            print(f"[BIOGEN] Error in extract_name: {e}")
            return "Unknown Subject"
        
        try:
            # Fallback method if summarized_data approach doesn't work
            # This preserves some backward compatibility
            for analysis in identity_analyses:
                if analysis.get('scraped_data') and analysis['scraped_data'].get('person_info'):
                    person_info = analysis['scraped_data']['person_info']
                    
                    # Check nested person object
                    if 'person' in person_info:
                        if 'fullName' in person_info['person'] and isinstance(person_info['person']['fullName'], str):
                            return person_info['person']['fullName']
                        elif 'full_name' in person_info['person'] and isinstance(person_info['person']['full_name'], str):
                            return person_info['person']['full_name']
                        elif 'name' in person_info['person'] and isinstance(person_info['person']['name'], str):
                            return person_info['person']['name']
                    
                    # Direct keys in person_info
                    if 'fullName' in person_info and isinstance(person_info['fullName'], str):
                        return person_info['fullName']
                    elif 'full_name' in person_info and isinstance(person_info['full_name'], str):
                        return person_info['full_name']
                    elif 'name' in person_info and isinstance(person_info['name'], str):
                        return person_info['name']
        except Exception as e:
            print(f"[BIOGEN] Error in extract_name fallback: {e}")
            
        # If we couldn't find a name
        return "Unknown Person"
    
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
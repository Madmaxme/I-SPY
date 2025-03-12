import sys
sys.path.append('../eyespy_server')

def filter_social_profiles_by_name(profiles, canonical_name):
    """
    Filter social profiles to only include those likely belonging to the canonical name
    """
    if not profiles or not canonical_name:
        return profiles
    
    filtered_profiles = []
    name_parts = canonical_name.lower().strip().split()
    
    for profile in profiles:
        # Skip if not a string
        if not isinstance(profile, str):
            continue
            
        # Extract username from URL
        username = None
        if "/in/" in profile:  # LinkedIn
            username = profile.split("/in/")[-1].split("/")[0].split("?")[0]
        elif "facebook.com/" in profile:  # Facebook
            path = profile.split("facebook.com/")[-1].split("/")[0].split("?")[0]
            if path not in ["pages", "groups", "photos"]:
                username = path
        elif "twitter.com/" in profile:  # Twitter
            username = profile.split("twitter.com/")[-1].split("/")[0].split("?")[0]
            if username in ["status", "hashtag"]:
                continue
                
        # If we couldn't extract a username, keep the URL (better to include than exclude)
        if not username:
            filtered_profiles.append(profile)
            print(f"[TEST] Keeping profile {profile} - couldn't extract username")
            continue
            
        # Check if any part of the name is in the username
        # This is a simple approach - could be improved with better matching
        username_lower = username.lower()
        name_match = False
        for part in name_parts:
            if len(part) >= 3 and part in username_lower:
                filtered_profiles.append(profile)
                print(f"[TEST] Keeping profile {profile} - username '{username}' matches part of canonical name '{canonical_name}'")
                name_match = True
                break
                
        # If no match, log and exclude
        if not name_match:
            print(f"[TEST] Excluding profile {profile} - username '{username}' doesn't match any part of canonical name '{canonical_name}'")
    
    return filtered_profiles

# Test with the example profiles
profiles = [
    'https://linkedin.com/in/harrisonmuchnic',
    'https://facebook.com/BNI.Europabruecke.Kehl.Deutschland'
]

# Test with Gunther's name
filtered = filter_social_profiles_by_name(profiles, 'gunther hoferer')
print(f"\nOriginal: {profiles}\nFiltered: {filtered}")

# Test with Harrison's name
filtered = filter_social_profiles_by_name(profiles, 'harrison muchnic')
print(f"\nOriginal: {profiles}\nFiltered: {filtered}")
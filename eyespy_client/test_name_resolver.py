import sys
sys.path.append('../eyespy_server')

from NameResolver import NameResolver

# Test scenario that mimics the issue you found
# Two different people with different URLs
test_analyses = [
    {
        "score": 85,
        "url": "https://www.meetup.com/members/338981318/",
        "scraped_data": {
            "person_info": {
                "person": {
                    "fullName": "Gunther Hoferer"
                }
            }
        }
    },
    {
        "score": 83,
        "url": "https://linkedin.com/in/harrisonmuchnic",
        "scraped_data": {
            "person_info": {
                "person": {
                    "fullName": "Harrison Muchnic"
                }
            }
        }
    },
    {
        "score": 80,
        "url": "https://facebook.com/BNI.Europabruecke.Kehl.Deutschland/photos/a.297508877648126/421387668593579/?type=3",
        "scraped_data": {
            "person_info": {
                "person": {
                    "fullName": "Gunther Hoferer"
                }
            }
        }
    }
]

print("Testing NameResolver with URL enhancement...")
name = NameResolver.resolve_canonical_name(test_analyses)
print(f"\nFinal result: '{name}'")

# Test the username extraction function
print("\nTesting username extraction...")
test_urls = [
    "https://linkedin.com/in/harrisonmuchnic",
    "https://facebook.com/BNI.Europabruecke.Kehl.Deutschland",
    "https://twitter.com/johndoe",
    "https://instagram.com/janedoe",
    "https://www.meetup.com/members/338981318/"
]

for url in test_urls:
    username = NameResolver.extract_username(url)
    print(f"URL: {url} -> Username: {username}")

# Test username-name matching
print("\nTesting username-name matching...")
test_pairs = [
    ("harrisonmuchnic", "Harrison Muchnic"),
    ("john.smith", "John Smith"),
    ("johndoe", "John Doe"),
    ("jsmith1234", "John Smith"),
    ("BNI.Europabruecke.Kehl.Deutschland", "Gunther Hoferer")
]

for username, name in test_pairs:
    result = NameResolver.username_name_match(username, name)
    print(f"Username '{username}' matches name '{name}': {result}")
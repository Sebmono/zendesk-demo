#!/usr/bin/env python3

import requests
import json
from config import API_TOKEN, ADMIN_EMAIL, BASE_URL

def get_auth():
    """Return the authentication tuple for requests"""
    return (f"{ADMIN_EMAIL}/token", API_TOKEN)

def create_organization(name, domain_names):
    """Create a new organization in Zendesk"""
    url = f"{BASE_URL}/organizations.json"
    data = {
        "organization": {
            "name": name,
            "domain_names": domain_names
        }
    }
    
    response = requests.post(url, json=data, auth=get_auth())
    if response.status_code == 201:
        return response.json()['organization']
    else:
        print(f"Error creating organization {name}: {response.status_code}")
        return None

def create_user(first_name, last_name, email, organization_id):
    """Create a new user in Zendesk"""
    url = f"{BASE_URL}/users.json"
    data = {
        "user": {
            "name": f"{first_name} {last_name}",
            "email": email,
            "organization_id": organization_id,
            "role": "end-user"
        }
    }
    
    response = requests.post(url, json=data, auth=get_auth())
    if response.status_code == 201:
        return response.json()['user']
    else:
        print(f"Error creating user {email}: {response.status_code}")
        return None

def main():
    """Main function to create organizations and users"""
    print("Starting organization and user creation...")
    
    # Read organizations from JSON file
    try:
        with open('organizations.json', 'r') as f:
            org_data = json.load(f)
    except FileNotFoundError:
        print("Error: organizations.json file not found")
        return
    except json.JSONDecodeError:
        print("Error: organizations.json is not valid JSON")
        return
    
    # Read users from JSON file
    try:
        with open('users.json', 'r') as f:
            user_data = json.load(f)
    except FileNotFoundError:
        print("Error: users.json file not found")
        return
    except json.JSONDecodeError:
        print("Error: users.json is not valid JSON")
        return
    
    # Create a dictionary to store created organizations by name
    orgs_by_name = {}
    
    # Create organizations
    for org_info in org_data['organizations']:
        org_name = org_info['name']
        domain_names = org_info['domain_names']
        
        # Create organization
        print(f"\nCreating organization: {org_name}")
        org = create_organization(org_name, domain_names)
        if org:
            orgs_by_name[org_name] = org
    
    # Create users for each organization
    print("\nCreating users...")
    for user_info in user_data['users']:
        org_name = user_info['organization']
        
        # Skip if the organization wasn't created successfully
        if org_name not in orgs_by_name:
            print(f"Skipping user {user_info['email']} - organization {org_name} not found")
            continue
        
        # Get the organization ID
        org_id = orgs_by_name[org_name]['id']
        
        # Create the user
        first_name = user_info['first_name']
        last_name = user_info['last_name']
        email = user_info['email']
        
        print(f"Creating user: {first_name} {last_name} ({email})")
        user = create_user(first_name, last_name, email, org_id)
        if user:
            print(f"Successfully created user {email} for organization {org_name}")
    
    print("\nOrganization and user creation completed!")

if __name__ == "__main__":
    main() 
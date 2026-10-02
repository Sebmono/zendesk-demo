#!/usr/bin/env python3

import requests
import json
import time
import random
import re
from config import API_TOKEN, ADMIN_EMAIL, BASE_URL

def get_auth():
    """Return the authentication tuple for requests"""
    return (f"{ADMIN_EMAIL}/token", API_TOKEN)

def get_random_user():
    """Get a random user from users.json file"""
    try:
        with open('users.json', 'r') as f:
            users_data = json.load(f)
            if users_data and 'users' in users_data and len(users_data['users']) > 0:
                return random.choice(users_data['users'])
            else:
                print("No users found in users.json")
                return None
    except FileNotFoundError:
        print("Error: users.json file not found")
        return None
    except json.JSONDecodeError:
        print("Error: users.json is not valid JSON")
        return None

def get_user_by_email(email):
    """Get a specific user from users.json by email"""
    try:
        with open('users.json', 'r') as f:
            users_data = json.load(f)
            if users_data and 'users' in users_data and len(users_data['users']) > 0:
                for user in users_data['users']:
                    if user['email'] == email:
                        return user
                # If not found, log and return None
                print(f"User with email {email} not found in users.json")
                return None
            else:
                print("No users found in users.json")
                return None
    except FileNotFoundError:
        print("Error: users.json file not found")
        return None
    except json.JSONDecodeError:
        print("Error: users.json is not valid JSON")
        return None

def get_agent_id():
    """Get the Zendesk agent ID for Sebastian"""
    url = f"{BASE_URL}/users/search.json?query=sebastian@sandgarden.com"
    response = requests.get(url, auth=get_auth())
    
    if response.status_code == 200:
        users = response.json().get('users', [])
        if users:
            return users[0]['id']
    
    print(f"Error finding agent user: {response.status_code}")
    return None

def get_user_id(email):
    """Get the Zendesk user ID for a given email"""
    url = f"{BASE_URL}/users/search.json?query={email}"
    response = requests.get(url, auth=get_auth())
    
    if response.status_code == 200:
        users = response.json().get('users', [])
        if users:
            return users[0]['id']
    
    print(f"Error finding user with email {email}: {response.status_code}")
    return None

def create_ticket(subject, comment, requester_name, requester_email):
    """Create a new ticket in Zendesk"""
    url = f"{BASE_URL}/tickets.json"
    data = {
        "ticket": {
            "subject": subject,
            "comment": {
                "body": comment
            },
            "requester": {
                "name": requester_name,
                "email": requester_email
            }
        }
    }
    
    response = requests.post(url, json=data, auth=get_auth())
    if response.status_code == 201:
        return response.json()['ticket']
    else:
        print(f"Error creating ticket: {response.status_code}")
        return None

def get_retry_after(response):
    """
    Extract retry wait time from response headers or response text
    
    According to Zendesk docs, when rate limit is exceeded:
    1. Response will have 429 status code
    2. Response will have a Retry-After header indicating seconds to wait
    3. If header is missing, fall back to parsing response text
    """
    # First check for the Retry-After header (most reliable)
    retry_after = response.headers.get('Retry-After')
    if retry_after:
        try:
            return int(retry_after)
        except (ValueError, TypeError):
            pass
    
    # If no header or couldn't parse it, check response text
    try:
        if 'retry after' in response.text.lower():
            match = re.search(r'retry after (\d+)', response.text.lower())
            if match:
                return int(match.group(1))
    except Exception:
        pass
    
    # Check rate limit reset time from other headers
    try:
        reset_time = response.headers.get('ratelimit-reset')
        if reset_time:
            return int(reset_time)
    except (ValueError, TypeError):
        pass
    
    # Default fallback: 60 seconds
    return 60

def api_request_with_retry(request_func, max_retries=5, *args, **kwargs):
    """Make an API request with retry logic for rate limiting"""
    retries = 0
    while retries < max_retries:
        success, response = request_func(*args, **kwargs)
        
        # If request succeeded, return immediately
        if success:
            # Log rate limit information if available
            if 'X-Rate-Limit-Remaining' in response.headers or 'ratelimit-remaining' in response.headers:
                remaining = response.headers.get('X-Rate-Limit-Remaining', 
                                            response.headers.get('ratelimit-remaining', 'unknown'))
                limit = response.headers.get('X-Rate-Limit', 
                                        response.headers.get('ratelimit-limit', 'unknown'))
                print(f"Rate limit status: {remaining}/{limit} requests remaining")
            return True
            
        # If we got a rate limit error, wait and retry
        if response.status_code == 429:
            retries += 1
            # Get wait time from response using headers
            wait_time = get_retry_after(response)
            print(f"Rate limit exceeded (429). Waiting {wait_time} seconds before retry {retries}/{max_retries}...")
            time.sleep(wait_time)
        else:
            # For non-rate-limit errors, don't retry
            print(f"Error: {response.status_code} - {response.text}")
            return False
            
    print(f"Maximum retries ({max_retries}) reached. Could not complete operation.")
    return False

def _assign_ticket(ticket_id, assignee_id):
    """Internal function for assign_ticket to use with retry logic"""
    url = f"{BASE_URL}/tickets/{ticket_id}.json"
    data = {
        "ticket": {
            "assignee_id": assignee_id
        }
    }
    
    response = requests.put(url, json=data, auth=get_auth())
    return response.status_code in [200, 201], response

def assign_ticket(ticket_id, assignee_id):
    """Assign a ticket to an agent with retry logic"""
    success = api_request_with_retry(_assign_ticket, 5, ticket_id, assignee_id)
    if success:
        print(f"Ticket #{ticket_id} assigned to agent")
        return True
    else:
        print(f"Failed to assign ticket #{ticket_id}")
        return False

def _close_ticket(ticket_id):
    """Internal function for close_ticket to use with retry logic"""
    url = f"{BASE_URL}/tickets/{ticket_id}.json"
    data = {
        "ticket": {
            "status": "solved"
        }
    }
    
    response = requests.put(url, json=data, auth=get_auth())
    return response.status_code in [200, 201], response

def close_ticket(ticket_id):
    """Close a ticket as resolved with retry logic"""
    success = api_request_with_retry(_close_ticket, 5, ticket_id)
    if success:
        print(f"Ticket #{ticket_id} closed as resolved")
        return True
    else:
        print(f"Failed to close ticket #{ticket_id}")
        return False

def _add_comment_as_customer(ticket_id, comment, customer_id):
    """Internal function for add_comment_as_customer to use with retry logic"""
    url = f"{BASE_URL}/tickets/{ticket_id}.json"
    
    data = {
        "ticket": {
            "comment": {
                "body": comment,
                "author_id": customer_id,
                "public": True
            }
        }
    }
    
    response = requests.put(url, json=data, auth=get_auth())
    return response.status_code in [200, 201], response

def add_comment_as_customer(ticket_id, comment, customer_id):
    """Add a comment as the customer with retry logic"""
    success = api_request_with_retry(_add_comment_as_customer, 5, ticket_id, comment, customer_id)
    return success

def _add_comment_as_agent(ticket_id, comment, agent_id):
    """Internal function for add_comment_as_agent to use with retry logic"""
    url = f"{BASE_URL}/tickets/{ticket_id}.json"
    
    data = {
        "ticket": {
            "comment": {
                "body": comment,
                "author_id": agent_id,
                "public": True
            }
        }
    }
    
    response = requests.put(url, json=data, auth=get_auth())
    return response.status_code in [200, 201], response

def add_comment_as_agent(ticket_id, comment, agent_id):
    """Add a comment as the agent with retry logic"""
    success = api_request_with_retry(_add_comment_as_agent, 5, ticket_id, comment, agent_id)
    return success

def random_wait_time():
    """Generate a random wait time between 5 and 20 seconds"""
    return random.randint(5, 20)

def create_conversations_from_file(filename, agent_id):
    """Create conversations from a specific JSON file"""
    print(f"Creating conversations from {filename}...")
    
    # Read conversation template from JSON file
    try:
        with open(filename, 'r') as f:
            conversation_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {filename} file not found")
        return
    except json.JSONDecodeError:
        print(f"Error: {filename} is not valid JSON")
        return
    
    # Process each conversation
    for conversation in conversation_data.get('conversations', []):
        # Get specified user for this conversation or fall back to random user if not specified
        user = None
        if 'user_email' in conversation:
            user = get_user_by_email(conversation['user_email'])
            if not user:
                print(f"Could not find user with email {conversation['user_email']}, falling back to random user")
        
        # If no user was specified or found, get a random user
        if not user:
            user = get_random_user()
            if not user:
                print("Could not get a random user, skipping conversation")
                continue
            
        # Get the customer ID for properly attributing comments
        customer_id = get_user_id(user['email'])
        if not customer_id:
            print(f"Could not find the customer user with email {user['email']}, skipping conversation")
            continue
            
        print(f"\nCreating conversation with user: {user['first_name']} {user['last_name']} ({user['email']})")
        print(f"Customer ID: {customer_id}")
        
        subject = conversation.get('subject', 'Support Request')
        comments = conversation.get('comments', [])
        should_close = conversation.get('should_close', False)
        
        if not comments:
            print("No comments found in conversation")
            continue
        
        # Create the initial ticket with the first comment
        initial_comment = comments[0]['content']
        print(f"Creating ticket: {subject}")
        ticket = create_ticket(
            subject,
            initial_comment,
            f"{user['first_name']} {user['last_name']}",
            user['email']
        )
        
        if not ticket:
            print("Failed to create the initial ticket")
            continue
        
        print(f"Successfully created ticket #{ticket['id']}")
        
        # Assign the ticket to the agent
        assign_ticket(ticket['id'], agent_id)
        
        # Add subsequent comments with random delays
        for i, comment_data in enumerate(comments[1:], 1):
            author = comment_data['author']
            content = comment_data['content']
            
            # Wait a random time between comments
            wait_time = random_wait_time()
            print(f"Waiting {wait_time} seconds before adding the next comment...")
            time.sleep(wait_time)
            
            # Add comment as customer or agent
            if author == 'agent':
                print(f"Adding agent comment #{i}")
                success = add_comment_as_agent(ticket['id'], content, agent_id)
            else:
                print(f"Adding customer comment #{i}")
                success = add_comment_as_customer(ticket['id'], content, customer_id)
                
            if not success:
                print(f"Failed to add comment #{i} after multiple retries. Skipping to next comment.")
        
        # Close the ticket if specified
        if should_close:
            print(f"Closing ticket #{ticket['id']} as resolved")
            close_ticket(ticket['id'])
        
        print(f"Completed conversation for ticket #{ticket['id']}")

def main():
    """Main function to create demo conversations"""
    print("Starting demo conversation creation...")
    
    # Get the agent ID
    agent_id = get_agent_id()
    if not agent_id:
        print("Could not find the agent user. Make sure Sebastian's email is correct.")
        return
        
    print(f"Found agent ID: {agent_id}")
    
    # Create conversations from both files
    #create_conversations_from_file('new_conversation.json', agent_id)
    #create_conversations_from_file('additional_conversations.json', agent_id)
    create_conversations_from_file('feature_missing.json', agent_id)
    
    print("\nDemo conversation creation completed!")

if __name__ == "__main__":
    main() 
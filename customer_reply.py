#!/usr/bin/env python3

import requests
import json
import time
import anthropic
import sys
from datetime import datetime
from config import API_TOKEN, ADMIN_EMAIL, BASE_URL, ANTHROPIC_API_KEY, ANTHROPIC_MODEL

# List of possible Claude models to try in order of preference
CLAUDE_MODELS = [
    "claude-3-opus-20240229",
    "claude-3-haiku-20240307",
    "claude-3-5-sonnet-20240620",
    "claude-3-sonnet-20240229"
]

def get_auth():
    """Return the authentication tuple for requests"""
    return (f"{ADMIN_EMAIL}/token", API_TOKEN)

def get_open_tickets_with_agent_comments():
    """Get a list of open tickets with comments from support agents"""
    # First, get all open tickets
    url = f"{BASE_URL}/search.json?query=type:ticket status:open"
    
    tickets_with_agent_comments = []
    
    try:
        response = requests.get(url, auth=get_auth())
        
        if response.status_code != 200:
            print(f"Error fetching tickets: {response.status_code} - {response.text}")
            return []
        
        tickets = response.json().get('results', [])
        
        if not tickets:
            print("No open tickets found.")
            return []
            
        print(f"Found {len(tickets)} open tickets. Checking for agent comments...")
        
        # For each ticket, get its comments and check if the most recent one is from an agent
        for ticket in tickets:
            ticket_id = ticket['id']
            
            # Get the ticket's comments
            comments_url = f"{BASE_URL}/tickets/{ticket_id}/comments.json"
            comments_response = requests.get(comments_url, auth=get_auth())
            
            if comments_response.status_code != 200:
                print(f"Error fetching comments for ticket #{ticket_id}: {comments_response.status_code}")
                continue
                
            comments = comments_response.json().get('comments', [])
            
            if len(comments) < 2:
                # Skip tickets with just one comment (the initial customer request)
                continue
                
            # Get the most recent comment
            latest_comment = comments[-1]
            
            # Check if it's from an agent (not the requester)
            if latest_comment['author_id'] != ticket['requester_id']:
                # Convert created_at string to datetime for sorting
                created_at = datetime.fromisoformat(latest_comment['created_at'].replace('Z', '+00:00'))
                
                tickets_with_agent_comments.append({
                    'ticket_id': ticket_id,
                    'subject': ticket['subject'],
                    'requester_id': ticket['requester_id'],
                    'latest_comment_time': created_at,
                    'latest_comment': latest_comment['body'],
                    'agent_id': latest_comment['author_id'],
                    'all_comments': comments
                })
        
        # Sort by the latest comment time, most recent first
        tickets_with_agent_comments.sort(key=lambda x: x['latest_comment_time'], reverse=True)
        
        return tickets_with_agent_comments
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return []

def get_user_data(user_id):
    """Get user data from their ID"""
    url = f"{BASE_URL}/users/{user_id}.json"
    
    try:
        response = requests.get(url, auth=get_auth())
        
        if response.status_code != 200:
            print(f"Error fetching user data: {response.status_code}")
            return None
            
        return response.json().get('user')
    except Exception as e:
        print(f"Error getting user data: {str(e)}")
        return None

def generate_customer_response(ticket_info):
    """Generate a customer response using the Anthropic API with fallback models"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    # Get user data for the customer name
    user = get_user_data(ticket_info['requester_id'])
    customer_name = f"{user['name']}" if user else "Customer"
    
    # Format the ticket's conversation history
    conversation_history = ""
    
    for i, comment in enumerate(ticket_info['all_comments']):
        author_id = comment['author_id']
        if author_id == ticket_info['requester_id']:
            author = customer_name
        else:
            author = "Support Agent"
            
        conversation_history += f"{author}: {comment['body']}\n\n"
    
    # Check if the latest comment is from an agent
    latest_comment = ticket_info['latest_comment']
    
    prompt = f"""
You are roleplaying as {customer_name}, a customer who has contacted support about an issue. 
I need you to write a reply to the support agent's most recent response.

Here is the ticket subject: "{ticket_info['subject']}"

Here is the conversation history:
{conversation_history}

The support agent's latest response is:
"{latest_comment}"

Please write a customer response that follows these guidelines:
1. If the support agent was helpful, kind, and addressed your concerns well, respond with extreme happiness and satisfaction. Mention that you're thrilled with the service and will definitely remain a loyal customer.
2. If the support agent was unhelpful, dismissive, or rude, respond with extreme anger and frustration. Threaten to cancel your subscription and take your business elsewhere.
3. Your response must clearly fall into one of these two categories - either very happy or very upset.
4. Stay in character as {customer_name} and refer to details from the conversation.
5. Keep your response under 200 words.

Write only the customer's response text, with no additional formatting or explanations.
"""

    # Try each model in the list until one works
    last_error = None
    for model in CLAUDE_MODELS:
        try:
            print(f"Trying to generate response with model: {model}")
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                temperature=0.7,
                system="You are an assistant that helps create realistic customer service conversations.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract the customer response from Claude's output
            customer_response = response.content[0].text.strip()
            print(f"Successfully generated response using model: {model}")
            return customer_response
        except Exception as e:
            last_error = e
            print(f"Error with model {model}: {str(e)}")
            continue
    
    # If we've tried all models and none worked
    print(f"All models failed. Last error: {str(last_error)}")
    return None

def add_comment_as_customer(ticket_id, comment, customer_id):
    """Add a comment to the ticket as the customer"""
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
    
    try:
        response = requests.put(url, json=data, auth=get_auth())
        
        if response.status_code in [200, 201]:
            return True
        else:
            print(f"Error adding customer comment: {response.status_code} - {response.text}")
            
            # Handle rate limiting
            if response.status_code == 429:
                # Extract retry time if possible
                wait_time = 60  # Default wait time
                if 'retry after' in response.text.lower():
                    import re
                    match = re.search(r'retry after (\d+)', response.text.lower())
                    if match:
                        wait_time = int(match.group(1))
                
                print(f"Rate limit encountered. Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                
                # Retry once after waiting
                retry_response = requests.put(url, json=data, auth=get_auth())
                return retry_response.status_code in [200, 201]
            
            return False
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

def main():
    """Main function to find the most recent ticket with an agent comment and add a customer reply"""
    print("Looking for open tickets with recent agent comments...")
    
    # Get open tickets with agent comments, sorted by most recent
    tickets = get_open_tickets_with_agent_comments()
    
    if not tickets:
        print("No suitable tickets found. Exiting.")
        sys.exit(0)
    
    # Get the most recent ticket
    most_recent_ticket = tickets[0]
    
    print(f"\nFound ticket #{most_recent_ticket['ticket_id']}: {most_recent_ticket['subject']}")
    print(f"Latest agent comment: {most_recent_ticket['latest_comment'][:100]}...")
    
    # Generate a customer response
    print("\nGenerating customer response...")
    response = generate_customer_response(most_recent_ticket)
    
    if not response:
        print("Failed to generate customer response. Exiting.")
        sys.exit(1)
    
    print(f"\nGenerated response:\n{response}\n")
    
    # Add the response to the ticket
    print(f"Adding response to ticket #{most_recent_ticket['ticket_id']}...")
    success = add_comment_as_customer(
        most_recent_ticket['ticket_id'],
        response,
        most_recent_ticket['requester_id']
    )
    
    if success:
        print("Customer response added successfully!")
    else:
        print("Failed to add customer response.")

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3

import requests
import json
import time
import warnings
from config import API_TOKEN, ADMIN_EMAIL, BASE_URL

# Suppress the specific urllib3 warning
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL 1.1.1+')

def get_auth():
    """Return the authentication tuple for requests"""
    return (f"{ADMIN_EMAIL}/token", API_TOKEN)

def delete_all_tickets():
    """Delete all tickets in the Zendesk instance"""
    print("Deleting all tickets...")
    
    # First, get all tickets
    url = f"{BASE_URL}/tickets.json"
    ticket_ids = []
    
    while url:
        response = requests.get(url, auth=get_auth())
        if response.status_code != 200:
            print(f"Error fetching tickets: {response.status_code} - {response.text}")
            return False
            
        data = response.json()
        tickets = data.get('tickets', [])
        if not tickets:
            break
            
        ticket_ids.extend([ticket['id'] for ticket in tickets])
        url = data.get('next_page')
    
    if not ticket_ids:
        print("No tickets found to delete")
        return True
    
    print(f"Found {len(ticket_ids)} tickets to delete")
    
    # Delete tickets in batches of 100 (Zendesk API limit)
    batch_size = 100
    success = True
    for i in range(0, len(ticket_ids), batch_size):
        batch = ticket_ids[i:i + batch_size]
        delete_url = f"{BASE_URL}/tickets/destroy_many.json?ids={','.join(map(str, batch))}"
        delete_response = requests.delete(delete_url, auth=get_auth())
        
        if delete_response.status_code in [200, 204]:
            print(f"Successfully deleted {len(batch)} tickets")
        else:
            print(f"Error deleting tickets batch: {delete_response.status_code}")
            success = False
    
    return success

def delete_customer_users():
    """Delete all customer users (not team members)"""
    print("Deleting customer users...")
    url = f"{BASE_URL}/users.json?role=end-user"
    success = True
    
    while True:
        response = requests.get(url, auth=get_auth())
        if response.status_code != 200:
            print(f"Error fetching users: {response.status_code}")
            return False
            
        users = response.json().get('users', [])
        if not users:
            break
            
        for user in users:
            # First try to deactivate the user
            deactivate_url = f"{BASE_URL}/users/{user['id']}.json"
            deactivate_data = {"user": {"active": False}}
            deactivate_response = requests.put(deactivate_url, json=deactivate_data, auth=get_auth())
            
            if deactivate_response.status_code not in [200, 204]:
                print(f"Could not deactivate user {user['email']}: {deactivate_response.status_code}")
                success = False
                continue
            
            # Then try to delete the user
            delete_url = f"{BASE_URL}/users/{user['id']}.json"
            delete_response = requests.delete(delete_url, auth=get_auth())
            
            if delete_response.status_code in [200, 204]:
                print(f"Successfully deleted user: {user['email']}")
            elif delete_response.status_code == 422:
                print(f"Could not delete user {user['email']} - may have associated tickets or other dependencies")
                # Try to get more information about why we can't delete
                user_url = f"{BASE_URL}/users/{user['id']}.json"
                user_response = requests.get(user_url, auth=get_auth())
                if user_response.status_code == 200:
                    user_data = user_response.json().get('user', {})
                    if user_data.get('active'):
                        print(f"  - User is still active")
                    if user_data.get('ticket_count', 0) > 0:
                        print(f"  - User has {user_data.get('ticket_count')} associated tickets")
                success = False
            else:
                print(f"Error deleting user {user['email']}: {delete_response.status_code} - {delete_response.text}")
                success = False
        
        # Check if there are more pages
        url = response.json().get('next_page')
        if not url:
            break
    
    return success

def delete_organizations():
    """Delete all organizations"""
    print("Deleting organizations...")
    url = f"{BASE_URL}/organizations.json"
    success = True
    
    while True:
        response = requests.get(url, auth=get_auth())
        if response.status_code != 200:
            print(f"Error fetching organizations: {response.status_code}")
            return False
            
        orgs = response.json().get('organizations', [])
        if not orgs:
            break
            
        for org in orgs:
            delete_url = f"{BASE_URL}/organizations/{org['id']}.json"
            delete_response = requests.delete(delete_url, auth=get_auth())
            if delete_response.status_code in [200, 204]:
                print(f"Successfully deleted organization: {org['name']}")
            elif delete_response.status_code == 422:
                print(f"Could not delete organization {org['name']} - may have associated users or tickets")
                success = False
            else:
                print(f"Error deleting organization {org['name']}: {delete_response.status_code} - {delete_response.text}")
                success = False
        
        # Check if there are more pages
        url = response.json().get('next_page')
        if not url:
            break
    
    return success

def delete_custom_fields():
    """Delete all custom fields (ticket, user, and organization fields)"""
    print("Deleting custom fields...")
    success = True
    
    # Delete ticket fields
    print("Deleting custom ticket fields...")
    url = f"{BASE_URL}/ticket_fields.json"
    
    response = requests.get(url, auth=get_auth())
    if response.status_code != 200:
        print(f"Error fetching ticket fields: {response.status_code}")
        success = False
    else:
        fields = response.json().get('ticket_fields', [])
        # Get both explicitly marked custom fields and "special" fields (neither system nor custom)
        custom_fields = [field for field in fields if (field.get('custom') and not field.get('system')) or 
                        (not field.get('system') and not field.get('custom') and field.get('active'))]
        
        # Special fields to target by specific names (adjust as needed)
        special_field_names = [
            "Sentiment", "Customer Value", "Resolution Trend", "Sandgarden Priority Score", 
            "Escalation Recommendation", "Sentiment Trend"
        ]
        
        # Add any field with these names if not already included
        for field in fields:
            if field.get('title') in special_field_names and field not in custom_fields:
                custom_fields.append(field)
        
        print(f"Found {len(custom_fields)} custom/special ticket fields to delete")
        
        for field in custom_fields:
            delete_url = f"{BASE_URL}/ticket_fields/{field['id']}.json"
            delete_response = requests.delete(delete_url, auth=get_auth())
            if delete_response.status_code in [200, 204]:
                print(f"Successfully deleted ticket field: {field['title']} (ID: {field['id']})")
            elif delete_response.status_code == 422:
                print(f"Could not delete ticket field {field['title']} - may have dependencies")
                success = False
            elif delete_response.status_code == 429:
                # Rate limit hit, wait and try again
                retry_after = delete_response.headers.get('Retry-After', '60')
                retry_seconds = int(retry_after)
                print(f"Rate limit reached. Waiting {retry_seconds} seconds before continuing...")
                time.sleep(retry_seconds)
                # Try again
                delete_response = requests.delete(delete_url, auth=get_auth())
                if delete_response.status_code in [200, 204]:
                    print(f"Successfully deleted ticket field: {field['title']} after rate limit wait")
                else:
                    print(f"Error deleting ticket field {field['title']} after rate limit wait: {delete_response.status_code} - {delete_response.text}")
                    success = False
            else:
                print(f"Error deleting ticket field {field['title']}: {delete_response.status_code} - {delete_response.text}")
                success = False
            
            # Small delay to avoid rate limiting
            time.sleep(0.5)
    
    # Delete user fields
    print("\nDeleting custom user fields...")
    url = f"{BASE_URL}/user_fields.json"
    
    response = requests.get(url, auth=get_auth())
    if response.status_code != 200:
        print(f"Error fetching user fields: {response.status_code}")
        success = False
    else:
        fields = response.json().get('user_fields', [])
        print(f"Found {len(fields)} custom user fields to delete")
        
        for field in fields:
            delete_url = f"{BASE_URL}/user_fields/{field['id']}.json"
            delete_response = requests.delete(delete_url, auth=get_auth())
            if delete_response.status_code in [200, 204]:
                print(f"Successfully deleted custom user field: {field['title']}")
            elif delete_response.status_code == 422:
                print(f"Could not delete custom user field {field['title']} - may have dependencies")
                success = False
            elif delete_response.status_code == 429:
                # Rate limit hit, wait and try again
                retry_after = delete_response.headers.get('Retry-After', '60')
                retry_seconds = int(retry_after)
                print(f"Rate limit reached. Waiting {retry_seconds} seconds before continuing...")
                time.sleep(retry_seconds)
                # Try again
                delete_response = requests.delete(delete_url, auth=get_auth())
                if delete_response.status_code in [200, 204]:
                    print(f"Successfully deleted custom user field: {field['title']} after rate limit wait")
                else:
                    print(f"Error deleting custom user field {field['title']} after rate limit wait: {delete_response.status_code} - {delete_response.text}")
                    success = False
            else:
                print(f"Error deleting custom user field {field['title']}: {delete_response.status_code} - {delete_response.text}")
                success = False
            
            # Small delay to avoid rate limiting
            time.sleep(0.5)
    
    # Delete organization fields
    print("\nDeleting custom organization fields...")
    url = f"{BASE_URL}/organization_fields.json"
    
    response = requests.get(url, auth=get_auth())
    if response.status_code != 200:
        print(f"Error fetching organization fields: {response.status_code}")
        success = False
    else:
        fields = response.json().get('organization_fields', [])
        print(f"Found {len(fields)} custom organization fields to delete")
        
        for field in fields:
            delete_url = f"{BASE_URL}/organization_fields/{field['id']}.json"
            delete_response = requests.delete(delete_url, auth=get_auth())
            if delete_response.status_code in [200, 204]:
                print(f"Successfully deleted custom organization field: {field['title']}")
            elif delete_response.status_code == 422:
                print(f"Could not delete custom organization field {field['title']} - may have dependencies")
                success = False
            elif delete_response.status_code == 429:
                # Rate limit hit, wait and try again
                retry_after = delete_response.headers.get('Retry-After', '60')
                retry_seconds = int(retry_after)
                print(f"Rate limit reached. Waiting {retry_seconds} seconds before continuing...")
                time.sleep(retry_seconds)
                # Try again
                delete_response = requests.delete(delete_url, auth=get_auth())
                if delete_response.status_code in [200, 204]:
                    print(f"Successfully deleted custom organization field: {field['title']} after rate limit wait")
                else:
                    print(f"Error deleting custom organization field {field['title']} after rate limit wait: {delete_response.status_code} - {delete_response.text}")
                    success = False
            else:
                print(f"Error deleting custom organization field {field['title']}: {delete_response.status_code} - {delete_response.text}")
                success = False
            
            # Small delay to avoid rate limiting
            time.sleep(0.5)
    
    # After all the field deletes, check if we need to delete ticket forms
    delete_ticket_forms()
    
    return success

def delete_ticket_forms():
    """Delete all ticket forms except the default one"""
    print("\nDeleting custom ticket forms...")
    url = f"{BASE_URL}/ticket_forms.json"
    success = True
    
    response = requests.get(url, auth=get_auth())
    if response.status_code != 200:
        print(f"Error fetching ticket forms: {response.status_code}")
        return False
        
    forms = response.json().get('ticket_forms', [])
    # Filter out the default form
    custom_forms = [form for form in forms if form.get('name') != 'Default Ticket Form']
    print(f"Found {len(custom_forms)} custom ticket forms to delete")
    
    for form in custom_forms:
        delete_url = f"{BASE_URL}/ticket_forms/{form['id']}.json"
        delete_response = requests.delete(delete_url, auth=get_auth())
        if delete_response.status_code in [200, 204]:
            print(f"Successfully deleted ticket form: {form['name']}")
        elif delete_response.status_code == 429:
            # Rate limit hit, wait and try again
            retry_after = delete_response.headers.get('Retry-After', '60')
            retry_seconds = int(retry_after)
            print(f"Rate limit reached. Waiting {retry_seconds} seconds before continuing...")
            time.sleep(retry_seconds)
            # Try again
            delete_response = requests.delete(delete_url, auth=get_auth())
            if delete_response.status_code in [200, 204]:
                print(f"Successfully deleted ticket form: {form['name']} after rate limit wait")
            else:
                print(f"Error deleting ticket form {form['name']} after rate limit wait: {delete_response.status_code} - {delete_response.text}")
                success = False
        else:
            print(f"Error deleting ticket form {form['name']}: {delete_response.status_code} - {delete_response.text}")
            success = False
        
        # Small delay to avoid rate limiting
        time.sleep(0.5)
    
    return success

def delete_triggers():
    """Delete all custom triggers"""
    print("Deleting custom triggers...")
    url = f"{BASE_URL}/triggers.json"
    success = True
    
    response = requests.get(url, auth=get_auth())
    if response.status_code != 200:
        print(f"Error fetching triggers: {response.status_code}")
        return False
        
    triggers = response.json().get('triggers', [])
    # Filter out system triggers
    custom_triggers = [trigger for trigger in triggers if not trigger.get('default')]
    print(f"Found {len(custom_triggers)} custom triggers to delete")
    
    for trigger in custom_triggers:
        delete_url = f"{BASE_URL}/triggers/{trigger['id']}.json"
        delete_response = requests.delete(delete_url, auth=get_auth())
        if delete_response.status_code in [200, 204]:
            print(f"Successfully deleted trigger: {trigger['title']}")
        elif delete_response.status_code == 429:
            # Rate limit hit, wait and try again
            retry_after = delete_response.headers.get('Retry-After', '60')
            retry_seconds = int(retry_after)
            print(f"Rate limit reached. Waiting {retry_seconds} seconds before continuing...")
            time.sleep(retry_seconds)
            # Try again
            delete_response = requests.delete(delete_url, auth=get_auth())
            if delete_response.status_code in [200, 204]:
                print(f"Successfully deleted trigger: {trigger['title']} after rate limit wait")
            else:
                print(f"Error deleting trigger {trigger['title']} after rate limit wait: {delete_response.status_code} - {delete_response.text}")
                success = False
        else:
            print(f"Error deleting trigger {trigger['title']}: {delete_response.status_code} - {delete_response.text}")
            success = False
        
        # Small delay to avoid rate limiting
        time.sleep(0.5)
    
    return success

def delete_automations():
    """Delete all custom automations"""
    print("Deleting custom automations...")
    url = f"{BASE_URL}/automations.json"
    success = True
    
    response = requests.get(url, auth=get_auth())
    if response.status_code != 200:
        print(f"Error fetching automations: {response.status_code}")
        return False
        
    automations = response.json().get('automations', [])
    # Filter out system automations
    custom_automations = [automation for automation in automations if not automation.get('default')]
    print(f"Found {len(custom_automations)} custom automations to delete")
    
    for automation in custom_automations:
        delete_url = f"{BASE_URL}/automations/{automation['id']}.json"
        delete_response = requests.delete(delete_url, auth=get_auth())
        if delete_response.status_code in [200, 204]:
            print(f"Successfully deleted automation: {automation['title']}")
        elif delete_response.status_code == 429:
            # Rate limit hit, wait and try again
            retry_after = delete_response.headers.get('Retry-After', '60')
            retry_seconds = int(retry_after)
            print(f"Rate limit reached. Waiting {retry_seconds} seconds before continuing...")
            time.sleep(retry_seconds)
            # Try again
            delete_response = requests.delete(delete_url, auth=get_auth())
            if delete_response.status_code in [200, 204]:
                print(f"Successfully deleted automation: {automation['title']} after rate limit wait")
            else:
                print(f"Error deleting automation {automation['title']} after rate limit wait: {delete_response.status_code} - {delete_response.text}")
                success = False
        else:
            print(f"Error deleting automation {automation['title']}: {delete_response.status_code} - {delete_response.text}")
            success = False
        
        # Small delay to avoid rate limiting
        time.sleep(0.5)
    
    return success

def delete_macros():
    """Delete all custom macros"""
    print("Deleting custom macros...")
    url = f"{BASE_URL}/macros.json"
    success = True
    
    response = requests.get(url, auth=get_auth())
    if response.status_code != 200:
        print(f"Error fetching macros: {response.status_code}")
        return False
        
    macros = response.json().get('macros', [])
    # Attempt to filter system macros
    custom_macros = [macro for macro in macros if not macro.get('default')]
    print(f"Found {len(custom_macros)} custom macros to delete")
    
    for macro in custom_macros:
        delete_url = f"{BASE_URL}/macros/{macro['id']}.json"
        delete_response = requests.delete(delete_url, auth=get_auth())
        if delete_response.status_code in [200, 204]:
            print(f"Successfully deleted macro: {macro['title']}")
        elif delete_response.status_code == 429:
            # Rate limit hit, wait and try again
            retry_after = delete_response.headers.get('Retry-After', '60')
            retry_seconds = int(retry_after)
            print(f"Rate limit reached. Waiting {retry_seconds} seconds before continuing...")
            time.sleep(retry_seconds)
            # Try again
            delete_response = requests.delete(delete_url, auth=get_auth())
            if delete_response.status_code in [200, 204]:
                print(f"Successfully deleted macro: {macro['title']} after rate limit wait")
            else:
                print(f"Error deleting macro {macro['title']} after rate limit wait: {delete_response.status_code} - {delete_response.text}")
                success = False
        else:
            print(f"Error deleting macro {macro['title']}: {delete_response.status_code} - {delete_response.text}")
            success = False
        
        # Small delay to avoid rate limiting
        time.sleep(0.5)
    
    return success

def delete_views():
    """Delete all custom views"""
    print("Deleting custom views...")
    url = f"{BASE_URL}/views.json"
    success = True
    
    response = requests.get(url, auth=get_auth())
    if response.status_code != 200:
        print(f"Error fetching views: {response.status_code}")
        return False
        
    views = response.json().get('views', [])
    # Filter out system views
    custom_views = [view for view in views if not view.get('default')]
    print(f"Found {len(custom_views)} custom views to delete")
    
    for view in custom_views:
        delete_url = f"{BASE_URL}/views/{view['id']}.json"
        delete_response = requests.delete(delete_url, auth=get_auth())
        if delete_response.status_code in [200, 204]:
            print(f"Successfully deleted view: {view['title']}")
        elif delete_response.status_code == 429:
            # Rate limit hit, wait and try again
            retry_after = delete_response.headers.get('Retry-After', '60')
            retry_seconds = int(retry_after)
            print(f"Rate limit reached. Waiting {retry_seconds} seconds before continuing...")
            time.sleep(retry_seconds)
            # Try again
            delete_response = requests.delete(delete_url, auth=get_auth())
            if delete_response.status_code in [200, 204]:
                print(f"Successfully deleted view: {view['title']} after rate limit wait")
            else:
                print(f"Error deleting view {view['title']} after rate limit wait: {delete_response.status_code} - {delete_response.text}")
                success = False
        else:
            print(f"Error deleting view {view['title']}: {delete_response.status_code} - {delete_response.text}")
            success = False
        
        # Small delay to avoid rate limiting
        time.sleep(0.5)
    
    return success

def analyze_ticket_fields():
    """Analyze and print all ticket fields to understand their structure"""
    print("Analyzing ticket fields...")
    url = f"{BASE_URL}/ticket_fields.json"
    
    response = requests.get(url, auth=get_auth())
    if response.status_code != 200:
        print(f"Error fetching ticket fields: {response.status_code}")
        return False
        
    fields = response.json().get('ticket_fields', [])
    print(f"Found {len(fields)} total ticket fields")
    
    # Count by type
    system_fields = 0
    custom_fields = 0
    active_fields = 0
    inactive_fields = 0
    
    # Print detailed info
    print("\nDetailed field information:")
    for i, field in enumerate(fields, 1):
        is_system = field.get('system', False)
        is_custom = field.get('custom', False)
        is_active = field.get('active', False)
        
        if is_system:
            system_fields += 1
        if is_custom:
            custom_fields += 1
        if is_active:
            active_fields += 1
        else:
            inactive_fields += 1
        
        print(f"{i}. Title: {field.get('title')}")
        print(f"   ID: {field.get('id')}")
        print(f"   Type: {field.get('type')}")
        print(f"   System: {is_system}")
        print(f"   Custom: {is_custom}")
        print(f"   Active: {is_active}")
        print()
    
    print(f"\nSummary:")
    print(f"Total fields: {len(fields)}")
    print(f"System fields: {system_fields}")
    print(f"Custom fields: {custom_fields}")
    print(f"Active fields: {active_fields}")
    print(f"Inactive fields: {inactive_fields}")
    
    return True

def check_dynamic_content():
    """Check for dynamic content fields that might be treated as custom fields in UI"""
    print("Checking dynamic content...")
    url = f"{BASE_URL}/dynamic_content/items.json"
    
    response = requests.get(url, auth=get_auth())
    if response.status_code != 200:
        print(f"Error fetching dynamic content: {response.status_code}")
        return False
        
    items = response.json().get('items', [])
    print(f"Found {len(items)} dynamic content items")
    
    if len(items) > 0:
        print("\nDynamic content details:")
        for i, item in enumerate(items, 1):
            print(f"{i}. Name: {item.get('name')}")
            print(f"   ID: {item.get('id')}")
            # Print any other relevant details
            print()
    
    return True

def check_brands():
    """Check for brands which might contain custom fields"""
    print("Checking brands...")
    url = f"{BASE_URL}/brands.json"
    
    response = requests.get(url, auth=get_auth())
    if response.status_code != 200:
        print(f"Error fetching brands: {response.status_code}")
        return False
        
    brands = response.json().get('brands', [])
    print(f"Found {len(brands)} brands")
    
    if len(brands) > 0:
        print("\nBrand details:")
        for i, brand in enumerate(brands, 1):
            print(f"{i}. Name: {brand.get('name')}")
            print(f"   ID: {brand.get('id')}")
            print(f"   Active: {brand.get('active')}")
            print()
    
    return True

def check_ticket_forms():
    """Check for ticket forms which might contain custom fields"""
    print("Checking ticket forms...")
    url = f"{BASE_URL}/ticket_forms.json"
    
    response = requests.get(url, auth=get_auth())
    if response.status_code != 200:
        print(f"Error fetching ticket forms: {response.status_code}")
        return False
        
    forms = response.json().get('ticket_forms', [])
    print(f"Found {len(forms)} ticket forms")
    
    if len(forms) > 0:
        print("\nTicket form details:")
        for i, form in enumerate(forms, 1):
            print(f"{i}. Name: {form.get('name')}")
            print(f"   ID: {form.get('id')}")
            print(f"   Active: {form.get('active')}")
            
            # Print the ticket field IDs used in this form
            ticket_field_ids = form.get('ticket_field_ids', [])
            print(f"   Fields: {ticket_field_ids}")
            print()
    
    return True

def analyze_all_custom_field_types():
    """Analyze all potential custom field types in Zendesk"""
    print("\n=======================================")
    print("ANALYZING ALL POTENTIAL CUSTOM FIELD TYPES")
    print("=======================================")
    
    # Check each type that might contain custom fields
    analyze_ticket_fields()
    
    print("\n---------------------------------------")
    check_dynamic_content()
    
    print("\n---------------------------------------")
    check_brands()
    
    print("\n---------------------------------------")
    check_ticket_forms()
    
    print("\n=======================================")
    print("CUSTOM FIELD ANALYSIS COMPLETE")
    print("=======================================")
    
    return True

def bulk_delete_special_ticket_fields():
    """Delete special ticket fields in bulk for efficiency"""
    print("\nBulk deleting special ticket fields...")
    
    # Get all ticket fields
    url = f"{BASE_URL}/ticket_fields.json"
    response = requests.get(url, auth=get_auth())
    if response.status_code != 200:
        print(f"Error fetching ticket fields: {response.status_code}")
        return False
    
    fields = response.json().get('ticket_fields', [])
    
    # Identify the special fields we want to delete (the ones with titles that match our patterns)
    special_field_patterns = [
        "Sentiment", "Customer Value", "Resolution Trend", "Sandgarden Priority Score", 
        "Escalation Recommendation", "Sentiment Trend"
    ]
    
    special_fields = []
    for field in fields:
        if any(pattern in field.get('title', '') for pattern in special_field_patterns) or \
           (not field.get('system') and not field.get('custom') and field.get('active')):
            special_fields.append(field)
    
    print(f"Found {len(special_fields)} special ticket fields to delete")
    
    # Delete in batches to avoid overwhelming the API
    batch_size = 10
    success = True
    total_deleted = 0
    
    for i in range(0, len(special_fields), batch_size):
        batch = special_fields[i:i + batch_size]
        print(f"\nProcessing batch {i//batch_size + 1} ({len(batch)} fields)...")
        
        for field in batch:
            delete_url = f"{BASE_URL}/ticket_fields/{field['id']}.json"
            delete_response = requests.delete(delete_url, auth=get_auth())
            
            if delete_response.status_code in [200, 204]:
                print(f"Successfully deleted field: {field['title']} (ID: {field['id']})")
                total_deleted += 1
            elif delete_response.status_code == 422:
                print(f"Could not delete field {field['title']} (ID: {field['id']}) - may have dependencies")
            elif delete_response.status_code == 429:
                # Rate limit hit, wait and try again
                retry_after = delete_response.headers.get('Retry-After', '60')
                retry_seconds = int(retry_after)
                print(f"Rate limit reached. Waiting {retry_seconds} seconds before continuing...")
                time.sleep(retry_seconds)
                
                # Try again
                delete_response = requests.delete(delete_url, auth=get_auth())
                if delete_response.status_code in [200, 204]:
                    print(f"Successfully deleted field: {field['title']} (ID: {field['id']}) after rate limit wait")
                    total_deleted += 1
                else:
                    print(f"Error deleting field {field['title']} (ID: {field['id']}) after rate limit wait: {delete_response.status_code}")
                    success = False
            else:
                print(f"Error deleting field {field['title']} (ID: {field['id']}): {delete_response.status_code}")
                success = False
            
            # Small delay to avoid rate limiting
            time.sleep(1)
        
        # Wait between batches
        if i + batch_size < len(special_fields):
            print(f"Waiting 10 seconds between batches...")
            time.sleep(10)
    
    print(f"\nBulk deletion complete. Successfully deleted {total_deleted} of {len(special_fields)} special fields.")
    return success

def main():
    """Main function to run all cleanup operations"""
    print("Starting Zendesk cleanup...")
    
    # Ask if the user wants just to run field analysis
    response = input("Do you want to run just the field analysis without cleanup? (yes/no): ")
    if response.lower() == 'yes':
        analyze_all_custom_field_types()
        return
    
    # Ask if the user wants to only delete special fields
    response = input("Do you want to only delete the special ticket fields? (yes/no): ")
    if response.lower() == 'yes':
        bulk_delete_special_ticket_fields()
        return
    
    # Ask if the user wants to run the full cleanup
    response = input("Do you want to run the full cleanup process? (yes/no): ")
    if response.lower() != 'yes':
        print("Cleanup process aborted by user.")
        return
    
    # Track overall success
    overall_success = True
    
    # Delete in order of dependencies
    print("\nStep 1: Deleting all tickets...")
    if not delete_all_tickets():
        overall_success = False
    
    # Wait for Zendesk to process the deletions
    print("\nWaiting for Zendesk to process ticket deletions...")
    time.sleep(30)  # Wait 30 seconds
    
    print("\nStep 2: Deleting customer users...")
    if not delete_customer_users():
        overall_success = False
    
    # Wait for Zendesk to process user deletions
    print("\nWaiting for Zendesk to process user deletions...")
    time.sleep(30)  # Wait 30 seconds
    
    print("\nStep 3: Deleting organizations...")
    if not delete_organizations():
        overall_success = False
    
    # Wait for Zendesk to process organization deletions
    print("\nWaiting for Zendesk to process organization deletions...")
    time.sleep(30)  # Wait 30 seconds
    
    # Delete dependencies of custom fields
    #print("\nStep 4: Deleting macros...")
    #if not delete_macros():
    #    overall_success = False
        
    #print("\nWaiting for Zendesk to process macro deletions...")
    #time.sleep(15)  # Wait 15 seconds
    
    #print("\nStep 5: Deleting views...")
    #if not delete_views():
    #    overall_success = False
        
    #print("\nWaiting for Zendesk to process view deletions...")
    #time.sleep(15)  # Wait 15 seconds
    
    #print("\nStep 6: Deleting triggers...")
    #if not delete_triggers():
    #    overall_success = False
        
    #print("\nWaiting for Zendesk to process trigger deletions...")
    #time.sleep(15)  # Wait 15 seconds
    
    #print("\nStep 7: Deleting automations...")
    #if not delete_automations():
    #    overall_success = False
    
    #print("\nWaiting for Zendesk to process automation deletions...")
    #time.sleep(15)  # Wait 15 seconds
    
    print("\nStep 8: Bulk deleting special ticket fields...")
    if not bulk_delete_special_ticket_fields():
        overall_success = False
    
    print("\nWaiting for Zendesk to process special field deletions...")
    time.sleep(15)  # Wait 15 seconds
    
    print("\nStep 9: Deleting remaining custom fields...")
    if not delete_custom_fields():
        overall_success = False
    
    if overall_success:
        print("\nCleanup completed successfully!")
    else:
        print("\nSome issues were encountered, not everything may have been cleaned up.")
        print("Note: If custom fields could not be deleted, it might be because there are still")
        print("dependencies such as triggers, automations, or views referencing them.")
        print("You may need to run this script multiple times or manually delete those dependencies.")

if __name__ == "__main__":
    main() 
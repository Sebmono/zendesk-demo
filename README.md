# Zendesk Management Scripts

This repository contains a set of Python scripts for managing your Zendesk instance. These scripts allow you to:
1. Clean up your Zendesk instance (delete tickets, users, organizations, and custom fields)
2. Create new organizations and users
3. Create test issues for each organization
4. Create realistic support conversations with back-and-forth interactions
5. Generate AI-powered customer responses to agent comments

## Prerequisites

- Python 3.6 or higher
- A Zendesk account with admin privileges
- Zendesk API token
- Anthropic API key (for Claude AI integration)

## Configuration

All credentials are read from environment variables. Nothing secret is stored in the
repository, and `config.py` exits with a clear message if a required variable is missing.

| Variable | Required | What it is |
| --- | --- | --- |
| `ZENDESK_API_TOKEN` | yes | Zendesk API token |
| `ZENDESK_EMAIL` | yes | Email of the Zendesk admin the token belongs to |
| `ZENDESK_SUBDOMAIN` | yes | Subdomain only: for `https://acme.zendesk.com`, use `acme` |
| `ANTHROPIC_API_KEY` | yes | Anthropic API key, used to generate customer replies |
| `ANTHROPIC_MODEL` | no | Model override, defaults to `claude-3-5-sonnet-latest` |

**Getting a Zendesk API token.** In Zendesk Admin Center, go to Apps and integrations >
APIs > Zendesk API, enable token access, and add an API token. Copy it when it is shown;
Zendesk will not show it again. The token authenticates as the admin user whose email you
put in `ZENDESK_EMAIL`.

**Getting an Anthropic API key.** Sign in at https://console.anthropic.com, open API keys,
and create a key.

### Setting the variables

Either export them in your shell:

```bash
export ZENDESK_API_TOKEN=...
export ZENDESK_EMAIL=admin@example.com
export ZENDESK_SUBDOMAIN=your-subdomain
export ANTHROPIC_API_KEY=...
```

Or copy the template and fill it in; `config.py` loads `.env` automatically via
`python-dotenv`:

```bash
cp .env.example .env
$EDITOR .env
```

`.env` is gitignored. Do not commit it, and do not put credentials back into `config.py`.

## Setup

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set the environment variables described above.

3. Prepare your data files:
   - `organizations.json`: Contains the list of organizations to create
   - `users.json`: Contains users for each organization
   - `new_conversation.json`: Contains templates for realistic support conversations
   - `additional_conversations.json`: Contains additional conversation templates

All organizations, users and conversations in this repository are fictional. The scripts
generate demo data only; none of it represents a real company or person.

## Usage

The scripts can be run independently in the following order:

1. Clean up your Zendesk instance:
   ```bash
   python cleanup_zendesk.py
   ```

2. Create organizations and users:
   ```bash
   python create_organizations_users.py
   ```

3. Create test issues:
   ```bash
   python create_test_issues.py
   ```

4. Create realistic support conversations:
   ```bash
   python create_demo_conversations.py
   ```

5. Generate AI-powered customer replies:
   ```bash
   python customer_reply.py
   ```

## File Structure

- `config.py`: Reads Zendesk and Anthropic credentials from the environment
- `.env.example`: Template listing the required environment variables
- `cleanup_zendesk.py`: Script to clean up your Zendesk instance
- `create_organizations_users.py`: Script to create organizations and users from JSON files
- `create_test_issues.py`: Script to create simple test issues
- `create_demo_conversations.py`: Script to create realistic support conversations
- `customer_reply.py`: Script to generate AI-powered customer responses to agent comments
- `organizations.json`: JSON file containing fictitious organization data
- `users.json`: JSON file containing user data (5 users per organization)
- `new_issues.json`: JSON file containing simple ticket template
- `new_conversation.json`: JSON file containing realistic support conversation templates
- `additional_conversations.json`: JSON file containing additional conversation templates
- `requirements.txt`: Python dependencies

## Conversation Features

The conversation creation script (`create_demo_conversations.py`) includes several realistic features:

- Back-and-forth conversations between customers and support agents
- Random selection of users from the users.json file
- Variable wait times between comments to simulate real-time interactions
- Tickets can be marked as resolved or left open
- Proper attribution of comments to the correct authors
- Advanced retry logic for handling Zendesk API rate limits

The conversation templates cover various scenarios including:

- Dashboard performance issues
- Billing discrepancies
- Feature requests
- Data access problems
- Integration issues
- Security alerts
- Data export errors
- Mobile app crashes
- Bulk user management
- Payment feature configuration

## AI-Powered Customer Replies

The `customer_reply.py` script adds dynamic AI-generated customer responses to tickets:

- Automatically finds tickets that have been recently replied to by a support agent
- Uses the Anthropic Claude API to generate a contextually relevant customer response
- Analyzes the tone and helpfulness of the agent's comment to determine the response attitude
- Generates either very happy responses (for helpful agent comments) or very upset responses (for unhelpful ones)
- Adds the generated response back to the ticket as a comment from the customer
- Implements fallback logic to try multiple Claude models if one isn't available
- Includes rate limit handling and retry logic

This script helps create a more dynamic and ongoing conversation flow in your demo environment, with responses that realistically reflect customer satisfaction levels based on agent performance.

## Rate Limiting and Retry Logic

The `create_demo_conversations.py` script includes built-in retry logic to handle Zendesk API rate limits:

- When a rate limit (429 status code) is encountered, the script will automatically wait the required time before retrying
- The retry mechanism parses the error response to determine the appropriate wait time
- Each operation will be retried up to 5 times with increasing wait periods
- This ensures that all comments are eventually added, even when Zendesk throttles the requests
- The script provides clear progress messages during retry attempts

To adjust the retry behavior, you can modify:
- Maximum retry attempts (default: 5) in the `api_request_with_retry` function
- Default wait time (default: 60 seconds) in the `get_retry_after` function

## Notes

- The cleanup script will delete ALL tickets and users. Use with caution!
- Make sure to back up any important data before running the cleanup script
- The scripts handle pagination for large datasets
- Error handling is implemented for API rate limits and other potential issues
- The demo setup creates 30 organizations with 150 total users (5 per organization)
- Conversations use realistic content with varied tones and scenarios

## Customization

You can modify the scripts and JSON files to add more functionality:
- Add more organizations to organizations.json
- Add more users to users.json
- Create new conversation templates with different scenarios
- Modify the timing between comments in create_demo_conversations.py
- Adjust the Claude model list in customer_reply.py to use different AI models
- Add more fields to the generated tickets
- Adjust the retry logic parameters for different rate limiting behaviors

## License

MIT. See [LICENSE](./LICENSE).

---

Built with [Claude Code](https://claude.com/claude-code).

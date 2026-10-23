# LangGraph AI Email Agent with Llama 3.2

An AI-powered email assistant built using **Python, LangGraph, Llama 3.2, and Ollama**. The agent automatically generates emails based on user requirements, allows revisions, and sends emails through Gmail after receiving explicit user approval.

## Features

- **AI Email Generation:** Generates complete emails based on user instructions.
- **Email Revisions:** Allows users to request modifications until satisfied.
- **Human-in-the-Loop:** Requires user approval before sending any email.
- **Gmail Integration:** Sends approved emails using Gmail API.
- **Local LLM:** Uses Llama 3.2 through Ollama for email generation.
- **Workflow Management:** Uses LangGraph to manage execution, decisions, and state.
- **Checkpointing:** Saves conversation and workflow progress using SQLite.
- **Secure Sending:** Includes email validation and duplicate-send protection.
- **Dry-Run Mode:** Allows testing without sending real emails.

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Application development |
| LangGraph | Agent workflow and state management |
| LangChain | LLM integration |
| Llama 3.2 | Email generation and revisions |
| Ollama | Running the language model locally |
| Gmail API | Sending emails |
| Google OAuth 2.0 | Gmail authentication |
| SQLite | Workflow checkpoints and sending records |

## Installation and Setup

### 1. Install Ollama

Download and install Ollama:

https://ollama.com/download

Start Ollama and download Llama 3.2 using Terminal:

`ollama pull llama3.2`

Test the model:

`ollama run llama3.2`

### 2. Set Up the Python Environment

Clone the GitHub repository:

`git clone https://github.com/moadil65/langgraph-email-agent.git`

Navigate to the project folder:

`cd langgraph-email-agent`

Create a virtual environment:

`python3 -m venv .venv`

Activate it:

`source .venv/bin/activate`

Install dependencies:

`pip install -r requirements.txt`

### 3. Configure the Environment

Create a `.env` file:

`cp .env.example .env`

Default configuration:

- `OLLAMA_MODEL=llama3.2`
- `OLLAMA_BASE_URL=http://localhost:11434`

The application uses the locally installed Llama model for email drafting.

## Running the AI Agent

### AI Drafting Mode

Start the agent:

`python main.py`

The agent will:

1. Ask for the recipient's email address.
2. Ask what the email should contain.
3. Generate a subject and email body using Llama 3.2.
4. Display the generated email for review.
5. Allow the user to approve, revise, change the recipient, or cancel.
6. Complete a dry run after approval without sending a real email.

### Mock Testing Mode

`python main.py --mock`

This mode tests the LangGraph workflow without running the language model. It uses placeholder email content and does not send real emails.

### Live Email Sending

`python main.py --live`

This mode enables actual Gmail delivery after the user explicitly approves the email.

## Gmail API Configuration

To enable email sending:

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a Google Cloud project.
3. Enable the Gmail API.
4. Configure the OAuth consent screen and required test users.
5. Create OAuth credentials for a **Desktop application**.
6. Download the credentials and save them as `credentials.json` in the project directory.
7. Run `python main.py --live`.
8. Complete Google authentication when prompted.

The application requests Gmail sending permission and stores the authorization token locally.

**Important:** Never upload `credentials.json`, `token.json`, or other sensitive authentication files to GitHub.

## Agent Workflow

The application follows this LangGraph workflow:

```text
START
  |
  v
Collect Recipient and Requirements
  |
  v
Generate Email Using Llama 3.2
  |
  v
Display Email for Approval
  |
  +---- Edit ----> Revise Using Llama
  |                    |
  |                    v
  |              Review Again
  |
  +---- Change Recipient --> Review Again
  |
  +---- Cancel --> END
  |
  +---- Approve
          |
          v
     Validate Approval
          |
          v
     Gmail API (Live Mode)
          |
          v
         END
```

LangGraph manages workflow execution, conditional transitions, and human-in-the-loop approval.

## Memory and Checkpointing

The agent uses LangGraph checkpointing to maintain workflow state.

- Conversation and execution state are stored in `checkpoints.sqlite`.
- The agent retains the recipient, email requirements, generated draft, and approval workflow state.
- Interrupted approval workflows can be resumed using their thread ID.
- Sending records are maintained in `send_ledger.sqlite` to help prevent duplicate sends.

To resume an unfinished conversation:

`python main.py --resume THREAD_ID`

For a live sending conversation, include the `--live` flag.

The current implementation uses thread-specific workflow memory rather than a cross-conversation long-term semantic memory system.

## Security Features

- Requires explicit human approval before live email sending.
- Keeps Gmail sending operations separate from LLM text generation.
- Verifies the approved recipient, subject, and email body.
- Uses SHA-256 approval fingerprints to detect changes.
- Validates email addresses.
- Uses SQLite sending records to help prevent duplicate sending attempts.
- Excludes local credentials, tokens, and databases through `.gitignore`.

## Testing

Run the included automated tests:

`python -m unittest discover -s tests -v`

These tests verify application functionality without sending real emails.

## Troubleshooting

**Ollama not running:** Open the Ollama application or start its server using `ollama serve`.

**Llama model not found:** Run `ollama pull llama3.2`.

**Email generation not working:** Verify that Ollama is running and use `python main.py` instead of mock mode.

**Gmail authentication error:** Verify that Gmail API is enabled and the OAuth credentials are configured correctly.

**Email not sent:** Ensure the application is running in live mode and the email has been explicitly approved.

## Future Improvements

- Implement long-term memory using LangGraph Store.
- Remember user email-writing preferences.
- Add recipient information management.
- Introduce document-based email generation.
- Develop memory-write validation and security mechanisms.
- Investigate prompt injection and memory-poisoning vulnerabilities.

## Project Repository

**GitHub:** https://github.com/moadil65/langgraph-email-agent
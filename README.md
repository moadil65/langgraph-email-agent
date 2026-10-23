# LangGraph email agent: local Llama edition (no paid LLM API)

**What it does:** asks who to email and what to say; drafts a complete email with a local Llama model; shows the exact recipient, subject and body; lets you request repeated revisions; and sends through Gmail **only if you explicitly approve** in live mode.

## What changed from the original OpenAI version

- Replaced `langchain-openai` / `ChatOpenAI` with `langchain-ollama` / `ChatOllama`.
- Uses Meta's Llama 3.2 locally via **Ollama**. No OpenAI API key or model API subscription.
- Keeps existing LangGraph state/checkpoints, revision loop, approval fingerprints, Gmail OAuth and duplicate-send protections.
- `--mock` **still** tests only the LangGraph flow and **does not generate real emails**. To use the actual Llama model, run `python main.py` **without `--mock`**.

## Setup on a Mac (first run)

1. Install the Ollama app from <https://ollama.com/download/mac> and launch it. The `ollama` command should become available in Terminal. If the server is not running, open the Ollama app (or use `ollama serve` in another Terminal).
2. Download the local model:

   ```bash
   ollama pull llama3.2
   ```

   This is the 3B text model (download about 2GB). Download requires internet, but local generation works offline afterward.

3. Optional: make sure Llama can actually generate text:

   ```bash
   ollama run llama3.2
   ```

   Type `Write a short friendly email to a friend.` and then `/bye` to exit.

4. In a Terminal **inside the extracted project folder**:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   cp .env.example .env
   ```

   `.env` is optional. Its defaults are `OLLAMA_MODEL=llama3.2` and `OLLAMA_BASE_URL=http://localhost:11434`. No API key is used.

5. Start AI email drafting, while keeping email sending **disabled**:

   ```bash
   python main.py
   ```

6. Enter the recipient's email and tell Llama what to write. It generates a new subject/body rather than copying the instructions. Review the draft and enter `edit` with new instructions as often as needed; choose `cancel` or `send`. In **default dry-run mode**, `send` means *approve only*: no real email is sent.

### Important: `--mock` is not Llama

Do not use `python main.py --mock` if you want the model to draft real emails. Mock mode merely copies the requirements into a template and appends revision instructions. It exists only for offline workflow testing.

### Choose a larger Llama if needed

The 3B model is a lightweight starting point. If your Mac has sufficient unified memory, try the more capable (but slower/larger) 8B model:

```bash
ollama pull llama3.1:8b
```

Update your `.env` to `OLLAMA_MODEL=llama3.1:8b` and start `python main.py` again. Download size is around 4.7GB; peak memory use is higher. Model quality varies, and all AI-generated email content must be reviewed.

## Enable real Gmail sending (optional)

**Keep `python main.py` for learning and safe drafts.** Gmail sending needs a *separate Google OAuth setup*; ChatGPT's Gmail connection cannot automatically be reused by this standalone app.

Google guide: <https://developers.google.com/workspace/gmail/api/quickstart/python>

1. Use Google Cloud Console to create/select a project and enable Gmail API.
2. Configure OAuth consent and add your own account as a test user if required.
3. Create an OAuth client with application type **Desktop**.
4. Download its JSON file and place it alongside `main.py` as `credentials.json`.
5. Only when ready to really send emails, start a **new** thread with:

   ```bash
   python main.py --live
   ```

6. On first live approval, Google's OAuth page opens. The app requests only Gmail's `gmail.send` scope and stores `token.json` locally. Test sending only to an email address you control. The app requires you to approve the exact **To**, **Subject**, and **Body** before sending.

## Under the hood

```text
START -> COLLECT [interrupt: recipient and requirements]
      -> DRAFT [local Llama through Ollama]
      -> REVIEW [interrupt: display exact draft]
         -> edit -> REVISE [local Llama] -> REVIEW
         -> to   -> REVIEW [updated recipient]
         -> cancel -> END
         -> send -> SEND [approval fingerprint check]
                    -> dry-run receipt OR Gmail OAuth and send -> END
```

LangGraph checkpoints are saved in `checkpoints.sqlite`; send reservations in `send_ledger.sqlite`. Restart an unfinished paused conversation with `python main.py --resume THREAD_ID` (and `--live` only if it was a live thread). If you were interrupted during drafting rather than at a waiting prompt, that graph may not be resumable automatically. Use a new thread in that case.

### Security notes

- The model writes **text only** and never receives Gmail sending authority.
- Any revision or changed recipient clears approval. The send node verifies a SHA-256 fingerprint of the approved recipient, subject and body.
- By default the program performs a **dry run**. Real Gmail transmission requires both `--live` and the `send` action.
- SQLite send reservations guard against automatic duplicate-send retries. If transmission is uncertain, inspect Gmail Sent before retrying manually.
- Protect OAuth credentials, token files, and checkpoint databases; these contain secrets or email text and are excluded by `.gitignore`.

## Troubleshooting

**`Cannot reach Ollama ...`** — Install/open Ollama and retry. Check `ollama list` and, if necessary, start `ollama serve`.

**`model ... is not installed`** — Run `ollama pull llama3.2` or the model specified in `.env`.

**`Local Llama drafting failed`** — Check `ollama run llama3.2`, available RAM, and whether Ollama is running. A 3B model can occasionally produce unsuitable drafts; request a revision or upgrade the model.

**Still copying instructions verbatim?** — Check that you ran `python main.py`, **not** `python main.py --mock`.

**Gmail credentials missing** — Nothing sends unless you use `--live`, approve, and complete Google OAuth setup.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests do not send email or require an Ollama service. Full local Llama + Gmail integration should be tested on your Mac since neither Ollama nor your account credentials are present here.

## Research connection

This project uses *thread-scoped LangGraph checkpoints*, not long-term semantic memories. Later you can add a LangGraph Store and study how untrusted email content moves across memory write boundaries, while keeping user approval outside untrusted data.

# llada-datagen-ce

Generates SFT (supervised fine-tuning) training data compatible with the **LLaDa 2.1** series of models from Inclusion Labs. The dataset trains the model to behave like a developer — reading codebases, planning changes, editing files, and running shell commands.

## What it does

For each GitHub repository in `repos.txt`, the pipeline:

1. Validates all repos are publicly accessible
2. Validates all configured AI agents are responsive
3. Clones each repo locally
4. Runs an AI agent against it with a set of tools (read, edit, write, terminal)
5. Saves the full tool-call conversation to `./output/` as a JSON file
6. Deletes the cloned repo to save disk space

After generation, run `convert_and_anonymise.py` to convert the raw conversations into training-ready JSONL, with tools injected into the system prompt and all user-identifying data scrubbed.

## Setup

```bash
pip install -r requirements.txt
```

Set your GitHub PAT to avoid API rate limits during repo validation:

```bash
export GITHUB_PAT_TOKEN=your_token_here
```

Configure your AI agent in `vars.py` — any OpenAI-compatible provider works (LM Studio, OpenRouter, or the openai compatible url):

```python
agents = {
    'exploration': AIAgent(
        model_id='your-model-id',
        provider=Providers.lmstudio,
        access_token='your-key',  # or '<MY_ENV_VAR>' to read from env
        context_window=262144
    ),
    ...
}
```

Add the repos you want to generate data from to `repos.txt` (one `owner/repo` per line).

## Usage

**Step 1 — Generate conversations:**

```bash
python main.py
```

Raw conversations are saved to `./output/<encoded_repo>-conversation.json`.

**Step 2 — Convert to training JSONL:**

```bash
python convert_and_anonymise.py
```

Outputs `./output/training_data.jsonl` — one conversation per line, ready for SFT training.

## Tools available to the agent

| Tool | Description |
|------|-------------|
| `read` | Read a file and return its contents |
| `edit` | Replace an exact string in a file |
| `write` | Write or overwrite a file |
| `terminal_command` | Run a bash command (Git Bash on Windows) |

File tools are sandboxed to the cloned repo directory — the agent cannot access paths outside it.

## Output format

`training_data.jsonl` follows the GLM-style tool-calling format used by LLaDa 2.1:

```json
{"messages": [
  {"role": "system", "content": "<tools schema> + agent instructions"},
  {"role": "user", "content": "Analyse this repo and create a plan..."},
  {"role": "assistant", "content": "I'll start by listing files.\n<tool_call>\n{\"name\": \"terminal_command\", \"arguments\": {\"command\": \"ls -la /home/user/project\"}}\n</tool_call>"},
  {"role": "observation", "content": "<tool_response>\ntotal 12\n...\n</tool_response>"},
  {"role": "assistant", "content": "The repository contains..."}
]}
```

All user-identifying data is scrubbed: local paths are replaced with `/home/user/project` and the system username is anonymised.

## Project structure

```
llada-datagen-ce/
├── main.py                    # Pipeline orchestration + Agent class
├── tools.py                   # Tool implementations + OpenAI schema
├── vars.py                    # Provider config, AIAgent class, agent definitions
├── convert_and_anonymise.py   # Convert output JSON -> training JSONL + anonymise
├── repos.txt                  # List of GitHub repos to process
├── requirements.txt
└── output/
    ├── *-conversation.json    # Raw per-repo conversations (intermediate)
    └── training_data.jsonl    # Final training data
```

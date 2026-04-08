import json
import re
import os
from glob import glob
from tools import tools_description


# ---------------------------------------------------------------------------
# Anonymisation
# ---------------------------------------------------------------------------

# Matches common absolute repository paths from this pipeline across platforms.
# Examples:
#   /home/alice/llada-datagen-ce/repos/AbC123...
#   C:/Users/Alice/llada-datagen-ce/repos/AbC123...
#   C:\Users\Alice\llada-datagen-ce\repos\AbC123...
_REPO_PATH_RE = re.compile(
    r'(?i)(?:[A-Z]:[\\/]|/)[^ \n\r\t"<>|]*?llada-datagen-ce[\\/]repos[\\/][A-Za-z0-9]+'
)

# Matches generic home-directory path segments to avoid leaking local usernames.
# Examples:
#   /home/alice/
#   /Users/alice/
#   C:\Users\Alice\
_HOME_PREFIX_RE = re.compile(
    r'(?i)(?:[A-Z]:[\\/]Users[\\/][^\\/:\n\r\t"<>|]+|/home/[^/:\n\r\t"<>|]+|/Users/[^/:\n\r\t"<>|]+)'
)

def anonymise(text: str) -> str:
    if not text:
        return text
    # Most specific first.
    text = _REPO_PATH_RE.sub('/home/user/project', text)
    text = _HOME_PREFIX_RE.sub('/home/user', text)
    return text


def anonymise_jsonish(value):
    if isinstance(value, str):
        return anonymise(value)
    if isinstance(value, list):
        return [anonymise_jsonish(v) for v in value]
    if isinstance(value, dict):
        return {k: anonymise_jsonish(v) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------
# System prompt builder (inline, no external dependency)
# ---------------------------------------------------------------------------

def build_tool_system_prompt(tools: list) -> str:
    schemas = [json.dumps(t, ensure_ascii=False, indent=2) for t in tools]
    tools_json = ',\n'.join(schemas)
    return (
        "You have access to the following tools. To use a tool, output a "
        "<tool_call> block with a JSON object containing \"name\" and \"arguments\".\n\n"
        f"Available tools:\n[{tools_json}]\n\n"
        "When you need to use a tool, respond with:\n"
        "<tool_call>\n"
        "{\"name\": \"tool_name\", \"arguments\": {\"param\": \"value\"}}\n"
        "</tool_call>\n\n"
        "After receiving the tool response in <tool_response> tags, "
        "use the result to provide a helpful answer."
    )


SYSTEM_PROMPT = (
    build_tool_system_prompt(tools_description)
    + "\n\n"
    "You are an expert coding assistant operating inside pi, a coding agent harness. "
    "You help users by reading files, executing commands, editing code, and writing new files. "
    "You must say exactly which tool you are calling, why, and your next steps before calling a tool. "
    "You may only access files under /home/user/project."
)


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def convert_conversation(messages: list) -> list | None:
    # Filter: skip if last assistant message is empty
    last_assistant = next(
        (m for m in reversed(messages) if m['role'] == 'assistant'),
        None
    )
    if last_assistant is None or not (last_assistant.get('content') or '').strip():
        return None

    converted = []
    for msg in messages:
        role = msg['role']

        if role == 'system':
            converted.append({'role': 'system', 'content': SYSTEM_PROMPT})

        elif role == 'user':
            converted.append({'role': 'user', 'content': anonymise(msg.get('content', ''))})

        elif role == 'assistant':
            tool_calls = msg.get('tool_calls')
            content = anonymise(msg.get('content') or '')
            if tool_calls:
                blocks = [content] if content.strip() else []
                for tc in tool_calls:
                    name = tc['function']['name']
                    raw_args = tc['function']['arguments']
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError:
                        args = {}
                    args = anonymise_jsonish(args)
                    payload = json.dumps({'name': name, 'arguments': args}, ensure_ascii=False)
                    blocks.append(f'<tool_call>\n{payload}\n</tool_call>')
                converted.append({'role': 'assistant', 'content': '\n'.join(blocks)})
            else:
                converted.append({'role': 'assistant', 'content': content})

        elif role == 'tool':
            inner = anonymise(msg.get('content', ''))
            converted.append({
                'role': 'observation',
                'content': f'<tool_response>\n{inner}\n</tool_response>'
            })

    return converted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    output_dir = './output'
    out_path = os.path.join(output_dir, 'training_data.jsonl')

    # Remove existing output so we don't append to stale data
    if os.path.exists(out_path):
        os.remove(out_path)

    files = sorted(glob(os.path.join(output_dir, '*.json')))
    written = 0
    skipped = 0

    with open(out_path, 'a', encoding='utf-8') as out_f:
        for path in files:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                messages = json.load(f)
            converted = convert_conversation(messages)
            if converted is None:
                print(f'  SKIP  {os.path.basename(path)} (empty final response)')
                skipped += 1
                continue
            out_f.write(json.dumps({'messages': converted}, ensure_ascii=False) + '\n')
            print(f'  OK    {os.path.basename(path)} ({len(converted)} messages)')
            written += 1

    print(f'\nDone: {written} written, {skipped} skipped -> {out_path}')

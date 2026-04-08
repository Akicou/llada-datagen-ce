import subprocess
import os
import shutil

def _find_git_bash() -> str:
    candidates = [
        'C:/Program Files/Git/bin/bash.exe',
        'C:/Program Files (x86)/Git/bin/bash.exe',
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return shutil.which('bash') or 'bash'

BASH_EXE = _find_git_bash()

def read(absolute_path: str) -> str:
    """
    Read the contents of a file and return it as a string.
    Use this to access the current contents of files before deciding how to edit them.
    - absolute_path: the full absolute path to the file to read
    Returns: the text content of the file
    """
    with open(absolute_path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()

def edit(absolute_path: str, old_str: str, new_str: str):
    """
    Edit an existing file by replacing an exact string match.
    Use this to make targeted changes to files without rewriting them entirely.
    - absolute_path: the full absolute path to the file to edit
    - old_str: the exact string to find and replace (must be unique in the file)
    - new_str: the string to replace it with
    """
    with open(absolute_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    with open(absolute_path, 'w', encoding='utf-8') as f:
        f.write(content.replace(old_str, new_str))

def write(absolute_path: str, content: str):
    """
    Write (or overwrite) a file at the given path with new content.
    Use this to create new files or fully replace the contents of an existing file.
    - absolute_path: the full absolute path to the file to write
    - content: the full text content to write into the file
    """
    with open(absolute_path, 'w', encoding='utf-8') as f:
        f.write(content)

def terminal_command(command: str) -> str:
    """
    Execute a shell command on the host system and return its output.
    The environment is Windows 11 running Git Bash (bash shell, Unix-style syntax).
    Use Unix/bash command syntax — forward slashes in paths, bash built-ins, etc.
    Do NOT use PowerShell or cmd.exe syntax (e.g. avoid backslashes, dir, type, etc.).
    - command: a valid bash command string to execute (e.g. "ls -la ./repos" or "git clone ...")
    Returns: combined stdout and stderr output from the command
    """
    result = subprocess.run([BASH_EXE, '-c', command], capture_output=True, text=True, encoding='utf-8', errors='replace')
    output = (result.stdout or '') + (result.stderr or '')
    return output.strip() if output.strip() else f'(exit code {result.returncode})'

tools_description = [
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read the contents of a file and return it as a string. Use this to access the current contents of files before deciding how to edit them.",
            "parameters": {
                "type": "object",
                "properties": {
                    "absolute_path": {
                        "type": "string",
                        "description": "The full absolute path to the file to read"
                    }
                },
                "required": ["absolute_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit",
            "description": "Edit an existing file by replacing an exact string match. Use this to make targeted changes to files without rewriting them entirely. old_str must be unique in the file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "absolute_path": {
                        "type": "string",
                        "description": "The full absolute path to the file to edit"
                    },
                    "old_str": {
                        "type": "string",
                        "description": "The exact string to find and replace (must be unique in the file)"
                    },
                    "new_str": {
                        "type": "string",
                        "description": "The string to replace it with"
                    }
                },
                "required": ["absolute_path", "old_str", "new_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write",
            "description": "Write (or overwrite) a file at the given path with new content. Use this to create new files or fully replace the contents of an existing file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "absolute_path": {
                        "type": "string",
                        "description": "The full absolute path to the file to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "The full text content to write into the file"
                    }
                },
                "required": ["absolute_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "terminal_command",
            "description": "Execute a shell command on the host system and return its output. The environment is Windows 11 running Git Bash (bash shell, Unix-style syntax). Use Unix/bash syntax — forward slashes in paths, bash built-ins, etc. Do NOT use PowerShell or cmd.exe syntax (no backslashes, dir, type, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "A valid bash command string to execute (e.g. 'ls -la ./repos' or 'git status')"
                    }
                },
                "required": ["command"]
            }
        }
    }
]

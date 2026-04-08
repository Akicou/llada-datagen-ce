# ------------------------
# Akicou/llada-datageb-ce | CE = Code Exploration / Editing
# This Repository creates SFT training data compatible with the LLaDa2.1 Series of Models from Inclusion labs.
# Training it not only for long context but how to act like a developer
# -- Scenarios to train it on --
# 1.  Analyzing the repo. Creating a user prompt on what the user wants to make (based off of the repo) and then recreating the repository
# 2. Analyzing the repo. Creating 300 User Prompts. the first 150 prompts are exploration based (editing or writing is off) the next 50 focus onedits that can be made to the repo

# ------------------------
from vars import repos, agents
from tqdm import tqdm
import requests
import sys
import os
import shutil
import hashlib
import json
import time
from tools import write, terminal_command, tools_description


def encode(s):
    return hashlib.md5(s.encode()).hexdigest().translate(str.maketrans("0123456789abcdef", "GHIJKLMNOPQrstuv"))[:12]


def is_valid_github_repo(user, repo):
    return requests.get(f"https://api.github.com/repos/{user}/{repo}", headers={"Authorization": f"token {os.environ.get('GITHUB_PAT_TOKEN', '')}"}).status_code == 200


class Agent():
    def __init__(self, agent_proc: str, allowed_min_abs_path: str):
        self.agent_proc = agent_proc
        self.agent = agents[agent_proc]
        self.allowed_min_abs_path = os.path.abspath(allowed_min_abs_path).replace('\\', '/')
        self.client = self.agent.getClient()
        self.system_prompt = f"""You are an expert coding assistant operating inside pi, a coding agent harness. You help users by reading files, executing commands, editing code, and writing new files. We recommend you to ensure that code is distributed to folders and other files to not bloat the context window. You must say exactly which tool you are calling why and your next steps before calling a tool. You may only access files under: {self.allowed_min_abs_path} — always use that exact absolute path prefix when calling file tools."""

    def _check_path(self, path: str) -> str | None:
        if not os.path.abspath(path).startswith(self.allowed_min_abs_path):
            return f"Error: path '{path}' is outside the allowed directory '{self.allowed_min_abs_path}'"
        return None

    def _dispatch(self, name: str, args: dict) -> str:
        from tools import read, edit, write as tool_write
        if name in ('read', 'edit', 'write'):
            err = self._check_path(args['absolute_path'])
            if err:
                return err
        if name == 'read':
            return read(args['absolute_path'])
        elif name == 'edit':
            edit(args['absolute_path'], args['old_str'], args['new_str'])
            return 'OK'
        elif name == 'write':
            tool_write(args['absolute_path'], args['content'])
            return 'OK'
        elif name == 'terminal_command':
            return terminal_command(args['command'])
        return f"Unknown tool: {name}"

    def run(self, user_msg: str) -> list:
        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': user_msg}
        ]

        empty_retries = 0
        while True:
            r = self.client.chat.completions.create(
                messages=messages,
                model=self.agent.model_id,
                max_tokens=2048,
                tools=tools_description
            )
            msg = r.choices[0].message

            assistant_msg = {'role': 'assistant', 'content': msg.content or ''}
            if msg.tool_calls:
                assistant_msg['tool_calls'] = [
                    {
                        'id': tc.id,
                        'type': 'function',
                        'function': {'name': tc.function.name, 'arguments': tc.function.arguments}
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(assistant_msg)

            if not msg.tool_calls:
                if not (msg.content or '').strip() and empty_retries < 5:
                    empty_retries += 1
                    print(f'Empty response, retrying ({empty_retries}/5)...')
                    messages.pop()
                    continue
                return messages

            if msg.content:
                print(f'Agent said: {msg.content}')
            for tc in msg.tool_calls:
                try:
                    result = self._dispatch(tc.function.name, json.loads(tc.function.arguments))
                except Exception as e:
                    result = f'Error: {e}'
                messages.append({
                    'role': 'tool',
                    'tool_call_id': tc.id,
                    'content': str(result)
                })
                print(f"Executed tool call '{tc.function.name}' with args: {tc.function.arguments}")


if __name__ == "__main__":

    print('-'*22)
    print('[Stage 1] - Do all Repos exist?')

    repo_check = {'valid': 0, 'invalid': []}
    repo_pbar = tqdm(repos)
    for repo in repo_pbar:
        repo_pbar.set_description(f"Validating Github Repositories [valid={repo_check['valid']},invalid={len(repo_check['invalid'])}] ")
        if is_valid_github_repo(user=repo.split('/')[0], repo=repo.split('/')[1]):
            repo_check['valid'] += 1
        else:
            repo_check['invalid'].append(repo)
    print('-'*22)
    if repo_check['invalid']:
        print(f'These Repositories are invalid: {", ".join(repo_check["invalid"])} | Please remove them from repos.txt. If they are private then change visibilty.')
        sys.exit(0)
    else:
        print('All Valid Moving on...')

    print('[Stage 2] - AI Agents work?')
    agents_pbar = tqdm(list(agents.keys()))
    for agent_proc in agents_pbar:
        agents_pbar.set_description(f"Validating Agents [{agent_proc}]")
        try:
            r = agents[agent_proc].getClient().chat.completions.create(
                messages=[{'role': 'user', 'content': 'What is 1+1'}],
                model=agents[agent_proc].model_id,
                max_tokens=24
            )
            reply = r.choices[0].message.content.strip() if r.choices else '(no response)'
            agents_pbar.write(f"  [{agent_proc}] OK -> {reply}")
        except Exception as e:
            agents_pbar.write(f"  [{agent_proc}] FAILED -> {e}")

    shutil.rmtree('./repos', ignore_errors=True)
    os.makedirs('./repos', exist_ok=True)
    os.makedirs('./output', exist_ok=True)

    print('[Stage 3] - Exploring Repos...')
    for repo in repo_pbar:
        encoded_repo = encode(repo)
        terminal_command(f'git clone https://github.com/{repo}.git ./repos/{encoded_repo} --quiet')
        abs_repo_path = os.path.abspath(f'./repos/{encoded_repo}').replace('\\', '/')
        agent = Agent(agent_proc='exploration', allowed_min_abs_path=abs_repo_path)
        user_prompt = f"""The following is a github repository that has been cloned locally. Analyze the repository and create a detailed file detailling what the repository does, what files it has, and what the user could do with it. Then create a plan for how to recreate this repository from scratch. Be sure to include details on how to structure the files and folders, and what code should go in each file. Here is the repo path: {abs_repo_path}"""
        t0 = time.time()
        conversation = agent.run(user_prompt)
        elapsed = time.time() - t0
        print(f'Finished Exploration for {repo} | Time took: {elapsed:.1f}s | Saving Conversation...')
        write(f'./output/{encoded_repo}-conversation.json', json.dumps(conversation, indent=2))
        print(f"Deleting Cloned Repo {repo} to save space...")
        shutil.rmtree(f'./repos/{encoded_repo}', ignore_errors=True)

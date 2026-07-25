# utils.py
import os
import subprocess

def find_git_repo_path(workspace_id):
    """
    Given a workspace_id (which could be a project name or path),
    finds if there is a matching directory that is a git repository.
    """
    if not workspace_id or workspace_id in ["Global/No Project", "Global/No Session"]:
        return None
    
    # Check if absolute path
    if os.path.isabs(workspace_id) and os.path.isdir(workspace_id):
        if os.path.isdir(os.path.join(workspace_id, ".git")):
            return workspace_id
        return None

    # Search common locations on the user's system
    search_dirs = [
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~"),
        os.path.expanduser("~/Documents"),
        os.getcwd()
    ]
    for parent in search_dirs:
        candidate = os.path.join(parent, workspace_id)
        if os.path.isdir(candidate) and os.path.isdir(os.path.join(candidate, ".git")):
            return candidate
    return None

def get_git_metadata(repo_path, max_commits=200):
    """
    Extracts Git branch and commit history from the specified repository directory.
    """
    if not repo_path:
        return None
    try:
        # Get active branch name
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        
        # Get commit history (hash, timestamp, message, author, email)
        log_output = subprocess.check_output(
            ["git", "log", "-n", str(max_commits), "--pretty=format:%H|%at|%s|%an|%ae"],
            cwd=repo_path,
            stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="ignore").strip()
        
        commits = []
        if log_output:
            for line in log_output.splitlines():
                parts = line.split("|", 4)
                if len(parts) == 5:
                    commits.append({
                        "hash": parts[0],
                        "timestamp": int(parts[1]),
                        "message": parts[2],
                        "author": parts[3],
                        "email": parts[4]
                    })
        return {
            "branch": branch,
            "commits": commits
        }
    except Exception:
        return None

def estimate_token_cost_and_savings(model_raw, input_tokens, output_tokens, cache_read_tokens):
    """
    Estimates the retail API cost and cached savings in USD.
    Based on standard pricing per 1M tokens.
    """
    # Fallback default pricing
    in_rate = 2.0 / 1000000.0
    out_rate = 6.0 / 1000000.0
    cache_discount = 0.90 # 90% savings for cache read
    
    m = str(model_raw).lower()
    
    # Match models to pricing tables
    if 'flash' in m or 'gemini-3.5-flash' in m or 'gemini-1.5-flash' in m:
        in_rate = 0.075 / 1000000.0
        out_rate = 0.30 / 1000000.0
    elif 'pro' in m and ('gemini' in m or 'google' in m):
        in_rate = 1.25 / 1000000.0
        out_rate = 5.0 / 1000000.0
    elif 'sonnet' in m or 'claude-3.5-sonnet' in m:
        in_rate = 3.0 / 1000000.0
        out_rate = 15.0 / 1000000.0
    elif 'haiku' in m:
        in_rate = 0.80 / 1000000.0
        out_rate = 4.0 / 1000000.0
    elif 'opus' in m:
        in_rate = 15.0 / 1000000.0
        out_rate = 75.0 / 1000000.0
    elif 'gpt-4o-mini' in m:
        in_rate = 0.150 / 1000000.0
        out_rate = 0.600 / 1000000.0
    elif 'gpt-4o' in m:
        in_rate = 5.0 / 1000000.0
        out_rate = 15.0 / 1000000.0
    elif 'gpt-4' in m:
        in_rate = 10.0 / 1000000.0
        out_rate = 30.0 / 1000000.0
    elif 'gpt-3.5' in m:
        in_rate = 0.50 / 1000000.0
        out_rate = 1.50 / 1000000.0
    elif 'codex' in m:
        in_rate = 2.0 / 1000000.0
        out_rate = 8.0 / 1000000.0
        
    # Cost formula
    cost = (input_tokens * in_rate) + (output_tokens * out_rate) + (cache_read_tokens * in_rate * (1.0 - cache_discount))
    savings = cache_read_tokens * in_rate * cache_discount
    
    return cost, savings

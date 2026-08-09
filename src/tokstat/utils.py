# utils.py
import fnmatch
import os
import re
import subprocess

from . import config

# Local model name fragment -> closest cloud equivalent (model, $/1M in, $/1M out).
# Used only for the "cloud cost avoidance" estimate; local inference itself is
# always billed $0.00. Users can override via [pricing.overrides] in config.toml.
LOCAL_TO_CLOUD_MAP = {
    # NOTE: dict order is match order (substring test). "codellama" must come
    # before "llama" or Codellama models would match the broader fragment and
    # get priced as gpt-4o. Keep more specific fragments ahead of generic ones.
    "codellama": ("gpt-3.5", 0.50, 1.50),
    "llama": ("gpt-4o", 5.0, 15.0),
    "qwen": ("gpt-4o-mini", 0.15, 0.60),
    "deepseek": ("claude-3.5-sonnet", 3.0, 15.0),
    "mistral": ("gpt-4o-mini", 0.15, 0.60),
    "phi": ("gpt-4o-mini", 0.15, 0.60),
}


def estimate_cloud_equivalent_cost(model_raw, input_tokens, output_tokens, cache_read_tokens=0):
    """Estimate what a local-model run would have cost through a cloud API.

    Returns (closest_cloud_model_name or None, cost_usd). User pricing
    overrides from config.toml ([pricing.overrides] glob patterns) win over
    the built-in LOCAL_TO_CLOUD_MAP. cache_read_tokens are priced at the
    input rate with a 90% cache discount, mirroring cloud caching.
    """
    m = str(model_raw or "").lower()
    cloud_model = None
    in_rate = out_rate = 0.0
    for pattern, (name, i_rate, o_rate) in LOCAL_TO_CLOUD_MAP.items():
        if pattern in m:
            cloud_model, in_rate, out_rate = name, i_rate, o_rate
            break
    if cloud_model is None:
        return None, 0.0

    for pat, rates in config.pricing_overrides().items():
        if fnmatch.fnmatch(m, str(pat).lower()):
            try:
                in_rate, out_rate = float(rates[0]), float(rates[1])
            except (TypeError, ValueError, IndexError):
                pass
            break

    inp = input_tokens or 0
    out = output_tokens or 0
    cread = cache_read_tokens or 0
    cost = (
        inp * in_rate / 1_000_000.0
        + out * out_rate / 1_000_000.0
        + cread * in_rate * 0.10 / 1_000_000.0
    )
    return cloud_model, cost


def normalize_model_display_name(raw):
    """
    Normalizes raw or sanitized model names into clean display identifiers.
    e.g., gpt_5_3_codex -> gpt-5.3-codex, claude_sonnet_4_6 -> claude-sonnet-4.6
    """
    if not raw:
        return 'System/Tools'
    s = str(raw).strip()
    m = re.match(r'^([a-zA-Z0-9]+(?:_[a-zA-Z0-9]+)*?)_(\d+)_(\d+)(.*)$', s)
    if m:
        prefix, major, minor, rest = m.groups()
        prefix = prefix.replace('_', '-')
        rest = rest.replace('_', '-')
        return f'{prefix}-{major}.{minor}{rest}'
    return s.replace('_', '-')


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

def estimate_token_cost_and_savings(model_raw, input_tokens, output_tokens, cache_read_tokens, provider_id=None):
    """
    Estimates the retail API cost and cached savings in USD.
    Based on standard pricing per 1M tokens.

    provider_id="local" is always zero-cost: local inference has no API bill,
    so it must never be charged fabricated cloud pricing (see
    docs/local_model_support_plan.md).
    """
    if provider_id == "local":
        return 0.0, 0.0

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
        
    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0
    cache_read_tokens = cache_read_tokens or 0

    # Cost formula
    cost = (input_tokens * in_rate) + (output_tokens * out_rate) + (cache_read_tokens * in_rate * (1.0 - cache_discount))
    savings = cache_read_tokens * in_rate * cache_discount
    
    return cost, savings

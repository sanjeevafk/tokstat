# analytics.py
import collections
import re
from datetime import datetime, timedelta

from . import db_access, utils


def parse_datetime(dt_str):
    if not dt_str:
        return None
    dt_str = str(dt_str).strip()
    m = re.match(r'^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})', dt_str)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    m2 = re.match(r'^(\d{4}-\d{2}-\d{2})', dt_str)
    if m2:
        try:
            return datetime.strptime(m2.group(1), "%Y-%m-%d")
        except ValueError:
            pass
    return None

def compute_uninterrupted_sessions(events, gap_minutes=30):
    """
    Groups events that are less than gap_minutes apart.
    Returns the duration of the longest uninterrupted session.
    """
    if not events:
        return 0
    
    # Sort events by time
    time_events = []
    for ev in events:
        dt = parse_datetime(ev['occurred_at'])
        if dt:
            time_events.append(dt)
    
    if not time_events:
        return 0
        
    time_events.sort()
    
    longest_duration = timedelta(0)
    current_start = time_events[0]
    current_end = time_events[0]
    
    for t in time_events[1:]:
        if t - current_end <= timedelta(minutes=gap_minutes):
            current_end = t
        else:
            duration = current_end - current_start
            longest_duration = max(longest_duration, duration)
            current_start = t
            current_end = t
            
    # check last one
    duration = current_end - current_start
    longest_duration = max(longest_duration, duration)
        
    return int(longest_duration.total_seconds())

def compute_git_correlations(events_by_project):
    """
    Correlates Git commits with telemetry data.
    """
    correlated_commits = []
    active_branches = {}
    repos_git_info = {}

    for project, p_events in events_by_project.items():
        repo_path = utils.find_git_repo_path(project)
        if not repo_path:
            continue
            
        git_meta = utils.get_git_metadata(repo_path)
        if not git_meta:
            continue

        branch = git_meta["branch"]
        active_branches[project] = branch
        commits = git_meta["commits"]
        
        repos_git_info[project] = {
            "path": repo_path,
            "branch": branch,
            "commits_count": len(commits)
        }
        
        # Sort project events chronologically
        p_events_parsed = []
        for ev in p_events:
            dt = parse_datetime(ev['occurred_at'])
            if dt:
                p_events_parsed.append((dt.timestamp(), ev))
        p_events_parsed.sort(key=lambda x: x[0])
        
        # Sort commits chronologically (from oldest to newest) to map windows
        commits_sorted = sorted(commits, key=lambda c: c["timestamp"])
        
        for idx, commit in enumerate(commits_sorted):
            commit_time = commit["timestamp"]
            
            # Find window start
            if idx == 0:
                # 4 hours before first commit
                window_start = commit_time - (4 * 3600)
            else:
                prev_commit_time = commits_sorted[idx - 1]["timestamp"]
                # Look since previous commit, but cap at 4 hours to avoid matching stale events
                window_start = max(prev_commit_time, commit_time - (4 * 3600))
                
            # Filter events in this window (window_start, commit_time]
            matched_events = [ev for ts, ev in p_events_parsed if window_start < ts <= commit_time]
            
            if matched_events:
                total_tokens = sum(ev["total_tokens"] for ev in matched_events)
                input_tokens = sum(ev["input_tokens"] for ev in matched_events)
                output_tokens = sum(ev["output_tokens"] for ev in matched_events)
                cache_read = sum(ev["cache_read_tokens"] for ev in matched_events)
                
                # Estimated coding time before commit
                first_event_ts = min(ts for ts, ev in p_events_parsed if window_start < ts <= commit_time)
                coding_time_sec = int(commit_time - first_event_ts)
                # Keep it positive and sensible (e.g. at least 1 min, at most 4 hours)
                coding_time_sec = max(60, min(coding_time_sec, 4 * 3600))
                
                cost, savings = 0.0, 0.0
                for ev in matched_events:
                    c_val, s_val = utils.estimate_token_cost_and_savings(
                        ev["model_raw"], ev["input_tokens"], ev["output_tokens"], ev["cache_read_tokens"]
                    )
                    cost += c_val
                    savings += s_val
                
                correlated_commits.append({
                    "project": project,
                    "hash": commit["hash"][:8],
                    "message": commit["message"],
                    "author": commit["author"],
                    "timestamp": commit_time,
                    "datetime": datetime.fromtimestamp(commit_time).strftime("%Y-%m-%d %H:%M:%S"),
                    "branch": branch,
                    "tokens": total_tokens,
                    "input": input_tokens,
                    "output": output_tokens,
                    "cache_read": cache_read,
                    "coding_time": coding_time_sec,
                    "cost": cost,
                    "savings": savings,
                    "requests": len(matched_events)
                })

    # Sort final correlated commits newest first
    correlated_commits.sort(key=lambda c: c["timestamp"], reverse=True)
    return correlated_commits, active_branches, repos_git_info

def compute_analytics():
    events = db_access.fetch_all_events()
    copilot_totals = db_access.query_copilot_db() # (in, out, tot, reqs)
    
    if not events:
        return {}

    # Preserve valid usage events that have no session; the browser needs these
    # for complete totals and filtering.
    client_events = [{
        "event_id": e.get("event_id"), "occurred_at": e.get("occurred_at"),
        "project": e.get("workspace_id") or "Global/No Project",
        "session_id": e.get("session_id") or "Global/No Session",
        "turn_id": e.get("turn_id"), "model": e.get("model_raw") or "System/Tools",
        "tool": e.get("agent_name") or "Unknown", "input": e.get("input_tokens", 0),
        "output": e.get("output_tokens", 0), "cache_read": e.get("cache_read_tokens", 0),
        "total": e.get("total_tokens", 0), "requests": e.get("requests", 1),
        "cost": utils.estimate_token_cost_and_savings(
            e.get("model_raw"), e.get("input_tokens", 0), e.get("output_tokens", 0),
            e.get("cache_read_tokens", 0))[0]
    } for e in events]

    # Initialize aggregators
    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_tokens = 0
    total_cost = 0.0
    total_savings = 0.0
    requests_count = 0
    
    workspaces = set()
    models = set()
    agents = set()
    
    # Timeline daily rollup
    daily_tokens = collections.defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0, "total": 0, "requests": 0, "cost": 0.0, "savings": 0.0})
    
    # Heatmaps
    weekday_heatmap = collections.defaultdict(lambda: collections.defaultdict(int)) # [day_of_week][hour]
    hourly_heatmap = collections.defaultdict(int) # [hour]
    weekday_totals = collections.defaultdict(int) # [day_of_week]
    monthly_tokens = collections.defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0, "total": 0, "cost": 0.0})
    
    # Grouping lists
    events_by_project = collections.defaultdict(list)
    events_by_session = collections.defaultdict(list)
    events_by_model = collections.defaultdict(list)
    events_by_tool = collections.defaultdict(list)

    largest_request = None
    
    for ev in events:
        occurred = ev.get('occurred_at')
        dt = parse_datetime(occurred)
        
        inp = ev.get('input_tokens') or 0
        out = ev.get('output_tokens') or 0
        cread = ev.get('cache_read_tokens') or 0
        tot = ev.get('total_tokens') or 0
        reqs = ev.get('requests') or 1
        
        total_input += inp
        total_output += out
        total_cache_read += cread
        total_tokens += tot
        requests_count += reqs
        
        cost, savings = utils.estimate_token_cost_and_savings(ev['model_raw'], inp, out, cread)
        total_cost += cost
        total_savings += savings
        
        # Track largest request
        if not largest_request or tot > largest_request['total_tokens']:
            largest_request = {
                "event_id": ev["event_id"],
                "occurred_at": occurred,
                "project": ev["workspace_id"] or "Global/No Project",
                "model": ev["model_raw"] or "Unknown",
                "tool": ev["agent_name"] or "Unknown",
                "input_tokens": inp,
                "output_tokens": out,
                "cache_read_tokens": cread,
                "total_tokens": tot,
                "cost": cost
            }

        # Track workspace/repo, model, agent
        ws = ev['workspace_id'] or 'Global/No Project'
        model = ev['model_raw'] or 'System/Tools'
        agent = ev['agent_name'] or 'Unknown'
        
        if ws != 'Global/No Project':
            workspaces.add(ws)
        models.add(model)
        agents.add(agent)
        
        # Groupings
        events_by_project[ws].append(ev)
        if ev['session_id']:
            events_by_session[ev['session_id']].append(ev)
        events_by_model[model].append(ev)
        events_by_tool[agent].append(ev)
        
        # Time processing
        if dt:
            day_str = dt.strftime("%Y-%m-%d")
            daily_tokens[day_str]["input"] += inp
            daily_tokens[day_str]["output"] += out
            daily_tokens[day_str]["cache_read"] += cread
            daily_tokens[day_str]["total"] += tot
            daily_tokens[day_str]["requests"] += reqs
            daily_tokens[day_str]["cost"] += cost
            daily_tokens[day_str]["savings"] += savings
            
            # Heatmaps
            weekday = dt.weekday() # 0 = Monday, 6 = Sunday
            hour = dt.hour
            weekday_heatmap[weekday][hour] += tot
            hourly_heatmap[hour] += tot
            weekday_totals[weekday] += tot
            
            month_str = dt.strftime("%Y-%m")
            monthly_tokens[month_str]["input"] += inp
            monthly_tokens[month_str]["output"] += out
            monthly_tokens[month_str]["cache_read"] += cread
            monthly_tokens[month_str]["total"] += tot
            monthly_tokens[month_str]["cost"] += cost

    # Add Copilot standalone details to overall totals
    cop_in, cop_out, cop_tot, cop_req = copilot_totals
    if cop_tot > 0:
        total_input += cop_in
        total_output += cop_out
        total_tokens += cop_tot
        requests_count += cop_req
        agents.add('copilot')

        cop_cost, cop_savings = utils.estimate_token_cost_and_savings('copilot', cop_in, cop_out, 0)
        total_cost += cop_cost
        total_savings += cop_savings

    # Preserve the event-log scope before applying cumulative provider metrics.
    # These are intentionally separate measures: event totals power the
    # repository/session drilldowns, while provider totals represent all-time
    # usage reported by the upstream daemon.
    local_event_totals = {
        "tokens": total_tokens,
        "input": total_input,
        "output": total_output,
        "cache_read": total_cache_read,
    }

    # Incorporate authoritative balance observations from OpenUsage daemon poller
    balance_obs = db_access.fetch_balance_observations()
    if balance_obs:
        obs_input = balance_obs.get('client_ide_input_tokens', 0) or balance_obs.get('provider_codex_input_tokens', 0)
        obs_cached = balance_obs.get('client_ide_cached_tokens', 0)
        obs_output = balance_obs.get('client_ide_output_tokens', 0) or balance_obs.get('provider_codex_output_tokens', 0)
        obs_cost = balance_obs.get('all_time_api_cost', 0) or balance_obs.get('total_cost_usd', 0)

        if obs_input > 0:
            total_input = max(total_input, int(obs_input))
            total_cache_read = max(total_cache_read, int(obs_cached))
            total_output = max(total_output, int(obs_output))
            total_tokens = total_input + total_output + total_cache_read
            if obs_cost > 0:
                total_cost = max(total_cost, float(obs_cost))

    # Session breakdown calculations
    sessions_list = []
    largest_session = None
    longest_session_duration = 0
    longest_session_id = "N/A"
    
    for sess_id, s_events in events_by_session.items():
        if sess_id == "Global/No Session" or not sess_id:
            continue
            
        times = [parse_datetime(e['occurred_at']) for e in s_events if parse_datetime(e['occurred_at'])]
        if not times:
            continue
        start_time = min(times)
        end_time = max(times)
        duration_sec = int((end_time - start_time).total_seconds())
        
        s_inp = sum(e['input_tokens'] for e in s_events)
        s_out = sum(e['output_tokens'] for e in s_events)
        s_cread = sum(e['cache_read_tokens'] for e in s_events)
        s_tot = sum(e['total_tokens'] for e in s_events)
        s_reqs = sum(e['requests'] for e in s_events)
        
        s_cost, s_savings = 0.0, 0.0
        s_model_counts = collections.defaultdict(int)
        s_timeline = []
        
        for idx, e in enumerate(sorted(s_events, key=lambda x: x['occurred_at'] or '')):
            e_cost, e_savings = utils.estimate_token_cost_and_savings(
                e['model_raw'], e['input_tokens'], e['output_tokens'], e['cache_read_tokens']
            )
            s_cost += e_cost
            s_savings += e_savings
            s_model_counts[e['model_raw']] += e['total_tokens']
            
            s_timeline.append({
                "turn_id": e["turn_id"] or str(idx),
                "occurred_at": e["occurred_at"],
                "input": e["input_tokens"],
                "output": e["output_tokens"],
                "cache_read": e["cache_read_tokens"],
                "total": e["total_tokens"],
                "model": e["model_raw"],
                "cost": e_cost,
                "status": e["status"]
            })
            
        proj = s_events[0]['workspace_id'] or 'Global/No Project'
        
        session_obj = {
            "session_id": sess_id,
            "project": proj,
            "start": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": duration_sec,
            "requests": s_reqs,
            "total_tokens": s_tot,
            "input": s_inp,
            "output": s_out,
            "cache_read": s_cread,
            "avg_context": int(s_inp / len(s_events)) if s_events else 0,
            "avg_output": int(s_out / len(s_events)) if s_events else 0,
            "model_distribution": sorted([{"model": m, "tokens": t} for m, t in s_model_counts.items()], key=lambda x: x["tokens"], reverse=True),
            "timeline": s_timeline,
            "estimated_cost": s_cost,
            "estimated_savings": s_savings
        }
        
        sessions_list.append(session_obj)
        
        # Track largest and longest session
        if not largest_session or s_tot > largest_session['total_tokens']:
            largest_session = session_obj
            
        if duration_sec > longest_session_duration:
            longest_session_duration = duration_sec
            longest_session_id = sess_id

    # Git correlations
    git_commits, active_branches, repos_git_info = compute_git_correlations(events_by_project)

    # Repositories breakdown calculations
    repositories_list = []
    for proj, p_events in events_by_project.items():
        p_inp = sum(e['input_tokens'] for e in p_events)
        p_out = sum(e['output_tokens'] for e in p_events)
        p_cread = sum(e['cache_read_tokens'] for e in p_events)
        p_tot = sum(e['total_tokens'] for e in p_events)
        p_reqs = sum(e['requests'] for e in p_events)
        p_sessions = len(set(e['session_id'] for e in p_events if e['session_id']))
        
        # Latest activity
        p_times = [parse_datetime(e['occurred_at']) for e in p_events if parse_datetime(e['occurred_at'])]
        latest_act = max(p_times).strftime("%Y-%m-%d %H:%M:%S") if p_times else "N/A"
        
        # Longest session in this repo
        p_longest_sess_duration = 0
        p_longest_sess_id = "N/A"
        for s_obj in sessions_list:
            if s_obj["project"] == proj and s_obj["duration"] > p_longest_sess_duration:
                p_longest_sess_duration = s_obj["duration"]
                p_longest_sess_id = s_obj["session_id"]
                
        # Top models & tools
        p_models = collections.defaultdict(int)
        p_tools = collections.defaultdict(int)
        p_daily_trend = collections.defaultdict(int)
        for e in p_events:
            p_models[e['model_raw']] += e['total_tokens']
            p_tools[e['agent_name']] += e['total_tokens']
            dt = parse_datetime(e['occurred_at'])
            if dt:
                p_daily_trend[dt.strftime("%Y-%m-%d")] += e['total_tokens']
                
        # Git metadata attachment
        git_info = repos_git_info.get(proj)
        
        repo_obj = {
            "repository": proj,
            "tokens": p_tot,
            "input": p_inp,
            "output": p_out,
            "cache_read": p_cread,
            "requests": p_reqs,
            "sessions": p_sessions,
            "avg_session_size": int(p_tot / p_sessions) if p_sessions > 0 else p_tot,
            "avg_request_size": int(p_tot / p_reqs) if p_reqs > 0 else p_tot,
            "cache_ratio": p_cread / (p_inp + p_cread) if (p_inp + p_cread) > 0 else 0,
            "daily_trend": sorted([{"day": d, "tokens": t} for d, t in p_daily_trend.items()], key=lambda x: x["day"]),
            "top_models": sorted([{"model": m, "tokens": t} for m, t in p_models.items()], key=lambda x: x["tokens"], reverse=True)[:5],
            "top_tools": sorted([{"tool": t, "tokens": tok} for t, tok in p_tools.items()], key=lambda x: x["tokens"], reverse=True)[:5],
            "longest_session": {"session_id": p_longest_sess_id, "duration": p_longest_sess_duration},
            "latest_activity": latest_act,
            "git_path": git_info["path"] if git_info else None,
            "branch": git_info["branch"] if git_info else None,
            "commits_count": git_info["commits_count"] if git_info else 0
        }
        repositories_list.append(repo_obj)

    # Sort repositories descending by tokens
    repositories_list.sort(key=lambda r: r["tokens"], reverse=True)

    # Model analytics calculations
    models_dict = {}
    for model_name, m_events in events_by_model.items():
        m_inp = sum(e['input_tokens'] for e in m_events)
        m_out = sum(e['output_tokens'] for e in m_events)
        m_cread = sum(e['cache_read_tokens'] for e in m_events)
        m_tot = sum(e['total_tokens'] for e in m_events)
        m_reqs = sum(e['requests'] for e in m_events)
        m_repos = list(set(e['workspace_id'] for e in m_events if e['workspace_id']))
        m_sessions = len(set(e['session_id'] for e in m_events if e['session_id']))
        
        # Usage over time
        m_daily = collections.defaultdict(int)
        for e in m_events:
            dt = parse_datetime(e['occurred_at'])
            if dt:
                m_daily[dt.strftime("%Y-%m-%d")] += e['total_tokens']
                
        # Estimate cost
        m_cost, m_savings = 0.0, 0.0
        for e in m_events:
            c_val, s_val = utils.estimate_token_cost_and_savings(
                e['model_raw'], e['input_tokens'], e['output_tokens'], e['cache_read_tokens']
            )
            m_cost += c_val
            m_savings += s_val
            
        models_dict[model_name] = {
            "model_name": model_name,
            "total_tokens": m_tot,
            "input_tokens": m_inp,
            "output_tokens": m_out,
            "cache_read_tokens": m_cread,
            "requests": m_reqs,
            "average_context": int(m_inp / m_reqs) if m_reqs > 0 else 0,
            "average_completion": int(m_out / m_reqs) if m_reqs > 0 else 0,
            "average_cache_hit": m_cread / (m_inp + m_cread) if (m_inp + m_cread) > 0 else 0,
            "repositories_used": m_repos,
            "sessions": m_sessions,
            "usage_over_time": sorted([{"day": d, "tokens": t} for d, t in m_daily.items()], key=lambda x: x["day"]),
            "estimated_cost": m_cost,
            "estimated_savings": m_savings,
            "latency": "N/A"
        }

    # Reconcile model metrics from balance_obs if present
    if balance_obs:
        # Extract model-specific observation keys
        # Pattern: model_<sanitized_name>_input_tokens, etc.
        model_obs_data = collections.defaultdict(dict)
        for k, val in balance_obs.items():
            if k.startswith('model_') and ('_tokens' in k or '_cost_usd' in k):
                # e.g., model_gpt_5_3_codex_input_tokens -> model: gpt_5_3_codex, metric: input_tokens
                parts = k.split('_')
                # find metric suffix
                if k.endswith('_input_tokens'):
                    m_name = '_'.join(parts[1:-2])
                    model_obs_data[m_name]['input'] = val
                elif k.endswith('_output_tokens'):
                    m_name = '_'.join(parts[1:-2])
                    model_obs_data[m_name]['output'] = val
                elif k.endswith('_cached_tokens'):
                    m_name = '_'.join(parts[1:-2])
                    model_obs_data[m_name]['cached'] = val
                elif k.endswith('_total_tokens'):
                    m_name = '_'.join(parts[1:-2])
                    model_obs_data[m_name]['total'] = val
                elif k.endswith('_cost_usd'):
                    m_name = '_'.join(parts[1:-2])
                    model_obs_data[m_name]['cost'] = val

        for raw_m_key, m_obs in model_obs_data.items():
            # Format display model name: gpt_5_3_codex -> gpt-5.3-codex
            canonical_m_name = raw_m_key.replace('_', '-').replace('-codex', '-codex')
            # find matching key in models_dict
            match_key = next((k for k in models_dict if k.replace('_', '-').replace('.', '-') == canonical_m_name.replace('.', '-')), None)
            target_key = match_key or canonical_m_name

            if target_key not in models_dict:
                models_dict[target_key] = {
                    "model_name": target_key,
                    "total_tokens": 0, "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0,
                    "requests": 1, "average_context": 0, "average_completion": 0, "average_cache_hit": 0,
                    "repositories_used": [], "sessions": 0, "usage_over_time": [],
                    "estimated_cost": 0.0, "estimated_savings": 0.0, "latency": "N/A"
                }

            m_obj = models_dict[target_key]
            m_inp = int(m_obs.get('input', m_obj['input_tokens']))
            m_out = int(m_obs.get('output', m_obj['output_tokens']))
            m_cread = int(m_obs.get('cached', m_obj['cache_read_tokens']))
            m_tot = int(m_obs.get('total', m_inp + m_out + m_cread))
            m_cost = float(m_obs.get('cost', m_obj['estimated_cost']))

            m_obj['input_tokens'] = max(m_obj['input_tokens'], m_inp)
            m_obj['output_tokens'] = max(m_obj['output_tokens'], m_out)
            m_obj['cache_read_tokens'] = max(m_obj['cache_read_tokens'], m_cread)
            m_obj['total_tokens'] = max(m_obj['total_tokens'], m_tot)
            m_obj['estimated_cost'] = max(m_obj['estimated_cost'], m_cost)
            if (m_obj['input_tokens'] + m_obj['cache_read_tokens']) > 0:
                m_obj['average_cache_hit'] = m_obj['cache_read_tokens'] / (m_obj['input_tokens'] + m_obj['cache_read_tokens'])

    models_list = list(models_dict.values())
    models_list.sort(key=lambda m: m["total_tokens"], reverse=True)

    # Tool analytics calculations
    tools_list = []
    # Incorporate copilot totals
    for agent_name, t_events in events_by_tool.items():
        t_inp = sum(e['input_tokens'] for e in t_events)
        t_out = sum(e['output_tokens'] for e in t_events)
        t_cread = sum(e['cache_read_tokens'] for e in t_events)
        t_tot = sum(e['total_tokens'] for e in t_events)
        t_reqs = sum(e['requests'] for e in t_events)
        t_repos = list(set(e['workspace_id'] for e in t_events if e['workspace_id']))
        t_models = list(set(e['model_raw'] for e in t_events if e['model_raw']))
        
        # Find average session length
        t_sess_durations = []
        t_sessions = set(e['session_id'] for e in t_events if e['session_id'])
        for s_id in t_sessions:
            if s_id == "Global/No Session" or not s_id: continue
            for s_obj in sessions_list:
                if s_obj["session_id"] == s_id:
                    t_sess_durations.append(s_obj["duration"])
                    
        avg_sess_len = int(sum(t_sess_durations) / len(t_sess_durations)) if t_sess_durations else 0
        
        # Display name mapping
        display_map = {
            "gemini_cli": "Antigravity CLI (agy)",
            "codex": "OpenAI Codex CLI",
            "copilot": "GitHub Copilot CLI",
            "claude_code": "Claude Code",
            "cursor": "Cursor IDE",
            "cursor-composer": "Cursor Composer",
            "provider_poller": "Provider Poller System"
        }
        disp_name = display_map.get(agent_name, agent_name.replace("_", " ").title())
        
        tool_obj = {
            "tool_name": agent_name,
            "display_name": disp_name,
            "total_tokens": t_tot,
            "input_tokens": t_inp,
            "output_tokens": t_out,
            "cache_read_tokens": cread,
            "cache_ratio": t_cread / (t_inp + t_cread) if (t_inp + t_cread) > 0 else 0,
            "requests": t_reqs,
            "repositories": t_repos,
            "models": t_models,
            "avg_session_length": avg_sess_len
        }
        tools_list.append(tool_obj)
        
    # Include Copilot standalone in tools_list if it doesn't already exist or merge if it does
    cop_tool = next((t for t in tools_list if t["tool_name"] == "copilot"), None)
    if cop_tool:
        # Merge copilot totals
        cop_tool["total_tokens"] += cop_tot
        cop_tool["input_tokens"] += cop_in
        cop_tool["output_tokens"] += cop_out
        cop_tool["requests"] += cop_req
    elif cop_tot > 0:
        tools_list.append({
            "tool_name": "copilot",
            "display_name": "GitHub Copilot CLI",
            "total_tokens": cop_tot,
            "input_tokens": cop_in,
            "output_tokens": cop_out,
            "cache_read_tokens": 0,
            "cache_ratio": 0.0,
            "requests": cop_req,
            "repositories": [],
            "models": ["copilot-default"],
            "avg_session_length": 0
        })

    tools_list.sort(key=lambda t: t["total_tokens"], reverse=True)

    # Time Analytics details
    peak_usage_day = "N/A"
    peak_usage_tokens = 0
    if daily_tokens:
        peak_day_str = max(daily_tokens.keys(), key=lambda d: daily_tokens[d]["total"])
        peak_usage_day = peak_day_str
        peak_usage_tokens = daily_tokens[peak_day_str]["total"]
        
    busiest_coding_day = "N/A"
    if daily_tokens:
        busiest_day_str = max(daily_tokens.keys(), key=lambda d: daily_tokens[d]["requests"])
        busiest_coding_day = busiest_day_str
        
    longest_uninterrupted_sec = compute_uninterrupted_sessions(events, gap_minutes=30)

    # Prepare daily timeline sorting
    sorted_days = sorted(daily_tokens.keys())
    daily_timeline = []
    for d in sorted_days:
        daily_timeline.append({
            "day": d,
            "total": daily_tokens[d]["total"],
            "input": daily_tokens[d]["input"],
            "output": daily_tokens[d]["output"],
            "cache_read": daily_tokens[d]["cache_read"],
            "requests": daily_tokens[d]["requests"],
            "cost": daily_tokens[d]["cost"],
            "savings": daily_tokens[d]["savings"]
        })
        
    # Calculate rolling averages (7-day window)
    for idx, d_data in enumerate(daily_timeline):
        window = daily_timeline[max(0, idx - 6):idx + 1]
        d_data["rolling_avg"] = sum(w["total"] for w in window) / len(window)

    # Calculate average coding session duration
    avg_session_duration = int(sum(s["duration"] for s in sessions_list) / len(sessions_list)) if sessions_list else 0

    # Build the final telemetry data report object
    report_data = {
        "global_overview": {
            "total_tokens": total_tokens,
            "total_input": total_input,
            "total_output": total_output,
            "cached_tokens": total_cache_read,
            "cache_hit_pct": (total_cache_read / (total_input + total_cache_read) * 100) if (total_input + total_cache_read) > 0 else 0,
            "requests_count": requests_count,
            "sessions_count": len(sessions_list),
            "active_repositories_count": len(workspaces),
            "active_models_count": len(models_list),
            "active_tools_count": len(tools_list),
            "avg_context_size": int(total_input / requests_count) if requests_count > 0 else 0,
            "avg_tokens_per_request": int(total_tokens / requests_count) if requests_count > 0 else 0,
            "largest_request": largest_request,
            "largest_session": {
                "session_id": largest_session["session_id"],
                "tokens": largest_session["total_tokens"],
                "requests": largest_session["requests"],
                "project": largest_session["project"]
            } if largest_session else None,
            "longest_session_duration": longest_session_duration,
            "longest_session_id": longest_session_id,
            "peak_usage_day": peak_usage_day,
            "peak_usage_tokens": peak_usage_tokens,
            "estimated_cost": total_cost,
            "estimated_savings": total_savings,
            "local_event_tokens": local_event_totals["tokens"],
            "local_event_input": local_event_totals["input"],
            "local_event_output": local_event_totals["output"],
            "local_event_cached_tokens": local_event_totals["cache_read"],
            "provider_reported_tokens": total_tokens,
            "provider_reported_input": total_input,
            "provider_reported_output": total_output,
            "provider_reported_cached_tokens": total_cache_read,
            "coverage_gap_tokens": max(0, total_tokens - local_event_totals["tokens"]),
        },
        "repositories": repositories_list,
        "sessions": sessions_list,
        "events": client_events,
        "models": models_list,
        "tools": tools_list,
        "time_analytics": {
            "daily_timeline": daily_timeline,
            "weekday_heatmap": dict(weekday_heatmap),
            "hourly_heatmap": dict(hourly_heatmap),
            "weekday_totals": dict(weekday_totals),
            "monthly_trends": sorted([{"month": m, "total": data["total"], "input": data["input"], "output": data["output"], "cache_read": data["cache_read"], "cost": data["cost"]} for m, data in monthly_tokens.items()], key=lambda x: x["month"]),
            "busiest_coding_day": busiest_coding_day,
            "longest_uninterrupted_coding_session_sec": longest_uninterrupted_sec
        },
        "productivity_metrics": {
            "tokens_per_repository": {r["repository"]: r["tokens"] for r in repositories_list},
            "tokens_per_request": int(total_tokens / requests_count) if requests_count > 0 else 0,
            "tokens_per_session": int(total_tokens / len(sessions_list)) if sessions_list else 0,
            "output_input_ratio": total_output / total_input if total_input > 0 else 0,
            "cache_savings": total_savings,
            "context_utilisation": total_input / total_tokens if total_tokens > 0 else 0,
            "requests_per_hour": requests_count / (len(daily_tokens) * 24) if daily_tokens else 0,
            "sessions_per_day": len(sessions_list) / len(daily_tokens) if daily_tokens else 0,
            "average_coding_session_length": avg_session_duration
        },
        "git_integration": {
            "correlated_commits": git_commits,
            "active_branches": active_branches,
            "repos_git_info": {k: {"path": v["path"], "branch": v["branch"], "commits_count": v["commits_count"]} for k, v in repos_git_info.items()}
        }
    }
    
    return report_data

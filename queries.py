# queries.py
# Contains SQL queries for the AI Engineering Observatory / Token Tracker.

QUERY_ALL_EVENTS = """
    SELECT 
        event_id,
        occurred_at,
        provider_id,
        agent_name,
        workspace_id,
        session_id,
        turn_id,
        event_type,
        model_raw,
        coalesce(input_tokens, 0) as input_tokens,
        coalesce(output_tokens, 0) as output_tokens,
        coalesce(cache_read_tokens, 0) as cache_read_tokens,
        coalesce(cache_write_tokens, 0) as cache_write_tokens,
        coalesce(total_tokens, 0) as total_tokens,
        coalesce(cost_usd, 0.0) as cost_usd,
        coalesce(requests, 1) as requests,
        status,
        dedup_key
    FROM usage_events
    WHERE occurred_at IS NOT NULL
      AND event_type = 'message_usage'
      AND (input_tokens > 0 OR output_tokens > 0 OR total_tokens > 0)
    ORDER BY occurred_at ASC
"""

QUERY_DAILY_ROLLUP = """
    SELECT 
        substr(occurred_at, 1, 10) as day,
        coalesce(workspace_id, 'Global/No Project') as project,
        coalesce(agent_name, 'Unknown') as agent,
        coalesce(model_raw, 'System/Tools') as model,
        sum(coalesce(input_tokens, 0)) as input,
        sum(coalesce(output_tokens, 0)) as output,
        sum(coalesce(cache_read_tokens, 0)) as cache_read,
        sum(coalesce(cache_write_tokens, 0)) as cache_write,
        sum(coalesce(total_tokens, 0)) as total,
        count(*) as requests
    FROM usage_events
    WHERE occurred_at IS NOT NULL
    GROUP BY day, project, agent, model
    ORDER BY day ASC
"""

QUERY_PROJECTS_BREAKDOWN = """
    SELECT 
        coalesce(workspace_id, 'Global/No Project') as project,
        sum(coalesce(input_tokens, 0)) as input,
        sum(coalesce(output_tokens, 0)) as output,
        sum(coalesce(cache_read_tokens, 0)) as cache_read,
        sum(coalesce(total_tokens, 0)) as total,
        count(*) as requests,
        count(distinct coalesce(session_id, 'No Session')) as sessions
    FROM usage_events
    WHERE event_type = 'message_usage'
      AND (input_tokens > 0 OR output_tokens > 0 OR total_tokens > 0)
    GROUP BY project
    ORDER BY total DESC
"""

QUERY_SESSIONS_BREAKDOWN = """
    SELECT 
        coalesce(workspace_id, 'Global/No Project') as project,
        coalesce(session_id, 'Global/No Session') as session,
        min(occurred_at) as start_time,
        max(occurred_at) as end_time,
        sum(coalesce(input_tokens, 0)) as input,
        sum(coalesce(output_tokens, 0)) as output,
        sum(coalesce(cache_read_tokens, 0)) as cache_read,
        sum(coalesce(total_tokens, 0)) as total,
        count(*) as requests
    FROM usage_events
    GROUP BY project, session
    ORDER BY start_time DESC
"""

QUERY_TOOL_TOTALS = """
    SELECT 
        coalesce(agent_name, 'Unknown') as agent,
        sum(coalesce(input_tokens, 0)) as input,
        sum(coalesce(output_tokens, 0)) as output,
        sum(coalesce(cache_read_tokens, 0)) as cache_read,
        sum(coalesce(total_tokens, 0)) as total,
        count(*) as requests
    FROM usage_events
    GROUP BY agent
"""

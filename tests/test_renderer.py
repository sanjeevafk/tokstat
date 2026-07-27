from tokstat import renderer


def test_dashboard_escapes_embedded_telemetry_script_delimiters(tmp_path):
    output = tmp_path / "dashboard.html"
    payload = "</script><img src=x onerror=alert(1)>"

    renderer.generate_html_report(
        {
            "global_overview": {},
            "repositories": [{"repository": payload}],
            "sessions": [],
            "events": [{"project": payload}],
            "models": [],
            "tools": [],
            "time_analytics": {},
            "productivity_metrics": {},
            "git_integration": {"correlated_commits": [], "repos_git_info": {}},
        },
        output,
    )

    html = output.read_text(encoding="utf-8")
    assert "const TELEMETRY_DATA" in html
    assert payload not in html
    assert "\\u003c/script\\u003e" in html


def test_dashboard_contains_safe_dynamic_rendering_helpers(tmp_path):
    output = tmp_path / "dashboard.html"
    renderer.generate_html_report({}, output)

    html = output.read_text(encoding="utf-8")
    assert "function escapeHtml(value)" in html
    assert "switchTab('repositories', { preserveDrilldown: true })" in html
    assert "switchTab('sessions', { preserveDrilldown: true })" in html
    assert '<div class="metric-value">${formatNumber(t.total_tokens)}</div>' in html

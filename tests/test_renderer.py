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


def _report_with_local_data():
    return {
        "global_overview": {
            "total_tokens": 6000,
            "estimated_cost": 1.5,
            "estimated_savings": 0.1,
            "provider_reported_tokens": 6000,
            "local_event_tokens": 6000,
            "coverage_gap_tokens": 0,
            "local_inference": {
                "total_tokens": 4500,
                "requests": 3,
                "cloud_cost_avoidance": 1.25,
                "models_used": ["llama3.1:8b"],
                "models_detail": [{"model": "llama3.1:8b", "tokens": 4500, "requests": 3}],
            },
        },
        "repositories": [],
        "sessions": [],
        "events": [{"project": "p", "provider": "local"}],
        "models": [],
        "tools": [],
        "time_analytics": {},
        "productivity_metrics": {},
        "git_integration": {"correlated_commits": [], "repos_git_info": {}},
    }


def test_dashboard_renders_local_model_sections(tmp_path):
    output = tmp_path / "dashboard.html"
    renderer.generate_html_report(_report_with_local_data(), output)

    html = output.read_text(encoding="utf-8")
    assert "Cloud Cost Avoidance" in html
    assert "id=\"local-inference-row\"" in html
    assert "id=\"localCloudChartOverview\"" in html
    assert "id=\"filter-provider\"" in html
    # Initial (server-rendered) values must be present, not zero placeholders
    assert 'id="stat-cloud-avoidance">$1.2500</' in html
    assert 'id="stat-local-tokens">4.5k</' in html


def test_dashboard_local_card_hidden_when_no_local_data(tmp_path):
    output = tmp_path / "dashboard.html"
    renderer.generate_html_report({}, output)

    html = output.read_text(encoding="utf-8")
    # The local inference row defaults to hidden via inline style
    assert 'id="local-inference-row" style="display: none;"' in html
    assert 'id="stat-cloud-avoidance">$0.0000</' in html
    # The coverage-gap hint stays hidden when there is no gap
    assert 'id="scope-gap-hint" style="display:none;"' in html


def test_dashboard_scope_hint_shown_when_gap(tmp_path):
    report = _report_with_local_data()
    report["global_overview"]["coverage_gap_tokens"] = 5000
    output = tmp_path / "dashboard.html"
    renderer.generate_html_report(report, output)

    html = output.read_text(encoding="utf-8")
    # Gap > 0 reveals the hint pointing at `tokstat sync`.
    assert 'id="scope-gap-hint" style="display:block;"' in html
    assert "tokstat sync" in html


def test_dashboard_provider_filter_is_wired(tmp_path):
    output = tmp_path / "dashboard.html"
    renderer.generate_html_report({}, output)

    html = output.read_text(encoding="utf-8")
    # applyFilters() must read the provider dropdown (regression: it was ignored)
    assert "const provVal = document.getElementById('filter-provider').value;" in html
    assert "activeFilters.provider = ['all', 'cloud', 'local'].includes(provVal) ? provVal : 'all';" in html
    # clearAllFilters() must reset the provider dropdown too
    assert "document.getElementById('filter-provider').value = 'all';" in html


def test_dashboard_providers_tab_and_drilldown(tmp_path):
    output = tmp_path / "dashboard.html"
    renderer.generate_html_report({}, output)

    html = output.read_text(encoding="utf-8")
    assert 'id="view-providers"' in html
    assert 'id="subview-providers-list"' in html
    assert 'id="subview-provider-drilldown"' in html
    assert "function renderProvidersList()" in html
    assert "function renderProviderDrilldown(" in html
    assert "function drilldownProvider(" in html
    assert "function providerDisplayName(" in html
    # Entry points: clickable donut segments and scope-card provider stat
    assert "drilldownProvider(elements[0].index === 0 ? 'local' : 'cloud')" in html
    assert "onclick=\"drilldownProvider('cloud')\"" in html
    # Models table carries a clickable provider column
    assert "<th>Provider</th>" in html
    assert "provider-pill-js" in html
    # Keyboard shortcut mapping covers the new tab
    assert "'providers', 'time', 'git', 'export'" in html

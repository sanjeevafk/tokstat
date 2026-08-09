# renderer.py
import json


def generate_html_report(report_data, output_path, watch_mode=False):
    """
    Generates a professional, self-contained AI Engineering Observatory dashboard
    and writes it to the output path.
    """
    
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Engineering Observatory - Token Telemetry</title>
    <!-- Favicon -->
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64' fill='none'><rect width='64' height='64' rx='16' fill='%23080b13'/><rect x='1' y='1' width='62' height='62' rx='15' stroke='%231c2336' stroke-width='2'/><path d='M14 42L25 28L36 34L49 18' stroke='url(%23g)' stroke-width='3.5' stroke-linecap='round' stroke-linejoin='round'/><circle cx='14' cy='42' r='3.5' fill='%237ed7bd'/><circle cx='25' cy='28' r='3.5' fill='%23ff7a00'/><circle cx='36' cy='34' r='3.5' fill='%23b9dc75'/><circle cx='49' cy='18' r='4' fill='%237ed7bd'/><rect x='12' y='46' width='4' height='6' rx='1' fill='%237ed7bd' opacity='0.5'/><rect x='23' y='34' width='4' height='18' rx='1' fill='%23ff7a00' opacity='0.5'/><rect x='34' y='40' width='4' height='12' rx='1' fill='%23b9dc75' opacity='0.5'/><rect x='47' y='24' width='4' height='28' rx='1' fill='%237ed7bd' opacity='0.5'/><defs><linearGradient id='g' x1='14' y1='42' x2='49' y2='18' gradientUnits='userSpaceOnUse'><stop stop-color='%237ed7bd'/><stop offset='0.4' stop-color='%23ff7a00'/><stop offset='1' stop-color='%23b9dc75'/></linearGradient></defs></svg>">
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Syne:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-base: #06080e;
            --bg-sidebar: #0b0e17;
            --bg-card: #0e121f;
            --bg-card-hover: #131828;
            --bg-header: #080b13;
            
            --border-color: #1c2336;
            --border-highlight: #28324e;
            
            --text-primary: #f0f3f6;
            --text-secondary: #8b95a5;
            --text-muted: #565d6c;
            
            --accent-orange: #ff7a00;
            --accent-orange-glow: rgba(255, 122, 0, 0.15);
            --accent-emerald: #b9dc75;
            --accent-emerald-glow: rgba(185, 220, 117, 0.12);
            --accent-cyan: #7ed7bd;
            --accent-cyan-glow: rgba(126, 215, 189, 0.12);
            --accent-purple: #b9dc75;
            --accent-purple-glow: rgba(185, 220, 117, 0.12);
            --accent-blue: #7ed7bd;
            --accent-blue-glow: rgba(126, 215, 189, 0.12);
            --accent-red: #f85149;
            
            --sidebar-width: 260px;
            --sidebar-collapsed-width: 68px;
            --header-height: 70px;
            --transition-speed: 0.25s;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }

        body {
            background-color: var(--bg-base);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            overflow-x: hidden;
        }

        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        ::-webkit-scrollbar-thumb {
            background: #232a3d;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #343f5c;
        }

        /* Main structure */
        #sidebar {
            width: var(--sidebar-width);
            background-color: var(--bg-sidebar);
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            position: fixed;
            top: 0;
            bottom: 0;
            left: 0;
            z-index: 1000;
            transition: width var(--transition-speed) ease;
            overflow-y: auto;
            overflow-x: hidden;
        }

        body.sidebar-collapsed #sidebar {
            width: var(--sidebar-collapsed-width);
        }

        #app-content {
            margin-left: var(--sidebar-width);
            flex: 1;
            display: flex;
            flex-direction: column;
            min-width: 0;
            transition: margin-left var(--transition-speed) ease;
        }

        body.sidebar-collapsed #app-content {
            margin-left: var(--sidebar-collapsed-width);
        }

        #header {
            height: var(--header-height);
            background-color: var(--bg-header);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 2rem;
            position: sticky;
            top: 0;
            z-index: 900;
        }

        #main-view {
            padding: 2rem;
            max-width: 1600px;
            width: 100%;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 2rem;
            flex: 1;
        }

        /* Brand styling */
        .brand-container {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 1.5rem 1.25rem;
            border-bottom: 1px solid var(--border-color);
            overflow: hidden;
            white-space: nowrap;
        }

        .logo-box {
            width: 36px;
            height: 36px;
            min-width: 36px;
            border-radius: 10px;
            background: linear-gradient(135deg, var(--accent-orange), var(--accent-purple));
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 12px rgba(255, 122, 0, 0.25);
        }

        .logo-box svg {
            width: 18px;
            height: 18px;
            fill: white;
        }

        .brand-text h1 {
            font-family: 'Outfit', sans-serif;
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: -0.01em;
        }

        .brand-text p {
            font-size: 0.7rem;
            color: var(--text-secondary);
            margin-top: 1px;
        }

        /* Sidebar Navigation */
        .nav-list {
            list-style: none;
            padding: 1rem 0.5rem;
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        .nav-item a {
            display: flex;
            align-items: center;
            gap: 0.85rem;
            padding: 0.75rem 0.85rem;
            color: var(--text-secondary);
            text-decoration: none;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 500;
            transition: all 0.2s ease;
            cursor: pointer;
            white-space: nowrap;
        }

        .nav-item a:hover {
            background-color: rgba(255, 255, 255, 0.03);
            color: var(--text-primary);
        }

        .nav-item.active a {
            background-color: var(--accent-orange-glow);
            color: var(--accent-orange);
            font-weight: 600;
        }

        .nav-item svg {
            width: 18px;
            height: 18px;
            min-width: 18px;
            stroke-width: 2.2;
        }

        .sidebar-collapse-btn {
            margin-top: auto;
            border-top: 1px solid var(--border-color);
            padding: 1rem;
            display: flex;
            justify-content: center;
            align-items: center;
            cursor: pointer;
            color: var(--text-muted);
            transition: color 0.2s ease;
        }

        .sidebar-collapse-btn:hover {
            color: var(--text-primary);
        }

        /* Header controls */
        .header-left {
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }

        .breadcrumbs {
            font-size: 0.85rem;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .breadcrumbs span.current {
            color: var(--text-primary);
            font-weight: 600;
        }

        .search-container {
            position: relative;
            width: 260px;
        }

        .search-container input {
            width: 100%;
            background-color: #0b0e18;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 0.45rem 1rem 0.45rem 2.2rem;
            font-size: 0.85rem;
            color: var(--text-primary);
            outline: none;
            transition: all 0.2s ease;
        }

        .search-container input:focus {
            border-color: var(--accent-orange);
            box-shadow: 0 0 10px var(--accent-orange-glow);
        }

        .search-icon {
            position: absolute;
            left: 0.75rem;
            top: 50%;
            transform: translateY(-50%);
            width: 14px;
            height: 14px;
            stroke: var(--text-muted);
            pointer-events: none;
        }

        .header-right {
            display: flex;
            align-items: center;
            gap: 1.25rem;
        }

        .live-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(16, 185, 129, 0.06);
            color: var(--accent-emerald);
            border: 1px solid rgba(16, 185, 129, 0.15);
            padding: 0.35rem 0.75rem;
            border-radius: 8px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .live-status::before {
            content: '';
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: var(--accent-emerald);
            box-shadow: 0 0 6px var(--accent-emerald);
        }
        
        .live-status.offline {
            background: rgba(139, 149, 165, 0.05);
            color: var(--text-secondary);
            border: 1px solid rgba(139, 149, 165, 0.15);
        }
        .live-status.offline::before {
            background-color: var(--text-muted);
            box-shadow: none;
        }

        /* Global filters bar */
        .filter-bar {
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            align-items: center;
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 0.75rem 1.25rem;
        }

        .filter-group {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .filter-label {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.03em;
        }

        .filter-select {
            background-color: var(--bg-sidebar);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 0.35rem 1.5rem 0.35rem 0.5rem;
            font-size: 0.8rem;
            color: var(--text-primary);
            outline: none;
            cursor: pointer;
            transition: border-color 0.2s ease;
        }

        .filter-select:hover {
            border-color: var(--border-highlight);
        }

        .filter-select:focus {
            border-color: var(--accent-orange);
        }

        /* Only the selected workspace view belongs in the document flow. */
        .tab-view { display: none; }
        .tab-view.active { display: block; }

        .date-btns {
            display: flex;
            background-color: var(--bg-sidebar);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 0.15rem;
        }

        .date-btn {
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.3rem 0.65rem;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .date-btn:hover {
            color: var(--text-primary);
        }

        .date-btn.active {
            background-color: var(--accent-orange);
            color: #000;
            font-weight: 700;
        }

        .clear-filters-btn {
            background: transparent;
            border: 1px dashed var(--border-color);
            color: var(--text-secondary);
            font-size: 0.75rem;
            padding: 0.35rem 0.65rem;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }

        .clear-filters-btn:hover {
            border-color: var(--accent-red);
            color: var(--accent-red);
            background-color: rgba(248, 81, 73, 0.05);
        }

        /* Overview Page widgets */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }

        .metric-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            position: relative;
            overflow: hidden;
            transition: border-color 0.2s ease;
        }

        .metric-card:hover {
            border-color: var(--border-highlight);
        }

        .metric-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: var(--text-secondary);
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            margin-bottom: 0.5rem;
        }

        .metric-value {
            font-family: 'Outfit', sans-serif;
            font-size: 1.65rem;
            font-weight: 700;
            letter-spacing: -0.01em;
        }
        
        .metric-value.tiny {
            font-size: 1.25rem;
            word-break: break-all;
        }

        .metric-footer {
            margin-top: 0.5rem;
            font-size: 0.7rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .metric-footer .trend-up {
            color: var(--accent-emerald);
            font-weight: 600;
        }

        .card-glow-orange::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background-color: var(--accent-orange);
        }
        .card-glow-purple::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background-color: var(--accent-purple);
        }
        .card-glow-emerald::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background-color: var(--accent-emerald);
        }
        .card-glow-cyan::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background-color: var(--accent-cyan);
        }

        /* Panel details */
        .panel-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.75rem;
        }

        .panel-title {
            font-family: 'Outfit', sans-serif;
            font-size: 1.05rem;
            font-weight: 600;
        }

        .panel-subtitle {
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: 0.15rem;
        }

        /* Two column layout */
        .two-col-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 1.5rem;
        }

        @media (max-width: 1024px) {
            .two-col-grid {
                grid-template-columns: 1fr;
            }
        }
        
        .three-col-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1.5rem;
        }
        @media (max-width: 900px) {
            .three-col-grid {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 720px) {
            :root { --sidebar-width: 0px; --header-height: 62px; }
            #sidebar {
                width: 0;
                transform: translateX(-100%);
                box-shadow: 18px 0 45px rgba(0,0,0,.45);
            }
            #sidebar.mobile-open { width: 260px; transform: translateX(0); }
            #app-content, body.sidebar-collapsed #app-content { margin-left: 0; }
            #header { padding: 0 1rem; }
            #main-view { padding: 1rem; gap: 1rem; }
            .search-container { max-width: 42vw; }
            .sidebar-collapse-btn { display: none; }
        }

        .chart-wrapper {
            position: relative;
            width: 100%;
            height: 320px;
        }

        /* Tables styling */
        .table-wrapper {
            overflow-x: auto;
            width: 100%;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.85rem;
        }

        th {
            padding: 0.75rem 1rem;
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid var(--border-color);
            cursor: pointer;
            user-select: none;
        }

        th:hover {
            color: var(--text-primary);
        }
        
        th.sort-asc::after {
            content: ' \2191';
        }
        th.sort-desc::after {
            content: ' \2193';
        }

        td {
            padding: 0.75rem 1rem;
            border-bottom: 1px solid rgba(255,255,255,0.02);
            color: var(--text-primary);
        }

        tr:last-child td {
            border-bottom: none;
        }

        tr.clickable-row {
            cursor: pointer;
            transition: background-color 0.2s ease;
        }

        tr.clickable-row:hover td {
            background-color: var(--bg-card-hover);
        }

        .pill {
            background-color: rgba(255,255,255,0.04);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            font-family: 'Fira Code', monospace;
            font-size: 0.75rem;
            white-space: nowrap;
        }
        
        .pill.pill-orange { color: var(--accent-orange); background-color: var(--accent-orange-glow); border-color: rgba(255,122,0,0.3); }
        .pill.pill-purple { color: var(--accent-purple); background-color: var(--accent-purple-glow); border-color: rgba(139,92,246,0.3); }
        .pill.pill-emerald { color: var(--accent-emerald); background-color: var(--accent-emerald-glow); border-color: rgba(16,185,129,0.3); }
        .pill.pill-cyan { color: var(--accent-cyan); background-color: var(--accent-cyan-glow); border-color: rgba(6,182,212,0.3); }
        .pill.pill-blue { color: var(--accent-blue); background-color: var(--accent-blue-glow); border-color: rgba(31,111,235,0.3); }

        .session-id-link {
            font-family: 'Fira Code', monospace;
            color: var(--accent-orange);
            font-weight: 600;
            text-decoration: none;
        }
        
        .session-id-link:hover {
            text-decoration: underline;
        }

        /* Heatmap Grid */
        .heatmap-container {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            padding: 0.5rem 0;
            overflow-x: auto;
            width: 100%;
        }

        .heatmap-grid-days {
            display: grid;
            grid-template-columns: repeat(53, 14px);
            grid-template-rows: repeat(7, 14px);
            gap: 3px;
        }

        .heatmap-cell {
            width: 14px;
            height: 14px;
            background-color: #161b22;
            border-radius: 2px;
            position: relative;
            cursor: pointer;
        }
        
        .heatmap-cell:hover {
            outline: 1px solid var(--text-primary);
            z-index: 10;
        }

        .heatmap-legend {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 0.4rem;
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 0.5rem;
        }

        .legend-box {
            width: 10px;
            height: 10px;
            border-radius: 2px;
        }

        /* Detail View Subpanel */
        .detail-view-container {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .detail-header-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
        }

        .back-btn {
            background-color: var(--bg-sidebar);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 0.45rem 1rem;
            border-radius: 8px;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            transition: all 0.2s ease;
        }

        .back-btn:hover {
            background-color: rgba(255,255,255,0.03);
            border-color: var(--border-highlight);
        }

        /* Tooltip style */
        .tooltip {
            position: relative;
            display: inline-block;
        }

        /* Timeline timeline styling */
        .timeline-flow {
            display: flex;
            flex-direction: column;
            position: relative;
            padding-left: 2rem;
        }

        .timeline-flow::before {
            content: '';
            position: absolute;
            left: 7px;
            top: 0;
            bottom: 0;
            width: 2px;
            background-color: var(--border-color);
        }

        .timeline-node {
            position: relative;
            padding-bottom: 2rem;
        }

        .timeline-node:last-child {
            padding-bottom: 0;
        }

        .timeline-dot {
            position: absolute;
            left: -29px;
            top: 4px;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background-color: var(--bg-sidebar);
            border: 3px solid var(--accent-orange);
            z-index: 5;
        }
        
        .timeline-dot.success { border-color: var(--accent-emerald); }
        .timeline-dot.error { border-color: var(--accent-red); }

        .timeline-content {
            background-color: rgba(255,255,255,0.01);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 1rem;
        }
        
        .timeline-content:hover {
            border-color: var(--border-highlight);
        }

        .timeline-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }

        .timeline-time {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }

        /* Loading indicator overlay */
        #loading-indicator {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent-orange), var(--accent-purple));
            z-index: 9999;
            width: 0;
            transition: width 0.4s ease;
            display: none;
        }

        /* Export block */
        .export-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.5rem;
        }

        .export-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
            text-align: center;
            align-items: center;
            justify-content: space-between;
            transition: all 0.25s ease;
        }

        .export-card:hover {
            transform: translateY(-2px);
            border-color: var(--accent-orange);
            box-shadow: 0 4px 15px rgba(255, 122, 0, 0.08);
        }

        .export-icon {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            background-color: rgba(255,255,255,0.03);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 0.5rem;
            color: var(--text-secondary);
        }

        .export-card:hover .export-icon {
            background-color: var(--accent-orange-glow);
            color: var(--accent-orange);
        }

        .export-btn {
            width: 100%;
            background-color: var(--bg-sidebar);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 0.6rem;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .export-btn:hover {
            background-color: var(--accent-orange);
            color: #000;
            border-color: var(--accent-orange);
        }

        /* Modal styling */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(0,0,0,0.6);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2000;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.2s ease;
        }
        
        .modal-overlay.active {
            opacity: 1;
            pointer-events: all;
        }

        .modal-box {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            width: 90%;
            max-width: 500px;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
            transform: scale(0.95);
            transition: transform 0.2s ease;
        }
        
        .modal-overlay.active .modal-box {
            transform: scale(1);
        }

        .modal-title {
            font-family: 'Outfit', sans-serif;
            font-size: 1.15rem;
            font-weight: 700;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .modal-close {
            background: transparent;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 1.25rem;
        }

        .modal-close:hover {
            color: var(--text-primary);
        }

        /* Shortcut keys helper */
        .kbd-shortcut {
            background-color: var(--bg-sidebar);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 0.1rem 0.35rem;
            font-size: 0.75rem;
            font-family: monospace;
            box-shadow: 0 2px 0 var(--border-color);
            color: var(--text-primary);
        }
        
        .empty-state {
            padding: 4rem 2rem;
            text-align: center;
            color: var(--text-muted);
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 1rem;
        }
        
        .empty-state svg {
            width: 48px;
            height: 48px;
            stroke: var(--text-muted);
        }
        /* Industrial telemetry console: graphite, signal orange, oxidized green. */
        :root {
            --bg-base: #090b0a;
            --bg-sidebar: #0d100e;
            --bg-card: #111512;
            --bg-card-hover: #171c17;
            --bg-header: #0a0d0b;
            --border-color: #263027;
            --border-highlight: #536451;
            --text-primary: #f2eee4;
            --text-secondary: #a6ada0;
            --text-muted: #687368;
            --accent-orange: #ff7849;
            --accent-orange-glow: rgba(255, 120, 73, .14);
            --accent-emerald: #b9dc75;
            --accent-emerald-glow: rgba(185, 220, 117, .12);
            --accent-cyan: #7ed7bd;
            --accent-cyan-glow: rgba(126, 215, 189, .12);
            --accent-purple: #b9dc75;
            --accent-purple-glow: rgba(185, 220, 117, .12);
            --accent-blue: #b9dc75;
            --accent-red: #ff5f56;
        }

        * { font-family: 'IBM Plex Mono', monospace; }
        body {
            background-color: var(--bg-base);
            background-image: linear-gradient(rgba(185,220,117,.025) 1px, transparent 1px), linear-gradient(90deg, rgba(185,220,117,.025) 1px, transparent 1px);
            background-size: 32px 32px;
        }
        h1, h2, h3, .brand-text h1, .panel-title, .metric-value { font-family: 'Syne', sans-serif; }
        ::-webkit-scrollbar-thumb { background: #344036; border-radius: 0; }
        ::-webkit-scrollbar-thumb:hover { background: var(--accent-emerald); }
        #sidebar { background: rgba(13,16,14,.96); border-right: 1px solid var(--border-color); }
        #app-content { background: linear-gradient(180deg, rgba(9,11,10,.2), rgba(9,11,10,.8)); }
        #header { background: rgba(10,13,11,.92); border-bottom: 1px solid var(--border-color); backdrop-filter: blur(14px); }
        #main-view { max-width: 1760px; padding: 1.5rem 2rem 3rem; gap: 1.25rem; }
        .brand-container { padding: 1.35rem 1.15rem; }
        .logo-box { width: 34px; height: 34px; border-radius: 6px; background: var(--accent-orange); box-shadow: 4px 4px 0 #5c2a1b; }
        .logo-box svg { fill: #17100c; }
        .brand-text h1 { letter-spacing: -.04em; text-transform: uppercase; }
        .brand-text p, .panel-subtitle { letter-spacing: .02em; }
        .nav-list { padding: 1.25rem .7rem; gap: .35rem; }
        .nav-item a { border-radius: 3px; padding: .7rem .8rem; font-size: .76rem; letter-spacing: .02em; }
        .nav-item.active a { background: var(--accent-orange); color: #1b100b; box-shadow: 4px 4px 0 rgba(255,120,73,.18); }
        .nav-item.active svg { stroke: #1b100b; }
        .breadcrumbs { font-size: .7rem; text-transform: uppercase; letter-spacing: .08em; }
        .search-container { width: 300px; }
        .search-container input { background: #0c100d; border-radius: 3px; font-size: .7rem; }
        .live-status { border-radius: 3px; text-transform: uppercase; letter-spacing: .08em; font-size: .62rem; }
        .filter-bar { background: #0f130f; border-radius: 3px; border-color: var(--border-color); padding: .65rem .85rem; box-shadow: 0 1px 0 rgba(255,255,255,.03); }
        .filter-label { font-size: .62rem; letter-spacing: .1em; color: var(--text-muted); }
        .filter-select, .date-btns { background: #0a0d0b; border-radius: 2px; font-size: .68rem; }
        .date-btn { font-size: .65rem; border-radius: 1px; }
        .date-btn.active { background: var(--accent-orange); color: #1b100b; }
        .clear-filters-btn { border-radius: 2px; font-size: .65rem; }
        .metrics-grid { gap: .7rem; }
        .metric-card { background: rgba(17,21,18,.92); border-radius: 3px; border-color: var(--border-color); padding: 1rem; min-height: 126px; box-shadow: inset 0 1px 0 rgba(255,255,255,.025); }
        .metric-card:hover { border-color: var(--accent-emerald); transform: translateY(-2px); }
        .metric-header { font-size: .62rem; letter-spacing: .1em; }
        .metric-value { font-size: 1.8rem; letter-spacing: -.06em; color: var(--text-primary); }
        .metric-footer { font-size: .62rem; }
        .card-glow-orange::before, .card-glow-purple::before, .card-glow-emerald::before, .card-glow-cyan::before { width: 3px; }
        .card-glow-purple::before { background: var(--accent-emerald); }
        .card-glow-cyan::before { background: var(--accent-cyan); }
        .panel-card { background: rgba(17,21,18,.9); border-radius: 3px; border-color: var(--border-color); padding: 1.15rem; gap: 1rem; box-shadow: inset 0 1px 0 rgba(255,255,255,.025); }
        .panel-header { border-bottom-color: var(--border-color); padding-bottom: .65rem; }
        .panel-title { font-size: .95rem; letter-spacing: -.02em; }
        .table-wrapper { border: 1px solid rgba(38,48,39,.55); }
        table { font-size: .7rem; }
        th { padding: .7rem .8rem; font-size: .6rem; letter-spacing: .1em; background: #0d110e; color: var(--text-muted); }
        td { padding: .7rem .8rem; border-bottom-color: rgba(38,48,39,.65); }
        tbody tr:hover { background: rgba(185,220,117,.055); }
        .chart-wrapper { height: 300px; }
        .empty-state { border: 1px dashed var(--border-highlight); border-radius: 3px; }
        button { font-family: 'IBM Plex Mono', monospace; }
        .action-btn, .view-all-btn { border-radius: 2px; text-transform: uppercase; letter-spacing: .08em; }
        .data-scope-banner { display: grid; grid-template-columns: auto minmax(240px, 1fr) repeat(3, auto); align-items: center; gap: 1rem; background: #151b14; border: 1px solid #45553f; border-left: 3px solid var(--accent-orange); border-radius: 3px; padding: .8rem 1rem; }
        .scope-mark { color: var(--accent-orange); font-size: .62rem; font-weight: 700; letter-spacing: .12em; writing-mode: vertical-rl; transform: rotate(180deg); }
        .scope-copy { display: flex; flex-direction: column; gap: .2rem; }
        .scope-copy strong { font-family: 'Syne', sans-serif; font-size: .9rem; }
        .scope-copy span { color: var(--text-secondary); font-size: .64rem; line-height: 1.5; }
        .scope-stat { border-left: 1px solid #45553f; padding-left: 1rem; display: flex; flex-direction: column; gap: .25rem; min-width: 105px; }
        .scope-stat small { color: var(--text-muted); font-size: .56rem; letter-spacing: .08em; }
        .scope-stat b { color: var(--accent-emerald); font-family: 'Syne', sans-serif; font-size: 1rem; }
        .scope-gap b { color: var(--accent-orange); }
        @media (max-width: 720px) {
            #main-view { padding: 1rem; }
            #header { padding: 0 1rem; }
            .header-right .live-status { display: none; }
            .data-scope-banner { grid-template-columns: 1fr 1fr; }
            .scope-mark { writing-mode: initial; transform: none; grid-column: 1 / -1; }
            .scope-copy { grid-column: 1 / -1; }
            .scope-stat { border-left: 0; padding-left: 0; }
        }
    </style>
</head>
<body>

    <!-- Top Loading bar -->
    <div id="loading-indicator"></div>

    <!-- Sidebar Navigation -->
    <nav id="sidebar">
        <div class="brand-container">
            <div class="logo-box">
                <svg viewBox="0 0 24 24">
                    <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-2 10H7v-2h10v2z"/>
                </svg>
            </div>
            <div class="brand-text">
                <h1>Observatory</h1>
                <p>AI Engine & Token Telemetry</p>
            </div>
        </div>

        <ul class="nav-list">
            <li class="nav-item active" id="nav-overview" onclick="switchTab('overview')">
                <a>
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2v-4zM14 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2v-4z"/>
                    </svg>
                    <span>Overview</span>
                </a>
            </li>
            <li class="nav-item" id="nav-repositories" onclick="switchTab('repositories')">
                <a>
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
                    </svg>
                    <span>Repositories</span>
                </a>
            </li>
            <li class="nav-item" id="nav-sessions" onclick="switchTab('sessions')">
                <a>
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    <span>Session Explorer</span>
                </a>
            </li>
            <li class="nav-item" id="nav-models" onclick="switchTab('models')">
                <a>
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                    </svg>
                    <span>Model Analytics</span>
                </a>
            </li>
            <li class="nav-item" id="nav-tools" onclick="switchTab('tools')">
                <a>
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
                        <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                    </svg>
                    <span>Tool Analytics</span>
                </a>
            </li>
            <li class="nav-item" id="nav-time" onclick="switchTab('time')">
                <a>
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                    </svg>
                    <span>Time & Heatmaps</span>
                </a>
            </li>
            <li class="nav-item" id="nav-git" onclick="switchTab('git')">
                <a>
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path d="M8 7a3 3 0 100-6 3 3 0 000 6zM8 7h8a3 3 0 100-6 3 3 0 000 6zM8 7v7a3 3 0 006 0v-4"/>
                    </svg>
                    <span>Git Integration</span>
                </a>
            </li>
            <li class="nav-item" id="nav-export" onclick="switchTab('export')">
                <a>
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                    </svg>
                    <span>Export Center</span>
                </a>
            </li>
        </ul>

        <div class="sidebar-collapse-btn" onclick="toggleSidebar()" title="Toggle Sidebar [Ctrl+B]">
            <svg style="width: 20px; height: 20px;" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path d="M11 19l-7-7 7-7m8 14l-7-7 7-7"/>
            </svg>
        </div>
    </nav>

    <!-- App Content Wrapper -->
    <div id="app-content">
        <!-- Header -->
        <header id="header">
            <div class="header-left">
                <div class="breadcrumbs" id="breadcrumb-trail">
                    <span>Observatory</span> &gt; <span class="current">Overview</span>
                </div>
            </div>

            <!-- Global Search -->
            <div class="search-container">
                <svg class="search-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
                <input type="text" id="global-search-input" placeholder="Search sessions, repos, models..." oninput="handleGlobalSearch()" title="Focus Search [/]">
            </div>

            <div class="header-right">
                <div id="connection-status" class="live-status offline">Static Mode</div>
                <div class="kbd-shortcut" onclick="showKeyboardShortcutsModal()" title="Show keyboard shortcuts" style="cursor: pointer;">?</div>
            </div>
        </header>

        <!-- Main View container -->
        <main id="main-view">
            
            <!-- Global filters -->
            <section class="filter-bar">
                <div class="filter-group">
                    <span class="filter-label">Project:</span>
                    <select class="filter-select" id="filter-project" onchange="applyFilters()">
                        <option value="all">All Projects</option>
                    </select>
                </div>
                <div class="filter-group">
                    <span class="filter-label">Model:</span>
                    <select class="filter-select" id="filter-model" onchange="applyFilters()">
                        <option value="all">All Models</option>
                    </select>
                </div>
                <div class="filter-group">
                    <span class="filter-label">Tool:</span>
                    <select class="filter-select" id="filter-tool" onchange="applyFilters()">
                        <option value="all">All Tools</option>
                    </select>
                </div>
                <div class="filter-group">
                    <span class="filter-label">Provider:</span>
                    <select class="filter-select" id="filter-provider" onchange="applyFilters()">
                        <option value="all">All</option>
                        <option value="cloud">Cloud</option>
                        <option value="local">Local</option>
                    </select>
                </div>
                <div class="filter-group">
                    <span class="filter-label">Timeframe:</span>
                    <div class="date-btns">
                        <button class="date-btn active" id="date-all" onclick="setDateRange('all')">All</button>
                        <button class="date-btn" id="date-90d" onclick="setDateRange('90d')">90d</button>
                        <button class="date-btn" id="date-30d" onclick="setDateRange('30d')">30d</button>
                        <button class="date-btn" id="date-7d" onclick="setDateRange('7d')">7d</button>
                        <button class="date-btn" id="date-24h" onclick="setDateRange('24h')">24h</button>
                    </div>
                </div>
                <button class="clear-filters-btn" onclick="clearAllFilters()">
                    <svg style="width: 12px; height: 12px;" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                    </svg>
                    Clear Filters
                </button>
            </section>

            <!-- ================= VIEW: OVERVIEW ================= -->
            <div id="view-overview" class="tab-view active">
                <div class="data-scope-banner">
                    <div class="scope-mark">DATA SCOPE</div>
                    <div class="scope-copy">
                        <strong>Two lenses, one telemetry picture</strong>
                        <span>Provider totals are cumulative; detailed tables use locally observed request events.</span>
                    </div>
                    <div class="scope-stat"><small>PROVIDER REPORTED</small><b>__SCOPE_PROVIDER__</b></div>
                    <div class="scope-stat"><small>LOCAL EVENT LOG</small><b>__SCOPE_EVENTS__</b></div>
                    <div class="scope-stat scope-gap"><small>NOT IN EVENT LOG</small><b>__SCOPE_GAP__</b></div>
                    <div class="scope-hint" id="scope-gap-hint" style="__SCOPE_HINT_STYLE__">
                        Provider totals exceed the local event log. Run <code>tokstat sync</code> to pull
                        authoritative all-time usage and cost from Anthropic and OpenAI.
                    </div>
                </div>
                <div class="metrics-grid">
                    <!-- Stat cards -->
                    <div class="metric-card card-glow-orange">
                        <div class="metric-header">
                            <span>Total Tokens</span>
                            <svg style="width: 16px; height: 16px;" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                        </div>
                        <div class="metric-value" id="stat-total-tokens">0</div>
                        <div class="metric-footer">
                            <span>In/Out ratio: <span id="stat-io-ratio">0.0</span></span>
                        </div>
                    </div>
                    <div class="metric-card card-glow-purple">
                        <div class="metric-header">
                            <span>Regular Input</span>
                            <svg style="width: 16px; height: 16px;" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>
                        </div>
                        <div class="metric-value" id="stat-input-tokens">0</div>
                        <div class="metric-footer">
                            <span>Output: <span id="stat-output-tokens">0</span></span>
                        </div>
                    </div>
                    <div class="metric-card card-glow-emerald">
                        <div class="metric-header">
                            <span>Cached Reads</span>
                            <svg style="width: 16px; height: 16px;" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
                        </div>
                        <div class="metric-value" id="stat-cached-tokens">0</div>
                        <div class="metric-footer">
                            <span>Cache Hit %: <span id="stat-cache-hit-pct" class="trend-up">0%</span></span>
                        </div>
                    </div>
                    <div class="metric-card card-glow-cyan">
                        <div class="metric-header">
                            <span>Retail API Cost</span>
                            <svg style="width: 16px; height: 16px;" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                        </div>
                        <div class="metric-value" id="stat-cost">0</div>
                        <div class="metric-footer">
                            <span>Cache Savings: <span id="stat-savings" class="trend-up">$0.00</span></span>
                        </div>
                    </div>
                    <div class="metric-card card-glow-emerald" id="local-avoidance-card">
                        <div class="metric-header">
                            <span>Cloud Cost Avoidance</span>
                            <svg style="width: 16px; height: 16px;" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z"/></svg>
                        </div>
                        <div class="metric-value" id="stat-cloud-avoidance">$0.0000</div>
                        <div class="metric-footer">
                            <span>Local tokens: <span id="stat-local-tokens">0</span></span>
                        </div>
                    </div>
                </div>
                
                <div class="metrics-grid" style="margin-top: -0.5rem;">
                    <div class="metric-card">
                        <div class="metric-header"><span>Sessions</span></div>
                        <div class="metric-value" id="stat-sessions">0</div>
                        <div class="metric-footer"><span id="stat-avg-session-tokens">0 / sess</span></div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-header"><span>Requests</span></div>
                        <div class="metric-value" id="stat-requests">0</div>
                        <div class="metric-footer"><span id="stat-avg-request-tokens">0 / req</span></div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-header"><span>Active Repos</span></div>
                        <div class="metric-value" id="stat-active-repos">0</div>
                        <div class="metric-footer"><span>Models: <span id="stat-active-models">0</span></span></div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-header"><span>Active Tools</span></div>
                        <div class="metric-value" id="stat-active-tools">0</div>
                        <div class="metric-footer"><span>Avg context: <span id="stat-avg-context">0</span></span></div>
                    </div>
                </div>

                <!-- Charts row -->
                <div class="two-col-grid">
                    <div class="panel-card">
                        <div class="panel-header">
                            <div>
                                <h2 class="panel-title">Token Consumption Trend</h2>
                                <p class="panel-subtitle">Daily token usage break-up (Input, Output, Cache)</p>
                            </div>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="trendChartOverview"></canvas>
                        </div>
                    </div>

                    <div class="panel-card">
                        <div class="panel-header">
                            <div>
                                <h2 class="panel-title">Model Distribution</h2>
                                <p class="panel-subtitle">Total tokens by model variant</p>
                            </div>
                        </div>
                        <div class="chart-wrapper" style="display: flex; align-items: center; justify-content: center; min-height: 320px;">
                            <canvas id="modelChartOverview" style="max-height: 420px; min-height: 300px; width: 100%;"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Local vs Cloud row (shown only when local inference data exists) -->
                <div class="two-col-grid" id="local-inference-row" style="display: none;">
                    <div class="panel-card">
                        <div class="panel-header">
                            <div>
                                <h2 class="panel-title">Local vs Cloud Usage</h2>
                                <p class="panel-subtitle">Token split between on-premise inference and cloud APIs</p>
                            </div>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="localCloudChartOverview"></canvas>
                        </div>
                    </div>
                    <div class="panel-card">
                        <div class="panel-header">
                            <div>
                                <h2 class="panel-title">Local Models</h2>
                                <p class="panel-subtitle">Tokens consumed per local model</p>
                            </div>
                        </div>
                        <div class="table-wrapper">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Model</th>
                                        <th style="text-align: right;">Tokens</th>
                                        <th style="text-align: right;">Requests</th>
                                    </tr>
                                </thead>
                                <tbody id="local-models-table">
                                    <!-- Populated by JS -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- Split view: Active repos & Recent sessions -->
                <div class="two-col-grid">
                    <div class="panel-card">
                        <div class="panel-header">
                            <div>
                                <h2 class="panel-title">Active Repositories</h2>
                                <p class="panel-subtitle">Telemetry activity summarized by project repository</p>
                            </div>
                            <span class="pill clickable-row" onclick="switchTab('repositories')">View All</span>
                        </div>
                        <div class="table-wrapper">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Repository</th>
                                        <th style="text-align: right;">Tokens</th>
                                        <th style="text-align: right;">Sessions</th>
                                        <th style="text-align: right;">Cache Ratio</th>
                                        <th>Branch</th>
                                    </tr>
                                </thead>
                                <tbody id="overview-repos-table">
                                    <!-- Populated by JS -->
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div class="panel-card">
                        <div class="panel-header">
                            <div>
                                <h2 class="panel-title">Recent Sessions</h2>
                                <p class="panel-subtitle">Latest active developer coding sessions</p>
                            </div>
                            <span class="pill clickable-row" onclick="switchTab('sessions')">View All</span>
                        </div>
                        <div class="table-wrapper">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Session ID</th>
                                        <th style="text-align: right;">Tokens</th>
                                        <th>Duration</th>
                                        <th>Date</th>
                                    </tr>
                                </thead>
                                <tbody id="overview-sessions-table">
                                    <!-- Populated by JS -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ================= VIEW: REPOSITORIES ================= -->
            <div id="view-repositories" class="tab-view">
                
                <!-- Main Repos list sub-view -->
                <div id="subview-repos-list" class="detail-view-container">
                    <div class="panel-card">
                        <div class="panel-header">
                            <div>
                                <h2 class="panel-title">Repository Telemetry Analytics</h2>
                                <p class="panel-subtitle">Locally observed request events grouped by workspace folder</p>
                            </div>
                        </div>
                        <div class="table-wrapper">
                            <table id="repos-table">
                                <thead>
                                    <tr>
                                        <th onclick="sortReposTable('repository')">Repository</th>
                                        <th onclick="sortReposTable('tokens')" style="text-align: right;">Total Tokens</th>
                                        <th onclick="sortReposTable('input')" style="text-align: right;">Input</th>
                                        <th onclick="sortReposTable('output')" style="text-align: right;">Output</th>
                                        <th onclick="sortReposTable('cache_read')" style="text-align: right;">Cache Read</th>
                                        <th onclick="sortReposTable('cache_ratio')" style="text-align: right;">Cache Ratio</th>
                                        <th onclick="sortReposTable('requests')" style="text-align: right;">Requests</th>
                                        <th onclick="sortReposTable('sessions')" style="text-align: right;">Sessions</th>
                                        <th onclick="sortReposTable('commits_count')" style="text-align: right;">Git Commits</th>
                                        <th>Latest Active</th>
                                    </tr>
                                </thead>
                                <tbody id="repos-table-body">
                                    <!-- Populated by JS -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- Repo Drilldown sub-view -->
                <div id="subview-repo-drilldown" class="detail-view-container" style="display: none;">
                    <div class="detail-header-row">
                        <div>
                            <h2 class="panel-title" id="repo-drilldown-title">Repo: depthapi</h2>
                            <p class="panel-subtitle" id="repo-drilldown-path">Local Path: /home/sanjeev/Downloads/depthapi</p>
                        </div>
                        <button class="back-btn" onclick="exitRepoDrilldown()">
                            &larr; Back to Repositories
                        </button>
                    </div>

                    <!-- Grid metrics for repo -->
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-header"><span>Total Tokens</span></div>
                            <div class="metric-value" id="repo-drill-total-tokens">0</div>
                            <div class="metric-footer"><span>Input: <span id="repo-drill-input">0</span></span></div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-header"><span>Output Tokens</span></div>
                            <div class="metric-value text-orange" id="repo-drill-output">0</div>
                            <div class="metric-footer"><span>Ratio Out/In: <span id="repo-drill-io-ratio">0.0</span></span></div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-header"><span>Cache Hit Ratio</span></div>
                            <div class="metric-value text-emerald" id="repo-drill-cache-ratio">0%</div>
                            <div class="metric-footer"><span>Cached: <span id="repo-drill-cache-tokens">0</span></span></div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-header"><span>Git Metadata</span></div>
                            <div class="metric-value tiny" id="repo-drill-git-branch">main</div>
                            <div class="metric-footer"><span>Commits count: <span id="repo-drill-commits-count">0</span></span></div>
                        </div>
                    </div>

                    <div class="two-col-grid">
                        <div class="panel-card">
                            <div class="panel-header">
                                <h2 class="panel-title">Repository Consumption Trend</h2>
                            </div>
                            <div class="chart-wrapper">
                                <canvas id="repoDrillChart"></canvas>
                            </div>
                        </div>
                        <div class="panel-card">
                            <div class="panel-header">
                                <h2 class="panel-title">Models & Tools</h2>
                            </div>
                            <div style="display: flex; flex-direction: column; gap: 1.5rem;">
                                <div>
                                    <h3 style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.5rem; text-transform: uppercase;">Top Models</h3>
                                    <div id="repo-drill-models-list" style="display: flex; flex-direction: column; gap: 0.4rem;"></div>
                                </div>
                                <div>
                                    <h3 style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.5rem; text-transform: uppercase;">Top Coding Tools</h3>
                                    <div id="repo-drill-tools-list" style="display: flex; flex-direction: column; gap: 0.4rem;"></div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Git Commits Timeline in Repo -->
                    <div class="panel-card" id="repo-drill-commits-panel">
                        <div class="panel-header">
                            <div>
                                <h2 class="panel-title">Git Commit Telemetry Correlation</h2>
                                <p class="panel-subtitle">Tokens and coding duration logged prior to commits</p>
                            </div>
                        </div>
                        <div class="table-wrapper">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Commit</th>
                                        <th>Date</th>
                                        <th>Message</th>
                                        <th style="text-align: right;">Tokens Prior</th>
                                        <th style="text-align: right;">Requests</th>
                                        <th style="text-align: right;">Coding Time</th>
                                        <th style="text-align: right;">Estimated Cost</th>
                                    </tr>
                                </thead>
                                <tbody id="repo-drill-commits-body">
                                    <!-- Populated by JS -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ================= VIEW: SESSIONS ================= -->
            <div id="view-sessions" class="tab-view">
                
                <!-- Main Sessions explorer -->
                <div id="subview-sessions-list" class="detail-view-container">
                    <div class="panel-card">
                        <div class="panel-header">
                            <div>
                                <h2 class="panel-title">Session Explorer</h2>
                                <p class="panel-subtitle">Locally observed request events grouped into sessions</p>
                            </div>
                        </div>
                        <div class="table-wrapper">
                            <table id="sessions-table">
                                <thead>
                                    <tr>
                                        <th onclick="sortSessionsTable('session_id')">Session ID</th>
                                        <th onclick="sortSessionsTable('project')">Repository</th>
                                        <th onclick="sortSessionsTable('start')">Start Time</th>
                                        <th onclick="sortSessionsTable('duration')" style="text-align: right;">Duration</th>
                                        <th onclick="sortSessionsTable('requests')" style="text-align: right;">Turns</th>
                                        <th onclick="sortSessionsTable('total_tokens')" style="text-align: right;">Total Tokens</th>
                                        <th onclick="sortSessionsTable('cache_read')" style="text-align: right;">Cached</th>
                                        <th onclick="sortSessionsTable('estimated_cost')" style="text-align: right;">API Cost</th>
                                        <th onclick="sortSessionsTable('estimated_savings')" style="text-align: right;">Savings</th>
                                    </tr>
                                </thead>
                                <tbody id="sessions-table-body">
                                    <!-- Populated by JS -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- Session Drilldown sub-view -->
                <div id="subview-session-drilldown" class="detail-view-container" style="display: none;">
                    <div class="detail-header-row">
                        <div>
                            <h2 class="panel-title" id="session-drilldown-title">Session: a1b2c3d4</h2>
                            <p class="panel-subtitle" id="session-drilldown-meta">Repo: depthapi | Timeframe: 2026-07-25 15:30 to 15:45</p>
                        </div>
                        <button class="back-btn" onclick="exitSessionDrilldown()">
                            &larr; Back to Sessions
                        </button>
                    </div>

                    <!-- Metrics -->
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-header"><span>Session Tokens</span></div>
                            <div class="metric-value" id="session-drill-tokens">0</div>
                            <div class="metric-footer"><span>In / Out: <span id="session-drill-in-out">0/0</span></span></div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-header"><span>Avg Context Size</span></div>
                            <div class="metric-value" id="session-drill-avg-context">0</div>
                            <div class="metric-footer"><span>Avg Output: <span id="session-drill-avg-output">0</span></span></div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-header"><span>API Retail Cost</span></div>
                            <div class="metric-value" id="session-drill-cost">$0.00</div>
                            <div class="metric-footer"><span>Savings: <span id="session-drill-savings" class="text-emerald">$0.00</span></span></div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-header"><span>Duration & Turns</span></div>
                            <div class="metric-value text-cyan" id="session-drill-duration">0m</div>
                            <div class="metric-footer"><span>Total turns: <span id="session-drill-turns">0</span></span></div>
                        </div>
                    </div>

                    <div class="two-col-grid">
                        <!-- Model distribution -->
                        <div class="panel-card">
                            <div class="panel-header">
                                <h2 class="panel-title">Model Mix in Session</h2>
                            </div>
                            <div id="session-drill-model-mix" style="display: flex; flex-direction: column; gap: 0.5rem;">
                                <!-- Populated by JS -->
                            </div>
                        </div>

                        <!-- Session timeline flow -->
                        <div class="panel-card">
                            <div class="panel-header">
                                <h2 class="panel-title">Request Execution Timeline</h2>
                            </div>
                            <div class="timeline-flow" id="session-drill-timeline">
                                <!-- Populated by JS -->
                            </div>
                        </div>
                    </div>
                </div>

            </div>

            <!-- ================= VIEW: MODELS ================= -->
            <div id="view-models" class="tab-view">
                <!-- Comparative view -->
                <div class="panel-card">
                    <div class="panel-header">
                        <div>
                            <h2 class="panel-title">Model Performance & Usage Comparison</h2>
                            <p class="panel-subtitle">Model analytics from the locally observed event log</p>
                        </div>
                    </div>
                    <div class="three-col-grid">
                        <div class="chart-wrapper" style="height: 380px;">
                            <canvas id="modelCompareTokensChart"></canvas>
                        </div>
                        <div class="chart-wrapper" style="height: 380px;">
                            <canvas id="modelCompareRequestsChart"></canvas>
                        </div>
                        <div class="chart-wrapper" style="height: 380px;">
                            <canvas id="modelCompareCacheChart"></canvas>
                        </div>
                    </div>
                </div>

                <div class="panel-card">
                    <div class="panel-header">
                        <h2 class="panel-title">Dedicated Model Diagnostics</h2>
                    </div>
                    <div class="table-wrapper">
                        <table>
                            <thead>
                                <tr>
                                    <th>Model Name</th>
                                    <th style="text-align: right;">Total Tokens</th>
                                    <th style="text-align: right;">Requests</th>
                                    <th style="text-align: right;">Avg Context (In)</th>
                                    <th style="text-align: right;">Avg Completion (Out)</th>
                                    <th style="text-align: right;">Cache Hit %</th>
                                    <th style="text-align: right;">API Cost</th>
                                    <th style="text-align: right;">Savings</th>
                                    <th>Active Repos</th>
                                </tr>
                            </thead>
                            <tbody id="models-table-body">
                                <!-- Populated by JS -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- ================= VIEW: TOOLS ================= -->
            <div id="view-tools" class="tab-view">
                <div class="panel-card">
                    <div class="panel-header">
                        <div>
                            <h2 class="panel-title">Coding Tool & Agent Telemetry</h2>
                            <p class="panel-subtitle">Tool analytics from the locally observed event log</p>
                        </div>
                    </div>
                    
                    <div class="three-col-grid" id="tools-grid-cards">
                        <!-- Discovered Tool Cards populating here -->
                    </div>
                </div>

                <div class="panel-card">
                    <div class="panel-header">
                        <h2 class="panel-title">Detailed Tool Usage Breakdown</h2>
                    </div>
                    <div class="table-wrapper">
                        <table>
                            <thead>
                                <tr>
                                    <th>Coding Agent/Tool</th>
                                    <th style="text-align: right;">Total Tokens</th>
                                    <th style="text-align: right;">Requests</th>
                                    <th style="text-align: right;">Cache Hit Rate</th>
                                    <th>Used in Repositories</th>
                                    <th>Supported Models</th>
                                    <th style="text-align: right;">Avg Session Length</th>
                                </tr>
                            </thead>
                            <tbody id="tools-table-body">
                                <!-- Populated by JS -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- ================= VIEW: TIME ================= -->
            <div id="view-time" class="tab-view">
                
                <!-- Calendar heatmap -->
                <div class="panel-card">
                    <div class="panel-header">
                        <div>
                            <h2 class="panel-title">Daily Activity Heatmap (Last 12 Months)</h2>
                            <p class="panel-subtitle">Standard calendar view of coding activity density (measured in tokens)</p>
                        </div>
                    </div>
                    <div class="heatmap-container">
                        <div class="heatmap-grid-days" id="daily-heatmap-grid">
                            <!-- Populated by JS -->
                        </div>
                        <div class="heatmap-legend">
                            <span>Less</span>
                            <div class="legend-box" style="background-color: #161b22;"></div>
                            <div class="legend-box" style="background-color: #0e4429;"></div>
                            <div class="legend-box" style="background-color: #006d32;"></div>
                            <div class="legend-box" style="background-color: #26a641;"></div>
                            <div class="legend-box" style="background-color: #39d353;"></div>
                            <span>More</span>
                        </div>
                    </div>
                </div>

                <div class="two-col-grid">
                    <!-- Weekday / Hourly heatmap -->
                    <div class="panel-card">
                        <div class="panel-header">
                            <div>
                                <h2 class="panel-title">Weekly Coding Heatmap</h2>
                                <p class="panel-subtitle">Busiest hours of coding by day of the week</p>
                            </div>
                        </div>
                        <div class="table-wrapper">
                            <table style="font-size: 0.75rem; text-align: center;">
                                <thead>
                                    <tr>
                                        <th>Day</th>
                                        <th>00h</th><th>02h</th><th>04h</th><th>06h</th><th>08h</th><th>10h</th><th>12h</th><th>14h</th><th>16h</th><th>18h</th><th>20h</th><th>22h</th>
                                    </tr>
                                </thead>
                                <tbody id="weekly-hour-heatmap-body">
                                    <!-- Populated by JS -->
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Busiest times charts -->
                    <div class="panel-card">
                        <div class="panel-header">
                            <div>
                                <h2 class="panel-title">Productivity & Timing Metrics</h2>
                                <p class="panel-subtitle">Telemetry-driven observations of developer schedules</p>
                            </div>
                        </div>
                        
                        <div style="display: flex; flex-direction: column; gap: 1.25rem;">
                            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;">
                                <span style="color: var(--text-secondary); font-size: 0.85rem;">Busiest Coding Day:</span>
                                <span style="font-weight: 600;" id="prod-busiest-day">N/A</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;">
                                <span style="color: var(--text-secondary); font-size: 0.85rem;">Busiest Hour:</span>
                                <span style="font-weight: 600;" id="prod-busiest-hour">N/A</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;">
                                <span style="color: var(--text-secondary); font-size: 0.85rem;">Longest Coding Sprint:</span>
                                <span style="font-weight: 600;" id="prod-longest-sprint">0 hours</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;">
                                <span style="color: var(--text-secondary); font-size: 0.85rem;">Tokens per Session (Avg):</span>
                                <span style="font-weight: 600;" id="prod-tokens-per-session">0</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;">
                                <span style="color: var(--text-secondary); font-size: 0.85rem;">Average Session Duration:</span>
                                <span style="font-weight: 600;" id="prod-avg-session-length">0 mins</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;">
                                <span style="color: var(--text-secondary); font-size: 0.85rem;">Context Window Utilisation:</span>
                                <span style="font-weight: 600; color: var(--accent-orange);" id="prod-context-util">0%</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ================= VIEW: GIT ================= -->
            <div id="view-git" class="tab-view">
                <div class="panel-card">
                    <div class="panel-header">
                        <div>
                            <h2 class="panel-title">Git Commit Telemetry Correlation</h2>
                            <p class="panel-subtitle">Correlates local project git repository history with TokStat telemetry data</p>
                        </div>
                    </div>
                    
                    <div class="table-wrapper" id="git-correlation-table-wrapper">
                        <table>
                            <thead>
                                <tr>
                                    <th>Repo</th>
                                    <th>Commit SHA</th>
                                    <th>Branch</th>
                                    <th>Timestamp</th>
                                    <th>Commit Message</th>
                                    <th style="text-align: right;">Requests Prior</th>
                                    <th style="text-align: right;">Tokens Logged</th>
                                    <th style="text-align: right;">Coding Time</th>
                                    <th style="text-align: right;">Est Cost</th>
                                </tr>
                            </thead>
                            <tbody id="git-commits-table-body">
                                <!-- Populated by JS -->
                            </tbody>
                        </table>
                    </div>
                    
                    <!-- Fallback display if Git is disabled -->
                    <div id="git-disabled-fallback" class="empty-state" style="display: none;">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                        </svg>
                        <h3>Git Telemetry Correlation Unavailable</h3>
                        <p>No active git metadata repositories were detected locally or linked with usage telemetry.</p>
                    </div>
                </div>
            </div>

            <!-- ================= VIEW: EXPORT ================= -->
            <div id="view-export" class="tab-view">
                <div class="panel-card">
                    <div class="panel-header">
                        <div>
                            <h2 class="panel-title">Observatory Exporter Hub</h2>
                            <p class="panel-subtitle">Export telemetry observations in standard formats for offline analysis and reporting</p>
                        </div>
                    </div>

                    <div class="export-grid">
                        <!-- JSON -->
                        <div class="export-card">
                            <div class="export-icon">
                                <span style="font-weight: 700; font-size: 1.25rem;">JSON</span>
                            </div>
                            <div>
                                <h3 style="font-size: 0.95rem; margin-bottom: 0.25rem;">Full Raw Payload</h3>
                                <p style="font-size: 0.75rem; color: var(--text-secondary);">Export all aggregated and correlated analytics in a single JSON structure</p>
                            </div>
                            <button class="export-btn" onclick="downloadJSONExport()">Download JSON</button>
                        </div>

                        <!-- CSV -->
                        <div class="export-card">
                            <div class="export-icon">
                                <span style="font-weight: 700; font-size: 1.25rem;">CSV</span>
                            </div>
                            <div>
                                <h3 style="font-size: 0.95rem; margin-bottom: 0.25rem;">Repositories & Sessions</h3>
                                <p style="font-size: 0.75rem; color: var(--text-secondary);">Download tabular data for easy integration in Excel or Pandas dataframes</p>
                            </div>
                            <div style="display: flex; gap: 0.5rem; width: 100%;">
                                <button class="export-btn" onclick="downloadCSVExport('repos')">Repos</button>
                                <button class="export-btn" onclick="downloadCSVExport('sessions')">Sessions</button>
                            </div>
                        </div>

                        <!-- Markdown -->
                        <div class="export-card">
                            <div class="export-icon">
                                <span style="font-weight: 700; font-size: 1.25rem;">MD</span>
                            </div>
                            <div>
                                <h3 style="font-size: 0.95rem; margin-bottom: 0.25rem;">Executive Summary</h3>
                                <p style="font-size: 0.75rem; color: var(--text-secondary);">A beautiful, human-readable markdown status report detailing overall stats</p>
                            </div>
                            <button class="export-btn" onclick="downloadMarkdownExport()">Download MD</button>
                        </div>

                        <!-- PDF -->
                        <div class="export-card">
                            <div class="export-icon">
                                <span style="font-weight: 700; font-size: 1.25rem;">PDF</span>
                            </div>
                            <div>
                                <h3 style="font-size: 0.95rem; margin-bottom: 0.25rem;">Printable PDF Report</h3>
                                <p style="font-size: 0.75rem; color: var(--text-secondary);">Generates a standard PDF audit file. Works directly using browser print templates</p>
                            </div>
                            <button class="export-btn" onclick="triggerPDFPrint()">Print Report</button>
                        </div>
                    </div>
                </div>
            </div>

        </main>
    </div>

    <!-- Keyboard Shortcuts Modal -->
    <div class="modal-overlay" id="shortcuts-modal" onclick="closeKeyboardShortcutsModal()">
        <div class="modal-box" onclick="event.stopPropagation()">
            <div class="modal-title">
                <span>Keyboard Shortcuts</span>
                <button class="modal-close" onclick="closeKeyboardShortcutsModal()">&times;</button>
            </div>
            <div style="display: flex; flex-direction: column; gap: 0.75rem; margin-top: 0.5rem; font-size: 0.85rem;">
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: var(--text-secondary);">Focus Search Bar</span>
                    <span class="kbd-shortcut">/</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: var(--text-secondary);">Toggle Sidebar collapse</span>
                    <span class="kbd-shortcut">Ctrl + B</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: var(--text-secondary);">Clear All Active Filters</span>
                    <span class="kbd-shortcut">Esc</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: var(--text-secondary);">Overview Page</span>
                    <span class="kbd-shortcut">1</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: var(--text-secondary);">Repository Analytics</span>
                    <span class="kbd-shortcut">2</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: var(--text-secondary);">Session Explorer</span>
                    <span class="kbd-shortcut">3</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: var(--text-secondary);">Model Analytics</span>
                    <span class="kbd-shortcut">4</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: var(--text-secondary);">Tool Analytics</span>
                    <span class="kbd-shortcut">5</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: var(--text-secondary);">Time Heatmaps</span>
                    <span class="kbd-shortcut">6</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: var(--text-secondary);">Git Correlation</span>
                    <span class="kbd-shortcut">7</span>
                </div>
            </div>
        </div>
    </div>

    <!-- Data Injection -->
    <script>
        const TELEMETRY_DATA = __TELEMETRY_DATA_JSON__;
        const watchModeActive = __WATCH_MODE_ACTIVE__;

        // State trackers
        let currentTab = 'overview';
        let repoDrillId = null;
        let sessionDrillId = null;
        
        // Sorting states
        let repoSortCol = 'tokens';
        let repoSortDesc = true;
        let sessSortCol = 'start';
        let sessSortDesc = true;

        // Current active filters
        let activeFilters = {
            project: 'all',
            model: 'all',
            tool: 'all',
            provider: 'all',
            timeframe: 'all'
        };

        // Charts handles
        let charts = {
            trendOverview: null,
            modelOverview: null,
            repoDrill: null,
            modelCompTokens: null,
            modelCompRequests: null,
            modelCompCache: null,
            localCloud: null
        };

        // Helper to format number
        function formatNumber(num) {
            if (num === null || num === undefined) return 'N/A';
            if (num >= 1000000000) return (num / 1000000000).toFixed(2) + 'B';
            if (num >= 1000000) return (num / 1000000).toFixed(2) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
            return num.toLocaleString();
        }

        function formatDuration(sec) {
            if (!sec) return '0s';
            if (sec < 60) return sec + 's';
            const mins = Math.floor(sec / 60);
            if (mins < 60) return mins + 'm';
            const hrs = Math.floor(mins / 60);
            const remainingMins = mins % 60;
            return hrs + 'h ' + remainingMins + 'm';
        }

        function escapeHtml(value) {
            return String(value ?? '').replace(/[&<>'"]/g, char => ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
            })[char]);
        }

        // Live Server Polling for updates
        if (watchModeActive) {
            const statusIndicator = document.getElementById('connection-status');
            statusIndicator.className = "live-status";
            statusIndicator.innerText = "Live Sync Mode";
            
            setInterval(() => {
                fetch('http://localhost:__SERVER_PORT__/data')
                    .then(res => res.json())
                    .then(newData => {
                        console.log("Telemetry sync updated.");
                        // Refresh data object
                        Object.assign(TELEMETRY_DATA, newData);
                        // Repopulate UI with filters preserved
                        renderUI();
                    })
                    .catch(err => {
                        console.warn("Live server not reachable:", err);
                        statusIndicator.className = "live-status offline";
                        statusIndicator.innerText = "Offline Mode";
                    });
            }, 3000);
        }

        // Initialize App on load
        window.addEventListener('DOMContentLoaded', () => {
            // Restore persistent filters/tabs if they exist
            const savedFilters = localStorage.getItem('obs_filters');
            if (savedFilters) {
                activeFilters = JSON.parse(savedFilters);
            }
            const savedTab = localStorage.getItem('obs_tab');
            if (savedTab) {
                currentTab = savedTab;
            }
            if (!['overview', 'repositories', 'sessions', 'models', 'tools', 'time', 'git', 'export'].includes(currentTab)) {
                currentTab = 'overview';
            }
            
            // Populate select lists
            populateFilterOptions();

            // A previous dashboard version may have persisted filters that no
            // longer exist. Invalid values make every client-side query return
            // zero rows, so normalize state against the current payload.
            const validProjects = new Set(TELEMETRY_DATA.repositories.map(r => r.repository));
            const validModels = new Set(TELEMETRY_DATA.models.map(m => m.model_name));
            const validTools = new Set(TELEMETRY_DATA.tools.map(t => t.tool_name));
            if (activeFilters.project !== 'all' && !validProjects.has(activeFilters.project)) activeFilters.project = 'all';
            if (activeFilters.model !== 'all' && !validModels.has(activeFilters.model)) activeFilters.model = 'all';
            if (activeFilters.tool !== 'all' && !validTools.has(activeFilters.tool)) activeFilters.tool = 'all';
            if (!['all', 'cloud', 'local'].includes(activeFilters.provider)) activeFilters.provider = 'all';
            if (!['all', '24h', '7d', '30d', '90d'].includes(activeFilters.timeframe)) activeFilters.timeframe = 'all';
            localStorage.setItem('obs_filters', JSON.stringify(activeFilters));
            
            // Sync filter elements value
            document.getElementById('filter-project').value = activeFilters.project;
            document.getElementById('filter-model').value = activeFilters.model;
            document.getElementById('filter-tool').value = activeFilters.tool;
            document.getElementById('filter-provider').value = activeFilters.provider;
            setDateBtnActive(activeFilters.timeframe);

            renderUI();
            // Some browsers restore the page before deferred DOM state settles;
            // render once more on the next task so cards/charts use live data.
            setTimeout(renderUI, 0);
            
            // Register Keyboard events
            setupKeyboardShortcuts();
        });

        function populateFilterOptions() {
            const projSelect = document.getElementById('filter-project');
            const modelSelect = document.getElementById('filter-model');
            const toolSelect = document.getElementById('filter-tool');
            
            // Clear except first
            projSelect.innerHTML = '<option value="all">All Projects</option>';
            modelSelect.innerHTML = '<option value="all">All Models</option>';
            toolSelect.innerHTML = '<option value="all">All Tools</option>';
            
            // Populate Projects
            const projects = [...new Set(TELEMETRY_DATA.repositories.map(r => r.repository))].sort();
            projects.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p;
                opt.innerText = p;
                projSelect.appendChild(opt);
            });

            // Populate Models
            const models = [...new Set(TELEMETRY_DATA.models.map(m => m.model_name))].sort();
            models.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.innerText = m;
                modelSelect.appendChild(opt);
            });

            // Populate Tools
            const tools = TELEMETRY_DATA.tools;
            tools.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.tool_name;
                opt.innerText = t.display_name;
                toolSelect.appendChild(opt);
            });
        }

        function toggleSidebar() {
            document.body.classList.toggle('sidebar-collapsed');
        }

        function showKeyboardShortcutsModal() {
            document.getElementById('shortcuts-modal').classList.add('active');
        }

        function closeKeyboardShortcutsModal() {
            document.getElementById('shortcuts-modal').classList.remove('active');
        }

        function setupKeyboardShortcuts() {
            window.addEventListener('keydown', (e) => {
                // Focus search bar
                if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
                    e.preventDefault();
                    document.getElementById('global-search-input').focus();
                }
                // Esc to clear filter / close modal
                if (e.key === 'Escape') {
                    closeKeyboardShortcutsModal();
                    if (document.getElementById('global-search-input') === document.activeElement) {
                        document.getElementById('global-search-input').blur();
                    } else {
                        clearAllFilters();
                    }
                }
                // Collapse sidebar Ctrl + B
                if (e.ctrlKey && e.key.toLowerCase() === 'b') {
                    e.preventDefault();
                    toggleSidebar();
                }
                // Switch tabs with numbers 1 to 7
                if (!e.ctrlKey && !e.altKey && !e.metaKey && document.activeElement.tagName !== 'INPUT') {
                    const numKeys = ['1', '2', '3', '4', '5', '6', '7', '8'];
                    const tabs = ['overview', 'repositories', 'sessions', 'models', 'tools', 'time', 'git', 'export'];
                    const idx = numKeys.indexOf(e.key);
                    if (idx !== -1) {
                        switchTab(tabs[idx]);
                    }
                }
            });
        }

        function switchTab(tabId, { preserveDrilldown = false } = {}) {
            currentTab = tabId;
            localStorage.setItem('obs_tab', tabId);
            
            // Update sidebar active state
            document.querySelectorAll('.nav-item').forEach(item => {
                item.classList.toggle('active', item.id === 'nav-' + tabId);
            });

            // Update main view content panels
            document.querySelectorAll('.tab-view').forEach(view => {
                if (view.id === 'view-' + tabId) {
                    view.classList.add('active');
                } else {
                    view.classList.remove('active');
                }
            });

            // Top-level navigation exits drilldowns; drilldown navigation preserves its target.
            if (!preserveDrilldown) {
                repoDrillId = null;
                sessionDrillId = null;
                document.getElementById('subview-repos-list').style.display = 'block';
                document.getElementById('subview-repo-drilldown').style.display = 'none';
                document.getElementById('subview-sessions-list').style.display = 'block';
                document.getElementById('subview-session-drilldown').style.display = 'none';
            }

            // Update breadcrumb
            updateBreadcrumb();
            
            // Loading flash
            showLoadingIndicator();

            renderUI();
        }

        function showLoadingIndicator() {
            const ind = document.getElementById('loading-indicator');
            ind.style.display = 'block';
            ind.style.width = '30%';
            setTimeout(() => {
                ind.style.width = '70%';
                setTimeout(() => {
                    ind.style.width = '100%';
                    setTimeout(() => {
                        ind.style.display = 'none';
                        ind.style.width = '0';
                    }, 150);
                }, 100);
            }, 50);
        }

        function updateBreadcrumb() {
            const breadcrumbTrail = document.getElementById('breadcrumb-trail');
            let text = `<span>Observatory</span> &gt; <span class="current">${currentTab.charAt(0).toUpperCase() + currentTab.slice(1)}</span>`;
            if (repoDrillId) {
                text = `<span style="cursor:pointer;" onclick="exitRepoDrilldown()">Observatory &gt; Repositories</span> &gt; <span class="current">${escapeHtml(repoDrillId)}</span>`;
            } else if (sessionDrillId) {
                text = `<span style="cursor:pointer;" onclick="exitSessionDrilldown()">Observatory &gt; Sessions</span> &gt; <span class="current">Session: ${escapeHtml(sessionDrillId.slice(0, 8))}</span>`;
            }
            breadcrumbTrail.innerHTML = text;
        }

        // Filters configuration
        function applyFilters() {
            activeFilters.project = document.getElementById('filter-project').value;
            activeFilters.model = document.getElementById('filter-model').value;
            activeFilters.tool = document.getElementById('filter-tool').value;
            
            localStorage.setItem('obs_filters', JSON.stringify(activeFilters));
            renderUI();
        }

        function highlightOrFilterModel(modelName) {
            if (!modelName) return;
            if (activeFilters.model === modelName) {
                activeFilters.model = 'all';
            } else {
                activeFilters.model = modelName;
            }
            const modelSelect = document.getElementById('filter-model');
            if (modelSelect) modelSelect.value = activeFilters.model;
            localStorage.setItem('obs_filters', JSON.stringify(activeFilters));
            renderUI();
        }

        function setDateRange(range) {
            activeFilters.timeframe = range;
            setDateBtnActive(range);
            localStorage.setItem('obs_filters', JSON.stringify(activeFilters));
            renderUI();
        }

        function setDateBtnActive(range) {
            document.querySelectorAll('.date-btn').forEach(btn => {
                if (btn.id === 'date-' + range) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        }

        function clearAllFilters() {
            activeFilters = {
                project: 'all',
                model: 'all',
                tool: 'all',
                timeframe: 'all'
            };
            document.getElementById('filter-project').value = 'all';
            document.getElementById('filter-model').value = 'all';
            document.getElementById('filter-tool').value = 'all';
            document.getElementById('global-search-input').value = '';
            setDateBtnActive('all');
            
            localStorage.setItem('obs_filters', JSON.stringify(activeFilters));
            renderUI();
        }

        // Global search filter logic
        function handleGlobalSearch() {
            renderUI();
        }

        // Check if event timestamp matches date range
        function matchesTimeframe(occurredAt) {
            if (activeFilters.timeframe === 'all') return true;
            
            const evDate = new Date(occurredAt);
            const now = new Date();
            
            if (activeFilters.timeframe === '24h') {
                return (now - evDate) <= (24 * 3600 * 1000);
            } else if (activeFilters.timeframe === '7d') {
                return (now - evDate) <= (7 * 24 * 3600 * 1000);
            } else if (activeFilters.timeframe === '30d') {
                return (now - evDate) <= (30 * 24 * 3600 * 1000);
            } else if (activeFilters.timeframe === '90d') {
                return (now - evDate) <= (90 * 24 * 3600 * 1000);
            }
            return true;
        }

        // Master UI Filter function. Returns array of matched telemetry raw events.
        function getFilteredRawEvents() {
            // Note: Since all telemetry is loaded in client memory, we filter events
            // matching the active sidebar project, model, tool and timeframe filters.
            const searchVal = document.getElementById('global-search-input') ? document.getElementById('global-search-input').value.toLowerCase().trim() : '';
            
            const sourceEvents = TELEMETRY_DATA.events || TELEMETRY_DATA.sessions.flatMap(s => s.timeline.map(turn => ({
                ...turn, project: s.project, session_id: s.session_id,
                tool: turn.tool || turn.tool_name || 'Unknown'
            })));
            return sourceEvents.filter(ev => {
                const proj = ev.project || ev.repository || '';
                const mdl = ev.model || ev.model_name || '';
                const tool = ev.tool || ev.tool_name || 'Unknown';

                // Project filter
                if (activeFilters.project !== 'all' && proj !== activeFilters.project) return false;
                // Model filter
                if (activeFilters.model !== 'all' && mdl !== activeFilters.model) return false;
                // Tool filter
                if (activeFilters.tool !== 'all' && tool !== activeFilters.tool) return false;
                // Provider filter (local vs cloud)
                if (activeFilters.provider === 'local' && ev.provider !== 'local') return false;
                if (activeFilters.provider === 'cloud' && ev.provider === 'local') return false;
                // Timeframe filter
                if (!matchesTimeframe(ev.occurred_at)) return false;
                
                // Search term
                if (searchVal) {
                    const matchesSearch = 
                        (proj && proj.toLowerCase().includes(searchVal)) ||
                        (ev.session_id && ev.session_id.toLowerCase().includes(searchVal)) ||
                        (mdl && mdl.toLowerCase().includes(searchVal)) ||
                        (tool && tool.toLowerCase().includes(searchVal)) ||
                        (ev.occurred_at && ev.occurred_at.includes(searchVal));
                    if (!matchesSearch) return false;
                }
                
                return true;
            });
        }

        // UI rendering router
        function renderUI() {
            if (currentTab === 'overview') {
                renderOverview();
            } else if (currentTab === 'repositories') {
                if (repoDrillId) {
                    renderRepoDrilldown(repoDrillId);
                } else {
                    renderRepositoriesList();
                }
            } else if (currentTab === 'sessions') {
                if (sessionDrillId) {
                    renderSessionDrilldown(sessionDrillId);
                } else {
                    renderSessionsList();
                }
            } else if (currentTab === 'models') {
                renderModels();
            } else if (currentTab === 'tools') {
                renderTools();
            } else if (currentTab === 'time') {
                renderTimeAnalytics();
            } else if (currentTab === 'git') {
                renderGitIntegration();
            } else if (currentTab === 'export') {
                // Export is a static panel; keep navigation state functional.
                document.getElementById('view-export').classList.add('active');
            }
        }

        // ================= OVERVIEW RENDERING =================
        function renderOverview() {
            let filteredEvents = getFilteredRawEvents();
            // Never show an empty dashboard when no filters are active. This
            // also protects against browser autofill/localStorage races.
            if (!filteredEvents.length && activeFilters.project === 'all' && activeFilters.model === 'all' && activeFilters.tool === 'all' && activeFilters.timeframe === 'all') {
                filteredEvents = TELEMETRY_DATA.events || [];
            }
            
            // Recompute stats for current active filters
            let totalTokens = 0;
            let totalInput = 0;
            let totalOutput = 0;
            let cachedTokens = 0;
            let cost = 0.0;
            let savings = 0.0;
            let uniqueSessions = new Set();
            let uniqueRepos = new Set();
            let uniqueModels = new Set();
            let uniqueTools = new Set();

            // Daily chart aggregation
            const dailyData = {};
            const modelData = {};

            filteredEvents.forEach(ev => {
                totalTokens += ev.total;
                totalInput += ev.input;
                totalOutput += ev.output;
                cachedTokens += ev.cache_read;
                
                // Estimate cost using utils mappings client-side
                cost += ev.cost;
                // Savings (server-side per-model estimate, consistent with exports)
                savings += ev.savings || 0;
                
                uniqueSessions.add(ev.session_id);
                uniqueRepos.add(ev.project);
                uniqueModels.add(ev.model);
                
                // Group daily
                const day = ev.occurred_at.slice(0, 10);
                if (!dailyData[day]) dailyData[day] = { input: 0, output: 0, cache_read: 0 };
                dailyData[day].input += ev.input;
                dailyData[day].output += ev.output;
                dailyData[day].cache_read += ev.cache_read;

                // Group models
                modelData[ev.model] = (modelData[ev.model] || 0) + ev.total;
            });

            const cacheHitPct = (totalInput + cachedTokens) > 0 ? (cachedTokens / (totalInput + cachedTokens) * 100) : 0;
            
            // If default 'all' filters are active, use authoritative global_overview totals
            const isAllDefault = activeFilters.project === 'all' && activeFilters.model === 'all' && activeFilters.tool === 'all' && activeFilters.timeframe === 'all';
            if (isAllDefault && TELEMETRY_DATA.global_overview) {
                const go = TELEMETRY_DATA.global_overview;
                if (go.total_tokens > totalTokens) {
                    totalTokens = go.total_tokens;
                    totalInput = go.total_input;
                    totalOutput = go.total_output;
                    cachedTokens = go.cached_tokens;
                    cost = go.estimated_cost;
                    savings = go.estimated_savings;
                }
            }

            // Set stats elements
            document.getElementById('stat-total-tokens').innerText = formatNumber(totalTokens);
            document.getElementById('stat-input-tokens').innerText = formatNumber(totalInput);
            document.getElementById('stat-output-tokens').innerText = formatNumber(totalOutput);
            document.getElementById('stat-cached-tokens').innerText = formatNumber(cachedTokens);
            document.getElementById('stat-cache-hit-pct').innerText = cacheHitPct.toFixed(1) + '%';
            document.getElementById('stat-cost').innerText = '$' + cost.toFixed(2);
            document.getElementById('stat-savings').innerText = '$' + savings.toFixed(2);
            document.getElementById('stat-io-ratio').innerText = totalInput > 0 ? (totalOutput / totalInput).toFixed(3) : '0.0';

            
            document.getElementById('stat-sessions').innerText = uniqueSessions.size;
            document.getElementById('stat-requests').innerText = filteredEvents.length;
            document.getElementById('stat-active-repos').innerText = uniqueRepos.size;
            document.getElementById('stat-active-models').innerText = uniqueModels.size;
            
            const toolCount = new Set(TELEMETRY_DATA.tools.map(t => t.tool_name)).size;
            document.getElementById('stat-active-tools').innerText = toolCount;

            const avgContext = filteredEvents.length > 0 ? Math.round(totalInput / filteredEvents.length) : 0;
            const avgTokensReq = filteredEvents.length > 0 ? Math.round(totalTokens / filteredEvents.length) : 0;
            const avgTokensSess = uniqueSessions.size > 0 ? Math.round(totalTokens / uniqueSessions.size) : 0;

            document.getElementById('stat-avg-context').innerText = formatNumber(avgContext);
            document.getElementById('stat-avg-request-tokens').innerText = formatNumber(avgTokensReq) + ' / req';
            document.getElementById('stat-avg-session-tokens').innerText = formatNumber(avgTokensSess) + ' / sess';

            // --- Local inference card + Local vs Cloud donut ---
            let localTokens = 0;
            let cloudAvoidance = 0.0;
            const localModelMap = {};
            filteredEvents.forEach(ev => {
                if (ev.provider === 'local') {
                    localTokens += ev.total;
                    cloudAvoidance += ev.cloud_avoidance || 0;
                    if (!localModelMap[ev.model]) localModelMap[ev.model] = { tokens: 0, requests: 0 };
                    localModelMap[ev.model].tokens += ev.total;
                    localModelMap[ev.model].requests += ev.requests || 1;
                }
            });
            const goLocal = TELEMETRY_DATA.global_overview || {};
            if (isAllDefault && goLocal.local_inference && goLocal.local_inference.total_tokens > localTokens) {
                localTokens = goLocal.local_inference.total_tokens;
                cloudAvoidance = goLocal.local_inference.cloud_cost_avoidance || 0;
            }
            document.getElementById('stat-local-tokens').innerText = formatNumber(localTokens);
            document.getElementById('stat-cloud-avoidance').innerText = '$' + cloudAvoidance.toFixed(4);
            const avoidCard = document.getElementById('local-avoidance-card');
            if (avoidCard) avoidCard.style.display = localTokens > 0 ? '' : 'none';

            const localRow = document.getElementById('local-inference-row');
            if (localRow) {
                localRow.style.display = localTokens > 0 ? '' : 'none';
                if (localTokens > 0) {
                    const cloudTokens = Math.max(0, totalTokens - localTokens);
                    if (charts.localCloud) charts.localCloud.destroy();
                    const ctxLocal = document.getElementById('localCloudChartOverview').getContext('2d');
                    charts.localCloud = new Chart(ctxLocal, {
                        type: 'doughnut',
                        data: {
                            labels: ['Local', 'Cloud'],
                            datasets: [{
                                data: [localTokens, cloudTokens],
                                backgroundColor: ['#b9dc75', '#ff7849'],
                                borderColor: '#111512',
                                borderWidth: 2
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { position: 'bottom', labels: { color: '#a6ada0', boxWidth: 12 } }
                            }
                        }
                    });
                    const localTbody = document.getElementById('local-models-table');
                    if (localTbody) {
                        localTbody.innerHTML = '';
                        const localModels = Object.keys(localModelMap).sort((a, b) => localModelMap[b].tokens - localModelMap[a].tokens);
                        if (localModels.length === 0) {
                            localTbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No local model data</td></tr>';
                        }
                        localModels.forEach(m => {
                            const row = document.createElement('tr');
                            row.innerHTML = `
                                <td><span style="font-weight:600;">${escapeHtml(m)}</span></td>
                                <td style="text-align: right; font-family: monospace;">${formatNumber(localModelMap[m].tokens)}</td>
                                <td style="text-align: right;">${formatNumber(localModelMap[m].requests)}</td>
                            `;
                            localTbody.appendChild(row);
                        });
                    }
                }
            }

            // Populate Overview Active Repos table (top 5)
            const repoMap = {};
            filteredEvents.forEach(ev => {
                if (!repoMap[ev.project]) repoMap[ev.project] = { tokens: 0, sessions: new Set() };
                repoMap[ev.project].tokens += ev.total;
                repoMap[ev.project].sessions.add(ev.session_id);
            });
            const sortedRepos = Object.keys(repoMap).map(k => ({
                name: k,
                tokens: repoMap[k].tokens,
                sessions: repoMap[k].sessions.size
            })).sort((a,b) => b.tokens - a.tokens).slice(0, 5);

            const reposTbody = document.getElementById('overview-repos-table');
            reposTbody.innerHTML = '';
            if (sortedRepos.length === 0) {
                reposTbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No data available</td></tr>';
            }
            sortedRepos.forEach(r => {
                // Find branch if any
                const gitInfo = TELEMETRY_DATA.git_integration.repos_git_info[r.name];
                const branch = gitInfo ? gitInfo.branch : 'N/A';
                
                const row = document.createElement('tr');
                row.className = 'clickable-row';
                row.onclick = () => drilldownRepo(r.name);
                row.innerHTML = `
                    <td><span style="font-weight:600;">${escapeHtml(r.name)}</span></td>
                    <td style="text-align: right; font-family: monospace;">${formatNumber(r.tokens)}</td>
                    <td style="text-align: right;">${r.sessions}</td>
                    <td style="text-align: right;"><span class="pill pill-emerald">cache</span></td>
                    <td><span class="pill">${escapeHtml(branch)}</span></td>
                `;
                reposTbody.appendChild(row);
            });

            // Populate Overview Sessions table (top 5 latest)
            const sessMap = {};
            filteredEvents.forEach(ev => {
                if (!sessMap[ev.session_id]) sessMap[ev.session_id] = { tokens: 0, times: [] };
                sessMap[ev.session_id].tokens += ev.total;
                sessMap[ev.session_id].times.push(new Date(ev.occurred_at));
            });
            const sortedSess = Object.keys(sessMap).map(k => {
                const times = sessMap[k].times;
                const start = new Date(Math.min(...times));
                const end = new Date(Math.max(...times));
                return {
                    id: k,
                    tokens: sessMap[k].tokens,
                    duration: (end - start) / 1000,
                    start: start
                };
            }).sort((a,b) => b.start - a.start).slice(0, 5);

            const sessTbody = document.getElementById('overview-sessions-table');
            sessTbody.innerHTML = '';
            if (sortedSess.length === 0) {
                sessTbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No data available</td></tr>';
            }
            sortedSess.forEach(s => {
                const row = document.createElement('tr');
                row.className = 'clickable-row';
                row.onclick = () => drilldownSession(s.id);
                row.innerHTML = `
                    <td><span class="session-id-link">${escapeHtml(s.id.slice(0, 8))}</span></td>
                    <td style="text-align: right; font-family: monospace; font-weight: 600;" class="text-cyan">${formatNumber(s.tokens)}</td>
                    <td>${formatDuration(s.duration)}</td>
                    <td style="font-size: 0.8rem; color: var(--text-secondary);">${s.start.toLocaleDateString()}</td>
                `;
                sessTbody.appendChild(row);
            });

            // Overview line chart (Trend)
            const days = Object.keys(dailyData).sort();
            const inputSeries = days.map(d => dailyData[d].input);
            const outputSeries = days.map(d => dailyData[d].output);
            const cacheSeries = days.map(d => dailyData[d].cache_read);

            if (charts.trendOverview) charts.trendOverview.destroy();
            const ctxTrend = document.getElementById('trendChartOverview').getContext('2d');
            charts.trendOverview = new Chart(ctxTrend, {
                type: 'line',
                data: {
                    labels: days.map(d => {
                        const dateObj = new Date(d);
                        return dateObj.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
                    }),
                    datasets: [
                        {
                            label: 'Regular Input',
                            data: inputSeries,
                            borderColor: '#b9dc75',
                            backgroundColor: 'rgba(185, 220, 117, 0.01)',
                            fill: true,
                            tension: 0.3,
                            borderWidth: 2,
                            pointRadius: days.length > 50 ? 0 : 2
                        },
                        {
                            label: 'Generations',
                            data: outputSeries,
                            borderColor: '#ff7a00',
                            backgroundColor: 'rgba(255, 122, 0, 0.01)',
                            fill: true,
                            tension: 0.3,
                            borderWidth: 2,
                            pointRadius: days.length > 50 ? 0 : 2
                        },
                        {
                            label: 'Cache Reads',
                            data: cacheSeries,
                            borderColor: '#b9dc75',
                            backgroundColor: 'rgba(185, 220, 117, 0.01)',
                            fill: true,
                            tension: 0.3,
                            borderWidth: 2,
                            pointRadius: days.length > 50 ? 0 : 2
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: '#8b95a5', font: { family: 'Plus Jakarta Sans', size: 9 } } },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                        backgroundColor: '#111512',
                        borderColor: '#263027',
                            borderWidth: 1,
                            callbacks: { label: function(context) { return ' ' + context.dataset.label + ': ' + formatNumber(context.raw); } }
                        }
                    },
                    scales: {
                        x: { grid: { color: '#141a29' }, ticks: { color: '#8b95a5', font: { size: 9 }, maxTicksLimit: 10 } },
                        y: { grid: { color: '#141a29' }, ticks: { color: '#8b95a5', font: { size: 9 }, callback: function(val) { return formatNumber(val); } } }
                    }
                }
            });

            // Overview Doughnut Chart (Models)
            let modelsLabels = [];
            let modelsValues = [];

            if (isAllDefault && TELEMETRY_DATA.models && TELEMETRY_DATA.models.length > 0) {
                modelsLabels = TELEMETRY_DATA.models.map(m => m.model_name);
                modelsValues = TELEMETRY_DATA.models.map(m => m.total_tokens);
            } else {
                modelsLabels = Object.keys(modelData);
                modelsValues = Object.values(modelData);
            }

            const chartColors = [
                '#ff7849', '#b9dc75', '#7ed7bd', '#e6a85c', '#ff5f56', '#d7c27d',
                '#c18f6b', '#a855f7', '#06b6d4', '#ec4899', '#3b82f6', '#10b981',
                '#f59e0b', '#84cc16', '#6366f1', '#687368'
            ];

            const sliceColors = modelsLabels.map((lbl, idx) => {
                const baseColor = chartColors[idx % chartColors.length];
                if (activeFilters.model !== 'all') {
                    return lbl === activeFilters.model ? baseColor : 'rgba(100, 116, 139, 0.25)';
                }
                return baseColor;
            });

            if (charts.modelOverview) charts.modelOverview.destroy();
            const ctxModel = document.getElementById('modelChartOverview').getContext('2d');
            charts.modelOverview = new Chart(ctxModel, {
                type: 'doughnut',
                data: {
                    labels: modelsLabels,
                    datasets: [{
                        data: modelsValues,
                        backgroundColor: sliceColors,
                        borderWidth: 2,
                        borderColor: '#0e121f'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: function(evt, elements, chart) {
                        if (elements && elements.length > 0) {
                            const index = elements[0].index;
                            const clickedModel = chart.data.labels[index];
                            highlightOrFilterModel(clickedModel);
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'bottom',
                            onClick: function(e, legendItem, legend) {
                                const clickedModel = legend.chart.data.labels[legendItem.index];
                                highlightOrFilterModel(clickedModel);
                            },
                            labels: {
                                color: function(ctx) {
                                    const labelText = ctx.text;
                                    if (activeFilters.model !== 'all' && activeFilters.model === labelText) {
                                        return '#ff7a00';
                                    }
                                    return '#f0f3f6';
                                },
                                boxWidth: 14,
                                padding: 14,
                                font: { family: 'Plus Jakarta Sans', size: 13, weight: '600' }
                            }
                        },
                        tooltip: {
                            backgroundColor: '#0e121f',
                            borderColor: '#1c2336',
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const pct = total > 0 ? (context.raw / total * 100).toFixed(1) : 0;
                                    return ' ' + context.label + ': ' + formatNumber(context.raw) + ' (' + pct + '%)';
                                }
                            }
                        }
                    },
                    cutout: '72%'
                }
            });
        }

        // ================= REPOSITORIES RENDERING =================
        function drilldownRepo(repoName) {
            repoDrillId = repoName;
            updateBreadcrumb();
            switchTab('repositories', { preserveDrilldown: true });
        }

        function exitRepoDrilldown() {
            repoDrillId = null;
            updateBreadcrumb();
            renderUI();
        }

        function sortReposTable(col) {
            if (repoSortCol === col) {
                repoSortDesc = !repoSortDesc;
            } else {
                repoSortCol = col;
                repoSortDesc = true;
            }
            renderRepositoriesList();
        }

        function renderRepositoriesList() {
            document.getElementById('subview-repos-list').style.display = 'block';
            document.getElementById('subview-repo-drilldown').style.display = 'none';

            // Populate table headers with sorting indicators
            const headers = document.querySelectorAll('#repos-table th');
            const colMap = ['repository', 'tokens', 'input', 'output', 'cache_read', 'cache_ratio', 'requests', 'sessions', 'commits_count'];
            headers.forEach((h, idx) => {
                h.className = '';
                const colName = colMap[idx];
                if (colName === repoSortCol) {
                    h.className = repoSortDesc ? 'sort-desc' : 'sort-asc';
                }
            });

            // Gather repo records
            // To compute dynamically under active model/tool/timeframe filters
            const filteredEvents = getFilteredRawEvents();
            const projectAgg = {};

            filteredEvents.forEach(ev => {
                if (!projectAgg[ev.project]) {
                    projectAgg[ev.project] = {
                        repository: ev.project,
                        tokens: 0,
                        input: 0,
                        output: 0,
                        cache_read: 0,
                        requests: 0,
                        sessions: new Set()
                    };
                }
                const agg = projectAgg[ev.project];
                agg.tokens += ev.total;
                agg.input += ev.input;
                agg.output += ev.output;
                agg.cache_read += ev.cache_read;
                agg.requests += 1;
                agg.sessions.add(ev.session_id);
            });

            // Convert to array and format
            const reposArr = Object.keys(projectAgg).map(k => {
                const item = projectAgg[k];
                // Match raw static database configs for branches & commits count
                const staticConf = TELEMETRY_DATA.repositories.find(r => r.repository === k) || {};
                
                return {
                    repository: k,
                    tokens: item.tokens,
                    input: item.input,
                    output: item.output,
                    cache_read: item.cache_read,
                    cache_ratio: (item.input + item.cache_read) > 0 ? item.cache_read / (item.input + item.cache_read) : 0,
                    requests: item.requests,
                    sessions: item.sessions.size,
                    commits_count: staticConf.commits_count || 0,
                    latest_activity: staticConf.latest_activity || 'N/A'
                };
            });

            // Sort
            reposArr.sort((a, b) => {
                let vA = a[repoSortCol];
                let vB = b[repoSortCol];
                if (typeof vA === 'string') {
                    return repoSortDesc ? vB.localeCompare(vA) : vA.localeCompare(vB);
                }
                return repoSortDesc ? vB - vA : vA - vB;
            });

            const tbody = document.getElementById('repos-table-body');
            tbody.innerHTML = '';
            if (reposArr.length === 0) {
                tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 3rem; color: var(--text-muted);">No repositories match active filters.</td></tr>';
                return;
            }

            reposArr.forEach(r => {
                const tr = document.createElement('tr');
                tr.className = 'clickable-row';
                tr.onclick = () => drilldownRepo(r.repository);
                tr.innerHTML = `
                    <td><span style="font-weight: 600;">${escapeHtml(r.repository)}</span></td>
                    <td style="text-align: right; font-family: monospace; font-weight:600;">${formatNumber(r.tokens)}</td>
                    <td style="text-align: right; font-family: monospace; color: var(--text-secondary);">${formatNumber(r.input)}</td>
                    <td style="text-align: right; font-family: monospace; color: var(--accent-orange);">${formatNumber(r.output)}</td>
                    <td style="text-align: right; font-family: monospace; color: var(--accent-emerald);">${formatNumber(r.cache_read)}</td>
                    <td style="text-align: right; font-weight: 600;" class="text-emerald">${(r.cache_ratio * 100).toFixed(1)}%</td>
                    <td style="text-align: right;">${r.requests}</td>
                    <td style="text-align: right;">${r.sessions}</td>
                    <td style="text-align: right; color: var(--accent-purple); font-weight: 600;">${r.commits_count}</td>
                    <td style="font-size: 0.8rem; color: var(--text-secondary);">${escapeHtml(r.latest_activity)}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        function renderRepoDrilldown(repoName) {
            document.getElementById('subview-repos-list').style.display = 'none';
            const subview = document.getElementById('subview-repo-drilldown');
            subview.style.display = 'flex';

            // Find metadata from static data
            const repoData = TELEMETRY_DATA.repositories.find(r => r.repository === repoName) || { repository: repoName };
            document.getElementById('repo-drilldown-title').innerText = 'Repository: ' + repoName;
            document.getElementById('repo-drilldown-path').innerText = 'Local Project Workspace Path: ' + (repoData.git_path || 'No local directory mapping');

            // Gather drilldown events for this repo
            const filteredEvents = getFilteredRawEvents().filter(ev => ev.project === repoName);
            
            let totalTokens = 0;
            let totalInput = 0;
            let totalOutput = 0;
            let cachedTokens = 0;
            let modelsMap = {};
            let toolsMap = {};
            let dailyMap = {};

            filteredEvents.forEach(ev => {
                totalTokens += ev.total;
                totalInput += ev.input;
                totalOutput += ev.output;
                cachedTokens += ev.cache_read;

                modelsMap[ev.model] = (modelsMap[ev.model] || 0) + ev.total;
                toolsMap[ev.tool] = (toolsMap[ev.tool] || 0) + ev.total;
                
                const d = ev.occurred_at.slice(0, 10);
                dailyMap[d] = (dailyMap[d] || 0) + ev.total;
            });

            document.getElementById('repo-drill-total-tokens').innerText = formatNumber(totalTokens);
            document.getElementById('repo-drill-input').innerText = formatNumber(totalInput);
            document.getElementById('repo-drill-output').innerText = formatNumber(totalOutput);
            document.getElementById('repo-drill-cache-tokens').innerText = formatNumber(cachedTokens);
            
            const cacheRatio = (totalInput + cachedTokens) > 0 ? (cachedTokens / (totalInput + cachedTokens) * 100) : 0;
            document.getElementById('repo-drill-cache-ratio').innerText = cacheRatio.toFixed(1) + '%';
            document.getElementById('repo-drill-io-ratio').innerText = totalInput > 0 ? (totalOutput / totalInput).toFixed(3) : '0.0';

            const activeBranch = repoData.branch || 'No Git Detected';
            document.getElementById('repo-drill-git-branch').innerText = activeBranch;
            document.getElementById('repo-drill-commits-count').innerText = repoData.commits_count || 0;

            // Render models lists
            const modelsList = document.getElementById('repo-drill-models-list');
            modelsList.innerHTML = '';
            Object.keys(modelsMap).sort((a,b) => modelsMap[b] - modelsMap[a]).forEach(m => {
                const pct = totalTokens > 0 ? (modelsMap[m] / totalTokens * 100).toFixed(1) : 0;
                modelsList.innerHTML += `
                    <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.8rem;">
                        <span class="pill pill-purple" style="max-width:160px; overflow:hidden; text-overflow:ellipsis;" title="${escapeHtml(m)}">${escapeHtml(m)}</span>
                        <span style="font-family:monospace;">${formatNumber(modelsMap[m])} (${pct}%)</span>
                    </div>
                `;
            });

            // Render tools lists
            const toolsList = document.getElementById('repo-drill-tools-list');
            toolsList.innerHTML = '';
            Object.keys(toolsMap).sort((a,b) => toolsMap[b] - toolsMap[a]).forEach(t => {
                const staticTool = TELEMETRY_DATA.tools.find(tool => tool.tool_name === t) || { display_name: t };
                const pct = totalTokens > 0 ? (toolsMap[t] / totalTokens * 100).toFixed(1) : 0;
                toolsList.innerHTML += `
                    <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.8rem;">
                        <span class="pill pill-orange">${escapeHtml(staticTool.display_name)}</span>
                        <span style="font-family:monospace;">${formatNumber(toolsMap[t])} (${pct}%)</span>
                    </div>
                `;
            });

            // Repo line chart trend
            const days = Object.keys(dailyMap).sort();
            const values = days.map(d => dailyMap[d]);

            if (charts.repoDrill) charts.repoDrill.destroy();
            const ctxRepoDrill = document.getElementById('repoDrillChart').getContext('2d');
            charts.repoDrill = new Chart(ctxRepoDrill, {
                type: 'bar',
                data: {
                    labels: days,
                    datasets: [{
                        label: 'Total Daily Tokens',
                        data: values,
                        backgroundColor: 'rgba(255, 122, 0, 0.4)',
                        borderColor: '#ff7a00',
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { color: '#141a29' }, ticks: { color: '#8b95a5', font: { size: 9 }, maxTicksLimit: 12 } },
                        y: { grid: { color: '#141a29' }, ticks: { color: '#8b95a5', font: { size: 9 }, callback: function(val) { return formatNumber(val); } } }
                    }
                }
            });

            // Correlated git commits list
            const commitsTbody = document.getElementById('repo-drill-commits-body');
            commitsTbody.innerHTML = '';
            
            const repoCommits = TELEMETRY_DATA.git_integration.correlated_commits.filter(c => c.project === repoName);
            if (repoCommits.length === 0) {
                document.getElementById('repo-drill-commits-panel').style.display = 'none';
            } else {
                document.getElementById('repo-drill-commits-panel').style.display = 'flex';
                repoCommits.forEach(c => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><span class="pill pill-purple">${escapeHtml(c.hash)}</span></td>
                        <td style="white-space:nowrap; font-size:0.75rem; color:var(--text-secondary);">${escapeHtml(c.datetime)}</td>
                        <td style="font-weight:500;">${escapeHtml(c.message)}</td>
                        <td style="text-align:right; font-family:monospace; font-weight:600;" class="text-orange">${formatNumber(c.tokens)}</td>
                        <td style="text-align:right;">${c.requests}</td>
                        <td style="text-align:right; font-size:0.8rem; color:var(--accent-cyan); font-weight:600;">${formatDuration(c.coding_time)}</td>
                        <td style="text-align:right; font-family:monospace; color:var(--text-secondary);">$${c.cost.toFixed(3)}</td>
                    `;
                    commitsTbody.appendChild(tr);
                });
            }
        }

        // ================= SESSIONS RENDERING =================
        function drilldownSession(sessId) {
            sessionDrillId = sessId;
            updateBreadcrumb();
            switchTab('sessions', { preserveDrilldown: true });
        }

        function exitSessionDrilldown() {
            sessionDrillId = null;
            updateBreadcrumb();
            renderUI();
        }

        function sortSessionsTable(col) {
            if (sessSortCol === col) {
                sessSortDesc = !sessSortDesc;
            } else {
                sessSortCol = col;
                sessSortDesc = true;
            }
            renderSessionsList();
        }

        function renderSessionsList() {
            document.getElementById('subview-sessions-list').style.display = 'block';
            document.getElementById('subview-subview-session-drilldown') ? 
                document.getElementById('subview-subview-session-drilldown').style.display = 'none' : null;
            document.getElementById('subview-session-drilldown').style.display = 'none';

            // Populate table headers with sorting indicators
            const headers = document.querySelectorAll('#sessions-table th');
            const colMap = ['session_id', 'project', 'start', 'duration', 'requests', 'total_tokens', 'cache_read', 'estimated_cost', 'estimated_savings'];
            headers.forEach((h, idx) => {
                h.className = '';
                const colName = colMap[idx];
                if (colName === sessSortCol) {
                    h.className = sessSortDesc ? 'sort-desc' : 'sort-asc';
                }
            });

            // Group filtered events into session records dynamically to apply active filters
            const filteredEvents = getFilteredRawEvents();
            const sessionAgg = {};

            filteredEvents.forEach(ev => {
                if (!sessionAgg[ev.session_id]) {
                    sessionAgg[ev.session_id] = {
                        session_id: ev.session_id,
                        project: ev.project,
                        start: ev.occurred_at,
                        end: ev.occurred_at,
                        duration: 0,
                        requests: 0,
                        total_tokens: 0,
                        cache_read: 0,
                        estimated_cost: 0.0,
                        estimated_savings: 0.0
                    };
                }
                const sess = sessionAgg[ev.session_id];
                sess.requests += 1;
                sess.total_tokens += ev.total;
                sess.cache_read += ev.cache_read;
                sess.estimated_cost += ev.cost;
                // Savings estimation
                sess.estimated_savings += (ev.savings || 0);

                if (ev.occurred_at < sess.start) sess.start = ev.occurred_at;
                if (ev.occurred_at > sess.end) sess.end = ev.occurred_at;
            });

            // Convert to array
            const sessionArr = Object.keys(sessionAgg).map(k => {
                const s = sessionAgg[k];
                const diffMs = new Date(s.end) - new Date(s.start);
                s.duration = Math.max(1, Math.round(diffMs / 1000));
                return s;
            });

            // Sort
            sessionArr.sort((a, b) => {
                let vA = a[sessSortCol];
                let vB = b[sessSortCol];
                if (typeof vA === 'string') {
                    return sessSortDesc ? vB.localeCompare(vA) : vA.localeCompare(vB);
                }
                return sessSortDesc ? vB - vA : vA - vB;
            });

            const tbody = document.getElementById('sessions-table-body');
            tbody.innerHTML = '';
            if (sessionArr.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 3rem; color: var(--text-muted);">No sessions match active filters.</td></tr>';
                return;
            }

            sessionArr.forEach(s => {
                const tr = document.createElement('tr');
                tr.className = 'clickable-row';
                tr.onclick = () => drilldownSession(s.session_id);
                tr.innerHTML = `
                    <td><span class="session-id-link">${escapeHtml(s.session_id.slice(0, 8))}</span></td>
                    <td><span style="font-weight: 500;">${escapeHtml(s.project)}</span></td>
                    <td style="color: var(--text-secondary); font-size: 0.8rem;">${escapeHtml(s.start)}</td>
                    <td style="text-align: right; font-weight:500;">${formatDuration(s.duration)}</td>
                    <td style="text-align: right;">${s.requests}</td>
                    <td style="text-align: right; font-family: monospace; font-weight:600;" class="text-cyan">${formatNumber(s.total_tokens)}</td>
                    <td style="text-align: right; font-family: monospace; color: var(--accent-emerald);">${formatNumber(s.cache_read)}</td>
                    <td style="text-align: right; font-family: monospace; font-weight: 600;">$${s.estimated_cost.toFixed(3)}</td>
                    <td style="text-align: right; font-family: monospace; color: var(--text-secondary);">$${s.estimated_savings.toFixed(3)}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        function renderSessionDrilldown(sessId) {
            document.getElementById('subview-sessions-list').style.display = 'none';
            const subview = document.getElementById('subview-session-drilldown');
            subview.style.display = 'flex';

            // Find session metadata from raw sessions
            const sessObj = TELEMETRY_DATA.sessions.find(s => s.session_id === sessId);
            if (!sessObj) {
                subview.innerHTML = '<div class="empty-state"><h3>Session not found</h3><button onclick="exitSessionDrilldown()">Back</button></div>';
                return;
            }

            document.getElementById('session-drilldown-title').innerText = 'Session: ' + sessId;
            document.getElementById('session-drilldown-meta').innerText = `Project: ${sessObj.project} | Start: ${sessObj.start} | End: ${sessObj.end}`;

            // Populate cards
            document.getElementById('session-drill-tokens').innerText = formatNumber(sessObj.total_tokens);
            document.getElementById('session-drill-in-out').innerText = `${formatNumber(sessObj.input)} / ${formatNumber(sessObj.output)}`;
            document.getElementById('session-drill-avg-context').innerText = formatNumber(sessObj.avg_context);
            document.getElementById('session-drill-avg-output').innerText = formatNumber(sessObj.avg_output);
            
            document.getElementById('session-drill-cost').innerText = '$' + sessObj.estimated_cost.toFixed(3);
            document.getElementById('session-drill-savings').innerText = '$' + sessObj.estimated_savings.toFixed(3);
            
            document.getElementById('session-drill-duration').innerText = formatDuration(sessObj.duration);
            document.getElementById('session-drill-turns').innerText = sessObj.requests;

            // Model Mix distribution
            const mixContainer = document.getElementById('session-drill-model-mix');
            mixContainer.innerHTML = '';
            sessObj.model_distribution.forEach(m => {
                const pct = sessObj.total_tokens > 0 ? (m.tokens / sessObj.total_tokens * 100).toFixed(1) : 0;
                mixContainer.innerHTML += `
                    <div>
                        <div style="display:flex; justify-content:space-between; font-size:0.8rem; margin-bottom:0.25rem;">
                            <span>${escapeHtml(m.model)}</span>
                            <span style="font-family:monospace; font-weight:600;">${formatNumber(m.tokens)} (${pct}%)</span>
                        </div>
                        <div style="height:6px; background-color:var(--border-color); border-radius:3px; overflow:hidden;">
                            <div style="height:100%; width:${pct}%; background-color:var(--accent-purple);"></div>
                        </div>
                    </div>
                `;
            });

            // Timeline turns layout
            const timelineContainer = document.getElementById('session-drill-timeline');
            timelineContainer.innerHTML = '';
            sessObj.timeline.forEach((turn, idx) => {
                const dotClass = turn.status === 'ok' ? 'success' : (turn.status === 'error' ? 'error' : '');
                
                timelineContainer.innerHTML += `
                    <div class="timeline-node">
                        <div class="timeline-dot ${dotClass}"></div>
                        <div class="timeline-content">
                            <div class="timeline-header">
                                <span class="pill pill-purple">Turn #${escapeHtml(turn.turn_id)}</span>
                                <span class="timeline-time">${escapeHtml(turn.occurred_at)}</span>
                            </div>
                            <div style="display:flex; flex-wrap:wrap; gap:1.5rem; margin-top:0.5rem; font-size:0.8rem;">
                                <div><span style="color:var(--text-secondary);">Model:</span> <span style="font-weight:600;">${escapeHtml(turn.model)}</span></div>
                                <div><span style="color:var(--text-secondary);">Input:</span> <span style="font-family:monospace;">${formatNumber(turn.input)}</span></div>
                                <div><span style="color:var(--text-secondary);">Gen (Out):</span> <span style="font-family:monospace; color:var(--accent-orange);">${formatNumber(turn.output)}</span></div>
                                <div><span style="color:var(--text-secondary);">Cached:</span> <span style="font-family:monospace; color:var(--accent-emerald);">${formatNumber(turn.cache_read)}</span></div>
                                <div><span style="color:var(--text-secondary);">Cost:</span> <span style="font-family:monospace; font-weight:600;">$${turn.cost.toFixed(4)}</span></div>
                            </div>
                        </div>
                    </div>
                `;
            });
        }

        // ================= MODELS RENDERING =================
        function renderModels() {
            const tbody = document.getElementById('models-table-body');
            tbody.innerHTML = '';

            const filteredEvents = getFilteredRawEvents();
            const modelAgg = {};

            filteredEvents.forEach(ev => {
                const mdl = ev.model || ev.model_name || 'Unknown';
                if (!modelAgg[mdl]) {
                    modelAgg[mdl] = {
                        model_name: mdl,
                        total_tokens: 0,
                        input: 0,
                        output: 0,
                        cache_read: 0,
                        requests: 0,
                        repositories_used: new Set(),
                        estimated_cost: 0.0,
                        estimated_savings: 0.0
                    };
                }
                const m = modelAgg[mdl];
                m.total_tokens += ev.total;
                m.input += ev.input;
                m.output += ev.output;
                m.cache_read += ev.cache_read;
                m.requests += 1;
                if (ev.project) m.repositories_used.add(ev.project);
                m.estimated_cost += ev.cost;
                m.estimated_savings += (ev.savings || 0);
            });

            const mData = Object.keys(modelAgg).map(k => {
                const m = modelAgg[k];
                const avgContext = m.requests > 0 ? Math.round(m.input / m.requests) : 0;
                const avgComp = m.requests > 0 ? Math.round(m.output / m.requests) : 0;
                const cacheRatio = (m.input + m.cache_read) > 0 ? (m.cache_read / (m.input + m.cache_read)) : 0;
                return {
                    model_name: k,
                    total_tokens: m.total_tokens,
                    requests: m.requests,
                    average_context: avgContext,
                    average_completion: avgComp,
                    average_cache_hit: cacheRatio,
                    estimated_cost: m.estimated_cost,
                    estimated_savings: m.estimated_savings,
                    repositories_used: Array.from(m.repositories_used)
                };
            }).sort((a, b) => b.total_tokens - a.total_tokens);

            if (mData.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 3rem; color: var(--text-muted);">No models match active filters.</td></tr>';
            }

            mData.forEach(m => {
                const cacheRatio = m.average_cache_hit * 100;
                const reposStr = m.repositories_used.join(', ') || 'N/A';
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><span class="pill pill-purple" style="font-weight:600;">${escapeHtml(m.model_name)}</span></td>
                    <td style="text-align: right; font-family: monospace; font-weight: 600;">${formatNumber(m.total_tokens)}</td>
                    <td style="text-align: right;">${m.requests}</td>
                    <td style="text-align: right; font-family: monospace;">${formatNumber(m.average_context)}</td>
                    <td style="text-align: right; font-family: monospace; color: var(--accent-orange);">${formatNumber(m.average_completion)}</td>
                    <td style="text-align: right; font-weight: 600;" class="text-emerald">${cacheRatio.toFixed(1)}%</td>
                    <td style="text-align: right; font-family: monospace; font-weight:600;">$${m.estimated_cost.toFixed(2)}</td>
                    <td style="text-align: right; font-family: monospace; color:var(--text-secondary);">$${m.estimated_savings.toFixed(2)}</td>
                    <td style="font-size:0.8rem; color:var(--text-secondary); max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(reposStr)}">${escapeHtml(reposStr)}</td>
                `;
                tbody.appendChild(tr);
            });

            // Model comparisons charts (bar comparison)
            const fullModelNames = mData.map(m => m.model_name);
            const labels = fullModelNames;
            const tokens = mData.map(m => m.total_tokens);
            const requests = mData.map(m => m.requests);
            const caches = mData.map(m => m.average_cache_hit * 100);

            // Chart 1: Tokens compare
            if (charts.modelCompTokens) charts.modelCompTokens.destroy();
            charts.modelCompTokens = new Chart(document.getElementById('modelCompareTokensChart').getContext('2d'), {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Total Tokens',
                        data: tokens,
                        backgroundColor: labels.map(lbl => activeFilters.model !== 'all' ? (lbl === activeFilters.model ? '#b9dc75' : 'rgba(185, 220, 117, 0.25)') : '#b9dc75'),
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: function(evt, elements, chart) {
                        if (elements && elements.length > 0) {
                            const index = elements[0].index;
                            const clickedModel = fullModelNames[index];
                            highlightOrFilterModel(clickedModel);
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        title: { display: true, text: 'Tokens Consumed by Model', color: '#f8fafc', font: { family: 'Plus Jakarta Sans', size: 14, weight: '700' }, padding: { bottom: 12 } }
                    },
                    scales: {
                        x: { grid: { color: '#141a29' }, ticks: { color: '#f0f3f6', font: { family: 'Plus Jakarta Sans', size: 12, weight: '600' }, maxRotation: 45, minRotation: 30 } },
                        y: { grid: { color: '#141a29' }, ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11, weight: '500' } } }
                    }
                }
            });

            // Chart 2: Requests compare
            if (charts.modelCompRequests) charts.modelCompRequests.destroy();
            charts.modelCompRequests = new Chart(document.getElementById('modelCompareRequestsChart').getContext('2d'), {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Requests Count',
                        data: requests,
                        backgroundColor: labels.map(lbl => activeFilters.model !== 'all' ? (lbl === activeFilters.model ? '#ff7a00' : 'rgba(255, 122, 0, 0.25)') : '#ff7a00'),
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: function(evt, elements, chart) {
                        if (elements && elements.length > 0) {
                            const index = elements[0].index;
                            const clickedModel = fullModelNames[index];
                            highlightOrFilterModel(clickedModel);
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        title: { display: true, text: 'API Invocations by Model', color: '#f8fafc', font: { family: 'Plus Jakarta Sans', size: 14, weight: '700' }, padding: { bottom: 12 } }
                    },
                    scales: {
                        x: { grid: { color: '#141a29' }, ticks: { color: '#f0f3f6', font: { family: 'Plus Jakarta Sans', size: 12, weight: '600' }, maxRotation: 45, minRotation: 30 } },
                        y: { grid: { color: '#141a29' }, ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11, weight: '500' } } }
                    }
                }
            });

            // Chart 3: Caches compare
            if (charts.modelCompCache) charts.modelCompCache.destroy();
            charts.modelCompCache = new Chart(document.getElementById('modelCompareCacheChart').getContext('2d'), {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Cache Hit %',
                        data: caches,
                        backgroundColor: labels.map(lbl => activeFilters.model !== 'all' ? (lbl === activeFilters.model ? '#b9dc75' : 'rgba(185, 220, 117, 0.25)') : '#b9dc75'),
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: function(evt, elements, chart) {
                        if (elements && elements.length > 0) {
                            const index = elements[0].index;
                            const clickedModel = fullModelNames[index];
                            highlightOrFilterModel(clickedModel);
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        title: { display: true, text: 'Cache Efficiency Ratio (%)', color: '#f8fafc', font: { family: 'Plus Jakarta Sans', size: 14, weight: '700' }, padding: { bottom: 12 } }
                    },
                    scales: {
                        x: { grid: { color: '#141a29' }, ticks: { color: '#f0f3f6', font: { family: 'Plus Jakarta Sans', size: 12, weight: '600' }, maxRotation: 45, minRotation: 30 } },
                        y: { min: 0, max: 100, grid: { color: '#141a29' }, ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11, weight: '500' } } }
                    }
                }
            });
        }

        // ================= TOOLS RENDERING =================
        function renderTools() {
            const grid = document.getElementById('tools-grid-cards');
            grid.innerHTML = '';
            
            const filteredEvents = getFilteredRawEvents();
            const toolAgg = {};

            filteredEvents.forEach(ev => {
                const toolName = ev.tool || ev.tool_name || 'Unknown';
                if (!toolAgg[toolName]) {
                    const staticTool = TELEMETRY_DATA.tools.find(t => t.tool_name === toolName) || {};
                    toolAgg[toolName] = {
                        tool_name: toolName,
                        display_name: staticTool.display_name || toolName,
                        total_tokens: 0,
                        input: 0,
                        output: 0,
                        cache_read: 0,
                        requests: 0,
                        repositories: new Set(),
                        models: new Set(),
                        sessions: new Set(),
                        times: []
                    };
                }
                const t = toolAgg[toolName];
                t.total_tokens += ev.total;
                t.input += ev.input;
                t.output += ev.output;
                t.cache_read += ev.cache_read;
                t.requests += 1;
                if (ev.project) t.repositories.add(ev.project);
                if (ev.model) t.models.add(ev.model);
                if (ev.session_id) t.sessions.add(ev.session_id);
                if (ev.occurred_at) t.times.push(new Date(ev.occurred_at));
            });

            const toolsArr = Object.keys(toolAgg).map(k => {
                const t = toolAgg[k];
                const cacheRatio = (t.input + t.cache_read) > 0 ? (t.cache_read / (t.input + t.cache_read)) : 0;
                const times = t.times;
                const duration = times.length > 0 ? (Math.max(...times) - Math.min(...times)) / 1000 : 0;
                const avgSessLen = t.sessions.size > 0 ? Math.round(duration / t.sessions.size) : 0;
                return {
                    tool_name: t.tool_name,
                    display_name: t.display_name,
                    total_tokens: t.total_tokens,
                    requests: t.requests,
                    cache_ratio: cacheRatio,
                    repositories: Array.from(t.repositories),
                    models: Array.from(t.models),
                    avg_session_length: avgSessLen
                };
            }).sort((a,b) => b.total_tokens - a.total_tokens);

            if (toolsArr.length === 0) {
                grid.innerHTML = '<div style="color: var(--text-muted); padding: 2rem;">No tools match active filters.</div>';
            }

            toolsArr.forEach(t => {
                const cachePct = t.cache_ratio * 100;
                grid.innerHTML += `
                    <div class="metric-card card-glow-orange">
                        <div class="metric-header">
                            <span>${escapeHtml(t.display_name)}</span>
                            <span class="text-emerald" style="font-weight:600;">${cachePct.toFixed(1)}% cached</span>
                        </div>
                        <div class="metric-value">${formatNumber(t.total_tokens)}</div>
                        <div class="metric-subtitle">${t.requests} requests · ${escapeHtml(t.models.join(', ') || 'No model data')}</div>
                    </div>
                `;
            });

            // Detailed tools breakdown table
            const tbody = document.getElementById('tools-table-body');
            tbody.innerHTML = '';
            toolsArr.forEach(t => {
                const reposStr = t.repositories.join(', ') || 'Global Scope';
                const modelsStr = t.models.join(', ') || 'N/A';
                const cacheHit = t.cache_ratio * 100;
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><span style="font-weight: 600;">${escapeHtml(t.display_name)}</span> <span class="pill">${escapeHtml(t.tool_name)}</span></td>
                    <td style="text-align: right; font-family: monospace; font-weight: 600;">${formatNumber(t.total_tokens)}</td>
                    <td style="text-align: right;">${t.requests}</td>
                    <td style="text-align: right; font-weight: 600;" class="text-emerald">${cacheHit.toFixed(1)}%</td>
                    <td style="font-size: 0.8rem; color: var(--text-secondary);">${escapeHtml(reposStr)}</td>
                    <td style="font-size: 0.8rem; color: var(--text-secondary);">${escapeHtml(modelsStr)}</td>
                    <td style="text-align: right; font-weight: 500;">${formatDuration(t.avg_session_length)}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        // ================= TIME ANALYTICS & HEATMAPS RENDERING =================
        function renderTimeAnalytics() {
            // 1. Render Calendar heatmap (standard GitHub calendar)
            const container = document.getElementById('daily-heatmap-grid');
            container.innerHTML = '';
            
            const filteredEvents = getFilteredRawEvents();
            
            // Build date & hourly mappings dynamically from filteredEvents
            const dailyMap = {};
            const hourlyMap = {};
            const weekdayHeatmap = Array.from({length: 7}, () => Array(24).fill(0));

            filteredEvents.forEach(ev => {
                if (!ev.occurred_at) return;
                const day = ev.occurred_at.slice(0, 10);
                dailyMap[day] = (dailyMap[day] || 0) + ev.total;
                
                const dt = new Date(ev.occurred_at);
                if (!isNaN(dt.getTime())) {
                    const hr = dt.getHours();
                    hourlyMap[hr] = (hourlyMap[hr] || 0) + ev.total;
                    
                    const dayIdx = dt.getDay() === 0 ? 6 : dt.getDay() - 1;
                    weekdayHeatmap[dayIdx][hr] += ev.total;
                }
            });

            // Fallback to static if filteredEvents empty and default filters active
            const isAllDefault = activeFilters.project === 'all' && activeFilters.model === 'all' && activeFilters.tool === 'all' && activeFilters.timeframe === 'all';
            if (isAllDefault && Object.keys(dailyMap).length === 0 && TELEMETRY_DATA.time_analytics && TELEMETRY_DATA.time_analytics.daily_timeline) {
                TELEMETRY_DATA.time_analytics.daily_timeline.forEach(d => {
                    dailyMap[d.day] = d.total;
                });
            }

            // We create cells for the last 365 days leading up to today (2026-07-25)
            const endDate = new Date("2026-07-25");
            const startDate = new Date();
            startDate.setDate(endDate.getDate() - 365);
            
            // Adjust to start on a Sunday or Monday to look neat
            const startDay = startDate.getDay();
            const daysOffset = startDay === 0 ? 0 : startDay; // align
            startDate.setDate(startDate.getDate() - daysOffset);

            // Collect all dates
            const datesArr = [];
            const temp = new Date(startDate);
            while (temp <= endDate) {
                datesArr.push(new Date(temp));
                temp.setDate(temp.getDate() + 1);
            }

            // Find maximum daily tokens for coloring scale
            const maxTokens = Math.max(...Object.values(dailyMap), 1);

            // Render columns (53 weeks)
            // Render rows (7 days: Sun-Sat)
            for (let i = 0; i < 7; i++) {
                for (let j = 0; j < 53; j++) {
                    const idx = j * 7 + i;
                    if (idx < datesArr.length) {
                        const cellDate = datesArr[idx];
                        const dateStr = cellDate.toISOString().slice(0, 10);
                        const tokens = dailyMap[dateStr] || 0;
                        
                        let level = 0;
                        if (tokens > 0) {
                            const ratio = tokens / maxTokens;
                            if (ratio < 0.15) level = 1;
                            else if (ratio < 0.45) level = 2;
                            else if (ratio < 0.75) level = 3;
                            else level = 4;
                        }
                        
                        const colors = ['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353'];
                        
                        const cell = document.createElement('div');
                        cell.className = 'heatmap-cell';
                        cell.style.backgroundColor = colors[level];
                        cell.title = `${dateStr}: ${formatNumber(tokens)} tokens`;
                        
                        cell.onclick = () => {
                            activeFilters.timeframe = 'all';
                            document.getElementById('global-search-input').value = dateStr;
                            switchTab('sessions');
                        };
                        
                        container.appendChild(cell);
                    }
                }
            }

            // 2. Render weekly coding heatmap (weekday hour grid)
            const weeklyBody = document.getElementById('weekly-hour-heatmap-body');
            weeklyBody.innerHTML = '';
            
            const daysNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
            const heatmapData = (Object.keys(dailyMap).length > 0) ? weekdayHeatmap : (TELEMETRY_DATA.time_analytics ? TELEMETRY_DATA.time_analytics.weekday_heatmap : weekdayHeatmap);

            let maxHourly = 1;
            for (let d = 0; d < 7; d++) {
                for (let h = 0; h < 24; h++) {
                    const val = (heatmapData[d] && heatmapData[d][h]) || 0;
                    if (val > maxHourly) maxHourly = val;
                }
            }

            for (let d = 0; d < 7; d++) {
                const tr = document.createElement('tr');
                
                const tdDay = document.createElement('td');
                tdDay.innerText = daysNames[d];
                tdDay.style.fontWeight = '600';
                tr.appendChild(tdDay);
                
                for (let h = 0; h < 24; h += 2) {
                    const val1 = (heatmapData[d] && heatmapData[d][h]) || 0;
                    const val2 = (heatmapData[d] && heatmapData[d][h+1]) || 0;
                    const val = val1 + val2;
                    
                    const ratio = val / maxHourly;
                    
                    const td = document.createElement('td');
                    td.style.backgroundColor = `rgba(255, 122, 0, ${Math.min(1, ratio.toFixed(2))})`;
                    td.style.height = '24px';
                    td.style.border = '1px solid var(--bg-card)';
                    td.style.cursor = 'pointer';
                    td.title = `${daysNames[d]} ${h}h-${h+2}h: ${formatNumber(val)} tokens`;
                    
                    tr.appendChild(td);
                }
                
                weeklyBody.appendChild(tr);
            }

            // 3. Set timing productivity stat fields
            document.getElementById('prod-busiest-day').innerText = TELEMETRY_DATA.time_analytics.busiest_coding_day;
            
            // Find busiest hour
            const targetHourlyMap = Object.keys(hourlyMap).length > 0 ? hourlyMap : (TELEMETRY_DATA.time_analytics ? TELEMETRY_DATA.time_analytics.hourly_heatmap : {});
            let busiestHour = 0;
            let busiestHourTokens = 0;
            Object.keys(targetHourlyMap).forEach(h => {
                if (targetHourlyMap[h] > busiestHourTokens) {
                    busiestHourTokens = targetHourlyMap[h];
                    busiestHour = h;
                }
            });
            document.getElementById('prod-busiest-hour').innerText = `${busiestHour}:00 - ${parseInt(busiestHour)+1}:00`;

            const sprintHrs = (TELEMETRY_DATA.time_analytics.longest_uninterrupted_coding_session_sec / 3600).toFixed(1);
            document.getElementById('prod-longest-sprint').innerText = sprintHrs + ' hours';
            
            const go = TELEMETRY_DATA.global_overview;
            const avgSessTok = go.sessions_count > 0 ? Math.round(go.total_tokens / go.sessions_count) : 0;
            document.getElementById('prod-tokens-per-session').innerText = formatNumber(avgSessTok);

            const avgSessLen = Math.round(TELEMETRY_DATA.productivity_metrics.average_coding_session_length / 60);
            document.getElementById('prod-avg-session-length').innerText = avgSessLen + ' mins';

            const contextUtil = (TELEMETRY_DATA.productivity_metrics.context_utilisation * 100).toFixed(1);
            document.getElementById('prod-context-util').innerText = contextUtil + '%';
        }

        // ================= GIT INTEGRATION RENDERING =================
        function renderGitIntegration() {
            const tbody = document.getElementById('git-commits-table-body');
            tbody.innerHTML = '';
            
            const searchVal = document.getElementById('global-search-input') ? document.getElementById('global-search-input').value.toLowerCase().trim() : '';
            const allCommits = TELEMETRY_DATA.git_integration ? (TELEMETRY_DATA.git_integration.correlated_commits || []) : [];

            const commits = allCommits.filter(c => {
                if (activeFilters.project !== 'all' && c.project !== activeFilters.project) return false;
                if (!matchesTimeframe(c.datetime)) return false;
                if (searchVal) {
                    const match = (c.project && c.project.toLowerCase().includes(searchVal)) ||
                                  (c.hash && c.hash.toLowerCase().includes(searchVal)) ||
                                  (c.message && c.message.toLowerCase().includes(searchVal));
                    if (!match) return false;
                }
                return true;
            });

            const fallback = document.getElementById('git-disabled-fallback');
            const wrapper = document.getElementById('git-correlation-table-wrapper');

            if (allCommits.length === 0) {
                wrapper.style.display = 'none';
                fallback.style.display = 'flex';
            } else {
                wrapper.style.display = 'block';
                fallback.style.display = 'none';

                if (commits.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:2rem; color:var(--text-muted);">No commits match active filters.</td></tr>';
                } else {
                    commits.forEach(c => {
                        const tr = document.createElement('tr');
                        tr.className = 'clickable-row';
                        tr.onclick = () => drilldownRepo(c.project);
                        tr.innerHTML = `
                            <td><span style="font-weight:700;">${escapeHtml(c.project)}</span></td>
                            <td><span class="pill pill-purple">${escapeHtml(c.hash)}</span></td>
                            <td><span class="pill">${escapeHtml(c.branch)}</span></td>
                            <td style="white-space:nowrap; font-size:0.75rem; color:var(--text-secondary);">${escapeHtml(c.datetime)}</td>
                            <td style="font-weight:500; max-width:240px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(c.message)}</td>
                            <td style="text-align:right;">${c.requests}</td>
                            <td style="text-align:right; font-family:monospace; font-weight:600;" class="text-orange">${formatNumber(c.tokens)}</td>
                            <td style="text-align:right; font-size:0.8rem; font-weight:600; color:var(--accent-cyan);">${formatDuration(c.coding_time)}</td>
                            <td style="text-align:right; font-family:monospace; color:var(--text-secondary);">$${c.cost.toFixed(3)}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                }
            }
        }

        // ================= EXPORT HUB DOWNLOADS =================
        function downloadJSONExport() {
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(TELEMETRY_DATA, null, 2));
            const dlAnchor = document.createElement('a');
            dlAnchor.setAttribute("href", dataStr);
            dlAnchor.setAttribute("download", "observatory_telemetry_report.json");
            document.body.appendChild(dlAnchor);
            dlAnchor.click();
            dlAnchor.remove();
        }

        function downloadCSVExport(type) {
            let csvContent = "";
            let filename = "";

            if (type === 'repos') {
                csvContent = "Repository,Total Tokens,Input,Output,Cache Read,Requests,Sessions,Cache Ratio %\\n";
                TELEMETRY_DATA.repositories.forEach(r => {
                    csvContent += `"${r.repository}",${r.tokens},${r.input},${r.output},${r.cache_read},${r.requests},${r.sessions},${(r.cache_ratio*100).toFixed(1)}\\n`;
                });
                filename = "observatory_repositories_export.csv";
            } else {
                csvContent = "Session ID,Repository,Start,End,Duration (s),Turns,Tokens,Input,Output,Cost USD\\n";
                TELEMETRY_DATA.sessions.forEach(s => {
                    csvContent += `"${s.session_id}","${s.project}","${s.start}","${s.end}",${s.duration},${s.requests},${s.total_tokens},${s.input},${s.output},${s.estimated_cost.toFixed(4)}\\n`;
                });
                filename = "observatory_sessions_export.csv";
            }

            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const dlAnchor = document.createElement('a');
            dlAnchor.setAttribute("href", url);
            dlAnchor.setAttribute("download", filename);
            document.body.appendChild(dlAnchor);
            dlAnchor.click();
            dlAnchor.remove();
        }

        function downloadMarkdownExport() {
            const go = TELEMETRY_DATA.global_overview;
            const prod = TELEMETRY_DATA.productivity_metrics;
            
            let md = `# AI Engineering Observatory - Token Telemetry Summary\\n`;
            md += `Generated: ${new Date().toLocaleString()}\\n\\n`;
            
            md += `## Global Performance\\n`;
            md += `- Total Tokens: ${formatNumber(go.total_tokens)}\\n`;
            md += `- Cached Tokens: ${formatNumber(go.cached_tokens)} (${go.cache_hit_pct.toFixed(1)}% hit rate)\\n`;
            md += `- Total Sessions / API Calls: ${go.sessions_count} / ${go.requests_count}\\n`;
            md += `- Retail API Cost: $${go.estimated_cost.toFixed(2)}\\n`;
            md += `- Saved Costs: $${go.estimated_savings.toFixed(2)}\\n\\n`;
            
            md += `## Repository Overview\\n`;
            md += `| Repository | Tokens | Sessions | Cache Ratio % |\\n`;
            md += `| --- | --- | --- | --- |\\n`;
            TELEMETRY_DATA.repositories.forEach(r => {
                md += `| ${r.repository} | ${formatNumber(r.tokens)} | ${r.sessions} | ${(r.cache_ratio*100).toFixed(1)}% |\\n`;
            });
            
            const blob = new Blob([md], { type: 'text/markdown;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const dlAnchor = document.createElement('a');
            dlAnchor.setAttribute("href", url);
            dlAnchor.setAttribute("download", "observatory_telemetry_summary.md");
            document.body.appendChild(dlAnchor);
            dlAnchor.click();
            dlAnchor.remove();
        }

        function triggerPDFPrint() {
            // Trigger standard browser print window, which matches printing media layouts
            window.print();
        }
    </script>
</body>
</html>
"""
    
    # Safely inject JSON data and variables into script
    # Escape < > & so they can't prematurely close the <script> tag or break innerHTML
    json_str = json.dumps(report_data)
    json_str = json_str.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    html_content = html_template.replace("__TELEMETRY_DATA_JSON__", json_str)
    html_content = html_content.replace("__WATCH_MODE_ACTIVE__", "true" if watch_mode else "false")

    # Render the headline cards with real values in the initial HTML. The
    # browser still recomputes them for filters, but a delayed/failed client
    # render must never leave the user staring at misleading zero placeholders.
    overview = report_data.get("global_overview", {})
    def compact_number(value):
        value = value or 0
        if value >= 1_000_000_000: return f"{value / 1_000_000_000:.2f}B"
        if value >= 1_000_000: return f"{value / 1_000_000:.2f}M"
        if value >= 1_000: return f"{value / 1_000:.1f}k"
        return f"{value:,}"
    initial_metrics = {
        "stat-total-tokens": compact_number(overview.get("total_tokens")),
        "stat-input-tokens": compact_number(overview.get("total_input")),
        "stat-output-tokens": compact_number(overview.get("total_output")),
        "stat-cached-tokens": compact_number(overview.get("cached_tokens")),
        "stat-cache-hit-pct": f"{overview.get('cache_hit_pct', 0):.1f}%",
        "stat-cost": f"${overview.get('estimated_cost', 0):.2f}",
        "stat-savings": f"${overview.get('estimated_savings', 0):.2f}",
        "stat-sessions": f"{overview.get('sessions_count', 0):,}",
        "stat-requests": f"{overview.get('requests_count', 0):,}",
        "stat-active-repos": f"{overview.get('active_repositories_count', 0):,}",
        "stat-active-models": f"{overview.get('active_models_count', 0):,}",
        "stat-active-tools": f"{overview.get('active_tools_count', 0):,}",
        "stat-local-tokens": compact_number((overview.get("local_inference") or {}).get("total_tokens")),
        "stat-cloud-avoidance": f"${(overview.get('local_inference') or {}).get('cloud_cost_avoidance', 0):.4f}",
    }
    for element_id, value in initial_metrics.items():
        html_content = html_content.replace(
            f'id="{element_id}">0</', f'id="{element_id}">{value}</'
        ).replace(
            f'id="{element_id}">0.0</', f'id="{element_id}">{value}</'
        ).replace(
            f'id="{element_id}">0%</', f'id="{element_id}">{value}'
        ).replace(
            f'id="{element_id}">$0.00</', f'id="{element_id}">{value}</'
        ).replace(
            f'id="{element_id}">$0.0000</', f'id="{element_id}">{value}</'
        )

    html_content = html_content.replace("__SCOPE_PROVIDER__", compact_number(overview.get("provider_reported_tokens", overview.get("total_tokens", 0))))
    html_content = html_content.replace("__SCOPE_EVENTS__", compact_number(overview.get("local_event_tokens", 0)))
    html_content = html_content.replace("__SCOPE_GAP__", compact_number(overview.get("coverage_gap_tokens", 0)))
    gap = overview.get("coverage_gap_tokens", 0) or 0
    hint_style = "display:block;" if gap > 0 else "display:none;"
    html_content = html_content.replace("__SCOPE_HINT_STYLE__", hint_style)
    
    with open(output_path, "w", encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Observatory HTML generated successfully at: {output_path}")

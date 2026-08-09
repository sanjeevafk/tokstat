# exporter.py
import csv
import json
import os
from datetime import datetime

import fpdf

from . import utils


def clean_txt(text):
    """
    Cleans text to be ascii-safe for standard FPDF fonts (Helvetica, Times, Courier).
    """
    return str(text).encode('ascii', 'ignore').decode('ascii')

class TokenTrackerPDF(fpdf.FPDF):
    def header(self):
        # Draw header banner
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(255, 122, 0) # Orange brand color
        self.cell(0, 10, 'AI Engineering Observatory - Telemetry Report', border=0, ln=1, align='L')
        self.set_font('Helvetica', 'I', 9)
        self.set_text_color(100, 110, 130)
        self.cell(0, 5, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | TokStat Telemetry', border=0, ln=1, align='L')
        self.line(10, 26, 200, 26)
        self.ln(6)

    def footer(self):
        # Page numbers
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', border=0, ln=0, align='C')

def format_tokens(num):
    if num >= 1000000000: return f"{(num / 1000000000):.2f}B"
    if num >= 1000000: return f"{(num / 1000000):.2f}M"
    if num >= 1000: return f"{(num / 1000):.1f}k"
    return str(num)

def export_json(report_data, path):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        print(f"Exported JSON to {path}")
        return True
    except Exception as e:
        print(f"Failed to export JSON: {e}")
        return False

def export_csv(report_data, base_dir):
    try:
        # 1. Export Repositories CSV
        repo_path = os.path.join(base_dir, "repositories.csv")
        with open(repo_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Repository", "Total Tokens", "Input Tokens", "Output Tokens", "Cache Read Tokens", "Requests", "Sessions", "Cache Ratio %", "Commits Count", "Branch"])
            for r in report_data["repositories"]:
                writer.writerow([
                    r["repository"], r["tokens"], r["input"], r["output"], r["cache_read"],
                    r["requests"], r["sessions"], f"{r['cache_ratio']*100:.1f}", r["commits_count"], r["branch"] or ""
                ])

        # 2. Export Sessions CSV
        session_path = os.path.join(base_dir, "sessions.csv")
        with open(session_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Session ID", "Project/Repo", "Start Time", "End Time", "Duration (sec)", "Requests", "Total Tokens", "Input Tokens", "Output Tokens", "Cache Read Tokens", "Estimated Cost USD", "Cached Savings USD"])
            for s in report_data["sessions"]:
                writer.writerow([
                    s["session_id"], s["project"], s["start"], s["end"], s["duration"], s["requests"],
                    s["total_tokens"], s["input"], s["output"], s["cache_read"], f"{s['estimated_cost']:.4f}", f"{s['estimated_savings']:.4f}"
                ])
                
        # 3. Export Local Models CSV (only when local inference data exists)
        li = (report_data.get("global_overview") or {}).get("local_inference") or {}
        if li.get("total_tokens"):
            local_path = os.path.join(base_dir, "local_models.csv")
            with open(local_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Model", "Total Tokens", "Requests", "Cloud Cost Avoidance USD"])
                for m in li.get("models_detail", []):
                    writer.writerow([m["model"], m["tokens"], m["requests"], f"{li['cloud_cost_avoidance']:.4f}"])

        print(f"Exported CSVs to {base_dir} (repositories.csv, sessions.csv"
              + (", local_models.csv)" if li.get("total_tokens") else ")"))
        return True
    except Exception as e:
        print(f"Failed to export CSVs: {e}")
        return False

def export_markdown(report_data, path):
    try:
        go = report_data["global_overview"]
        prod = report_data["productivity_metrics"]
        
        md = []
        md.append("# AI Engineering Observatory - Token Telemetry Report")
        md.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        md.append("## Global Overview")
        md.append(f"- **Total Tokens:** {format_tokens(go['total_tokens'])}")
        md.append(f"- **Total Input / Output:** {format_tokens(go['total_input'])} / {format_tokens(go['total_output'])}")
        md.append(f"- **Cached Tokens:** {format_tokens(go['cached_tokens'])} ({go['cache_hit_pct']:.1f}% hit rate)")
        md.append(f"- **Total Requests:** {go['requests_count']:,}")
        md.append(f"- **Total Sessions:** {go['sessions_count']:,}")
        md.append(f"- **Estimated Retail Cost:** ${go['estimated_cost']:.2f}")
        md.append(f"- **Estimated Cached Savings:** ${go['estimated_savings']:.2f}")
        md.append(f"- **Active Repos / Models / Tools:** {go['active_repositories_count']} / {go['active_models_count']} / {go['active_tools_count']}")
        md.append(f"- **Avg Context Size / Avg Request Size:** {format_tokens(go['avg_context_size'])} / {format_tokens(go['avg_tokens_per_request'])}")
        md.append(f"- **Peak Usage Day:** {go['peak_usage_day']} ({format_tokens(go['peak_usage_tokens'])} tokens)")
        md.append(f"- **Longest Coding Session:** {go['longest_session_duration'] // 60} minutes")
        md.append("")
        
        li = go.get("local_inference") or {}
        if li.get("total_tokens"):
            md.append("## Local Inference (On-Premise)")
            md.append(f"- **Local Tokens:** {format_tokens(li['total_tokens'])}")
            md.append(f"- **Local Requests:** {li.get('requests', 0):,}")
            md.append(f"- **Cloud Cost Avoidance:** ${li.get('cloud_cost_avoidance', 0):.4f}")
            md.append(f"- **Local Models:** {', '.join(li.get('models_used', [])) or 'N/A'}")
            md.append("")
        
        md.append("## Repository Analytics")
        md.append("| Repository | Total Tokens | Requests | Sessions | Cache Ratio % | Commits | Branch |")
        md.append("| --- | --- | --- | --- | --- | --- | --- |")
        for r in report_data["repositories"]:
            md.append(f"| {r['repository']} | {format_tokens(r['tokens'])} | {r['requests']} | {r['sessions']} | {r['cache_ratio']*100:.1f}% | {r['commits_count']} | {r['branch'] or 'N/A'} |")
        md.append("")
        
        md.append("## Model Analytics")
        md.append("| Model Name | Total Tokens | Requests | Average Context | Average Output | Cache Ratio % | Cost |")
        md.append("| --- | --- | --- | --- | --- | --- | --- |")
        for m in report_data["models"]:
            md.append(f"| {m['model_name']} | {format_tokens(m['total_tokens'])} | {m['requests']} | {format_tokens(m['average_context'])} | {format_tokens(m['average_completion'])} | {m['average_cache_hit']*100:.1f}% | ${m['estimated_cost']:.2f} |")
        md.append("")

        md.append("## Tool Analytics")
        md.append("| Tool Name | Total Tokens | Requests | Cache % | Repos | Models | Avg Session Length |")
        md.append("| --- | --- | --- | --- | --- | --- | --- |")
        for t in report_data["tools"]:
            repos_str = ", ".join(t["repositories"][:3]) + ("..." if len(t["repositories"]) > 3 else "")
            norm_models = [utils.normalize_model_display_name(m) for m in t["models"]]
            models_str = ", ".join(norm_models[:2]) + ("..." if len(norm_models) > 2 else "")
            md.append(f"| {t['display_name']} | {format_tokens(t['total_tokens'])} | {t['requests']} | {t['cache_ratio']*100:.1f}% | {repos_str or 'N/A'} | {models_str or 'N/A'} | {t['avg_session_length']//60}m |")
        md.append("")

        md.append("## Productivity Metrics")
        md.append(f"- **Output/Input Ratio:** {prod['output_input_ratio']:.3f}")
        md.append(f"- **Cache Savings:** ${prod['cache_savings']:.2f}")
        md.append(f"- **Tokens per Commit (Avg):** {format_tokens(prod['tokens_per_request'])} / request")
        md.append(f"- **Sessions per Day:** {prod['sessions_per_day']:.2f}")
        md.append(f"- **Avg Session Duration:** {prod['average_coding_session_length'] // 60} minutes")
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write("\n".join(md))
        print(f"Exported Markdown report to {path}")
        return True
    except Exception as e:
        print(f"Failed to export Markdown: {e}")
        return False

def export_pdf(report_data, path):
    try:
        go = report_data["global_overview"]
        
        pdf = TokenTrackerPDF()
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # 1. Section: Overview
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_fill_color(240, 243, 246)
        pdf.cell(0, 8, ' 1. Global Overview Metrics', ln=1, fill=True)
        pdf.ln(3)
        
        pdf.set_font('Helvetica', '', 10)
        
        # Define summary metrics
        metrics = [
            ("Total Tokens Used:", f"{go['total_tokens']:,}", "Active Repositories:", f"{go['active_repositories_count']}"),
            ("Input Tokens:", f"{go['total_input']:,}", "Active Models:", f"{go['active_models_count']}"),
            ("Output Tokens:", f"{go['total_output']:,}", "Active Coding Tools:", f"{go['active_tools_count']}"),
            ("Cached Tokens (Hit %):", f"{go['cached_tokens']:,} ({go['cache_hit_pct']:.1f}%)", "Average Context Size:", f"{go['avg_context_size']:,}"),
            ("Total API Requests:", f"{go['requests_count']:,}", "Average Tokens/Req:", f"{go['avg_tokens_per_request']:,}"),
            ("Total Telemetry Sessions:", f"{go['sessions_count']:,}", "Busiest Coding Day:", f"{report_data['time_analytics']['busiest_coding_day']}"),
            ("Estimated Retail Cost:", f"${go['estimated_cost']:.2f}", "Peak Usage Day:", f"{go['peak_usage_day']}"),
            ("Estimated Cache Savings:", f"${go['estimated_savings']:.2f}", "Longest Session:", f"{go['longest_session_duration'] // 60} mins")
        ]
        
        for m in metrics:
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(45, 6, clean_txt(m[0]), 0, 0)
            pdf.set_font('Helvetica', '', 9)
            pdf.cell(45, 6, clean_txt(m[1]), 0, 0)
            
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(45, 6, clean_txt(m[2]), 0, 0)
            pdf.set_font('Helvetica', '', 9)
            pdf.cell(45, 6, clean_txt(m[3]), 0, 1)
            
        li = go.get("local_inference") or {}
        if li.get("total_tokens"):
            pdf.ln(3)
            pdf.set_font('Helvetica', 'B', 12)
            pdf.set_fill_color(240, 243, 246)
            pdf.cell(0, 8, ' Local Inference (On-Premise)', ln=1, fill=True)
            pdf.ln(3)
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(0, 6, clean_txt(
                f"Local Tokens: {li['total_tokens']:,} | Requests: {li.get('requests', 0)} | "
                f"Cloud Cost Avoidance: ${li.get('cloud_cost_avoidance', 0):.4f}"
            ), ln=1)
            pdf.cell(0, 6, clean_txt(
                f"Local Models: {', '.join(li.get('models_used', [])) or 'N/A'}"
            ), ln=1)
            pdf.ln(4)
        
        # 2. Section: Repositories
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, ' 2. Repository Token Breakdown', ln=1, fill=True)
        pdf.ln(3)
        
        # Table Headers
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(50, 6, 'Repository Name', 1, 0, 'L')
        pdf.cell(25, 6, 'Total Tokens', 1, 0, 'R')
        pdf.cell(20, 6, 'Requests', 1, 0, 'R')
        pdf.cell(20, 6, 'Sessions', 1, 0, 'R')
        pdf.cell(25, 6, 'Cache Ratio %', 1, 0, 'R')
        pdf.cell(20, 6, 'Commits', 1, 0, 'R')
        pdf.cell(30, 6, 'Active Branch', 1, 1, 'L')
        
        pdf.set_font('Helvetica', '', 8)
        for r in report_data["repositories"][:15]: # Limit to top 15 in PDF
            pdf.cell(50, 5, clean_txt(r["repository"][:28]), 1, 0, 'L')
            pdf.cell(25, 5, clean_txt(format_tokens(r["tokens"])), 1, 0, 'R')
            pdf.cell(20, 5, clean_txt(str(r["requests"])), 1, 0, 'R')
            pdf.cell(20, 5, clean_txt(str(r["sessions"])), 1, 0, 'R')
            pdf.cell(25, 5, clean_txt(f"{r['cache_ratio']*100:.1f}%"), 1, 0, 'R')
            pdf.cell(20, 5, clean_txt(str(r["commits_count"])), 1, 0, 'R')
            pdf.cell(30, 5, clean_txt((r["branch"] or "N/A")[:18]), 1, 1, 'L')
            
        if len(report_data["repositories"]) > 15:
            pdf.cell(0, 5, f'... and {len(report_data["repositories"])-15} more repositories. Export to CSV for full list.', 0, 1, 'C')
            
        pdf.ln(6)
        
        # 3. Section: Models
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, ' 3. LLM Model Statistics', ln=1, fill=True)
        pdf.ln(3)
        
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(60, 6, 'Model Name', 1, 0, 'L')
        pdf.cell(25, 6, 'Total Tokens', 1, 0, 'R')
        pdf.cell(20, 6, 'Requests', 1, 0, 'R')
        pdf.cell(30, 6, 'Avg Context (In)', 1, 0, 'R')
        pdf.cell(30, 6, 'Avg Comp (Out)', 1, 0, 'R')
        pdf.cell(25, 6, 'Cache Ratio %', 1, 1, 'R')
        
        pdf.set_font('Helvetica', '', 8)
        for m in report_data["models"][:12]:
            pdf.cell(60, 5, clean_txt(m["model_name"][:35]), 1, 0, 'L')
            pdf.cell(25, 5, clean_txt(format_tokens(m["total_tokens"])), 1, 0, 'R')
            pdf.cell(20, 5, clean_txt(str(m["requests"])), 1, 0, 'R')
            pdf.cell(30, 5, clean_txt(format_tokens(m["average_context"])), 1, 0, 'R')
            pdf.cell(30, 5, clean_txt(format_tokens(m["average_completion"])), 1, 0, 'R')
            pdf.cell(25, 5, clean_txt(f"{m['average_cache_hit']*100:.1f}%"), 1, 1, 'R')
            
        pdf.ln(6)
        
        # 4. Section: Tools
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, ' 4. Coding Tool Analytics', ln=1, fill=True)
        pdf.ln(3)
        
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(60, 6, 'Tool / Agent Name', 1, 0, 'L')
        pdf.cell(30, 6, 'Total Tokens', 1, 0, 'R')
        pdf.cell(25, 6, 'Requests', 1, 0, 'R')
        pdf.cell(25, 6, 'Cache Hit %', 1, 0, 'R')
        pdf.cell(50, 6, 'Primary Model', 1, 1, 'L')
        
        pdf.set_font('Helvetica', '', 8)
        for t in report_data["tools"]:
            primary_model = utils.normalize_model_display_name(t["models"][0]) if t["models"] else "Unknown"
            pdf.cell(60, 5, clean_txt(t["display_name"]), 1, 0, 'L')
            pdf.cell(30, 5, clean_txt(format_tokens(t["total_tokens"])), 1, 0, 'R')
            pdf.cell(25, 5, clean_txt(str(t["requests"])), 1, 0, 'R')
            pdf.cell(25, 5, clean_txt(f"{t['cache_ratio']*100:.1f}%"), 1, 0, 'R')
            pdf.cell(50, 5, clean_txt(primary_model[:28]), 1, 1, 'L')
            
        pdf.output(path)
        print(f"Exported PDF report to {path}")
        return True
    except Exception as e:
        print(f"Failed to export PDF: {e}")
        import traceback
        traceback.print_exc()
        return False

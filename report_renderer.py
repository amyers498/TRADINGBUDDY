"""Utilities for rendering markdown trade reports as styled HTML."""
from __future__ import annotations

from datetime import date

from markdown import markdown


STYLE = """
body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #0f172a; color: #e2e8f0; margin: 0; padding: 2rem; }
.container { max-width: 800px; margin: 0 auto; background: #1e293b; border-radius: 16px; box-shadow: 0 20px 45px rgba(15,23,42,0.6); padding: 2.5rem; }
h1 { color: #38bdf8; margin-bottom: 0.5rem; }
h2 { color: #f472b6; border-bottom: 1px solid rgba(148,163,184,0.3); padding-bottom: 0.25rem; }
p, li { line-height: 1.6; }
ul { padding-left: 1.5rem; }
strong { color: #fbbf24; }
blockquote { border-left: 4px solid #38bdf8; margin: 1rem 0; padding-left: 1rem; color: #cbd5f5; }
.badge { display: inline-block; background: linear-gradient(90deg,#38bdf8,#818cf8); color: #0f172a; padding: 0.2rem 0.75rem; border-radius: 999px; font-size: 0.85rem; font-weight: 600; }
section { margin-bottom: 1.5rem; padding: 1rem; border-radius: 12px; background: rgba(148,163,184,0.08); }
footer { text-align: center; font-size: 0.85rem; color: #94a3b8; margin-top: 2rem; }
"""


def render_html_report(title: str, report_markdown: str, report_date: date | None = None) -> str:
    """Wrap Gemini markdown output with a modern HTML shell."""
    body = markdown(report_markdown, extensions=["extra", "sane_lists"])
    subtitle = (
        f"<p class='badge'>Generated for {report_date:%B %d, %Y}</p>"
        if report_date
        else ""
    )
    return f"""
    <html>
        <head>
            <meta charset='utf-8'/>
            <style>{STYLE}</style>
        </head>
        <body>
            <div class="container">
                <h1>{title}</h1>
                {subtitle}
                {body}
                <footer>Trade Buddy Auto-reports</footer>
            </div>
        </body>
    </html>
    """.strip()

"""Email digest over SMTP (Gmail app password by default).

Secrets: SMTP_USER, SMTP_APP_PASSWORD, ALERT_EMAIL_TO. Optional: SMTP_HOST, SMTP_PORT.
"""
from __future__ import annotations

import html
import os
import smtplib
from email.message import EmailMessage

from ..models import Job


def configured() -> bool:
    return all(os.environ.get(k) for k in ("SMTP_USER", "SMTP_APP_PASSWORD", "ALERT_EMAIL_TO"))


def render(jobs: list[Job], dashboard_url: str = "") -> tuple[str, str]:
    from . import ELIGIBILITY_LABEL, format_stipend

    rows_txt, rows_html = [], []
    for j in jobs:
        where = " · ".join(j.locations[:2]) or "Remote"
        elig = ELIGIBILITY_LABEL.get(j.eligibility, j.eligibility)
        stip = format_stipend(j)
        rows_txt.append(f"- {j.company}: {j.title}\n  {where} | {elig} | {stip}\n  {j.url}")
        rows_html.append(
            '<tr><td style="padding:16px 0;border-bottom:1px solid #e3d6c5">'
            f'<div style="font-size:12px;font-weight:600;text-transform:uppercase;color:#615f5c">'
            f'{html.escape(j.company)}</div>'
            f'<a href="{html.escape(j.url)}" style="font-size:18px;color:#1d1e1c;text-decoration:none">'
            f'{html.escape(j.title)}</a>'
            f'<div style="font-size:14px;color:#615f5c;margin-top:4px">{html.escape(where)} · '
            f'{html.escape(elig)} · {html.escape(stip)}</div></td></tr>'
        )
    link = f'<p><a href="{html.escape(dashboard_url)}" style="display:inline-block;background:#fa5d00;color:#fff;' \
           f'padding:12px 24px;border-radius:16px;text-decoration:none;font-size:16px;font-weight:600">Open the tracker</a></p>' if dashboard_url else ""
    body_html = (
        '<div style="font-family:Inter,Helvetica,Arial,sans-serif;background:#fff8f1;padding:24px">'
        '<div style="max-width:640px;margin:auto;background:#fff;border:1px solid #e3d6c5;border-radius:20px;padding:32px">'
        f'<h1 style="font-family:Georgia,serif;font-weight:400;font-size:32px;color:#1d1e1c;margin:0 0 8px">{len(jobs)} new internship'
        f'{"s" if len(jobs) != 1 else ""}</h1><table style="width:100%;border-collapse:collapse">'
        + "".join(rows_html) + f"</table>{link}</div></div>"
    )
    body_txt = "\n\n".join(rows_txt) + (f"\n\nDashboard: {dashboard_url}" if dashboard_url else "")
    return body_txt, body_html


def send(jobs: list[Job], dashboard_url: str = "") -> None:
    msg = EmailMessage()
    first = jobs[0]
    more = f" +{len(jobs) - 1} more" if len(jobs) > 1 else ""
    msg["Subject"] = f"[Internships] {first.company}: {first.title}{more}"[:200]
    msg["From"] = os.environ["SMTP_USER"]
    msg["To"] = os.environ["ALERT_EMAIL_TO"]
    text, body = render(jobs, dashboard_url)
    msg.set_content(text)
    msg.add_alternative(body, subtype="html")
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_APP_PASSWORD"])
        smtp.send_message(msg)

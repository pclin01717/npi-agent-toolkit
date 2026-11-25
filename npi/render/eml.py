"""產生 .eml 草稿（X-Unsent: 1）。內文由 jinja2 範本產生，第一行是「Subject: …」。"""
import datetime
import email
import json
from email import policy
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, getaddresses
from pathlib import Path

import jinja2

from . import TEMPLATES

PEOPLE = Path(__file__).resolve().parents[2] / "config" / "people.json"
_env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES), keep_trailing_newline=True,
                          trim_blocks=True, lstrip_blocks=True, undefined=jinja2.StrictUndefined)


def people():
    return json.loads(PEOPLE.read_text(encoding="utf-8"))


def render_text(template, **data):
    text = _env.get_template(template).render(**data)
    first, _, body = text.partition("\n")
    if not first.startswith("Subject: "):
        raise ValueError(f"{template} 第一行要是 Subject:")
    return first[len("Subject: "):].strip(), body.lstrip("\n")


def write_eml(path, sender, to, cc, subject, body, date):
    msg = EmailMessage()
    msg["From"] = formataddr((sender["name"], sender["email"]))
    msg["To"] = ", ".join(formataddr((p["name"], p["email"])) for p in to)
    if cc:
        msg["Cc"] = ", ".join(formataddr((p["name"], p["email"])) for p in cc)
    msg["Subject"] = subject
    day = datetime.date.fromisoformat(date)
    msg["Date"] = format_datetime(datetime.datetime(day.year, day.month, day.day, 10, 0,   # PLANS P53
                                                    tzinfo=datetime.timezone(datetime.timedelta(hours=8))))
    msg["X-Unsent"] = "1"
    msg.set_content(body)
    Path(path).write_bytes(msg.as_bytes())
    return Path(path)


def read_eml(path):
    msg = email.message_from_bytes(Path(path).read_bytes(), policy=policy.default)
    part = msg.get_body(preferencelist=("plain",))
    return {"file": Path(path).name, "subject": str(msg["Subject"]),
            "to": [a for _, a in getaddresses([str(msg["To"] or "")])],
            "cc": [a for _, a in getaddresses([str(msg["Cc"] or "")])],
            "body": part.get_content() if part else ""}

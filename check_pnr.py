import json, os, smtplib, requests
from email.message import EmailMessage

PNR = os.environ["PNR"].strip()
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
LABEL = os.environ.get("LABEL", "PNR")


def fetch_status():
    url = os.environ["API_URL"].strip().replace("{pnr}", PNR)
    r = requests.get(
        url,
        headers={
            "x-rapidapi-key": os.environ["API_KEY"].strip(),
            "x-rapidapi-host": os.environ["API_HOST"].strip(),
        },
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError("API returned success=false")
    d = body["data"]
    return {
        "train": f"{d['trainNumber']} {d['trainName']}",
        "date": d["dateOfJourney"],
        "chart": d["chartStatus"],
        "passengers": {
            str(p["passengerSerialNumber"]): p["currentStatusDetails"]
            for p in d["passengerList"]
        },
    }


def send_mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ["GMAIL_USER"].strip()
    msg["To"] = os.environ["MAIL_TO"].strip()
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(
            os.environ["GMAIL_USER"].strip(),
            os.environ["GMAIL_APP_PASSWORD"].replace(" ", ""),
        )
        s.send_message(msg)


new = fetch_status()
old = None
if os.path.exists(STATE_FILE):
    try:
        old = json.load(open(STATE_FILE))
        if "passengers" not in old:
            old = None
    except ValueError:
        old = None

summary = "\n".join(f"Passenger {k}: {v}" for k, v in new["passengers"].items())
header = f"{new['train']} | Journey: {new['date']}"
tag = f"[{LABEL}]"

if old is None:
    send_mail(f"{tag} PNR tracking started", f"{header}\nChart: {new['chart']}\n\n{summary}")
    print(f"{tag} first run, tracking started")
else:
    lines = []
    for k, v in new["passengers"].items():
        before = old["passengers"].get(k)
        if before != v:
            lines.append(f"Passenger {k}: {before} -> {v}")
    if old["chart"] != new["chart"]:
        lines.append(f"Chart: {old['chart']} -> {new['chart']}")
    if lines:
        send_mail(
            f"{tag} PNR status changed",
            f"{header}\n\n" + "\n".join(lines) + f"\n\nCurrent:\n{summary}",
        )
        print(f"{tag} change detected, mail sent")
    else:
        print(f"{tag} no change")

json.dump(new, open(STATE_FILE, "w"), indent=2)

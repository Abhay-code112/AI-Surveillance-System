"""
alert.py — Email + Telegram alert system

Setup:
    Email: Gmail App Password needed
    Telegram: Bot token + chat ID needed
"""

import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


# ── EMAIL CONFIG ───────────────────────────────────────────────
EMAIL_SENDER   = ""
EMAIL_PASSWORD = ""       # Gmail App Password
EMAIL_RECEIVER = "motarolafusion@gmail.com"  # Who gets the alert

# ── TELEGRAM CONFIG ────────────────────────────────────────────
TELEGRAM_TOKEN   = ""        # From @BotFather
TELEGRAM_CHAT_ID = ""          # Your chat ID


def send_email_alert(activity, confidence, camera="Webcam"):
    """Send Gmail alert for suspicious activity."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        subject = f" ALERT: {activity} Detected!"
        body    = f"""
 SURVEILLANCE ALERT 
Activity Detected: {activity}
Confidence:        {confidence:.1%}
Camera:            {camera}
Time:              {timestamp}

This is an automated alert from your surveillance system.
Please review the footage immediately.

---
Surveillance Detection System
        """

        msg = MIMEMultipart()
        msg["From"]    = EMAIL_SENDER
        msg["To"]      = EMAIL_RECEIVER
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())

        print(f"  Email sent to {EMAIL_RECEIVER}")
        return True

    except Exception as e:
        print(f"  Email failed: {e}")
        return False


def send_telegram_alert(activity, confidence, camera="Webcam"):
    """Send Telegram bot alert."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = (
            f" *SURVEILLANCE ALERT* 🚨\n\n"
            f" *{activity}* Detected!\n"
            f" Confidence: {confidence:.1%}\n"
            f" Camera: {camera}\n"
            f" Time: {timestamp}\n\n"
            f"Please review footage immediately!"
        )

        url = (f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
               f"/sendMessage")
        response = requests.post(url, json={
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       message,
            "parse_mode": "Markdown"
        }, timeout=10)

        if response.status_code == 200:
            print(f"   Telegram alert sent!")
            return True
        else:
            print(f"  Telegram failed: {response.text}")
            return False

    except Exception as e:
        print(f"  Telegram failed: {e}")
        return False


def send_alert(activity, confidence, camera="Webcam"):
    """Send both Email + Telegram alerts."""
    print(f"\n Sending alerts for: {activity} ({confidence:.1%})")
    email_ok    = send_email_alert(activity, confidence, camera)
    telegram_ok = send_telegram_alert(activity, confidence, camera)
    return email_ok, telegram_ok


if __name__ == "__main__":
    # Test alerts
    print("Testing alert system...")
    send_alert("Fighting", 0.89, "Camera 1")

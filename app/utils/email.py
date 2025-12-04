import smtplib
import traceback
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

from app.config import settings


def send_email_qq(
    recipient_emails,
    subject,
    body,
    sender_name=None,
) -> bool:
    # 使用你提供的 QQ 邮箱逻辑，但从 .env 读取账号密码
    smtp_server = settings.EMAIL_SMTP_SERVER
    port = settings.EMAIL_SMTP_PORT
    sender_email = settings.EMAIL_SENDER
    sender_password = settings.EMAIL_PASSWORD
    sender_name = sender_name or settings.EMAIL_SENDER_NAME

    if isinstance(recipient_emails, str):
        recipient_emails = [recipient_emails]

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = formataddr(
        (str(Header(sender_name, "utf-8")), sender_email)
    )
    msg["To"] = Header(", ".join(recipient_emails), "utf-8")
    msg["Subject"] = Header(subject, "utf-8")

    is_send = False
    server = None
    try:
        server = smtplib.SMTP_SSL(smtp_server, port)
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_emails, msg.as_string())
        print("✅ 邮件发送成功")
        is_send = True
    except Exception:
        traceback.print_exc()
        print("❌ 发送失败")
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass
    return is_send

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.utils import parseaddr
from smtplib import SMTP_SSL, SMTPException
from socket import create_connection

logger: list[str] = []


def getTime() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def sendEmail(content: list[str]) -> None:
    mail_host = 'smtp.126.com'
    mail_user_full = os.environ.get('mail_user')
    mail_pass = os.environ.get('mail_pass')
    if not (mail_user_full and mail_pass):
        logger.append(f'[ERROR] {getTime()} 未找到可用邮箱！')
        raise OSError
    _, mail_user = parseaddr(mail_user_full)
    recv_list = [mail_user]
    recv_str = ', '.join(recv_list)
    subject = '服务器连通性提示'
    content_str = '\n'.join(content)
    body = (
        '监测到以下服务器节点可能下线，需要进一步排查。\n'
        f'{content_str}'
        '\n本邮件由腾讯云 SCF 发送，请勿回复\n'
    )
    message = MIMEText(body, 'plain', 'utf-8')
    message['From'] = mail_user_full
    message['To'] = recv_str
    message['Subject'] = subject
    try:
        smtpObj = SMTP_SSL(mail_host, 465)
        _ = smtpObj.login(mail_user, mail_pass)
        _ = smtpObj.sendmail(mail_user, recv_list, message.as_string())
    except SMTPException as e:
        logger.append(f'[ERROR] {getTime()} - 邮件发送失败！{type(e).__name__}: {e}')
        raise SMTPException from e


def test_url(host_list: list[str], port: int = 33890) -> None:
    errorinfo: list[str] = []
    for host in host_list:
        try:
            logger.append(f'[INFO] {getTime()} - {host}')
            with create_connection((host, port), timeout=3):
                continue
        except OSError as e:
            logger.append(f'[WARNING] {getTime()} - {host} - {type(e).__name__}: {e}')
            errorinfo.append(host)
    if errorinfo:
        sendEmail(errorinfo)


def main_handler(event, context) -> None:
    host_list = ['apple.cvm.xiaozhiyuqwq.top', 'banana.cvm.xiaozhiyuqwq.top']
    # host_list = ['182.254.222.77', '101.37.17.212']
    test_url(host_list)
    # print('\n'.join(logger))


if __name__ == '__main__':
    main_handler('', '')

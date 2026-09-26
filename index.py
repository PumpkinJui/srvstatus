import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.utils import parseaddr
from smtplib import SMTP_SSL, SMTPException
from socket import create_connection

from alibabacloud_alidns20150109 import models as alidns_20150109_models
from alibabacloud_alidns20150109.client import Client as Alidns20150109Client
from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_credentials.models import Config as CredentialConfig
from alibabacloud_tea_openapi import models as open_api_models
from darabonba.runtime import RuntimeOptions as util_runtime_options

logger: list[str] = []

def get_time() -> str:
    return (
        datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    )

def create_client() -> Alidns20150109Client:
    access_key_id = os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID')
    access_key_secret = os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
    role_arn = os.environ.get('ALIBABA_CLOUD_ROLE_ARN')
    if not (access_key_id and access_key_secret and role_arn):
        logger.append(f'[ERROR] {get_time()} 未找到阿里云信息！')
        raise OSError('未找到阿里云信息！')
    credentialsConfig = CredentialConfig(
        type='ram_role_arn',
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        role_arn=role_arn,
        role_session_name='scf',
        role_session_expiration=900,
    )
    credentialsClient = CredentialClient(credentialsConfig)
    config = open_api_models.Config(
        credential=credentialsClient, endpoint='alidns.aliyuncs.com'
    )
    return Alidns20150109Client(config)

def list_record(
    client: Alidns20150109Client,
) -> list[dict[str, str | int | bool]]:
    describe_sub_domain_records_request = (
        alidns_20150109_models.DescribeSubDomainRecordsRequest(
            sub_domain='mc2gslb.xiaozhiyuqwq.top'
        )
    )
    runtime = util_runtime_options()
    resp = client.describe_sub_domain_records_with_options(
        describe_sub_domain_records_request, runtime
    )
    return [item.__dict__ for item in list(resp.body.domain_records.record)]


def set_status(client: Alidns20150109Client) -> None:
    # client = create_client()
    set_domain_record_status_request = (
        alidns_20150109_models.SetDomainRecordStatusRequest(
            status='Disable', record_id='pgp123'
        )
    )
    runtime = util_runtime_options()
    resp = client.set_domain_record_status_with_options(
        set_domain_record_status_request, runtime
    )
    print(json.dumps(resp, default=str, indent=2))


def send_email(content: list[str], down: bool) -> None:
    mail_host = 'smtp.126.com'
    mail_user_full = os.environ.get('MAIL_USER')
    mail_pass = os.environ.get('MAIL_PASS')
    if not (mail_user_full and mail_pass):
        logger.append(f'[ERROR] {get_time()} 未找到可用邮箱！')
        raise OSError('未找到可用邮箱！')
    _, mail_user = parseaddr(mail_user_full)
    recv_list = [mail_user]
    recv_str = ', '.join(recv_list)
    subject = '服务器连通性提示'
    content_str = '\n'.join(content)
    body = (
        '监测到以下服务器节点已经下线，相关 DNS 记录已禁用。\n'
        if down
        else '监测到以下服务器节点已经上线，相关 DNS 记录已启用。\n'
    )
    body += f'{content_str}\n本邮件由腾讯云 SCF 自动发送，请勿回复\n'
    message = MIMEText(body, 'plain', 'utf-8')
    message['From'] = mail_user_full
    message['To'] = recv_str
    message['Subject'] = subject
    try:
        smtpObj = SMTP_SSL(mail_host, 465)
        _ = smtpObj.login(mail_user, mail_pass)
        _ = smtpObj.sendmail(mail_user, recv_list, message.as_string())
    except SMTPException as e:
        logger.append(f'[ERROR] {get_time()} - 邮件发送失败！{type(e).__name__}: {e}')
        raise SMTPException('邮件发送失败！') from e

def test_dns(error_hosts: list[str]) -> None:
    send_email(error_hosts, True)

def test_url(host_list: list[str], port: int = 33890) -> None:
    error_hosts: list[str] = []
    ok_hosts: list[str] = []
    for host in host_list:
        try:
            logger.append(f'[INFO] {get_time()} - {host} - 开始。')
            with create_connection((host, port), timeout=3):
                logger.append(f'[INFO] {get_time()} - {host} - 成功。')
                ok_hosts.append(host)
                continue
        except OSError as e:
            logger.append(f'[WARNING] {get_time()} - {host} - {type(e).__name__}: {e}')
            error_hosts.append(host)
    if error_hosts:
        print(error_hosts)

def main_handler(event: dict[str, str | int], context: dict[str, str | int]) -> None:
    host_list = [
        'apple.cvm.xiaozhiyuqwq.top',
        'banana.cvm.xiaozhiyuqwq.top',
        'cherry.cvm.xiaozhiyuqwq.top',
    ]
    test_url(host_list)
    # print('\n'.join(logger))

if __name__ == '__main__':
    main_handler({}, {})
    # print(list_record(create_client()))

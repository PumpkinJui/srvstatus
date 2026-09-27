import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from email.mime.text import MIMEText
from email.utils import parseaddr
from logging import DEBUG, Formatter, StreamHandler, getLogger, shutdown
from smtplib import SMTP_SSL, SMTPException
from socket import create_connection
from typing import cast

from alibabacloud_alidns20150109 import models as alidns_20150109_models
from alibabacloud_alidns20150109.client import Client as Alidns20150109Client
from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_credentials.models import Config as CredentialConfig
from alibabacloud_tea_openapi import models as open_api_models
from darabonba.runtime import RuntimeOptions as util_runtime_options


def create_client() -> Alidns20150109Client:
    access_key_id = os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID')
    access_key_secret = os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
    role_arn = os.environ.get('ALIBABA_CLOUD_ROLE_ARN')
    if not (access_key_id and access_key_secret and role_arn):
        raise OSError('未找到阿里云信息！')
    credentials_config = CredentialConfig(
        type='ram_role_arn',
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        role_arn=role_arn,
        role_session_name='scf',
        role_session_expiration=900,
    )
    credentials_client = CredentialClient(credentials_config)
    config = open_api_models.Config(
        credential=credentials_client, endpoint='alidns.aliyuncs.com'
    )
    return Alidns20150109Client(config)


def list_record(
    client: Alidns20150109Client,
) -> dict[str, tuple[str, str]]:
    logger.info('开始获取 DNS 记录。')
    describe_sub_domain_records_request = (
        alidns_20150109_models.DescribeSubDomainRecordsRequest(
            sub_domain='mc2gslb.xiaozhiyuqwq.top'
        )
    )
    runtime = util_runtime_options()
    resp = client.describe_sub_domain_records_with_options(
        describe_sub_domain_records_request, runtime
    )
    logger.info('成功获取 DNS 记录。')
    return {
        item.__dict__['value']: (item.__dict__['record_id'], item.__dict__['status'])
        for item in list(resp.body.domain_records.record)
    }


def set_status(client: Alidns20150109Client, record_id: str, status: str) -> None:
    set_domain_record_status_request = (
        alidns_20150109_models.SetDomainRecordStatusRequest(
            status=status, record_id=record_id
        )
    )
    runtime = util_runtime_options()
    resp = client.set_domain_record_status_with_options(
        set_domain_record_status_request, runtime
    )
    logger.info('%s: %s', record_id, cast(str, resp.body.status))


def write_email(content: dict[str, bool]) -> None:
    mail_user_full = os.environ.get('MAIL_USER')
    mail_pass = os.environ.get('MAIL_PASS')
    if not (mail_user_full and mail_pass):
        raise OSError('未找到可用邮箱！')
    _, mail_user = parseaddr(mail_user_full)
    recv_list = [mail_user]
    recv_str = ', '.join(recv_list)
    subject = '服务器连通性提示'
    content_lt: list[str] = []
    for host, real_status in content.items():
        content_lt.append(f'{host}：当前在线' if real_status else f'{host}：当前离线')
    content_str = '\n'.join(content_lt)
    body = (
        '监测到以下节点的 FRP 转发状态变化，DNS 记录已相应调整。\n\n'
        f'{content_str}\n\n'
        '本邮件由定时拨测脚本自动发送，请勿回复\n'
    )
    message = MIMEText(body, 'plain', 'utf-8')
    message['From'] = mail_user_full
    message['To'] = recv_str
    message['Subject'] = subject
    send_email(mail_user, mail_pass, recv_list, message)


def send_email(
    mail_user: str, mail_pass: str, recv_list: list[str], message: MIMEText
) -> None:
    mail_host = 'smtp.126.com'
    try:
        smtp_object = SMTP_SSL(mail_host, 465)
        _ = smtp_object.login(mail_user, mail_pass)
        _ = smtp_object.sendmail(mail_user, recv_list, message.as_string())
    except SMTPException as e:
        raise SMTPException('邮件发送失败！') from e


def test_dns(host_status: dict[str, bool]) -> None:
    client = create_client()
    switched: dict[str, bool] = {}
    for host, (record_id, remote_status) in list_record(client).items():
        local_status = host_status[host]
        if (local_status and remote_status.upper() == 'ENABLE') or (
            not local_status and remote_status.upper() == 'DISABLE'
        ):
            logger.info('%s 匹配状态 %s。', host, remote_status)
            continue
        if local_status:
            logger.warning('%s 拨测成功，而 DNS 状态为 %s。', host, remote_status)
            switched[host] = local_status
            set_status(client, record_id, 'Enable')
            continue
        logger.warning('%s 拨测成功，而 DNS 状态为 %s。', host, remote_status)
        switched[host] = local_status
        set_status(client, record_id, 'Disable')
    if switched:
        write_email(switched)


def test_url(host_list: list[str], port: int = 33890) -> None:
    host_status: dict[str, bool] = {}
    for host in host_list:
        try:
            logger.info('%s - 开始。', host)
            with create_connection((host, port), timeout=3):
                logger.info('%s - 成功。', host)
                host_status[host] = True
                continue
        except OSError as e:
            logger.warning('%s - %s: %s', host, type(e).__name__, e)
            host_status[host] = False
    test_dns(host_status)


def main_handler(event: dict[str, str | int], context: dict[str, str | int]) -> None:
    _ = (event, context)
    host_list = [
        'apple.cvm.xiaozhiyuqwq.top',
        'banana.cvm.xiaozhiyuqwq.top',
        'cherry.cvm.xiaozhiyuqwq.top',
    ]
    try:
        test_url(host_list)
    except Exception:
        logger.exception('未知异常。')
    finally:
        shutdown()


logger = getLogger(__name__)
logger.handlers.clear()
logger.setLevel(DEBUG)
formatter = Formatter('[%(levelname)s] - %(asctime)s - %(message)s')
stream_handler = StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

if __name__ == '__main__':
    main_handler({}, {})

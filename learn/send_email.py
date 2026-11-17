import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

# 邮件服务器域名（自行修改）
EMAIL_HOST = 'smtp.126.com'
# 邮件服务端口（通常是465）
EMAIL_PORT = 465
# 登录邮件服务器的账号（自行修改）
EMAIL_USER = 'c1542475200@126.com'
# 开通SMTP服务的授权码（自行修改）
EMAIL_AUTH = 'ZMQ4taubQiKBSBLd'


def send_email(*, to_users, subject='', content='', filenames=None):
    """发送邮件
    :param to_users: 收件人，多个收件人用英文分号进行分隔
    :param subject: 邮件的主题
    :param content: 邮件正文内容
    :param filenames: 附件要发送的文件路径列表
    """
    if filenames is None:
        filenames = []

    email = MIMEMultipart()
    email['From'] = EMAIL_USER  # ✅ 直接使用配置的账号
    email['To'] = to_users
    email['Subject'] = subject

    message = MIMEText(content, 'plain', 'utf-8')
    email.attach(message)

    for filename in filenames:
        with open(filename, 'rb') as file:
            pos = filename.rfind('/')
            display_filename = filename[pos + 1:] if pos >= 0 else filename
            display_filename = quote(display_filename)

            # ✅ MIMEApplication 原生接受 bytes，专用于二进制附件
            attachment = MIMEApplication(file.read())
            attachment['Content-Disposition'] = f'attachment; filename="{display_filename}"'
            email.attach(attachment)

    smtp = smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT)
    smtp.login(EMAIL_USER, EMAIL_AUTH)
    smtp.sendmail(EMAIL_USER, to_users.split(';'), email.as_string())  # ✅ 保持一致
    smtp.quit()  # ⚠️ 原代码缺少关闭连接，建议加上

send_email(to_users='1479016418@qq.com;1542475200@qq.com', subject='测试邮件', content='测试邮件内容'
           , filenames=[])

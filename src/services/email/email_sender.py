"""
邮件发送服务
提供 SMTP 邮件发送功能
"""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional, Tuple, Union

aiosmtplib: Any
try:
    import aiosmtplib as _aiosmtplib
except ImportError:
    AIOSMTPLIB_AVAILABLE = False
    aiosmtplib = None
else:
    AIOSMTPLIB_AVAILABLE = True
    aiosmtplib = _aiosmtplib


def _create_ssl_context() -> ssl.SSLContext:
    """创建 SSL 上下文，使用 certifi 证书或系统默认证书"""
    try:
        import certifi

        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    return context

from sqlalchemy.orm import Session

from src.core.crypto import crypto_service
from src.core.logger import logger
from src.services.system.config import SystemConfigService
from src.utils.async_utils import run_in_executor

from .email_template import EmailTemplate


class EmailSenderService:
    """邮件发送服务"""

    # SMTP 超时配置（秒）
    SMTP_TIMEOUT = 30

    @staticmethod
    def _get_smtp_config(db: Session) -> dict:
        """
        从数据库获取 SMTP 配置

        Args:
            db: 数据库会话

        Returns:
            SMTP 配置字典
        """
        # 获取加密的密码并解密
        encrypted_password = SystemConfigService.get_config(db, "smtp_password")
        smtp_password = None
        if encrypted_password:
            try:
                smtp_password = crypto_service.decrypt(encrypted_password, silent=True)
            except Exception:
                # 解密失败，可能是旧的未加密密码，直接使用
                smtp_password = encrypted_password

        config = {
            "smtp_host": SystemConfigService.get_config(db, "smtp_host"),
            "smtp_port": SystemConfigService.get_config(db, "smtp_port", default=587),
            "smtp_user": SystemConfigService.get_config(db, "smtp_user"),
            "smtp_password": smtp_password,
            "smtp_use_tls": SystemConfigService.get_config(db, "smtp_use_tls", default=True),
            "smtp_use_ssl": SystemConfigService.get_config(db, "smtp_use_ssl", default=False),
            "smtp_from_email": SystemConfigService.get_config(db, "smtp_from_email"),
            "smtp_from_name": SystemConfigService.get_config(db, "smtp_from_name", default="Aether"),
        }
        return config

    @staticmethod
    def _validate_smtp_config(config: dict) -> Tuple[bool, Optional[str]]:
        """
        验证 SMTP 配置

        Args:
            config: SMTP 配置字典

        Returns:
            (是否有效, 错误信息)
        """
        required_fields = ["smtp_host", "smtp_from_email"]

        for field in required_fields:
            if not config.get(field):
                return False, f"缺少必要的 SMTP 配置: {field}"

        return True, None

    @staticmethod
    async def send_verification_code(
        db: Session, to_email: str, code: str, expire_minutes: int = 30
    ) -> Tuple[bool, Optional[str]]:
        """
        发送验证码邮件

        Args:
            db: 数据库会话
            to_email: 收件人邮箱
            code: 验证码
            expire_minutes: 过期时间（分钟）

        Returns:
            (是否发送成功, 错误信息)
        """
        # 获取 SMTP 配置
        config = EmailSenderService._get_smtp_config(db)

        # 验证配置
        valid, error = EmailSenderService._validate_smtp_config(config)
        if not valid:
            logger.error(f"SMTP 配置无效: {error}")
            return False, error

        # 生成邮件内容
        # 优先使用 email_app_name，否则回退到 smtp_from_name
        app_name = SystemConfigService.get_config(db, "email_app_name", default=None)
        if not app_name:
            app_name = SystemConfigService.get_config(db, "smtp_from_name", default="Aether")

        html_body = EmailTemplate.get_verification_code_html(
            code=code, expire_minutes=expire_minutes, db=db, app_name=app_name, email=to_email
        )
        text_body = EmailTemplate.get_verification_code_text(
            code=code, expire_minutes=expire_minutes, db=db, app_name=app_name, email=to_email
        )
        subject = EmailTemplate.get_subject("verification", db=db)

        # 发送邮件
        return await EmailSenderService._send_email(
            config=config, to_email=to_email, subject=subject, html_body=html_body, text_body=text_body
        )

    @staticmethod
    async def _send_email(
        config: dict,
        to_email: str,
        subject: str,
        html_body: Optional[str] = None,
        text_body: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        发送邮件（内部方法）

        Args:
            config: SMTP 配置
            to_email: 收件人邮箱
            subject: 邮件主题
            html_body: HTML 邮件内容
            text_body: 纯文本邮件内容

        Returns:
            (是否发送成功, 错误信息)
        """
        if AIOSMTPLIB_AVAILABLE:
            return await EmailSenderService._send_email_async(
                config, to_email, subject, html_body, text_body
            )
        else:
            return await EmailSenderService._send_email_sync_wrapper(
                config, to_email, subject, html_body, text_body
            )

    @staticmethod
    async def _send_email_async(
        config: dict,
        to_email: str,
        subject: str,
        html_body: Optional[str] = None,
        text_body: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        异步发送邮件（使用 aiosmtplib）

        Args:
            config: SMTP 配置
            to_email: 收件人邮箱
            subject: 邮件主题
            html_body: HTML 邮件内容
            text_body: 纯文本邮件内容

        Returns:
            (是否发送成功, 错误信息)
        """
        try:
            # 构建邮件
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{config['smtp_from_name']} <{config['smtp_from_email']}>"
            message["To"] = to_email

            # 添加纯文本部分
            if text_body:
                message.attach(MIMEText(text_body, "plain", "utf-8"))

            # 添加 HTML 部分
            if html_body:
                message.attach(MIMEText(html_body, "html", "utf-8"))

            # 发送邮件
            ssl_context = _create_ssl_context()
            if config["smtp_use_ssl"]:
                await aiosmtplib.send(
                    message,
                    hostname=config["smtp_host"],
                    port=config["smtp_port"],
                    use_tls=True,
                    tls_context=ssl_context,
                    username=config["smtp_user"],
                    password=config["smtp_password"],
                    timeout=EmailSenderService.SMTP_TIMEOUT,
                )
            else:
                await aiosmtplib.send(
                    message,
                    hostname=config["smtp_host"],
                    port=config["smtp_port"],
                    start_tls=config["smtp_use_tls"],
                    tls_context=ssl_context if config["smtp_use_tls"] else None,
                    username=config["smtp_user"],
                    password=config["smtp_password"],
                    timeout=EmailSenderService.SMTP_TIMEOUT,
                )

            logger.info(f"验证码邮件发送成功: {to_email}")
            return True, None

        except Exception as e:
            error_msg = f"发送邮件失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    @staticmethod
    async def _send_email_sync_wrapper(
        config: dict,
        to_email: str,
        subject: str,
        html_body: Optional[str] = None,
        text_body: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        同步邮件发送的异步包装器

        Args:
            config: SMTP 配置
            to_email: 收件人邮箱
            subject: 邮件主题
            html_body: HTML 邮件内容
            text_body: 纯文本邮件内容

        Returns:
            (是否发送成功, 错误信息)
        """
        return await run_in_executor(
            EmailSenderService._send_email_sync,
            config,
            to_email,
            subject,
            html_body,
            text_body,
        )

    @staticmethod
    def _send_email_sync(
        config: dict,
        to_email: str,
        subject: str,
        html_body: Optional[str] = None,
        text_body: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        同步发送邮件（使用标准库 smtplib）

        Args:
            config: SMTP 配置
            to_email: 收件人邮箱
            subject: 邮件主题
            html_body: HTML 邮件内容
            text_body: 纯文本邮件内容

        Returns:
            (是否发送成功, 错误信息)
        """
        try:
            # 构建邮件
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{config['smtp_from_name']} <{config['smtp_from_email']}>"
            message["To"] = to_email

            # 添加纯文本部分
            if text_body:
                message.attach(MIMEText(text_body, "plain", "utf-8"))

            # 添加 HTML 部分
            if html_body:
                message.attach(MIMEText(html_body, "html", "utf-8"))

            # 连接 SMTP 服务器
            server: Optional[smtplib.SMTP] = None
            ssl_context = _create_ssl_context()
            try:
                if config["smtp_use_ssl"]:
                    server = smtplib.SMTP_SSL(
                        config["smtp_host"],
                        config["smtp_port"],
                        context=ssl_context,
                        timeout=EmailSenderService.SMTP_TIMEOUT,
                    )
                else:
                    server = smtplib.SMTP(
                        config["smtp_host"],
                        config["smtp_port"],
                        timeout=EmailSenderService.SMTP_TIMEOUT,
                    )
                    if config["smtp_use_tls"]:
                        server.starttls(context=ssl_context)

                assert server is not None

                # 登录
                if config["smtp_user"] and config["smtp_password"]:
                    server.login(config["smtp_user"], config["smtp_password"])

                # 发送邮件
                server.send_message(message)

                logger.info(f"验证码邮件发送成功（同步方式）: {to_email}")
                return True, None
            finally:
                # 确保服务器连接被关闭
                if server is not None:
                    try:
                        server.quit()
                    except Exception as quit_error:
                        logger.warning(f"关闭 SMTP 连接时出错: {quit_error}")

        except Exception as e:
            error_msg = f"发送邮件失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    @staticmethod
    async def test_smtp_connection(
        db: Session, override_config: Optional[dict] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        测试 SMTP 连接

        Args:
            db: 数据库会话
            override_config: 可选的覆盖配置（通常来自未保存的前端表单）

        Returns:
            (是否连接成功, 错误信息)
        """
        config = EmailSenderService._get_smtp_config(db)

        # 用外部传入的配置覆盖（仅覆盖提供的字段）
        if override_config:
            config.update({k: v for k, v in override_config.items() if v is not None})

        # 验证配置
        valid, error = EmailSenderService._validate_smtp_config(config)
        if not valid:
            return False, error

        try:
            ssl_context = _create_ssl_context()
            if AIOSMTPLIB_AVAILABLE:
                # 使用异步方式测试
                # 注意: use_tls=True 表示隐式 SSL (端口 465)
                # start_tls=True 表示 STARTTLS (端口 587)
                use_ssl = config["smtp_use_ssl"]
                use_starttls = config["smtp_use_tls"] and not use_ssl

                smtp = aiosmtplib.SMTP(
                    hostname=config["smtp_host"],
                    port=config["smtp_port"],
                    use_tls=use_ssl,
                    start_tls=use_starttls,
                    tls_context=ssl_context if (use_ssl or use_starttls) else None,
                    timeout=EmailSenderService.SMTP_TIMEOUT,
                )
                await smtp.connect()

                if config["smtp_user"] and config["smtp_password"]:
                    await smtp.login(config["smtp_user"], config["smtp_password"])

                await smtp.quit()
            else:
                # 使用同步方式测试
                server: Union[smtplib.SMTP, smtplib.SMTP_SSL]
                if config["smtp_use_ssl"]:
                    server = smtplib.SMTP_SSL(
                        config["smtp_host"],
                        config["smtp_port"],
                        context=ssl_context,
                        timeout=EmailSenderService.SMTP_TIMEOUT,
                    )
                else:
                    server = smtplib.SMTP(
                        config["smtp_host"],
                        config["smtp_port"],
                        timeout=EmailSenderService.SMTP_TIMEOUT,
                    )
                    if config["smtp_use_tls"]:
                        server.starttls(context=ssl_context)

                if config["smtp_user"] and config["smtp_password"]:
                    server.login(config["smtp_user"], config["smtp_password"])

                server.quit()

            logger.info("SMTP 连接测试成功")
            return True, None

        except Exception as e:
            error_msg = _translate_smtp_error(str(e))
            logger.error(f"SMTP 连接测试失败: {error_msg}")
            return False, error_msg


def _translate_smtp_error(error: str) -> str:
    """将 SMTP 错误信息转换为用户友好的中文提示"""
    error_lower = error.lower()

    # 认证相关错误
    if "username and password not accepted" in error_lower:
        return "用户名或密码错误，请检查 SMTP 凭据"
    if "authentication failed" in error_lower:
        return "认证失败，请检查用户名和密码"
    if "invalid credentials" in error_lower or "badcredentials" in error_lower:
        return "凭据无效，请检查用户名和密码"
    if "smtp auth extension is not supported" in error_lower:
        return "服务器不支持认证，请尝试使用 TLS 或 SSL 加密"

    # 连接相关错误
    if "connection refused" in error_lower:
        return "连接被拒绝，请检查服务器地址和端口"
    if "connection timed out" in error_lower or "timed out" in error_lower:
        return "连接超时，请检查网络或服务器地址"
    if "name or service not known" in error_lower or "getaddrinfo failed" in error_lower:
        return "无法解析服务器地址，请检查 SMTP 服务器地址"
    if "network is unreachable" in error_lower:
        return "网络不可达，请检查网络连接"

    # SSL/TLS 相关错误
    if "certificate verify failed" in error_lower:
        return "SSL 证书验证失败，请检查服务器证书或尝试其他加密方式"
    if "ssl" in error_lower and "wrong version" in error_lower:
        return "SSL 版本不匹配，请尝试其他加密方式"
    if "starttls" in error_lower:
        return "STARTTLS 握手失败，请检查加密设置"

    # 其他常见错误
    if "sender address rejected" in error_lower:
        return "发件人地址被拒绝，请检查发件人邮箱设置"
    if "relay access denied" in error_lower:
        return "中继访问被拒绝，请检查 SMTP 服务器配置"

    # 返回原始错误（简化格式）
    # 去掉错误码前缀，如 "(535, '5.7.8 ..."
    if error.startswith("(") and "'" in error:
        # 提取引号内的内容
        start = error.find("'") + 1
        end = error.rfind("'")
        if start > 0 and end > start:
            return error[start:end].replace("\\n", " ").strip()

    return error

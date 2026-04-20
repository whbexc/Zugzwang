import sys
from unittest.mock import patch

from src.ui.email_sender_page import EmailSenderPage


def test_build_ssl_context_uses_certifi_when_available():
    certifi_mock = type("CertifiMock", (), {"where": staticmethod(lambda: "C:/bundle/cacert.pem")})

    with patch.dict(sys.modules, {"certifi": certifi_mock}), \
         patch("src.ui.email_sender_page.ssl.create_default_context") as create_default_context:
        EmailSenderPage._build_ssl_context()
        create_default_context.assert_called_once_with(cafile="C:/bundle/cacert.pem")


def test_build_ssl_context_falls_back_without_certifi():
    with patch.dict(sys.modules, {"certifi": None}), \
         patch("src.ui.email_sender_page.ssl.create_default_context") as create_default_context:
        EmailSenderPage._build_ssl_context()
        create_default_context.assert_called_once_with(cafile=None)

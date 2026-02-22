"""
NextOCR Python SDK

Official client library for interacting with the NextOCR Developer API.

Example:
    from nextocr import NextOCRClient

    client = NextOCRClient(
        username="your_username",
        secretkey="your_secretkey"
    )

    text = client.ocr_image("document.jpg")
    print(text)
"""

from .nextocr import (
    NextOCRClient,
    NextOCRResponse,
    NextOCRError,
    NEXTOCR_OCR,
)

__all__ = [
    "NextOCRClient",
    "NextOCRResponse",
    "NextOCRError",
    "NEXTOCR_OCR",
]

__version__ = "0.1.0"
__author__ = "Danh Hong"
__license__ = "Proprietary"

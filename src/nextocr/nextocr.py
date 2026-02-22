#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nextocr.py — NextOCR Python SDK (Proprietary)

Install:
  pip install nextocr-python

Usage:
  from nextocr import NextOCRClient
  client = NextOCRClient(username="...", secretkey="...")
  text = client.ocr_image("test.jpg")
  print(text)

Env vars (optional):
  NEXTOCR_API_URL     default: https://developer.nextocr.org/ocr_api
  NEXTOCR_USERNAME
  NEXTOCR_SECRETKEY   (or NEXTOCR_SECRET_KEY)
  NEXTOCR_TIMEOUT     default: 120
"""

from __future__ import annotations

import os
import mimetypes
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

import requests


DEFAULT_API_URL = "https://developer.nextocr.org/ocr_api"
DEFAULT_TIMEOUT = 120


class NextOCRError(RuntimeError):
    """Raised when NextOCR API request fails."""


@dataclass
class NextOCRResponse:
    """Normalized SDK response."""
    ok: bool
    status_code: int
    text: str
    raw: Union[str, Dict[str, Any]]
    request_id: Optional[str] = None


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def _get_timeout() -> int:
    raw = _env("NEXTOCR_TIMEOUT")
    if not raw:
        return DEFAULT_TIMEOUT
    try:
        t = int(raw)
        return t if t > 0 else DEFAULT_TIMEOUT
    except Exception:
        return DEFAULT_TIMEOUT


def _normalize_secretkey(secretkey: Optional[str]) -> Optional[str]:
    if secretkey:
        return secretkey
    return _env("NEXTOCR_SECRETKEY") or _env("NEXTOCR_SECRET_KEY")


class NextOCRClient:
    """
    Minimal client for NextOCR Developer API.

    Auth headers sent:
      X-Username: <username>
      X-Secret-Key: <secretkey>

    Expected response:
      - Plain text (OCR text)
      - or JSON with common fields like: msg/text/result
    """

    def __init__(
        self,
        username: Optional[str] = None,
        secretkey: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: Optional[int] = None,
        session: Optional[requests.Session] = None,
        user_agent: str = "nextocr-python/0.1.0",
    ) -> None:
        self.api_url = (api_url or _env("NEXTOCR_API_URL") or DEFAULT_API_URL).strip()
        self.username = username or _env("NEXTOCR_USERNAME")
        self.secretkey = _normalize_secretkey(secretkey)
        self.timeout = int(timeout) if timeout is not None else _get_timeout()
        self.session = session or requests.Session()
        self.user_agent = user_agent

        if not self.api_url:
            raise ValueError("api_url is required (or set NEXTOCR_API_URL).")

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {"User-Agent": self.user_agent}
        if self.username:
            h["X-Username"] = self.username
        if self.secretkey:
            h["X-Secret-Key"] = self.secretkey
        return h

    def _check_auth(self) -> None:
        if not self.username or not self.secretkey:
            raise NextOCRError(
                "Missing credentials. Provide username/secretkey or set "
                "NEXTOCR_USERNAME and NEXTOCR_SECRETKEY."
            )

    def ocr_image(
        self,
        image_path: str,
        *,
        extra_fields: Optional[Dict[str, Any]] = None,
        return_full: bool = False,
    ) -> Union[str, NextOCRResponse]:
        """
        OCR from an image file path.

        Args:
            image_path: path to image.
            extra_fields: optional extra POST fields (if your API supports).
            return_full: if True returns NextOCRResponse, else returns text.

        Returns:
            OCR text (default) or NextOCRResponse (return_full=True).
        """
        self._check_auth()

        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(f"File not found: {image_path}")

        filename = os.path.basename(image_path)
        mime, _ = mimetypes.guess_type(filename)
        mime = mime or "application/octet-stream"

        data = None
        if extra_fields:
            data = {k: str(v) for k, v in extra_fields.items()}

        with open(image_path, "rb") as f:
            files = {"file": (filename, f, mime)}
            resp = self.session.post(
                self.api_url,
                files=files,
                data=data,
                headers=self._headers(),
                timeout=self.timeout,
            )

        parsed = self._parse_response(resp)
        return parsed if return_full else parsed.text

    def ocr_bytes(
        self,
        content: bytes,
        *,
        filename: str = "upload.png",
        content_type: Optional[str] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
        return_full: bool = False,
    ) -> Union[str, NextOCRResponse]:
        """
        OCR from bytes (in-memory).

        Args:
            content: image bytes.
            filename: virtual filename for upload.
            content_type: override mime type.
            extra_fields: optional extra POST fields.
            return_full: if True returns NextOCRResponse, else returns text.
        """
        self._check_auth()

        if not isinstance(content, (bytes, bytearray)) or len(content) == 0:
            raise ValueError("content must be non-empty bytes")

        mime = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

        data = None
        if extra_fields:
            data = {k: str(v) for k, v in extra_fields.items()}

        files = {"file": (filename, content, mime)}
        resp = self.session.post(
            self.api_url,
            files=files,
            data=data,
            headers=self._headers(),
            timeout=self.timeout,
        )

        parsed = self._parse_response(resp)
        return parsed if return_full else parsed.text

    def health(self) -> bool:
        """
        Optional: health-check. If your server supports /health, this will work.
        If not supported, returns False.
        """
        self._check_auth()
        base = self.api_url.rsplit("/", 1)[0]
        url = f"{base}/health"
        try:
            r = self.session.get(url, headers=self._headers(), timeout=min(10, self.timeout))
            return r.status_code == 200
        except Exception:
            return False

    def _parse_response(self, resp: requests.Response) -> NextOCRResponse:
        status = resp.status_code
        request_id = resp.headers.get("X-Request-Id") or resp.headers.get("X-Request-ID")

        raw_text = (resp.text or "").strip()

        if status != 200:
            # Try JSON error details
            try:
                j = resp.json()
                msg = j.get("error") or j.get("message") or raw_text
                raise NextOCRError(f"NextOCR API error HTTP {status}: {msg}")
            except ValueError:
                raise NextOCRError(f"NextOCR API error HTTP {status}: {raw_text}")

        # 200 OK: try JSON first
        try:
            j = resp.json()
            text = j.get("msg")
            if text is None:
                text = j.get("text") or j.get("result") or raw_text
            text = str(text).replace("\r\n", "\n")
            if text and not text.endswith("\n"):
                text += "\n"
            return NextOCRResponse(ok=True, status_code=status, text=text, raw=j, request_id=request_id)
        except ValueError:
            # plain text
            text = raw_text.replace("\r\n", "\n")
            if text and not text.endswith("\n"):
                text += "\n"
            return NextOCRResponse(ok=True, status_code=status, text=text, raw=raw_text, request_id=request_id)


def NEXTOCR_OCR(filename: str) -> Optional[str]:
    """
    Simple helper for quick usage.
    Returns OCR text or None on error.
    """
    try:
        return NextOCRClient().ocr_image(filename)
    except Exception:
        return None


__all__ = ["NextOCRClient", "NextOCRResponse", "NextOCRError", "NEXTOCR_OCR"]

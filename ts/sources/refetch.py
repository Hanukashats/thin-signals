"""Safe, bounded re-fetching of advisory public-web leads."""
from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from ts.sources.connectors import ConnectorError, Hit

MAX_BODY_BYTES = 2_000_000
MAX_REDIRECTS = 5
_TEXT_TYPES = (
    "text/",
    "application/json",
    "application/xml",
    "application/xhtml+xml",
)


@dataclass(frozen=True)
class RefetchResponse:
    status_code: int
    headers: Mapping[str, str]
    content: bytes


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._title = False
        self._ignored = 0

    def handle_starttag(self, tag, attrs):
        _ = attrs
        if tag in {"script", "style", "noscript"}:
            self._ignored += 1
        elif tag == "title":
            self._title = True

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self._ignored:
            self._ignored -= 1
        elif tag == "title":
            self._title = False

    def handle_data(self, data):
        if self._ignored:
            return
        text = data.strip()
        if not text:
            return
        self.parts.append(text)
        if self._title:
            self.title_parts.append(text)


def _public_url(url: str, resolver=socket.getaddrinfo) -> str:
    try:
        parsed = urlparse(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise ConnectorError("advisory URL is invalid") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConnectorError("advisory URL must be public HTTP(S)")
    if parsed.username or parsed.password:
        raise ConnectorError("advisory URL credentials are forbidden")
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local")):
        raise ConnectorError("advisory URL is not public")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            answers = resolver(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ConnectorError("advisory URL cannot be resolved") from exc
        addresses = []
        for answer in answers:
            try:
                addresses.append(ipaddress.ip_address(answer[4][0]))
            except (IndexError, TypeError, ValueError):
                continue
    if not addresses or any(not address.is_global for address in addresses):
        raise ConnectorError("advisory URL is not public")
    return url


def _text(content: bytes, content_type: str) -> tuple[str, str]:
    try:
        decoded = content.decode("utf-8", errors="replace")
    except (AttributeError, UnicodeError) as exc:
        raise ConnectorError("advisory response is not text") from exc
    if "html" not in content_type:
        clean = re.sub(r"\s+", " ", decoded).strip()
        return clean, ""
    parser = _TextParser()
    try:
        parser.feed(decoded)
    except (ValueError, AssertionError) as exc:
        raise ConnectorError("advisory HTML is invalid") from exc
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip(), " ".join(parser.title_parts).strip()


def refetch_public_url(
    url: str,
    request: Callable[[str], object],
    *,
    resolver=socket.getaddrinfo,
    max_body_bytes: int = MAX_BODY_BYTES,
) -> Hit:
    """Re-fetch a lead after checking every redirect target against SSRF."""
    current = url
    response = None
    for _hop in range(MAX_REDIRECTS + 1):
        _public_url(current, resolver)
        response = request(current)
        status = getattr(response, "status_code", None)
        headers = getattr(response, "headers", {})
        if not isinstance(status, int) or not isinstance(headers, Mapping):
            raise ConnectorError("advisory response is invalid")
        if status in {301, 302, 303, 307, 308}:
            location = headers.get("location") or headers.get("Location")
            if not isinstance(location, str) or not location:
                raise ConnectorError("advisory redirect has no target")
            current = urljoin(current, location)
            continue
        break
    else:
        raise ConnectorError("advisory redirect limit exceeded")
    if response is None or not 200 <= response.status_code < 300:
        raise ConnectorError("advisory re-fetch failed")
    content = getattr(response, "content", None)
    if not isinstance(content, bytes):
        raise ConnectorError("advisory response body is invalid")
    if len(content) > max_body_bytes:
        raise ConnectorError("advisory response is too large")
    content_type = str(response.headers.get("content-type") or "").lower().split(";", 1)[0]
    if not any(content_type.startswith(allowed) for allowed in _TEXT_TYPES):
        raise ConnectorError("advisory response content type is unsupported")
    text, title = _text(content, content_type)
    if not text:
        raise ConnectorError("advisory response has no readable text")
    host = urlparse(current).hostname or current
    doi_match = re.search(r"10\.\d{4,9}/[^\s?#]+", current, re.IGNORECASE)
    doi = doi_match.group(0).rstrip(").,") if doi_match else None
    return Hit(
        connector="refetch",
        url=current,
        title=title or host,
        snippet=text[:500],
        source_type="paper" if doi else "web",
        doi=doi,
        fetched_body=content,
        fetched_text=text,
        fetched_content_type=content_type,
    )

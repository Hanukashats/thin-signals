"""Safe, bounded re-fetching of advisory public-web leads."""
from __future__ import annotations

import errno
import http.client
import ipaddress
import re
import socket
import ssl
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from time import monotonic
from urllib.parse import quote, urljoin, urlparse

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


@dataclass(frozen=True)
class PublicTarget:
    """One URL plus the exact public addresses validated for this hop.

    The transport must connect to one of ``addresses``.  Handing the hostname
    back to a generic HTTP client would create a second DNS lookup and reopen a
    DNS-rebinding SSRF window.
    """

    url: str
    scheme: str
    host: str
    port: int
    addresses: tuple[str, ...]


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


def _public_target(url: str, resolver=socket.getaddrinfo) -> PublicTarget:
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
    return PublicTarget(
        url=url,
        scheme=parsed.scheme,
        host=host,
        port=port,
        addresses=tuple(dict.fromkeys(str(address) for address in addresses)),
    )


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """HTTP connection whose TCP peer is an already validated numeric IP."""

    def __init__(self, target: PublicTarget, address: str, timeout: float):
        super().__init__(target.host, port=target.port, timeout=timeout)
        self._pinned_address = address

    def _connect_socket(self):
        sock = _numeric_socket(
            self._pinned_address, self.port, self.timeout, self.source_address,
        )
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError as exc:
            if exc.errno != errno.ENOPROTOOPT:
                sock.close()
                raise
        return sock

    def connect(self):
        self.sock = self._connect_socket()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS variant: pinned TCP peer, original hostname for TLS SNI/checks."""

    def __init__(self, target: PublicTarget, address: str, timeout: float):
        super().__init__(target.host, port=target.port, timeout=timeout)
        self._pinned_address = address

    def connect(self):
        sock = _numeric_socket(
            self._pinned_address, self.port, self.timeout, self.source_address,
        )
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def _numeric_socket(address: str, port: int, timeout: float, source_address=None):
    """Connect to a numeric peer without invoking getaddrinfo again."""
    parsed = ipaddress.ip_address(address)
    family = socket.AF_INET6 if parsed.version == 6 else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout)
        if source_address:
            sock.bind(source_address)
        peer = (address, port, 0, 0) if parsed.version == 6 else (address, port)
        sock.connect(peer)
        return sock
    except Exception:
        sock.close()
        raise


def fetch_public_target(
    target: PublicTarget,
    *,
    headers: Mapping[str, str],
    timeout_seconds: float,
    max_body_bytes: int = MAX_BODY_BYTES,
) -> RefetchResponse:
    """Fetch one validated hop without resolving its hostname a second time."""
    deadline_at = monotonic() + max(0.001, timeout_seconds)
    parsed = urlparse(target.url)
    path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
    if parsed.query:
        path += f"?{parsed.query}"
    default_port = 443 if target.scheme == "https" else 80
    host = target.host.encode("idna").decode("ascii")
    if ":" in host:
        host = f"[{host}]"
    authority = host if target.port == default_port else f"{host}:{target.port}"
    request_headers = {
        **{str(key): str(value) for key, value in headers.items()},
        "Host": authority,
        "Accept-Encoding": "identity",
        "Connection": "close",
    }
    last_error: BaseException | None = None
    for address in target.addresses:
        connection = None
        try:
            remaining = deadline_at - monotonic()
            if remaining <= 0:
                raise TimeoutError("advisory re-fetch deadline exceeded")
            connection_type = (
                _PinnedHTTPSConnection if target.scheme == "https" else _PinnedHTTPConnection
            )
            connection = connection_type(target, address, remaining)
            connection.request("GET", path, headers=request_headers)
            response = connection.getresponse()
            declared = response.getheader("content-length")
            if declared and declared.isdigit() and int(declared) > max_body_bytes:
                raise ConnectorError("advisory response is too large")
            body = bytearray()
            read_chunk = getattr(response, "read1", response.read)
            while True:
                remaining = deadline_at - monotonic()
                if remaining <= 0:
                    raise TimeoutError("advisory re-fetch deadline exceeded")
                read_socket = connection.sock
                if read_socket is None:
                    raw = getattr(getattr(response, "fp", None), "raw", None)
                    read_socket = getattr(raw, "_sock", None)
                if read_socket is not None:
                    read_socket.settimeout(max(0.001, remaining))
                chunk = read_chunk(min(65_536, max_body_bytes + 1 - len(body)))
                if monotonic() >= deadline_at:
                    raise TimeoutError("advisory re-fetch deadline exceeded")
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > max_body_bytes:
                    raise ConnectorError("advisory response is too large")
            return RefetchResponse(
                status_code=int(response.status),
                headers={key.lower(): value for key, value in response.getheaders()},
                content=bytes(body),
            )
        except ConnectorError:
            raise
        except (OSError, TimeoutError, http.client.HTTPException, ssl.SSLError) as exc:
            last_error = exc
        finally:
            if connection is not None:
                connection.close()
    raise ConnectorError("advisory re-fetch transport failed") from last_error


def extract_text(content: bytes, content_type: str) -> tuple[str, str]:
    """Return the deterministic readable text used by snapshot attestations."""
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
    request: Callable[[PublicTarget], object],
    *,
    resolver=socket.getaddrinfo,
    max_body_bytes: int = MAX_BODY_BYTES,
) -> Hit:
    """Re-fetch a lead after checking every redirect target against SSRF."""
    current = url
    response = None
    for _hop in range(MAX_REDIRECTS + 1):
        target = _public_target(current, resolver)
        response = request(target)
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
    text, title = extract_text(content, content_type)
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

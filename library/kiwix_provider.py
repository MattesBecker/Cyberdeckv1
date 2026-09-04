import logging
import os
import re
import socket
import subprocess
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from urllib.error import URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

from config import (
    KIWIX_ENABLED,
    KIWIX_HOST,
    KIWIX_HTTP_TIMEOUT,
    KIWIX_MAX_RESPONSE_BYTES,
    KIWIX_POLL_INTERVAL,
    KIWIX_PORT,
    KIWIX_RESULT_LIMIT,
    KIWIX_SERVER_PATH,
    KIWIX_START_TIMEOUT,
    KIWIX_STOP_TIMEOUT,
    KIWIX_THREADS,
    KIWIX_ZIM_PATH,
)

from .base import (
    ITEM_TYPE_BACK,
    ITEM_TYPE_SEARCH,
    LibraryDocument,
    LibraryItem,
    LibraryProvider,
    LibraryProviderError,
    SearchResult,
)


logger = logging.getLogger(__name__)
_VOID_TAGS = frozenset(
    (
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    )
)
_BLOCK_TAGS = frozenset(
    (
        "article",
        "blockquote",
        "dd",
        "div",
        "dl",
        "dt",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "main",
        "p",
        "pre",
        "section",
        "tr",
    )
)
_HIDDEN_TAGS = frozenset(
    (
        "aside",
        "canvas",
        "footer",
        "form",
        "nav",
        "noscript",
        "script",
        "style",
        "svg",
        "template",
    )
)
_HIDDEN_ATTRIBUTE_MARKERS = (
    "menu",
    "nav",
    "sidebar",
    "site-header",
    "site-footer",
    "toolbar",
)


class KiwixProviderError(LibraryProviderError):
    """Raised when local Wikipedia cannot be started or read."""


class _LocalOnlyRedirectHandler(HTTPRedirectHandler):
    def __init__(self, host: str, port: int) -> None:
        super().__init__()
        self.host = host
        self.port = port

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _is_expected_local_url(newurl, self.host, self.port):
            raise URLError("Kiwix redirected outside the configured localhost")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _SearchHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: List[Tuple[str, str]] = []
        self._href: Optional[str] = None
        self._text_parts: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a" or self._href is not None:
            return
        href = dict(attrs).get("href", "")
        try:
            self._href = _normalize_content_id(href)
        except ValueError:
            self._href = None
            return
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._href is None:
            return
        title = " ".join(" ".join(self._text_parts).split())
        self.links.append((self._href, title))
        self._href = None
        self._text_parts = []

    def close(self) -> None:
        if self._href is not None:
            title = " ".join(" ".join(self._text_parts).split())
            self.links.append((self._href, title))
            self._href = None
        super().close()


class _ArticleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: List[str] = []
        self.heading_parts: List[str] = []
        self.blocks: List[str] = []
        self._current: List[str] = []
        self._hidden_depth = 0
        self._head_depth = 0
        self._in_title = False
        self._h1_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if self._hidden_depth:
            if tag not in _VOID_TAGS:
                self._hidden_depth += 1
            return
        if tag in _HIDDEN_TAGS or (
            tag not in _VOID_TAGS and _is_hidden_container(attrs)
        ):
            self._flush()
            self._hidden_depth = 1
            return
        if tag == "title":
            self._in_title = True
            return
        if tag == "head":
            self._head_depth += 1
            return
        if self._head_depth:
            return
        if tag in _BLOCK_TAGS or tag in ("br", "hr"):
            self._flush()
        if tag == "li":
            self._current.append("-")
        if tag == "h1":
            self._h1_depth += 1

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag.lower() in ("br", "hr") and not self._hidden_depth:
            self._flush()

    def handle_data(self, data: str) -> None:
        clean = " ".join(data.split())
        if not clean:
            return
        if self._in_title:
            self.title_parts.append(clean)
            return
        if self._hidden_depth or self._head_depth:
            return
        self._current.append(clean)
        if self._h1_depth:
            self.heading_parts.append(clean)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._hidden_depth:
            self._hidden_depth -= 1
            return
        if tag == "title":
            self._in_title = False
            return
        if tag == "head":
            self._head_depth = max(0, self._head_depth - 1)
            return
        if self._head_depth:
            return
        if tag == "h1":
            self._h1_depth = max(0, self._h1_depth - 1)
        if tag in _BLOCK_TAGS:
            self._flush()

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        text = " ".join(self._current).strip()
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        if text and (not self.blocks or text != self.blocks[-1]):
            self.blocks.append(text)
        self._current = []

    @property
    def title(self) -> str:
        return " ".join(" ".join(self.title_parts).split())

    @property
    def first_heading(self) -> str:
        return " ".join(" ".join(self.heading_parts).split())

    @property
    def text(self) -> str:
        return "\n\n".join(self.blocks).strip()


class KiwixProvider(LibraryProvider):
    """Read one local ZIM through a lazily managed kiwix-serve process."""

    key = "kiwix"
    title = "Wikipedia"
    supports_search = True
    search_title = "SEARCH WIKI"

    def __init__(
        self,
        zim_path: Path = KIWIX_ZIM_PATH,
        server_path: Path = KIWIX_SERVER_PATH,
        host: str = KIWIX_HOST,
        port: int = KIWIX_PORT,
        enabled: bool = KIWIX_ENABLED,
        start_timeout: float = KIWIX_START_TIMEOUT,
        http_timeout: float = KIWIX_HTTP_TIMEOUT,
        poll_interval: float = KIWIX_POLL_INTERVAL,
        stop_timeout: float = KIWIX_STOP_TIMEOUT,
        threads: int = KIWIX_THREADS,
        result_limit: int = KIWIX_RESULT_LIMIT,
        max_response_bytes: int = KIWIX_MAX_RESPONSE_BYTES,
        urlopen: Optional[Callable] = None,
        popen_factory: Callable = subprocess.Popen,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        port_checker: Optional[Callable[[str, int], bool]] = None,
    ) -> None:
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("Kiwix host must be localhost.")
        if not 1 <= int(port) <= 65535:
            raise ValueError("Kiwix port is invalid.")

        self.zim_path = Path(zim_path)
        self.server_path = Path(server_path)
        self.host = host
        self.port = int(port)
        self.enabled = enabled
        self.start_timeout = max(0.0, float(start_timeout))
        self.http_timeout = max(0.1, float(http_timeout))
        self.poll_interval = max(0.01, float(poll_interval))
        self.stop_timeout = max(0.1, float(stop_timeout))
        self.threads = max(1, int(threads))
        self.result_limit = max(1, int(result_limit))
        self.max_response_bytes = max(1024, int(max_response_bytes))
        self._popen_factory = popen_factory
        self._sleeper = sleeper
        self._monotonic = monotonic
        self._port_checker = port_checker or self._default_port_checker
        if urlopen is None:
            opener = build_opener(_LocalOnlyRedirectHandler(host, self.port))
            self._urlopen = opener.open
        else:
            self._urlopen = urlopen
        self._process = None
        self._owns_process = False

    @property
    def base_url(self) -> str:
        host = "[{0}]".format(self.host) if ":" in self.host else self.host
        return "http://{0}:{1}".format(host, self.port)

    @property
    def owns_process(self) -> bool:
        return self._owns_process

    def is_available(self) -> bool:
        try:
            self._ensure_server()
            return True
        except LibraryProviderError:
            return False

    def list_items(self, container_id: str = "") -> List[LibraryItem]:
        if container_id:
            raise KiwixProviderError("Wikipedia unavailable")
        self._ensure_server()
        return [
            LibraryItem(self.key, "search", "Search", ITEM_TYPE_SEARCH),
            LibraryItem(self.key, "back", "Back", ITEM_TYPE_BACK),
        ]

    def search(self, query: str) -> List[SearchResult]:
        clean_query = " ".join(query.split()) if isinstance(query, str) else ""
        if not clean_query:
            raise KiwixProviderError("Invalid search query")

        self._ensure_server()
        path = "/search?{0}".format(
            urlencode(
                {
                    "pattern": clean_query,
                    "pageLength": self.result_limit,
                }
            )
        )
        html = self._fetch_text(path, "Wikipedia unavailable")
        parser = _SearchHTMLParser()
        try:
            parser.feed(html)
            parser.close()
        except Exception as exc:
            logger.warning("Could not parse Kiwix search HTML: %s", exc)
            return []

        results = []
        seen = set()
        for item_id, parsed_title in parser.links:
            if item_id in seen:
                continue
            seen.add(item_id)
            results.append(
                SearchResult(
                    provider=self.key,
                    id=item_id,
                    title=parsed_title or self.get_title(item_id),
                    preview="",
                )
            )
            if len(results) >= self.result_limit:
                break
        return results

    def open_item(self, item_id: str) -> LibraryDocument:
        try:
            normalized_id = _normalize_content_id(item_id)
        except ValueError as exc:
            logger.warning(
                "Rejected invalid Kiwix content ID %r: %s", item_id, exc
            )
            raise KiwixProviderError("Article unavailable") from exc

        self._ensure_server()
        encoded_path = quote(normalized_id, safe="/%:@-._~!$&'()*+,;=")
        html = self._fetch_text(encoded_path, "Article unavailable")
        parser = _ArticleHTMLParser()
        try:
            parser.feed(html)
            parser.close()
        except Exception as exc:
            logger.warning("Could not parse Kiwix article HTML: %s", exc)
            raise KiwixProviderError("Article unavailable") from exc

        if not parser.text:
            logger.warning("Kiwix article %s contained no readable text", item_id)
            raise KiwixProviderError("Article unavailable")
        title = parser.title or parser.first_heading or self.get_title(item_id)
        return LibraryDocument(
            provider=self.key,
            id=normalized_id,
            title=title,
            text=parser.text,
            source=normalized_id,
        )

    def get_title(self, item_id: str) -> str:
        try:
            normalized_id = _normalize_content_id(item_id)
        except ValueError:
            return "Wikipedia article"
        slug = unquote(normalized_id.rsplit("/", 1)[-1])
        title = slug.replace("_", " ").strip()
        return title or "Wikipedia article"

    def close(self) -> None:
        self._stop_owned_process()

    def _ensure_server(self) -> None:
        if self._server_is_ready():
            return

        if self._owns_process and self._process is not None:
            if self._process.poll() is None and self._wait_until_ready():
                return
            self._stop_owned_process()

        if self._port_checker(self.host, self.port):
            logger.error(
                "Port %s:%d is occupied but does not answer as configured Kiwix",
                self.host,
                self.port,
            )
            raise KiwixProviderError("Wikipedia unavailable")
        if not self.enabled:
            logger.error("Kiwix provider is disabled")
            raise KiwixProviderError("Wikipedia unavailable")
        if not self.zim_path.is_file():
            logger.error("Kiwix ZIM is missing: %s", self.zim_path)
            raise KiwixProviderError("Wikipedia unavailable")
        if not self.server_path.is_file() or not os.access(
            self.server_path, os.X_OK
        ):
            logger.error(
                "kiwix-serve is missing or not executable: %s",
                self.server_path,
            )
            raise KiwixProviderError("Wikipedia unavailable")

        command = [
            str(self.server_path),
            "--address={0}".format(self.host),
            "--port={0}".format(self.port),
            "--threads={0}".format(self.threads),
            str(self.zim_path),
        ]
        try:
            self._process = self._popen_factory(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                start_new_session=True,
            )
            self._owns_process = True
        except (OSError, subprocess.SubprocessError) as exc:
            logger.error("Could not start kiwix-serve: %s", exc)
            self._process = None
            self._owns_process = False
            raise KiwixProviderError("Wikipedia unavailable") from exc

        if self._wait_until_ready():
            return
        return_code = self._process.poll() if self._process is not None else None
        logger.error("kiwix-serve did not become ready; exit=%s", return_code)
        self._stop_owned_process()
        raise KiwixProviderError("Wikipedia unavailable")

    def _wait_until_ready(self) -> bool:
        deadline = self._monotonic() + self.start_timeout
        while self._monotonic() <= deadline:
            process = self._process
            if process is None or process.poll() is not None:
                return False
            if self._server_is_ready():
                return True
            self._sleeper(self.poll_interval)
        return False

    def _server_is_ready(self) -> bool:
        response = None
        try:
            response = self._urlopen(
                self.base_url + "/", timeout=min(1.0, self.http_timeout)
            )
            final_url = _response_url(response, self.base_url + "/")
            if not _is_expected_local_url(final_url, self.host, self.port):
                return False
            response.read(1)
            return True
        except Exception:
            return False
        finally:
            _close_response(response)

    def _fetch_text(self, path: str, user_message: str) -> str:
        if not path.startswith("/") or path.startswith("//"):
            raise KiwixProviderError(user_message)
        url = self.base_url + path
        response = None
        try:
            response = self._urlopen(url, timeout=self.http_timeout)
            final_url = _response_url(response, url)
            if not _is_expected_local_url(final_url, self.host, self.port):
                raise URLError("Kiwix response left configured localhost")
            data = response.read(self.max_response_bytes + 1)
            if len(data) > self.max_response_bytes:
                logger.warning(
                    "Truncating oversized Kiwix response from %s to %d bytes",
                    path,
                    self.max_response_bytes,
                )
                data = data[: self.max_response_bytes]
            charset = "utf-8"
            headers = getattr(response, "headers", None)
            get_charset = getattr(headers, "get_content_charset", None)
            if callable(get_charset):
                charset = get_charset() or charset
            try:
                return data.decode(charset, errors="replace")
            except LookupError:
                return data.decode("utf-8", errors="replace")
        except KiwixProviderError:
            raise
        except Exception as exc:
            logger.warning("Kiwix HTTP request failed for %s: %s", path, exc)
            raise KiwixProviderError(user_message) from exc
        finally:
            _close_response(response)

    def _stop_owned_process(self) -> None:
        process = self._process
        if not self._owns_process or process is None:
            self._process = None
            self._owns_process = False
            return

        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=self.stop_timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=self.stop_timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("Could not stop owned kiwix-serve cleanly: %s", exc)
        finally:
            self._process = None
            self._owns_process = False

    @staticmethod
    def _default_port_checker(host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            return False


def _normalize_content_id(item_id: str) -> str:
    if not isinstance(item_id, str) or "\x00" in item_id:
        raise ValueError("invalid content ID")
    parsed = urlsplit(item_id)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/content/"):
        raise ValueError("content ID must be a local /content/ path")
    decoded_parts = unquote(parsed.path).split("/")
    if ".." in decoded_parts:
        raise ValueError("content ID contains path traversal")
    return parsed.path


def _is_expected_local_url(url: str, host: str, port: int) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname != host:
        return False
    actual_port = parsed.port if parsed.port is not None else 80
    return actual_port == port


def _response_url(response, fallback: str) -> str:
    geturl = getattr(response, "geturl", None)
    return geturl() if callable(geturl) else fallback


def _is_hidden_container(attrs) -> bool:
    values = []
    role = ""
    for name, value in attrs:
        if value is None:
            continue
        if name.lower() == "role":
            role = value.lower()
        if name.lower() in ("class", "id"):
            values.append(value.lower())
    if role in ("menu", "menubar", "navigation"):
        return True
    combined = " ".join(values)
    return any(marker in combined for marker in _HIDDEN_ATTRIBUTE_MARKERS)


def _close_response(response) -> None:
    close = getattr(response, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass

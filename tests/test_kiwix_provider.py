import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from urllib.error import URLError

from library import (
    ITEM_TYPE_BACK,
    ITEM_TYPE_SEARCH,
    KiwixProvider,
    KiwixProviderError,
)


class FakeHeaders:
    def get_content_charset(self):
        return "utf-8"


class FakeResponse:
    def __init__(self, body, url):
        self.body = body.encode("utf-8") if isinstance(body, str) else body
        self.url = url
        self.headers = FakeHeaders()
        self.closed = False

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]

    def geturl(self):
        return self.url

    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self, return_code=None):
        self.return_code = return_code
        self.terminated = False
        self.killed = False
        self.wait_timeouts = []

    def poll(self):
        return self.return_code

    def terminate(self):
        self.terminated = True
        self.return_code = 0

    def kill(self):
        self.killed = True
        self.return_code = -9

    def wait(self, timeout=None):
        self.wait_timeouts.append(timeout)
        return self.return_code


class KiwixProviderTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root = Path(self.temporary_directory.name)
        self.zim_path = root / "wikipedia.zim"
        self.zim_path.write_bytes(b"test zim placeholder")
        self.server_path = root / "kiwix-serve"
        self.server_path.write_text("test executable", encoding="utf-8")
        self.server_path.chmod(0o700)

    def make_provider(self, urlopen, **overrides):
        options = {
            "zim_path": self.zim_path,
            "server_path": self.server_path,
            "urlopen": urlopen,
            "port_checker": lambda _host, _port: False,
            "start_timeout": 0.2,
            "poll_interval": 0.05,
        }
        options.update(overrides)
        return KiwixProvider(**options)

    def test_existing_server_is_reused_and_not_stopped(self):
        popen = Mock()

        def urlopen(url, timeout):
            return FakeResponse("Kiwix", url)

        provider = self.make_provider(urlopen, popen_factory=popen)

        items = provider.list_items()
        provider.close()

        self.assertEqual(
            [item.item_type for item in items],
            [ITEM_TYPE_SEARCH, ITEM_TYPE_BACK],
        )
        self.assertFalse(provider.owns_process)
        popen.assert_not_called()

    def test_server_is_started_without_shell_and_becomes_ready(self):
        calls = []
        process = FakeProcess()
        popen = Mock(return_value=process)

        def urlopen(url, timeout):
            calls.append(url)
            if len(calls) == 1:
                raise URLError("not running")
            return FakeResponse("Kiwix", url)

        provider = self.make_provider(urlopen, popen_factory=popen)

        provider.list_items()

        self.assertTrue(provider.owns_process)
        command = popen.call_args.args[0]
        self.assertEqual(command[0], str(self.server_path))
        self.assertIn("--address=127.0.0.1", command)
        self.assertIn("--port=8080", command)
        self.assertIn("--threads=1", command)
        self.assertEqual(command[-1], str(self.zim_path))
        self.assertFalse(popen.call_args.kwargs["shell"])
        provider.close()

    def test_server_start_failure_is_reported(self):
        popen = Mock(return_value=FakeProcess(return_code=1))

        def unavailable(_url, timeout):
            raise URLError("not running")

        provider = self.make_provider(unavailable, popen_factory=popen)

        with self.assertRaisesRegex(KiwixProviderError, "unavailable"):
            provider.list_items()
        self.assertFalse(provider.owns_process)

    def test_server_start_timeout_is_bounded_and_process_is_stopped(self):
        process = FakeProcess()
        clock = {"now": 0.0}

        def unavailable(_url, timeout):
            raise URLError("not running")

        def monotonic():
            return clock["now"]

        def sleep(seconds):
            clock["now"] += seconds

        provider = self.make_provider(
            unavailable,
            popen_factory=Mock(return_value=process),
            monotonic=monotonic,
            sleeper=sleep,
        )

        with self.assertRaisesRegex(KiwixProviderError, "unavailable"):
            provider.list_items()

        self.assertTrue(process.terminated)
        self.assertLessEqual(clock["now"], 0.25)
        self.assertFalse(provider.owns_process)

    def test_missing_files_and_occupied_port_are_reported(self):
        def unavailable(_url, timeout):
            raise URLError("not running")

        missing_zim = self.make_provider(
            unavailable, zim_path=self.zim_path.parent / "missing.zim"
        )
        with self.assertRaisesRegex(KiwixProviderError, "unavailable"):
            missing_zim.list_items()

        missing_server = self.make_provider(
            unavailable, server_path=self.server_path.parent / "missing"
        )
        with self.assertRaisesRegex(KiwixProviderError, "unavailable"):
            missing_server.list_items()

        popen = Mock()
        occupied = self.make_provider(
            unavailable,
            popen_factory=popen,
            port_checker=lambda _host, _port: True,
        )
        with self.assertRaisesRegex(KiwixProviderError, "unavailable"):
            occupied.list_items()
        popen.assert_not_called()

    def test_search_results_are_parsed_deduplicated_and_limited(self):
        search_html = """
            <a href="/content/wikipedia/Raspberry_Pi">
              <span>Raspberry Pi</span>
            </a>
            <a href="/content/wikipedia/Raspberry_Pi">Duplicate</a>
            <a href="/content/wikipedia/Banana_Pi">Banana Pi</a>
            <a href="https://example.com/content/ignored">Ignored</a>
        """
        requested_urls = []

        def urlopen(url, timeout):
            requested_urls.append(url)
            body = search_html if "/search?" in url else "Kiwix"
            return FakeResponse(body, url)

        provider = self.make_provider(urlopen, result_limit=2)

        results = provider.search("Raspberry Pi")

        self.assertEqual(
            [(result.id, result.title) for result in results],
            [
                ("/content/wikipedia/Raspberry_Pi", "Raspberry Pi"),
                ("/content/wikipedia/Banana_Pi", "Banana Pi"),
            ],
        )
        self.assertTrue(
            any("pattern=Raspberry+Pi" in url for url in requested_urls)
        )
        self.assertTrue(any("pageLength=2" in url for url in requested_urls))

    def test_search_uses_only_links_from_official_results_container(self):
        search_html = """
            <div class="header">
              <a href="/content/wikipedia/Wikipedia">Header link</a>
            </div>
            <div class="results">
              <ul>
                <li>
                  <a href="/content/wikipedia/Asien">Asien</a>
                  <cite>Asien ist der größte Erdteil ...</cite>
                </li>
              </ul>
            </div>
            <div class="footer">
              <a href="/content/wikipedia/Not_A_Result">Footer link</a>
            </div>
        """

        def urlopen(url, timeout):
            body = search_html if "/search?" in url else "Kiwix"
            return FakeResponse(body, url)

        provider = self.make_provider(urlopen)

        results = provider.search("Asien")

        self.assertEqual(
            [(result.id, result.title) for result in results],
            [("/content/wikipedia/Asien", "Asien")],
        )

    def test_search_without_results_returns_empty_list(self):
        def urlopen(url, timeout):
            body = (
                "<html><p>No result links</p></html>"
                if "/search?" in url
                else "Kiwix"
            )
            return FakeResponse(body, url)

        provider = self.make_provider(urlopen)

        self.assertEqual(provider.search("does-not-exist"), [])

    def test_empty_search_query_is_rejected_without_http(self):
        urlopen = Mock()
        provider = self.make_provider(urlopen)

        with self.assertRaisesRegex(KiwixProviderError, "Invalid"):
            provider.search("   ")
        urlopen.assert_not_called()

    def test_article_html_becomes_readable_plain_text(self):
        article_html = """
            <html><head>
              <title>Raspberry Pi</title>
              <style>.hidden { color: red; }</style>
            </head><body>
              <nav><p>Navigation menu</p></nav>
              <h1>Raspberry Pi</h1>
              <p>Der <strong>Raspberry Pi</strong> ist ein &amp; Computer.</p>
              <ul><li>Ein Eintrag</li><li>Noch ein Eintrag</li></ul>
              <script>window.bad = true;</script>
            </body></html>
        """

        def urlopen(url, timeout):
            body = article_html if "/content/" in url else "Kiwix"
            return FakeResponse(body, url)

        provider = self.make_provider(urlopen)

        document = provider.open_item("/content/wikipedia/Raspberry_Pi")

        self.assertEqual(document.title, "Raspberry Pi")
        self.assertEqual(document.provider, "kiwix")
        self.assertIn("Der Raspberry Pi ist ein & Computer.", document.text)
        self.assertIn("- Ein Eintrag", document.text)
        self.assertNotIn("Navigation menu", document.text)
        self.assertNotIn("window.bad", document.text)
        self.assertNotIn("color: red", document.text)

    def test_modern_wikipedia_root_classes_do_not_hide_article(self):
        article_html = """
            <html class="client-nojs vector-feature-main-menu-pinned-disabled">
              <head><title>Asien</title></head>
              <body class="skin-vector vector-feature-toc-pinned-clientpref-1">
                <div class="vector-main-menu-landmark">
                  <p>Navigation menu</p>
                </div>
                <main id="content">
                  <h1>Asien</h1>
                  <div id="mw-content-text">
                    <div class="mw-parser-output">
                      <p>Asien ist der größte Erdteil.</p>
                    </div>
                  </div>
                </main>
              </body>
            </html>
        """
        requested_urls = []

        def urlopen(url, timeout):
            requested_urls.append(url)
            body = article_html if "/content/" in url else "Kiwix"
            return FakeResponse(body, url)

        provider = self.make_provider(urlopen)

        document = provider.open_item("/content/wikipedia/Asien")

        self.assertEqual(document.title, "Asien")
        self.assertIn("Asien ist der größte Erdteil.", document.text)
        self.assertNotIn("Navigation menu", document.text)
        self.assertFalse(any("/raw/" in url for url in requested_urls))

    def test_empty_content_response_retries_raw_zim_entry(self):
        requested_urls = []

        def urlopen(url, timeout):
            requested_urls.append(url)
            if "/raw/" in url:
                return FakeResponse(
                    "<html><head><title>Asien</title></head>"
                    "<body><p>Lesbarer Rohtext.</p></body></html>",
                    url,
                )
            if "/content/" in url:
                return FakeResponse("<script>viewer only</script>", url)
            return FakeResponse("Kiwix", url)

        provider = self.make_provider(urlopen)

        document = provider.open_item("/content/wikipedia/Asien")

        self.assertEqual(document.title, "Asien")
        self.assertIn("Lesbarer Rohtext.", document.text)
        self.assertTrue(
            any("/raw/wikipedia/content/Asien" in url for url in requested_urls)
        )

    def test_heading_and_id_are_used_as_title_fallbacks(self):
        def heading_response(url, timeout):
            body = (
                "<h1>Erste Überschrift</h1><p>Inhalt</p>"
                if "/content/" in url
                else "Kiwix"
            )
            return FakeResponse(body, url)

        provider = self.make_provider(heading_response)
        document = provider.open_item("/content/wikipedia/Fallback_Name")
        self.assertEqual(document.title, "Erste Überschrift")

        self.assertEqual(
            provider.get_title("/content/wikipedia/Raspberry_Pi"),
            "Raspberry Pi",
        )

    def test_malformed_html_does_not_crash(self):
        def urlopen(url, timeout):
            body = (
                "<title>Kaputt</title><p>Lesbarer <b>Text"
                if "/content/" in url
                else "Kiwix"
            )
            return FakeResponse(body, url)

        provider = self.make_provider(urlopen)
        document = provider.open_item("/content/wikipedia/Kaputt")

        self.assertEqual(document.title, "Kaputt")
        self.assertIn("Lesbarer Text", document.text)

    def test_html_without_readable_article_is_reported(self):
        def urlopen(url, timeout):
            body = "<script>only code</script>" if "/content/" in url else "Kiwix"
            return FakeResponse(body, url)

        provider = self.make_provider(urlopen)

        with self.assertRaisesRegex(KiwixProviderError, "Article unavailable"):
            provider.open_item("/content/wikipedia/Empty")

    def test_http_timeout_is_reported(self):
        def urlopen(url, timeout):
            if "/search?" in url:
                raise TimeoutError("timed out")
            return FakeResponse("Kiwix", url)

        provider = self.make_provider(urlopen)

        with self.assertRaisesRegex(KiwixProviderError, "Wikipedia unavailable"):
            provider.search("Raspberry")

    def test_missing_article_is_reported(self):
        def urlopen(url, timeout):
            if "/content/" in url:
                raise URLError("not found")
            return FakeResponse("Kiwix", url)

        provider = self.make_provider(urlopen)

        with self.assertRaisesRegex(KiwixProviderError, "Article unavailable"):
            provider.open_item("/content/wikipedia/Missing")

    def test_cleanup_terminates_only_owned_process(self):
        calls = []
        process = FakeProcess()
        popen = Mock(return_value=process)

        def urlopen(url, timeout):
            calls.append(url)
            if len(calls) == 1:
                raise URLError("not running")
            return FakeResponse("Kiwix", url)

        provider = self.make_provider(urlopen, popen_factory=popen)
        provider.list_items()

        provider.close()

        self.assertTrue(process.terminated)
        self.assertFalse(process.killed)
        self.assertFalse(provider.owns_process)

    def test_cleanup_kills_owned_process_after_stop_timeout(self):
        class StubbornProcess(FakeProcess):
            def terminate(self):
                self.terminated = True

            def wait(self, timeout=None):
                if not self.killed:
                    raise subprocess.TimeoutExpired("kiwix-serve", timeout)
                return self.return_code

        calls = []
        process = StubbornProcess()

        def urlopen(url, timeout):
            calls.append(url)
            if len(calls) == 1:
                raise URLError("not running")
            return FakeResponse("Kiwix", url)

        provider = self.make_provider(
            urlopen, popen_factory=Mock(return_value=process)
        )
        provider.list_items()

        provider.close()

        self.assertTrue(process.terminated)
        self.assertTrue(process.killed)


if __name__ == "__main__":
    unittest.main()

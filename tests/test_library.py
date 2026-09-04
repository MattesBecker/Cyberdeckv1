import tempfile
import unittest
from pathlib import Path

from library import (
    ITEM_TYPE_DIRECTORY,
    ITEM_TYPE_DOCUMENT,
    LibraryProviderError,
    LibraryProviderRegistry,
    LocalLibraryProvider,
    SearchResult,
)
from pages.library import LibraryPage


class FakeDisplay:
    def __init__(self, body_line_count=3):
        self.body_line_count = body_line_count
        self.last = None
        self.wrap_count = 0

    def render_page(self, title, lines, footer):
        self.last = (title, list(lines), footer)
        return True

    def wrap_text(self, text):
        self.wrap_count += 1
        return text.splitlines() or [""]


class LocalLibraryProviderTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.base = Path(self.temporary_directory.name)
        self.root = self.base / "library"
        self.provider = LocalLibraryProvider(self.root)

    def test_empty_directory_is_created_and_listed(self):
        self.assertFalse(self.root.exists())
        self.assertEqual(self.provider.list_items(), [])
        self.assertTrue(self.root.is_dir())

    def test_lists_directories_then_supported_files(self):
        self.root.mkdir()
        (self.root / "Documents").mkdir()
        (self.root / "Manual.txt").write_text("Manual", encoding="utf-8")
        (self.root / "Ideas.md").write_text("Ideas", encoding="utf-8")
        (self.root / "photo.png").write_bytes(b"not an image")

        items = self.provider.list_items()

        self.assertEqual(
            [(item.title, item.item_type, item.provider) for item in items],
            [
                ("Documents", ITEM_TYPE_DIRECTORY, "local"),
                ("Ideas.md", ITEM_TYPE_DOCUMENT, "local"),
                ("Manual.txt", ITEM_TYPE_DOCUMENT, "local"),
            ],
        )
        self.assertEqual(items[0].id, "Documents")

    def test_reads_text_and_markdown_as_plain_utf8(self):
        self.root.mkdir()
        (self.root / "Text.txt").write_text("Grüße", encoding="utf-8")
        markdown = "# Heading\n\n**plain markdown**"
        (self.root / "Guide.md").write_text(markdown, encoding="utf-8")

        text_document = self.provider.open_item("Text.txt")
        markdown_document = self.provider.open_item("Guide.md")

        self.assertEqual(text_document.text, "Grüße")
        self.assertEqual(text_document.provider, "local")
        self.assertEqual(text_document.title, "Text.txt")
        self.assertEqual(markdown_document.text, markdown)

    def test_get_title_uses_provider_or_item_title(self):
        self.root.mkdir()
        (self.root / "Manual.txt").write_text("Manual", encoding="utf-8")

        self.assertEqual(self.provider.get_title(""), "Local files")
        self.assertEqual(self.provider.get_title("Manual.txt"), "Manual.txt")

    def test_invalid_utf8_is_reported(self):
        self.root.mkdir()
        (self.root / "broken.txt").write_bytes(b"\xff\xfe")

        with self.assertRaisesRegex(LibraryProviderError, "UTF-8"):
            self.provider.open_item("broken.txt")

    def test_path_traversal_and_absolute_paths_are_rejected(self):
        outside = self.base / "secret.md"
        outside.write_text("secret", encoding="utf-8")

        for unsafe_id in ("../secret.md", str(outside)):
            with self.subTest(item_id=unsafe_id):
                with self.assertRaises(LibraryProviderError):
                    self.provider.open_item(unsafe_id)
        with self.assertRaises(LibraryProviderError):
            self.provider.list_items("../")

    def test_symbolic_links_are_not_listed_or_opened(self):
        self.root.mkdir()
        outside = self.base / "secret.md"
        outside.write_text("secret", encoding="utf-8")
        link = self.root / "escape.md"
        try:
            link.symlink_to(outside)
        except (NotImplementedError, OSError) as exc:
            self.skipTest("Symbolic links unavailable: {0}".format(exc))

        self.assertEqual(self.provider.list_items(), [])
        with self.assertRaisesRegex(LibraryProviderError, "Symbolic"):
            self.provider.open_item("escape.md")

    def test_local_search_is_not_implemented(self):
        with self.assertRaisesRegex(LibraryProviderError, "not supported"):
            self.provider.search("manual")


class LibraryProviderRegistryTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root = Path(self.temporary_directory.name) / "library"
        self.provider = LocalLibraryProvider(root)

    def test_lists_and_resolves_provider(self):
        registry = LibraryProviderRegistry((self.provider,))

        self.assertEqual(registry.list_providers(), (self.provider,))
        self.assertIs(registry.get("local"), self.provider)

    def test_invalid_provider_is_reported(self):
        registry = LibraryProviderRegistry((self.provider,))

        with self.assertRaisesRegex(LibraryProviderError, "Unknown"):
            registry.get("kiwix")

    def test_duplicate_provider_is_rejected(self):
        with self.assertRaisesRegex(LibraryProviderError, "Duplicate"):
            LibraryProviderRegistry((self.provider, self.provider))

    def test_search_result_is_provider_independent(self):
        result = SearchResult(
            provider="future", id="article/1", title="Article", preview="Text"
        )

        self.assertEqual(result.provider, "future")
        self.assertEqual(result.id, "article/1")


class LibraryPageTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name) / "library"
        self.root.mkdir()
        self.provider = LocalLibraryProvider(self.root)
        self.registry = LibraryProviderRegistry((self.provider,))
        self.page = LibraryPage(self.registry)
        self.display = FakeDisplay()

    def _open_local_files(self):
        self.page.open_library()
        self.assertEqual(self.page.select(), "changed")

    def test_provider_menu_renders_local_search_and_back(self):
        self.page.open_library()
        self.page.render(self.display)

        self.assertEqual(self.display.last[0], "LIBRARY")
        self.assertEqual(
            self.display.last[1],
            ["> Local files", "  Search", "  Back"],
        )

    def test_empty_local_provider_renders_without_navigation_changes(self):
        self._open_local_files()
        self.page.render(self.display)

        self.assertEqual(self.display.last[0], "Local files")
        self.assertEqual(self.display.last[1], ["(empty)"])
        self.assertFalse(self.page.move_up())
        self.assertFalse(self.page.move_down())
        self.assertEqual(self.page.select(), "unchanged")

    def test_folder_file_and_back_navigation(self):
        documents = self.root / "Documents"
        documents.mkdir()
        (documents / "Manual.txt").write_text("Read me", encoding="utf-8")

        self._open_local_files()
        self.assertEqual(self.page.select(), "changed")
        self.assertEqual(self.page.current_container_id, "Documents")
        self.assertEqual(self.page.select(), "opened")
        self.assertEqual(self.page.mode, self.page.DOCUMENT_MODE)

        self.assertTrue(self.page.back())
        self.assertEqual(self.page.current_container_id, "Documents")
        self.assertEqual(self.page.mode, self.page.BROWSE_MODE)
        self.assertTrue(self.page.back())
        self.assertEqual(self.page.current_container_id, "")
        self.assertTrue(self.page.back())
        self.assertEqual(self.page.mode, self.page.MAIN_MODE)
        self.assertFalse(self.page.back())

    def test_large_file_pages_and_is_wrapped_only_once(self):
        lines = ["line {0}".format(index) for index in range(7)]
        (self.root / "Large.txt").write_text(
            "\n".join(lines), encoding="utf-8"
        )
        self._open_local_files()
        self.assertEqual(self.page.select(), "opened")

        self.page.render(self.display)
        self.assertEqual(self.display.last[1], lines[:3])
        self.assertEqual(self.display.wrap_count, 1)
        self.assertTrue(self.page.move_down())
        self.page.render(self.display)
        self.assertEqual(self.display.last[1], lines[3:6])
        self.assertEqual(self.display.wrap_count, 1)
        self.assertTrue(self.page.move_down())
        self.page.render(self.display)
        self.assertEqual(self.display.last[1], lines[6:])
        self.assertFalse(self.page.move_down())

    def test_invalid_file_shows_message_and_back_returns_to_provider(self):
        (self.root / "broken.md").write_bytes(b"\xff")
        self._open_local_files()

        self.assertEqual(self.page.select(), "changed")
        self.assertEqual(self.page.mode, self.page.MESSAGE_MODE)
        self.page.render(self.display)
        self.assertEqual(self.display.last[0], "broken.md")
        self.assertIn("UTF-8", " ".join(self.display.last[1]))
        self.assertTrue(self.page.back())
        self.assertEqual(self.page.mode, self.page.BROWSE_MODE)

    def test_search_is_an_explicit_nonfunctional_placeholder(self):
        self.page.open_library()
        self.assertTrue(self.page.move_down())

        self.assertEqual(self.page.select(), "changed")
        self.assertEqual(self.page.mode, self.page.MESSAGE_MODE)
        self.page.render(self.display)
        self.assertEqual(self.display.last[0], "SEARCH")
        self.assertIn("not available", " ".join(self.display.last[1]))
        self.assertTrue(self.page.back())
        self.assertEqual(self.page.mode, self.page.MAIN_MODE)

    def test_back_menu_item_returns_back_action(self):
        self.page.open_library()
        self.page.move_down()
        self.page.move_down()

        self.assertEqual(self.page.select(), "back")

    def test_invalid_provider_is_displayed_without_crashing(self):
        self.page.open_library()

        self.assertFalse(self.page.open_provider("kiwix"))
        self.assertEqual(self.page.mode, self.page.MESSAGE_MODE)
        self.page.render(self.display)
        self.assertIn("Unknown", " ".join(self.display.last[1]))


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from pages.library import LibraryPage
from services import LibraryService, LibraryServiceError


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


class LibraryServiceTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.base = Path(self.temporary_directory.name)
        self.root = self.base / "library"
        self.service = LibraryService(self.root)

    def test_empty_directory_is_created_and_listed(self):
        self.assertFalse(self.root.exists())
        self.assertEqual(self.service.list_directory(), [])
        self.assertTrue(self.root.is_dir())

    def test_lists_directories_then_supported_files(self):
        self.root.mkdir()
        (self.root / "Documents").mkdir()
        (self.root / "Manual.txt").write_text("Manual", encoding="utf-8")
        (self.root / "Ideas.md").write_text("Ideas", encoding="utf-8")
        (self.root / "photo.png").write_bytes(b"not an image")

        entries = self.service.list_directory()

        self.assertEqual(
            [(entry.name, entry.is_directory) for entry in entries],
            [
                ("Documents", True),
                ("Ideas.md", False),
                ("Manual.txt", False),
            ],
        )

    def test_reads_text_and_markdown_as_plain_utf8(self):
        self.root.mkdir()
        (self.root / "Text.txt").write_text("Grüße", encoding="utf-8")
        markdown = "# Heading\n\n**plain markdown**"
        (self.root / "Guide.md").write_text(markdown, encoding="utf-8")

        self.assertEqual(
            self.service.read_document("Text.txt").text, "Grüße"
        )
        self.assertEqual(
            self.service.read_document("Guide.md").text, markdown
        )

    def test_invalid_utf8_is_reported(self):
        self.root.mkdir()
        (self.root / "broken.txt").write_bytes(b"\xff\xfe")

        with self.assertRaisesRegex(LibraryServiceError, "UTF-8"):
            self.service.read_document("broken.txt")

    def test_path_traversal_and_absolute_paths_are_rejected(self):
        outside = self.base / "secret.md"
        outside.write_text("secret", encoding="utf-8")

        for unsafe_path in ("../secret.md", outside):
            with self.subTest(path=unsafe_path):
                with self.assertRaises(LibraryServiceError):
                    self.service.read_document(unsafe_path)
        with self.assertRaises(LibraryServiceError):
            self.service.list_directory("../")

    def test_symbolic_links_are_not_listed_or_opened(self):
        self.root.mkdir()
        outside = self.base / "secret.md"
        outside.write_text("secret", encoding="utf-8")
        link = self.root / "escape.md"
        try:
            link.symlink_to(outside)
        except (NotImplementedError, OSError) as exc:
            self.skipTest("Symbolic links unavailable: {0}".format(exc))

        self.assertEqual(self.service.list_directory(), [])
        with self.assertRaisesRegex(LibraryServiceError, "Symbolic"):
            self.service.read_document("escape.md")


class LibraryPageTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name) / "library"
        self.root.mkdir()
        self.service = LibraryService(self.root)
        self.page = LibraryPage(self.service)
        self.display = FakeDisplay()

    def test_empty_directory_renders_without_navigation_changes(self):
        self.page.open_root()
        self.page.render(self.display)

        self.assertEqual(self.display.last[0], "LIBRARY")
        self.assertEqual(self.display.last[1], ["(empty)"])
        self.assertFalse(self.page.move_up())
        self.assertFalse(self.page.move_down())
        self.assertEqual(self.page.select(), "unchanged")

    def test_folder_file_and_back_navigation(self):
        documents = self.root / "Documents"
        documents.mkdir()
        (documents / "Manual.txt").write_text("Read me", encoding="utf-8")

        self.page.open_root()
        self.assertEqual(self.page.select(), "changed")
        self.assertEqual(self.page.current_directory, Path("Documents"))
        self.assertEqual(self.page.select(), "opened")
        self.assertEqual(self.page.mode, self.page.FILE_MODE)

        self.assertTrue(self.page.back())
        self.assertEqual(self.page.current_directory, Path("Documents"))
        self.assertEqual(self.page.mode, self.page.LIST_MODE)
        self.assertTrue(self.page.back())
        self.assertEqual(self.page.current_directory, Path())
        self.assertFalse(self.page.back())

    def test_large_file_pages_and_is_wrapped_only_once(self):
        lines = ["line {0}".format(index) for index in range(7)]
        (self.root / "Large.txt").write_text(
            "\n".join(lines), encoding="utf-8"
        )
        self.page.open_root()
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

    def test_invalid_file_shows_error_and_back_returns_to_list(self):
        (self.root / "broken.md").write_bytes(b"\xff")
        self.page.open_root()

        self.assertEqual(self.page.select(), "changed")
        self.assertEqual(self.page.mode, self.page.ERROR_MODE)
        self.page.render(self.display)
        self.assertEqual(self.display.last[0], "broken.md")
        self.assertIn("UTF-8", " ".join(self.display.last[1]))
        self.assertTrue(self.page.back())
        self.assertEqual(self.page.mode, self.page.LIST_MODE)


if __name__ == "__main__":
    unittest.main()

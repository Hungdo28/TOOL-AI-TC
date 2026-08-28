import unittest

from services.file_processing import (
    GOOGLE_DOC_MIME_TYPE,
    GOOGLE_SHEET_MIME_TYPE,
    prepare_workspace_file,
)


class FileProcessingTests(unittest.TestCase):
    def test_word_is_prepared_as_google_doc(self):
        result = prepare_workspace_file(
            "SRS đăng nhập.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            b"docx",
        )
        self.assertEqual(result.title, "SRS đăng nhập")
        self.assertEqual(result.target_mime_type, GOOGLE_DOC_MIME_TYPE)

    def test_excel_is_prepared_as_google_sheet(self):
        result = prepare_workspace_file(
            "Danh sách API.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"xlsx",
        )
        self.assertEqual(result.title, "Danh sách API")
        self.assertEqual(result.target_mime_type, GOOGLE_SHEET_MIME_TYPE)

    def test_path_is_removed_from_filename(self):
        result = prepare_workspace_file("../spec.pdf", "application/pdf", b"pdf")
        self.assertEqual(result.title, "spec")

    def test_unknown_extension_is_rejected(self):
        with self.assertRaises(ValueError):
            prepare_workspace_file("payload.exe", "application/octet-stream", b"exe")


if __name__ == "__main__":
    unittest.main()


#!/usr/bin/env python3
"""
Basic test script for RenameWithLLM.
"""

from pathlib import Path
import tempfile

from src.detectors import ContentDetector, ExtensionDetector, MimeDetector
from src.extractors import CodeExtractor, TextExtractor
from src.naming import CaseFormatterImpl


def _create_test_files(temp_path: Path) -> tuple[Path, Path]:
    """Create test files and return text_file, code_file paths."""
    # Test text file
    text_file = temp_path / "test.txt"
    text_file.write_text("This is a test document with some content.")

    # Test code file
    code_file = temp_path / "test.py"
    code_file.write_text(
        """
def hello_world():
    print("Hello, World!")

class TestClass:
    def __init__(self):
        self.value = 42
"""
    )

    return text_file, code_file


def test_detectors():
    """Test file type detectors."""
    print("Testing file type detectors...")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        text_file, code_file = _create_test_files(temp_path)

        # Test detectors
        mime_detector = MimeDetector()
        content_detector = ContentDetector()
        extension_detector = ExtensionDetector()

        # Test text file
        print("Text file detection:")
        print(f"  MIME: {mime_detector.detect(text_file)}")
        print(f"  Content: {content_detector.detect(text_file)}")
        print(f"  Extension: {extension_detector.detect(text_file)}")

        # Test code file
        print("Code file detection:")
        print(f"  MIME: {mime_detector.detect(code_file)}")
        print(f"  Content: {content_detector.detect(code_file)}")
        print(f"  Extension: {extension_detector.detect(code_file)}")


def test_extractors():
    """Test content extractors."""
    print("\nTesting content extractors...")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        text_file, code_file = _create_test_files(temp_path)

        text_extractor = TextExtractor()
        content = text_extractor.extract(text_file, {"max_chars": 100})
        print(f"Text extraction: {content.text[:50]}...")

        code_extractor = CodeExtractor()
        content = code_extractor.extract(code_file, {"max_chars": 100})
        print(f"Code extraction: {content.text[:50]}...")
        print(f"Functions found: {content.metadata.get('functions', [])}")


def test_case_formatter():
    """Test case formatting."""
    print("\nTesting case formatter...")

    formatter = CaseFormatterImpl()
    test_text = "hello world test"

    cases = ["snake_case", "Title Case", "camelCase", "kebab-case", "UPPER_CASE"]

    for case in cases:
        formatted = formatter.format(test_text, case)
        print(f"  {case}: {formatted}")


def test_basic_functionality():
    """Test basic functionality without OpenAI API."""
    print("Testing basic functionality...")

    try:
        test_detectors()
        test_extractors()
        test_case_formatter()
        print("\n✅ Basic functionality tests passed!")
        return True
    except Exception as e:
        print(f"\n❌ Basic functionality test failed: {e}")
        return False


if __name__ == "__main__":
    print("AI File Rename Tool - Basic Tests")
    print("=" * 40)

    success = test_basic_functionality()

    if success:
        print("\n🎉 All basic tests passed! The tool structure is working.")
        print("\nTo test with OpenAI API:")
        print("1. Set OPENAI_API_KEY environment variable")
        print("2. Run: python main.py test.txt")
    else:
        print("\n💥 Some tests failed. Check the error messages above.")

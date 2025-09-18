"""File type detection implementations."""

try:
    import magic

    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

from pathlib import Path

from .core import FileType, FileTypeDetector


class MimeDetector(FileTypeDetector):
    """File type detection using MIME types."""

    def __init__(self):
        if not MAGIC_AVAILABLE:
            raise ImportError("python-magic is not available")
        self.magic = magic.Magic(mime=True)
        self.mime_mapping = {
            # Documents
            "application/pdf": FileType.PDF,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
                FileType.DOCX
            ),
            "application/msword": FileType.DOCX,
            # Images
            "image/jpeg": FileType.IMAGE,
            "image/png": FileType.IMAGE,
            "image/gif": FileType.IMAGE,
            "image/bmp": FileType.IMAGE,
            "image/tiff": FileType.IMAGE,
            "image/webp": FileType.IMAGE,
            "image/svg+xml": FileType.IMAGE,
            # Text and code
            "text/plain": FileType.TEXT,
            "text/html": FileType.MARKUP,
            "text/xml": FileType.MARKUP,
            "text/css": FileType.CODE,
            "text/javascript": FileType.CODE,
            "text/x-python": FileType.CODE,
            "text/x-java": FileType.CODE,
            "text/x-c": FileType.CODE,
            "text/x-c++": FileType.CODE,
            "text/x-go": FileType.CODE,
            "text/x-rust": FileType.CODE,
            "text/x-ruby": FileType.CODE,
            "text/x-php": FileType.CODE,
            "text/x-perl": FileType.CODE,
            "text/x-shellscript": FileType.CODE,
            "text/x-sql": FileType.CODE,
            # Data formats
            "text/csv": FileType.DATA,
            "text/tab-separated-values": FileType.DATA,
            "application/json": FileType.DATA,
            "text/x-json": FileType.DATA,
            "text/x-yaml": FileType.CONFIG,
            "application/x-yaml": FileType.CONFIG,
            # Archives
            "application/zip": FileType.ARCHIVE,
            "application/x-tar": FileType.ARCHIVE,
            "application/gzip": FileType.ARCHIVE,
        }

    def detect(self, file_path: Path) -> FileType:
        """Detect file type using MIME type."""
        try:
            mime_type = self.magic.from_file(str(file_path))
            return self.mime_mapping.get(mime_type, FileType.UNKNOWN)
        except Exception:
            return FileType.UNKNOWN

    def get_confidence(self) -> float:
        """MIME detection is reliable, but content detection is better for code."""
        return 0.8


class SignatureDetector(FileTypeDetector):
    """File type detection using file signatures."""

    def __init__(self):
        self.signatures = {
            b"%PDF": FileType.PDF,
            b"PK\x03\x04": FileType.DOCX,  # ZIP-based format
            b"\x89PNG": FileType.IMAGE,
            b"\xff\xd8\xff": FileType.IMAGE,  # JPEG
            b"GIF8": FileType.IMAGE,
            b"BM": FileType.IMAGE,  # BMP
            b"RIFF": FileType.IMAGE,  # WebP
            b"<!DOCTYPE": FileType.MARKUP,
            b"<html": FileType.MARKUP,
            b"<?xml": FileType.MARKUP,
            b"{": FileType.DATA,  # JSON
            b"[": FileType.DATA,  # JSON array
        }

    def detect(self, file_path: Path) -> FileType:
        """Detect file type using file signature."""
        try:
            with open(file_path, "rb") as f:
                header = f.read(512)
                for signature, file_type in self.signatures.items():
                    if header.startswith(signature):
                        return file_type
            return FileType.UNKNOWN
        except Exception:
            return FileType.UNKNOWN

    def get_confidence(self) -> float:
        """Signature detection is very reliable when it matches."""
        return 0.95


class ContentDetector(FileTypeDetector):
    """File type detection using content analysis."""

    def __init__(self):
        self.code_patterns = [
            r"\b(function|def|class|interface|struct|enum|import|require|"
            r"module|package|namespace)\b",
            r"\b(if|else|elif|while|for|switch|case|break|continue|return)\b",
            r"\b(var|let|const|int|string|bool|float|double|char|void)\b",
            r"[{}();]",  # Common code symbols
            r"/\*.*?\*/",  # Block comments
            r"//.*",  # Line comments
            r"#.*",  # Hash comments
        ]

        self.markup_patterns = [
            r"<[^>]+>",  # XML/HTML tags
            r"^\s*#+\s",  # Markdown headers
            r"^\s*\*\s",  # Markdown lists
            r"\[.*?\]\(.*?\)",  # Markdown links
        ]

        self.config_patterns = [
            r"^\s*\w+\s*=",  # Key=value pairs
            r"^\s*\[.*?\]",  # INI sections
            r"^\s*\w+:",  # YAML-style
        ]

    def detect(self, file_path: Path) -> FileType:
        """Detect file type using content analysis."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read(1000)

            if self._looks_like_code(content):
                return FileType.CODE
            elif self._looks_like_markup(content):
                return FileType.MARKUP
            elif self._looks_like_config(content):
                return FileType.CONFIG
            elif self._looks_like_data(content):
                return FileType.DATA
            else:
                return FileType.TEXT
        except UnicodeDecodeError:
            return FileType.BINARY
        except Exception:
            return FileType.UNKNOWN

    def _looks_like_code(self, content: str) -> bool:
        """Check if content looks like source code."""
        import re

        content_lower = content.lower()

        # Check for code patterns
        pattern_count = sum(
            1
            for pattern in self.code_patterns
            if re.search(pattern, content, re.IGNORECASE)
        )

        # Check for common keywords
        keywords = [
            "function",
            "def",
            "class",
            "import",
            "var",
            "let",
            "const",
            "if",
            "for",
            "while",
        ]
        keyword_count = sum(
            1
            for keyword in keywords
            if f" {keyword} " in content_lower
            or content_lower.startswith(f"{keyword} ")
        )

        return pattern_count >= 2 or keyword_count >= 2

    def _looks_like_markup(self, content: str) -> bool:
        """Check if content looks like markup."""
        import re

        return any(
            re.search(pattern, content, re.MULTILINE)
            for pattern in self.markup_patterns
        )

    def _looks_like_config(self, content: str) -> bool:
        """Check if content looks like configuration."""
        import re

        return any(
            re.search(pattern, content, re.MULTILINE)
            for pattern in self.config_patterns
        )

    def _looks_like_data(self, content: str) -> bool:
        """Check if content looks like structured data."""
        content = content.strip()
        return content.startswith(("{", "[")) or (
            "," in content and content.count(",") > content.count("\n")
        )

    def get_confidence(self) -> float:
        """Content detection is very reliable for code and structured files."""
        return 0.9


class ExtensionDetector(FileTypeDetector):
    """File type detection using file extensions as fallback."""

    def __init__(self):
        self.extension_mapping = {
            ".py": FileType.CODE,
            ".js": FileType.CODE,
            ".ts": FileType.CODE,
            ".java": FileType.CODE,
            ".cpp": FileType.CODE,
            ".c": FileType.CODE,
            ".go": FileType.CODE,
            ".rs": FileType.CODE,
            ".rb": FileType.CODE,
            ".php": FileType.CODE,
            ".swift": FileType.CODE,
            ".kt": FileType.CODE,
            ".html": FileType.MARKUP,
            ".htm": FileType.MARKUP,
            ".xml": FileType.MARKUP,
            ".css": FileType.CODE,
            ".scss": FileType.CODE,
            ".sass": FileType.CODE,
            ".json": FileType.DATA,
            ".yaml": FileType.CONFIG,
            ".yml": FileType.CONFIG,
            ".ini": FileType.CONFIG,
            ".conf": FileType.CONFIG,
            ".properties": FileType.CONFIG,
            ".txt": FileType.TEXT,
            ".md": FileType.MARKUP,
            ".rst": FileType.MARKUP,
            ".pdf": FileType.PDF,
            ".docx": FileType.DOCX,
            ".doc": FileType.DOCX,
        }

    def detect(self, file_path: Path) -> FileType:
        """Detect file type using extension."""
        suffix = file_path.suffix.lower()
        return self.extension_mapping.get(suffix, FileType.UNKNOWN)

    def get_confidence(self) -> float:
        """Extension detection is less reliable than content-based methods."""
        return 0.5


class CompositeDetector(FileTypeDetector):
    """Composite detector that tries multiple detection methods."""

    def __init__(self, detectors: list[FileTypeDetector]):
        self.detectors = detectors

    def detect(self, file_path: Path) -> FileType:
        """Try all detectors in order of confidence."""
        results = []
        for detector in self.detectors:
            try:
                file_type = detector.detect(file_path)
                confidence = detector.get_confidence()
                results.append((file_type, confidence))
            except Exception:
                continue

        if not results:
            return FileType.UNKNOWN

        # Return result with highest confidence
        results.sort(key=lambda x: x[1], reverse=True)
        return results[0][0]

    def get_confidence(self) -> float:
        """Return confidence of the best detector."""
        if not self.detectors:
            return 0.0
        return max(detector.get_confidence() for detector in self.detectors)

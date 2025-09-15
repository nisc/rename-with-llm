"""
Core interfaces and base classes for the AI file rename tool.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class FileType(Enum):
    """Supported file types."""

    PDF = "pdf"
    DOCX = "docx"
    CODE = "code"
    TEXT = "text"
    IMAGE = "image"
    MARKUP = "markup"
    CONFIG = "config"
    DATA = "data"
    ARCHIVE = "archive"
    BINARY = "binary"
    UNKNOWN = "unknown"


@dataclass
class Content:
    """Extracted content from a file."""

    text: str
    metadata: dict[str, Any]
    file_type: FileType
    confidence: float = 1.0
    extraction_method: str = "unknown"


@dataclass
class FileAnalysis:
    """Complete analysis of a file."""

    file_path: Path
    file_type: FileType
    content: Content
    size: int
    modified_time: float
    detection_confidence: float = 1.0


@dataclass
class NamingResult:
    """Result of AI naming analysis."""

    suggestions: list[str]
    summary: str | None = None
    confidence: float = 1.0
    cost: float = 0.0
    tokens_used: int = 0


@dataclass
class Config:
    """Configuration for the AI rename tool."""

    file_types: dict[str, dict[str, Any]]
    extraction: dict[str, Any]
    cost_management: dict[str, Any]
    naming: dict[str, Any]
    safety: dict[str, Any]

    @classmethod
    def from_file(cls, config_path: str) -> "Config":
        """Load configuration from YAML file."""
        if not YAML_AVAILABLE:
            raise ImportError("PyYAML is not available")
        with open(config_path) as f:
            data = yaml.safe_load(f)
        return cls(**data)


class FileTypeDetector(ABC):
    """Base class for file type detectors."""

    @abstractmethod
    def detect(self, file_path: Path) -> FileType:
        """Detect the file type."""
        pass

    @abstractmethod
    def get_confidence(self) -> float:
        """Get confidence score for this detector."""
        pass


class ContentExtractor(ABC):
    """Base class for content extractors."""

    @abstractmethod
    def can_handle(self, file_type: FileType) -> bool:
        """Check if this extractor can handle the file type."""
        pass

    @abstractmethod
    def extract(self, file_path: Path, config: dict[str, Any]) -> Content:
        """Extract content from file."""
        pass


class NamingEngine(ABC):
    """Base class for naming engines."""

    @abstractmethod
    def generate_names(
        self,
        analysis: FileAnalysis,
        count: int,
        case_format: str,
        include_summary: bool,
    ) -> NamingResult:
        """Generate filename suggestions."""
        pass


class CaseFormatter(ABC):
    """Base class for case formatters."""

    @abstractmethod
    def format(self, text: str, case_type: str) -> str:
        """Format text according to case type."""
        pass


class SafetyChecker(ABC):
    """Base class for safety checks."""

    @abstractmethod
    def check_rename_safety(self, source: Path, target: Path) -> dict[str, Any]:
        """Check if rename operation is safe."""
        pass

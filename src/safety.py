"""
Safety checks and file operation safeguards.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .core import SafetyChecker


class FileSafetyChecker(SafetyChecker):
    """Implementation of safety checks for file operations."""

    def __init__(self, create_backups: bool = False, backup_dir: Path | None = None):
        self.create_backups = create_backups
        self.backup_dir = backup_dir or Path(".backups")

    def check_rename_safety(self, source: Path, target: Path) -> dict[str, Any]:
        """Check if rename operation is safe."""
        result: dict[str, Any] = {
            "safe": True,
            "warnings": [],
            "errors": [],
            "backup_created": False,
        }

        # Check if source exists
        if not source.exists():
            result["safe"] = False
            result["errors"].append(f"Source file does not exist: {source}")
            return result

        # Check if target already exists
        if target.exists():
            result["safe"] = False
            result["errors"].append(f"Target file already exists: {target}")
            return result

        # Check if source and target are the same
        if source.resolve() == target.resolve():
            result["safe"] = False
            result["errors"].append("Source and target are the same file")
            return result

        # Check if target directory exists
        if not target.parent.exists():
            result["safe"] = False
            result["errors"].append(f"Target directory does not exist: {target.parent}")
            return result

        # Check if target directory is writable
        if not target.parent.is_dir() or not target.parent.stat().st_mode & 0o200:
            result["safe"] = False
            result["errors"].append(
                f"Target directory is not writable: {target.parent}"
            )
            return result

        # Check file size (warn for very large files)
        file_size = source.stat().st_size
        if file_size > 100 * 1024 * 1024:  # 100MB
            result["warnings"].append(
                f"Large file detected: {file_size / (1024 * 1024):.1f}MB"
            )

        # Create backup if requested
        if self.create_backups and result["safe"]:
            backup_path = self._create_backup(source)
            if backup_path:
                result["backup_created"] = True
                result["backup_path"] = backup_path
            else:
                result["warnings"].append("Failed to create backup")

        return result

    def _create_backup(self, source: Path) -> Path | None:
        """Create a backup of the source file."""
        try:
            # Create backup directory if it doesn't exist
            self.backup_dir.mkdir(parents=True, exist_ok=True)

            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{source.stem}_{timestamp}{source.suffix}"
            backup_path = self.backup_dir / backup_name

            # Copy file to backup location
            shutil.copy2(source, backup_path)
            return backup_path

        except Exception as e:
            print(f"Warning: Failed to create backup: {e}")
            return None

    def suggest_alternative_name(self, target: Path) -> Path:
        """Suggest an alternative name if target exists."""
        base_name = target.stem
        extension = target.suffix
        parent = target.parent

        counter = 1
        while True:
            alternative = parent / f"{base_name}_{counter}{extension}"
            if not alternative.exists():
                return alternative
            counter += 1

            # Prevent infinite loop
            if counter > 1000:
                # Use timestamp as fallback
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                return parent / f"{base_name}_{timestamp}{extension}"

    def validate_filename(self, filename: str) -> dict[str, Any]:
        """Validate filename for filesystem compatibility."""
        result: dict[str, Any] = {"valid": True, "warnings": [], "errors": []}

        # Check for invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            if char in filename:
                result["valid"] = False
                result["errors"].append(f"Invalid character: {char}")

        # Check length
        if len(filename) > 255:
            result["valid"] = False
            result["errors"].append("Filename too long (max 255 characters)")

        # Check for reserved names (Windows)
        reserved_names = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        }

        name_without_ext = filename.rsplit(".", 1)[0].upper()
        if name_without_ext in reserved_names:
            result["valid"] = False
            result["errors"].append(f"Reserved name: {name_without_ext}")

        # Check for leading/trailing spaces or dots
        if filename.startswith((" ", ".")) or filename.endswith((" ", ".")):
            result["warnings"].append("Filename has leading/trailing spaces or dots")

        return result

    def check_disk_space(self, source: Path, target_dir: Path) -> dict[str, Any]:
        """Check if there's enough disk space for the operation."""
        result: dict[str, Any] = {
            "sufficient": True,
            "available_space": 0,
            "required_space": 0,
            "warnings": [],
        }

        try:
            # Get file size
            file_size = source.stat().st_size
            result["required_space"] = file_size

            # Get available space (simplified - works on most systems)
            statvfs = os.statvfs(str(target_dir))
            available_space = statvfs.f_frsize * statvfs.f_bavail
            result["available_space"] = available_space

            # Check if there's enough space (with some buffer)
            if file_size > available_space * 0.9:  # 90% of available space
                result["sufficient"] = False
                result["warnings"].append("Low disk space warning")

        except Exception as e:
            result["warnings"].append(f"Could not check disk space: {e}")

        return result


class BatchSafetyChecker:
    """Safety checker for batch operations."""

    def __init__(self, safety_checker: FileSafetyChecker):
        self.safety_checker = safety_checker

    def check_batch_safety(self, operations: list[dict[str, Any]]) -> dict[str, Any]:
        """Check safety for a batch of rename operations."""
        result: dict[str, Any] = {
            "safe": True,
            "total_operations": len(operations),
            "safe_operations": 0,
            "unsafe_operations": 0,
            "warnings": [],
            "errors": [],
            "operation_results": [],
        }

        for i, operation in enumerate(operations):
            source = Path(operation["source"])
            target = Path(operation["target"])

            op_result = self.safety_checker.check_rename_safety(source, target)
            op_result["operation_index"] = i
            result["operation_results"].append(op_result)

            if op_result["safe"]:
                result["safe_operations"] += 1
            else:
                result["unsafe_operations"] += 1
                result["errors"].extend(op_result["errors"])

            result["warnings"].extend(op_result["warnings"])

        # Overall safety
        result["safe"] = result["unsafe_operations"] == 0

        return result

    def suggest_batch_alternatives(
        self, operations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Suggest alternative names for conflicting operations."""
        alternatives = []

        for operation in operations:
            source = Path(operation["source"])
            target = Path(operation["target"])

            if target.exists():
                alternative = self.safety_checker.suggest_alternative_name(target)
                alternatives.append(
                    {
                        "source": str(source),
                        "original_target": str(target),
                        "alternative_target": str(alternative),
                    }
                )

        return alternatives

"""
Command-line interface for the AI file rename tool.
"""

import os
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, IntPrompt

from .core import Config, FileAnalysis
from .detectors import (
    CompositeDetector,
    ContentDetector,
    ExtensionDetector,
    MimeDetector,
    SignatureDetector,
)
from .extractors import (
    CodeExtractor,
    CompositeExtractor,
    DOCXExtractor,
    FallbackExtractor,
    ImageExtractor,
    PDFExtractor,
    TextExtractor,
)
from .naming import OpenAINamingEngine
from .safety import FileSafetyChecker

console = Console()


class AIRenameTool:
    """Main AI rename tool class."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.detector = self._setup_detector()
        self.extractor = self._setup_extractor()
        self.naming_engine = self._setup_naming_engine()
        self.safety_checker = self._setup_safety_checker()

    def _load_config(self, config_path: str) -> Config:
        """Load configuration from file."""
        try:
            return Config.from_file(config_path)
        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not load config from {config_path}: "
                f"{e}[/yellow]"
            )
            # Return default config
            return self._get_default_config()

    def _get_default_config(self) -> Config:
        """Get default configuration."""
        return Config(
            file_types={},
            extraction={},
            cost_management={"target_cost_per_file": 0.05},
            naming={"default_count": 3, "default_case": "snake_case"},
            safety={"prevent_overwrites": True, "confirm_renames": True},
        )

    def _setup_detector(self) -> CompositeDetector:
        """Setup file type detector."""
        detectors = [
            MimeDetector(),
            SignatureDetector(),
            ContentDetector(),
            ExtensionDetector(),
        ]
        return CompositeDetector(detectors)

    def _setup_extractor(self) -> CompositeExtractor:
        """Setup content extractor."""
        extractors = [
            PDFExtractor(),
            DOCXExtractor(),
            CodeExtractor(),
            TextExtractor(),
            ImageExtractor(),
            FallbackExtractor(),
        ]
        return CompositeExtractor(extractors)

    def _setup_naming_engine(self) -> OpenAINamingEngine:
        """Setup naming engine."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise click.ClickException(
                "OPENAI_API_KEY environment variable is required"
            )

        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return OpenAINamingEngine(api_key, model)

    def _setup_safety_checker(self) -> FileSafetyChecker:
        """Setup safety checker."""
        create_backups = self.config.safety.get("create_backups", False)
        return FileSafetyChecker(create_backups=create_backups)

    def analyze_file(self, file_path: Path) -> FileAnalysis:
        """Analyze a single file."""
        # Detect file type
        file_type = self.detector.detect(file_path)

        # Extract content
        content = self.extractor.extract(
            file_path, {"file_type": file_type, "max_chars": 1000}
        )

        # Get file stats
        stat = file_path.stat()

        return FileAnalysis(
            file_path=file_path,
            file_type=file_type,
            content=content,
            size=stat.st_size,
            modified_time=stat.st_mtime,
        )

    def process_files(
        self,
        file_paths: list[Path],
        count: int,
        case_format: str,
        include_summary: bool,
        dry_run: bool,
    ) -> list[dict[str, Any]]:
        """Process multiple files."""
        results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Processing files...", total=len(file_paths))

            for file_path in file_paths:
                try:
                    # Analyze file
                    analysis = self.analyze_file(file_path)

                    # Generate names
                    naming_result = self.naming_engine.generate_names(
                        analysis, count, case_format, include_summary
                    )

                    results.append(
                        {
                            "file_path": file_path,
                            "analysis": analysis,
                            "naming_result": naming_result,
                            "success": True,
                        }
                    )

                except Exception as e:
                    results.append(
                        {"file_path": file_path, "error": str(e), "success": False}
                    )

                progress.advance(task)

        return results

    def display_results(self, results: list[dict[str, Any]], include_summary: bool):
        """Display processing results."""
        for result in results:
            if not result["success"]:
                console.print(
                    f"[red]Error processing {result['file_path']}: "
                    f"{result['error']}[/red]"
                )
                continue

            file_path = result["file_path"]
            naming_result = result["naming_result"]

            # Display file info
            console.print(f"\n[bold]File: {file_path.name}[/bold]")

            # Display suggestions
            console.print("Suggestions:")
            for i, suggestion in enumerate(naming_result.suggestions, 1):
                console.print(f"  {i}. {suggestion}")

            # Display summary if requested
            if include_summary and naming_result.summary:
                console.print(f"\n[dim]Summary: {naming_result.summary}[/dim]")

            # Display cost info
            if naming_result.cost > 0:
                console.print(f"[dim]Cost: ${naming_result.cost:.6f}[/dim]")


@click.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True))
@click.option("--count", "-c", default=3, help="Number of filename suggestions")
@click.option(
    "--case",
    default="snake_case",
    type=click.Choice(
        [
            "snake_case",
            "Title Case",
            "camelCase",
            "kebab-case",
            "UPPER_CASE",
            "lower case",
            "no caps",
            "PascalCase",
        ]
    ),
    help="Case format for filenames",
)
@click.option("--summary", "-s", is_flag=True, help="Include file summary")
@click.option("--dry-run", "-d", is_flag=True, help="Preview without renaming")
@click.option(
    "--model",
    default="gpt-4o-mini",
    type=click.Choice(["gpt-4o-mini", "gpt-3.5-turbo", "gpt-4"]),
    help="OpenAI model to use",
)
@click.option("--date-prefix", is_flag=True, help="Add date prefix to filenames")
@click.option("--config", default="config.yaml", help="Configuration file path")
def main(files, count, case, summary, dry_run, model, date_prefix, config):
    """AI-powered file renaming tool with content analysis."""

    # Set model environment variable
    os.environ["OPENAI_MODEL"] = model

    try:
        # Initialize tool
        tool = AIRenameTool(config)

        # Collect files
        file_paths = []
        for file_path in files:
            path = Path(file_path)
            if path.is_file():
                file_paths.append(path)
            elif path.is_dir():
                # Add all files in directory
                file_paths.extend([f for f in path.rglob("*") if f.is_file()])

        if not file_paths:
            console.print("[red]No files found to process[/red]")
            return

        # Process all files - let MIME type detection handle file type identification
        # This allows support for any file type that our detectors can identify
        filtered_files = file_paths

        if not filtered_files:
            console.print("[red]No files found to process[/red]")
            return

        # Process files
        results = tool.process_files(filtered_files, count, case, summary, dry_run)

        # Display results
        tool.display_results(results, summary)

        # Handle renaming if not dry run
        if not dry_run:
            _handle_renaming(results, tool.safety_checker, date_prefix)

    except click.ClickException:
        # Re-raise click exceptions without modification
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


def _handle_renaming(
    results: list[dict[str, Any]], safety_checker: FileSafetyChecker, date_prefix: bool
):
    """Handle the actual renaming process."""
    successful_results = [r for r in results if r["success"]]

    if not successful_results:
        console.print("[red]No files to rename[/red]")
        return

    # Show cost summary
    total_cost = sum(r["naming_result"].cost for r in successful_results)
    console.print(f"\n[bold]Total estimated cost: ${total_cost:.6f}[/bold]")

    # Confirm before proceeding
    if not Confirm.ask("Proceed with renaming?"):
        console.print("Operation cancelled")
        return

    # Process each file
    for result in successful_results:
        file_path = result["file_path"]
        naming_result = result["naming_result"]

        # Let user choose suggestion
        choice = IntPrompt.ask(
            f"Choose filename for {file_path.name} "
            f"(1-{len(naming_result.suggestions)})",
            default=1,
        )

        if 1 <= choice <= len(naming_result.suggestions):
            new_name = naming_result.suggestions[choice - 1]

            # Add date prefix if requested
            if date_prefix:
                from datetime import datetime

                date_str = datetime.now().strftime("%Y-%m-%d")
                new_name = f"{date_str}_{new_name}"

            # Create target path
            target_path = file_path.parent / new_name

            # Check safety
            safety_result = safety_checker.check_rename_safety(file_path, target_path)

            if not safety_result["safe"]:
                console.print(
                    f"[red]Cannot rename {file_path.name}: "
                    f"{safety_result['errors'][0]}[/red]"
                )
                continue

            # Perform rename
            try:
                file_path.rename(target_path)
                console.print(f"[green]Renamed: {file_path.name} → {new_name}[/green]")
            except Exception as e:
                console.print(f"[red]Failed to rename {file_path.name}: {e}[/red]")

"""Command-line interface for the AI file rename tool."""

import asyncio
import os
from pathlib import Path
from typing import Any

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import IntPrompt

from .constants import (
    CASE_FORMATS,
    DEFAULT_CASE,
    DEFAULT_CONFIG_FILE,
    DEFAULT_COUNT,
    DEFAULT_MODEL,
    ENV_OPENAI_API_KEY,
    ENV_OPENAI_MODEL,
    MAX_CONTENT_EXTRACTION_LENGTH,
    MAX_FILENAME_LENGTH,
    OPENAI_MODELS,
    TOKENS_FOR_SUMMARY,
    TOKENS_PER_SUGGESTION,
)
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

# Load environment variables from .env file
load_dotenv()

console = Console()


class AIRenameTool:
    """Main AI rename tool class."""

    def __init__(
        self,
        config_path: str = "config.yaml",
        verbose: bool = False,
        max_chars: int = 50,
    ):
        self.config = self._load_config(config_path)
        self.verbose = verbose
        self.max_chars = max_chars

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
            naming={"default_count": 3, "default_case": DEFAULT_CASE},
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
        api_key = os.getenv(ENV_OPENAI_API_KEY)
        if not api_key:
            raise click.ClickException(
                f"{ENV_OPENAI_API_KEY} environment variable is required"
            )

        model = os.getenv(ENV_OPENAI_MODEL, DEFAULT_MODEL)
        return OpenAINamingEngine(api_key, model, self.verbose)

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
            file_path,
            {"file_type": file_type, "max_chars": MAX_CONTENT_EXTRACTION_LENGTH},
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

    async def process_files(
        self,
        file_paths: list[Path],
        count: int,
        case_format: str,
        summary: bool,
        dry_run: bool,
    ) -> list[dict[str, Any]]:
        """Process multiple files asynchronously for better performance."""
        import asyncio

        async def process_single_file(file_path: Path) -> dict[str, Any]:
            """Process a single file asynchronously."""
            try:
                # Analyze file
                analysis = self.analyze_file(file_path)

                # Generate names asynchronously
                naming_result = await self.naming_engine.generate_names(
                    analysis, count, case_format, summary, self.max_chars
                )

                return {
                    "file_path": file_path,
                    "analysis": analysis,
                    "naming_result": naming_result,
                    "success": True,
                }
            except Exception as e:
                return {
                    "file_path": file_path,
                    "error": str(e),
                    "success": False,
                }

        # Process all files concurrently
        tasks = [process_single_file(file_path) for file_path in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions that weren't caught
        processed_results: list[dict[str, Any]] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "file_path": file_paths[i],
                        "error": str(result),
                        "success": False,
                    }
                )
            elif isinstance(result, dict):
                processed_results.append(result)

        return processed_results

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
            original_extension = file_path.suffix
            for i, suggestion in enumerate(naming_result.suggestions, 1):
                suggestion_with_extension = f"{suggestion}{original_extension}"
                console.print(
                    f"  [bold cyan]{i}.[/bold cyan] {suggestion_with_extension}",
                    highlight=False,
                )

            # Display summary if requested
            if include_summary and naming_result.summary:
                console.print(f"\n[dim]Summary: {naming_result.summary}[/dim]")

    def display_and_choose(
        self,
        results: list[dict[str, Any]],
        include_summary: bool,
        dry_run: bool,
        date_prefix: bool,
    ):
        """Display results and let user choose filenames immediately."""
        successful_results = [r for r in results if r.get("success", False)]
        failed_results = [r for r in results if not r.get("success", False)]

        if not successful_results:
            if failed_results:
                console.print("[red]Failed to process files:[/red]")
                for result in failed_results:
                    file_path = result["file_path"]
                    error = result.get("error", "Unknown error")
                    console.print(f"  [red]{file_path.name}: {error}[/red]")
            else:
                console.print("[red]No files to rename[/red]")
            return

        # Process each file immediately
        for result in successful_results:
            file_path = result["file_path"]
            naming_result = result["naming_result"]

            # Display file info
            console.print(f"\n[bold]File: {file_path.name}[/bold]")

            # Display summary if requested
            if include_summary and naming_result.summary:
                console.print(f"[dim]Summary: {naming_result.summary}[/dim]")

            # Display suggestions
            console.print("Suggestions:")
            original_extension = file_path.suffix
            console.print(
                f"  [bold cyan]0.[/bold cyan] {file_path.name} (keep current)",
                highlight=False,
            )
            for i, suggestion in enumerate(naming_result.suggestions, 1):
                # Add date prefix if requested
                if date_prefix:
                    from datetime import datetime

                    date_str = datetime.now().strftime("%Y-%m-%d")
                    suggestion = f"{date_str}_{suggestion}"

                suggestion_with_extension = f"{suggestion}{original_extension}"
                console.print(
                    f"  [bold cyan]{i}.[/bold cyan] {suggestion_with_extension}",
                    highlight=False,
                )

            # Add custom input option as the last option
            custom_option_number = len(naming_result.suggestions) + 1
            console.print(
                f"  [bold cyan]{custom_option_number}.[/bold cyan] Enter custom name",
                highlight=False,
            )

            # Ask for choice immediately
            if not dry_run:
                choice = IntPrompt.ask(
                    f"Choose filename for {file_path.name} (0-{custom_option_number})",
                    default=0,
                )

                if choice == 0:
                    # Keep current filename - no action needed
                    console.print(
                        f"[yellow]Keeping current filename: {file_path.name}[/yellow]"
                    )
                elif 1 <= choice <= len(naming_result.suggestions):
                    new_name = naming_result.suggestions[choice - 1]
                elif choice == custom_option_number:
                    # Custom input option
                    from rich.prompt import Prompt

                    new_name = Prompt.ask("Enter custom filename (without extension)")
                else:
                    console.print(f"[red]Invalid choice: {choice}[/red]")
                    continue

                # Process the rename if not keeping current
                if choice != 0:
                    # Add date prefix if requested
                    if date_prefix:
                        from datetime import datetime

                        date_str = datetime.now().strftime("%Y-%m-%d")
                        new_name = f"{date_str}_{new_name}"

                    # Preserve the original file extension
                    new_name_with_extension = f"{new_name}{original_extension}"

                    # Create target path
                    target_path = file_path.parent / new_name_with_extension

                    # Check safety
                    safety_result = self.safety_checker.check_rename_safety(
                        file_path, target_path
                    )

                    if not safety_result["safe"]:
                        console.print(
                            f"[red]Cannot rename {file_path.name}: "
                            f"{safety_result['errors'][0]}[/red]"
                        )
                        continue

                    # Perform rename
                    try:
                        file_path.rename(target_path)
                        console.print(
                            f"[green]Renamed: {file_path.name} → "
                            f"{new_name_with_extension}[/green]"
                        )
                    except Exception as e:
                        console.print(
                            f"[red]Failed to rename {file_path.name}: {e}[/red]"
                        )


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("files", nargs=-1, type=click.Path(exists=True))
@click.option(
    "--count",
    "-c",
    default=DEFAULT_COUNT,
    help=f"Number of filename suggestions [default: {DEFAULT_COUNT}]",
)
@click.option(
    "--case",
    default=DEFAULT_CASE,
    type=click.Choice(CASE_FORMATS),
    help=f"Case format for filenames [default: {DEFAULT_CASE}]",
)
@click.option("--summary", "-s", is_flag=True, help="Include file summary")
@click.option("--dry-run", "-d", is_flag=True, help="Preview without renaming")
@click.option(
    "--model",
    default=DEFAULT_MODEL,
    type=click.Choice(list(OPENAI_MODELS.values())),
    help=f"OpenAI model to use [default: {DEFAULT_MODEL}]",
)
@click.option("--date-prefix", is_flag=True, help="Add date prefix to filenames")
@click.option("--verbose", "-v", is_flag=True, help="Show the prompt sent to OpenAI")
@click.option(
    "--yes", "-y", is_flag=True, help="Auto-confirm the cost estimation prompt"
)
@click.option(
    "--max-chars",
    default=MAX_FILENAME_LENGTH,
    type=int,
    help=(
        f"Maximum characters for filename suggestions [default: {MAX_FILENAME_LENGTH}]"
    ),
)
@click.option(
    "--config",
    default=DEFAULT_CONFIG_FILE,
    help=f"Configuration file path [default: {DEFAULT_CONFIG_FILE}]",
)
def main(
    files,
    count,
    case,
    summary,
    dry_run,
    model,
    date_prefix,
    verbose,
    yes,
    max_chars,
    config,
):
    """AI-powered file renaming tool with content analysis."""

    # Set model environment variable
    os.environ["OPENAI_MODEL"] = model

    try:
        # Collect files first (before expensive initialization)
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

        # Initialize tool only if we have files to process
        tool = AIRenameTool(config, verbose=verbose, max_chars=max_chars)

        # Process all files - let MIME type detection handle file type identification
        # This allows support for any file type that our detectors can identify
        filtered_files = file_paths

        if not filtered_files:
            console.print("[red]No files found to process[/red]")
            return

        # Calculate and display cost estimate
        console.print("[yellow]Calculating cost estimate...[/yellow]")
        estimated_cost = 0.0
        for _ in filtered_files:
            # Estimate input tokens based on content length (roughly 4 chars per token)
            # We extract up to MAX_CONTENT_EXTRACTION_LENGTH chars, so estimate
            input_tokens = MAX_CONTENT_EXTRACTION_LENGTH // 4
            output_tokens = count * TOKENS_PER_SUGGESTION + (
                TOKENS_FOR_SUMMARY if summary else 0
            )

            # Use the same pricing as the naming engine
            from .constants import MODEL_PRICING, OPENAI_MODELS

            model = os.getenv("OPENAI_MODEL", "gpt-4.1-nano")
            input_cost, output_cost = MODEL_PRICING.get(
                model, MODEL_PRICING[OPENAI_MODELS["GPT_4_1_NANO"]]
            )
            cost = (input_tokens * input_cost + output_tokens * output_cost) / 1000
            estimated_cost += cost

        console.print(f"[bold]Estimated cost: ${estimated_cost:.4f} USD[/bold]")
        # Ask for confirmation before proceeding
        from rich.prompt import Confirm

        mode_text = "dry-run preview" if dry_run else "processing"
        if not yes and not Confirm.ask(f"Proceed with {mode_text}?", default=True):
            console.print("Operation cancelled")
            return

        # Process files asynchronously for better performance
        console.print("[yellow]Sending data to OpenAI...[/yellow]")
        results = asyncio.run(
            tool.process_files(filtered_files, count, case, summary, dry_run)
        )

        # Display results and handle renaming immediately
        console.print("[green]✓ Processing complete![/green]")
        tool.display_and_choose(results, summary, dry_run, date_prefix)

    except click.ClickException:
        # Re-raise click exceptions without modification
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e

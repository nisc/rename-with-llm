"""Naming engine and case formatting implementations."""

import re

import openai

from .constants import (
    CASE_CAMEL,
    CASE_KEBAB,
    CASE_LOWER,
    CASE_NO_CAPS,
    CASE_PASCAL,
    CASE_SNAKE,
    CASE_TITLE,
    CASE_UPPER,
    DEFAULT_MODEL,
    MAX_FILENAME_LENGTH,
    MODEL_PRICING,
    OPENAI_MODELS,
)
from .core import (
    CaseFormatter,
    FileAnalysis,
    NamingEngine,
    NamingResult,
    format_api_error,
)


class OpenAINamingEngine(NamingEngine):
    """OpenAI-based naming engine."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, verbose: bool = False):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.verbose = verbose
        self.case_formatter = CaseFormatterImpl()

    async def generate_names(
        self,
        analysis: FileAnalysis,
        count: int,
        case_format: str,
        include_summary: bool,
        max_chars: int = MAX_FILENAME_LENGTH,
    ) -> NamingResult:
        """Generate filename suggestions using OpenAI asynchronously."""
        try:
            # Prepare content for AI
            content = self._prepare_content(analysis)

            # Create prompt
            prompt = self._create_prompt(
                content,
                analysis.file_path.name,
                count,
                case_format,
                include_summary,
                max_chars,
            )

            # Output prompt if verbose mode is enabled
            if self.verbose:
                print("\n" + "=" * 80)
                print("PROMPT SENT TO OPENAI:")
                print("=" * 80)
                print(prompt)
                print("=" * 80 + "\n")

            # Calculate token usage
            input_tokens = len(prompt.split())  # Rough estimation
            output_tokens = count * 20 + (50 if include_summary else 0)

            # Make async API call using asyncio.to_thread for non-async client
            import asyncio

            def make_api_call():
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=output_tokens,
                    temperature=0.7,
                )

            response = await asyncio.to_thread(make_api_call)

            # Extract response content
            response_content = response.choices[0].message.content or ""

            # Output response if verbose mode is enabled
            if self.verbose:
                print("OPENAI RESPONSE:")
                print("=" * 80)
                print(response_content)
                print("=" * 80 + "\n")

            suggestions, summary = self._parse_response(
                response_content, include_summary
            )

            # Apply case formatting
            formatted_suggestions = [
                self.case_formatter.format(s, case_format) for s in suggestions
            ]

            # Calculate cost
            cost = self._calculate_cost(input_tokens, output_tokens)

            return NamingResult(
                suggestions=formatted_suggestions,
                summary=summary,
                confidence=0.9,
                cost=cost,
                tokens_used=input_tokens + output_tokens,
            )

        except Exception as e:
            # Format the error nicely before re-raising
            formatted_error = format_api_error(e)
            raise Exception(formatted_error) from e

    def _prepare_content(self, analysis: FileAnalysis) -> str:
        """Prepare content for AI analysis."""
        content_parts = []

        # Add main content
        if analysis.content.text:
            content_parts.append(f"Content: {analysis.content.text}")

        # Add metadata
        metadata = analysis.content.metadata
        if metadata.get("title"):
            content_parts.append(f"Title: {metadata['title']}")
        if metadata.get("author"):
            content_parts.append(f"Author: {metadata['author']}")
        if metadata.get("subject"):
            content_parts.append(f"Subject: {metadata['subject']}")
        if metadata.get("functions"):
            content_parts.append(f"Functions: {', '.join(metadata['functions'][:3])}")
        if metadata.get("classes"):
            content_parts.append(f"Classes: {', '.join(metadata['classes'][:3])}")
        if metadata.get("headings"):
            content_parts.append(f"Headings: {', '.join(metadata['headings'][:3])}")

        return "\n".join(content_parts)

    def _create_prompt(
        self,
        content: str,
        current_name: str,
        count: int,
        case_format: str,
        include_summary: bool,
        max_chars: int,
    ) -> str:
        """Create prompt for OpenAI."""

        prompt = f"""Analyze this file and suggest {count} descriptive filenames.

{content}

Current filename: {current_name}

Suggest {count} filenames that are:
- Descriptive of the main content
- Professional and clear
- Vary in length: include some short names (10-20 chars), some medium
  (20-{max_chars // 2} chars), and some longer names
  ({max_chars // 2}-{max_chars} chars)

Return format:
1. filename1
2. filename2
3. filename3"""

        if include_summary:
            prompt += (
                "\n\nAlso provide a brief 1-2 sentence summary of the file "
                "content.\n\nSUMMARY:\n"
            )

        return prompt

    def _parse_response(
        self, response: str, include_summary: bool
    ) -> tuple[list[str], str]:
        """Parse OpenAI response."""
        suggestions = []
        summary = ""

        if include_summary and "SUMMARY:" in response:
            # Split on SUMMARY: and parse both parts
            parts = response.split("SUMMARY:", 1)
            if len(parts) == 2:
                suggestions_text = parts[0]
                summary = parts[1].strip()
            else:
                suggestions_text = response
        else:
            suggestions_text = response

        # Parse suggestions
        for line in suggestions_text.split("\n"):
            line = line.strip()
            if line and (
                line[0].isdigit() or line.startswith("-") or line.startswith("*")
            ):
                # Remove numbering
                suggestion = re.sub(r"^[\d\.\-\*\s]+", "", line).strip()
                if suggestion:
                    suggestions.append(suggestion)

        return suggestions, summary

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate API cost."""
        input_cost, output_cost = MODEL_PRICING.get(
            self.model, MODEL_PRICING[OPENAI_MODELS["GPT_4_1_NANO"]]
        )
        return (input_tokens * input_cost + output_tokens * output_cost) / 1000


class CaseFormatterImpl(CaseFormatter):
    """Implementation of case formatting."""

    def format(self, text: str, case_type: str) -> str:
        """Format text according to case type."""
        # Clean the text first
        text = self._clean_text(text)

        formatters = {
            CASE_SNAKE: self._to_snake_case,
            CASE_TITLE: self._to_title_case,
            CASE_CAMEL: self._to_camel_case,
            CASE_KEBAB: self._to_kebab_case,
            CASE_UPPER: self._to_upper_case,
            CASE_LOWER: self._to_lower_case,
            CASE_NO_CAPS: self._to_no_caps,
            CASE_PASCAL: self._to_pascal_case,
        }

        formatter = formatters.get(case_type, self._to_snake_case)
        return formatter(text)

    def _clean_text(self, text: str) -> str:
        """Clean text for formatting."""
        # Remove file extension if present
        if "." in text:
            text = text.rsplit(".", 1)[0]

        # Remove special characters except spaces and hyphens
        text = re.sub(r"[^\w\s\-]", "", text)

        # Replace multiple spaces with single space
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def _to_snake_case(self, text: str) -> str:
        """Convert to snake_case."""
        # Replace spaces and hyphens with underscores
        text = re.sub(r"[\s\-]+", "_", text)
        return text.lower()

    def _to_title_case(self, text: str) -> str:
        """Convert to Title Case with simple abbreviation handling."""
        # Convert underscores to spaces first for proper Title Case
        text = text.replace("_", " ")

        # First, identify and preserve abbreviations before title casing
        # Pattern 1: All caps words (CV, NY, USA, API, etc.)
        text = re.sub(r"\b([A-Z]{2,})\b", lambda m: f"__ABBREV_{m.group(1)}__", text)

        # Pattern 2: Mixed case with numbers (B2B, iOS, etc.)
        text = re.sub(
            r"\b([A-Z][a-z]*[0-9][A-Za-z]*)\b",
            lambda m: f"__ABBREV_{m.group(1)}__",
            text,
        )

        # Pattern 3: Short all-caps words (AI, IT, HR, etc.)
        text = re.sub(r"\b([A-Z]{2,3})\b", lambda m: f"__ABBREV_{m.group(1)}__", text)

        # Now apply title case
        result = text.title()

        # Restore abbreviations (case-insensitive match)
        result = re.sub(
            r"__abbrev_([A-Za-z0-9]+)__",
            lambda m: m.group(1).upper(),
            result,
            flags=re.IGNORECASE,
        )

        return result

    def _to_camel_case(self, text: str) -> str:
        """Convert to camelCase."""
        words = text.split()
        if not words:
            return text
        return words[0].lower() + "".join(word.capitalize() for word in words[1:])

    def _to_kebab_case(self, text: str) -> str:
        """Convert to kebab-case."""
        # Replace spaces with hyphens
        text = re.sub(r"\s+", "-", text)
        return text.lower()

    def _to_upper_case(self, text: str) -> str:
        """Convert to UPPER_CASE."""
        # Replace spaces with underscores
        text = re.sub(r"\s+", "_", text)
        return text.upper()

    def _to_lower_case(self, text: str) -> str:
        """Convert to lower case."""
        return text.lower()

    def _to_no_caps(self, text: str) -> str:
        """Convert to no caps (lower case with spaces)."""
        return text.lower()

    def _to_pascal_case(self, text: str) -> str:
        """Convert to PascalCase."""
        return "".join(word.capitalize() for word in text.split())

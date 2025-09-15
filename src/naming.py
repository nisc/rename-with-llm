"""
Naming engine and case formatting implementations.
"""

import re

import openai

from .core import CaseFormatter, FileAnalysis, NamingEngine, NamingResult


class OpenAINamingEngine(NamingEngine):
    """OpenAI-based naming engine."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.case_formatter = CaseFormatterImpl()

    def generate_names(
        self,
        analysis: FileAnalysis,
        count: int,
        case_format: str,
        include_summary: bool,
    ) -> NamingResult:
        """Generate filename suggestions using OpenAI."""
        try:
            # Prepare content for AI
            content = self._prepare_content(analysis)

            # Create prompt
            prompt = self._create_prompt(
                content, analysis.file_path.name, count, case_format, include_summary
            )

            # Calculate token usage
            input_tokens = len(prompt.split())  # Rough estimation
            output_tokens = count * 20 + (50 if include_summary else 0)

            # Make API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=output_tokens,
                temperature=0.7,
            )

            # Parse response
            response_content: str | None = response.choices[0].message.content
            if response_content is None:
                return NamingResult(suggestions=[], summary="No response from AI")
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

        except Exception:
            # Fallback to basic naming
            return self._fallback_naming(analysis, count, case_format)

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
    ) -> str:
        """Create prompt for OpenAI."""
        case_instruction = self._get_case_instruction(case_format)

        prompt = f"""Analyze this file and suggest {count} descriptive filenames.

{content}

Current filename: {current_name}
Format: {case_instruction}
Max length: 50 characters

Suggest {count} filenames that are:
- Descriptive of the main content
- Professional and clear
- Under 50 characters
- Use {case_format} format

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

    def _get_case_instruction(self, case_format: str) -> str:
        """Get case formatting instruction."""
        instructions = {
            "snake_case": "snake_case, <50 chars, descriptive",
            "Title Case": "Title Case, <50 chars, descriptive",
            "camelCase": "camelCase, <50 chars, descriptive",
            "kebab-case": "kebab-case, <50 chars, descriptive",
            "UPPER_CASE": "UPPER_CASE, <50 chars, descriptive",
            "lower case": "lower case, <50 chars, descriptive",
            "no caps": "no caps, <50 chars, descriptive",
            "PascalCase": "PascalCase, <50 chars, descriptive",
        }
        return instructions.get(case_format, "snake_case, <50 chars, descriptive")

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
        costs = {
            "gpt-4o-mini": (0.00015, 0.0006),
            "gpt-3.5-turbo": (0.0015, 0.002),
            "gpt-4": (0.03, 0.06),
        }

        input_cost, output_cost = costs.get(self.model, (0.00015, 0.0006))
        return (input_tokens * input_cost + output_tokens * output_cost) / 1000

    def _fallback_naming(
        self, analysis: FileAnalysis, count: int, case_format: str
    ) -> NamingResult:
        """Fallback naming when AI fails."""
        base_name = analysis.file_path.stem
        suggestions = []

        for i in range(count):
            suggestion = f"{base_name}_v{i + 1}"
            formatted = self.case_formatter.format(suggestion, case_format)
            suggestions.append(formatted)

        return NamingResult(
            suggestions=suggestions,
            summary="Fallback naming due to API error",
            confidence=0.3,
            cost=0.0,
            tokens_used=0,
        )


class CaseFormatterImpl(CaseFormatter):
    """Implementation of case formatting."""

    def format(self, text: str, case_type: str) -> str:
        """Format text according to case type."""
        # Clean the text first
        text = self._clean_text(text)

        formatters = {
            "snake_case": self._to_snake_case,
            "Title Case": self._to_title_case,
            "camelCase": self._to_camel_case,
            "kebab-case": self._to_kebab_case,
            "UPPER_CASE": self._to_upper_case,
            "lower case": self._to_lower_case,
            "no caps": self._to_no_caps,
            "PascalCase": self._to_pascal_case,
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
        """Convert to Title Case."""
        return " ".join(word.capitalize() for word in text.split())

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

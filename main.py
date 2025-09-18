#!/usr/bin/env python3
"""RenameWithLLM - A smart file renaming tool using LLM for descriptive filenames."""

from dotenv import load_dotenv

from src.cli import main

# Load environment variables from .env file
load_dotenv()

if __name__ == "__main__":
    main()

"""Constants used throughout the application."""

# OpenAI Models
OPENAI_MODELS = {
    "GPT_4_1_NANO": "gpt-4.1-nano",
    "GPT_4O_MINI": "gpt-4o-mini",
    "GPT_3_5_TURBO": "gpt-3.5-turbo",
    "GPT_4": "gpt-4",
}

# Default model
DEFAULT_MODEL = OPENAI_MODELS["GPT_4_1_NANO"]

# Model pricing (input_cost, output_cost) per 1M tokens
MODEL_PRICING = {
    OPENAI_MODELS["GPT_4_1_NANO"]: (0.0001, 0.0004),  # $0.10/$0.40 per 1M tokens
    OPENAI_MODELS["GPT_4O_MINI"]: (0.00015, 0.0006),  # $0.15/$0.60 per 1M tokens
    OPENAI_MODELS["GPT_3_5_TURBO"]: (0.0015, 0.002),  # $1.50/$2.00 per 1M tokens
    OPENAI_MODELS["GPT_4"]: (0.03, 0.06),  # $30/$60 per 1M tokens
}

# Environment variable names
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_OPENAI_MODEL = "OPENAI_MODEL"
ENV_CONFIG_FILE = "CONFIG_FILE"

# Default values
DEFAULT_CONFIG_FILE = "config.yaml"
DEFAULT_COUNT = 5
DEFAULT_CASE = "Title Case"

# Case formats
CASE_FORMATS = [
    "snake_case",
    "Title Case",
    "camelCase",
    "kebab-case",
    "UPPER_CASE",
    "lower case",
    "no caps",
    "PascalCase",
]

# Individual case format constants
CASE_SNAKE = "snake_case"
CASE_TITLE = "Title Case"
CASE_CAMEL = "camelCase"
CASE_KEBAB = "kebab-case"
CASE_UPPER = "UPPER_CASE"
CASE_LOWER = "lower case"
CASE_NO_CAPS = "no caps"
CASE_PASCAL = "PascalCase"

# File type limits
MAX_FILENAME_LENGTH = 50
MAX_CONTENT_EXTRACTION_LENGTH = 5000

# Token estimation constants
DEFAULT_INPUT_TOKENS_ESTIMATE = 100  # Conservative estimate for cost calculation
TOKENS_PER_SUGGESTION = 20
TOKENS_FOR_SUMMARY = 50

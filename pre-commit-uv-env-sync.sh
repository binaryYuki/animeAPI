#!/bin/zsh

echo "Running pre-commit hook"

uv pip compile pyproject.toml -o requirements.txt
echo "uv env sync successfully"

echo "pre-commit hook finished"
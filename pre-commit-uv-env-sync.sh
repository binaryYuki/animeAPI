#!/bin/zsh

echo "Running pre-commit hook"

uv pip freeze > requirements.txt
uv add --requirements requirements.txt
rm requirements.txt
echo "uv env sync successfully"

echo "pre-commit hook finished"
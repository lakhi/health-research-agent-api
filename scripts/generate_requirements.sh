#!/bin/bash

############################################################################
# Generate requirements.txt from pyproject.toml
# Usage:
# ./scripts/generate_requirements.sh: Generate requirements.txt
# ./scripts/generate_requirements.sh upgrade: Upgrade requirements.txt
# ./scripts/generate_requirements.sh linux: Generate for Linux deployment
############################################################################

CURR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname $CURR_DIR)"
source ${CURR_DIR}/_utils.sh

print_heading "Generating requirements.txt..."

if [[ "$1" = "linux" ]]; then
  print_heading "Generating requirements.txt for Linux deployment..."
  UV_CUSTOM_COMPILE_COMMAND="./scripts/generate_requirements.sh linux" \
    uv pip compile ${REPO_ROOT}/pyproject.toml \
    --index-strategy unsafe-best-match \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.org/simple/ \
    --python-platform x86_64-manylinux_2_28 \
    --python-version 3.12 \
    --no-cache --upgrade -o ${REPO_ROOT}/requirements-linux.txt
elif [[ "$1" = "upgrade" ]]; then
  print_heading "Generating requirements.txt for local development..."
  UV_CUSTOM_COMPILE_COMMAND="./scripts/generate_requirements.sh upgrade" \
    uv pip compile ${REPO_ROOT}/pyproject.toml \
    --no-cache --upgrade -o ${REPO_ROOT}/requirements.txt
else
  print_heading "Generating requirements.txt for local development..."
  UV_CUSTOM_COMPILE_COMMAND="./scripts/generate_requirements.sh" \
    uv pip compile ${REPO_ROOT}/pyproject.toml \
    --no-cache -o ${REPO_ROOT}/requirements.txt
fi

#!/bin/bash

############################################################################
# Script to build the Docker image for linux/amd64 platform.
#
# Instructions:
# 1. Set the IMAGE_NAME and IMAGE_TAG variables to the desired values.
# 2. Ensure Docker is installed and you're authenticated to the registry.
#
# This script builds a Docker image for linux/amd64 platform and pushes it.
############################################################################

# Exit immediately if a command exits with a non-zero status.
set -e

CURR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(dirname ${CURR_DIR})"
DOCKER_FILE="Dockerfile"
IMAGE_NAME="gcr.io/expanded-origin-464315-i8/health-research-agent-api"
IMAGE_TAG="latest"

echo "Running: docker build --platform=linux/amd64 -t $IMAGE_NAME:$IMAGE_TAG -f $DOCKER_FILE $WS_ROOT"
docker build --platform=linux/amd64 -t $IMAGE_NAME:$IMAGE_TAG -f $DOCKER_FILE $WS_ROOT

echo "Running: docker push $IMAGE_NAME:$IMAGE_TAG"
docker push $IMAGE_NAME:$IMAGE_TAG

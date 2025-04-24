#!/bin/bash

CONTAINER_NAME="opencanary_container"
IMAGE_NAME="opencanary-pi-image"
HOST_IP=$(hostname -I | awk '{print $1}')

run_container() {
  echo "Creating new container with HOST_IP: ${HOST_IP}"
  docker run -d \
    --name "${CONTAINER_NAME}" \
    -p 21:21 \
    -p 80:80 \
    -p 8022:8022 \
    -e HOST_IP="$HOST_IP" \
    -v /home/nathan/docker/opencanary_config:/etc/opencanaryd \
    -v /home/nathan/docker/opencanary_logs:/var/tmp \
    -v /home/nathan/docker/opencanary_archive:/var/tmp/log_archive \
    "${IMAGE_NAME}"
}

if docker ps -a --filter "name=${CONTAINER_NAME}" --format '{{.ID}}' | grep -q .; then
  echo "Container '${CONTAINER_NAME}' already exists."

  if docker ps --filter "name=${CONTAINER_NAME}" --format '{{.Status}}' | grep -q "Up"; then
    echo "Stopping existing container..."
    docker stop "${CONTAINER_NAME}"
  fi

  echo "Removing container..."
  docker rm "${CONTAINER_NAME}"
fi

run_container
echo "Container '${CONTAINER_NAME}' is running with HOST_IP: ${HOST_IP}"

#!/bin/bash

# Script para ver logs do backend

# Usa docker compose (nova sintaxe) ou docker-compose (antiga)
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "❌ docker-compose não encontrado"
    exit 1
fi

# Se passar argumento, mostra logs de serviço específico
if [ ! -z "$1" ]; then
    $DOCKER_COMPOSE logs -f "$1"
else
    $DOCKER_COMPOSE logs -f


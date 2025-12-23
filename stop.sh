#!/bin/bash

# Script para parar o backend e Stripe webhook listener

set -e

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configurações
STRIPE_PID_FILE="/tmp/stripe-webhook-listener.pid"

echo -e "${YELLOW}🛑 Parando SecondBrain Backend...${NC}"
echo ""

# Para o Stripe webhook listener se estiver rodando
if [ -f "$STRIPE_PID_FILE" ]; then
    PID=$(cat "$STRIPE_PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${CYAN}💳 Parando Stripe webhook listener (PID: $PID)...${NC}"
        kill "$PID" 2>/dev/null || true
        sleep 1
    fi
    rm -f "$STRIPE_PID_FILE"
fi

# Usa docker compose (nova sintaxe) ou docker-compose (antiga)
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${RED}❌ docker-compose não encontrado${NC}"
    exit 1
fi

echo -e "${YELLOW}🐳 Parando containers Docker...${NC}"
$DOCKER_COMPOSE down

echo ""
echo -e "${GREEN}✅ Backend parado${NC}"


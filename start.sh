#!/bin/bash

# Script para iniciar o backend com docker-compose
# Inclui opção para iniciar Stripe webhook listener

set -e

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configurações
STRIPE_CLI="${HOME}/bin/stripe"
WEBHOOK_ENDPOINT="http://localhost:8000/api/webhooks/stripe"
STRIPE_PID_FILE="/tmp/stripe-webhook-listener.pid"

# Função para iniciar Stripe webhook listener
start_stripe_listener() {
    if [ ! -f "$STRIPE_CLI" ]; then
        echo -e "${YELLOW}⚠️  Stripe CLI não encontrado em $STRIPE_CLI${NC}"
        echo -e "${YELLOW}   Webhooks locais não serão encaminhados.${NC}"
        echo -e "${YELLOW}   Para instalar: ./stripe-webhooks.sh${NC}"
        return 1
    fi
    
    # Verifica se já está rodando
    if [ -f "$STRIPE_PID_FILE" ]; then
        OLD_PID=$(cat "$STRIPE_PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  Stripe listener já está rodando (PID: $OLD_PID)${NC}"
            return 0
        fi
    fi
    
    echo -e "${CYAN}💳 Iniciando Stripe webhook listener...${NC}"
    
    # Inicia em background e salva o PID
    nohup $STRIPE_CLI listen \
        --forward-to "$WEBHOOK_ENDPOINT" \
        --events checkout.session.completed,checkout.session.expired \
        > /tmp/stripe-webhook.log 2>&1 &
    
    STRIPE_PID=$!
    echo $STRIPE_PID > "$STRIPE_PID_FILE"
    
    sleep 2
    
    if ps -p "$STRIPE_PID" > /dev/null 2>&1; then
        # Obtém o webhook secret
        WEBHOOK_SECRET=$($STRIPE_CLI listen --print-secret 2>/dev/null || echo "")
        echo -e "${GREEN}✅ Stripe listener iniciado (PID: $STRIPE_PID)${NC}"
        if [ -n "$WEBHOOK_SECRET" ]; then
            echo -e "${CYAN}   Webhook Secret: ${WEBHOOK_SECRET}${NC}"
        fi
        echo -e "${CYAN}   Logs: tail -f /tmp/stripe-webhook.log${NC}"
        return 0
    else
        echo -e "${RED}❌ Falha ao iniciar Stripe listener${NC}"
        rm -f "$STRIPE_PID_FILE"
        return 1
    fi
}

# Função para parar Stripe webhook listener
stop_stripe_listener() {
    if [ -f "$STRIPE_PID_FILE" ]; then
        PID=$(cat "$STRIPE_PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            kill "$PID" 2>/dev/null || true
            echo -e "${YELLOW}🛑 Stripe listener parado (PID: $PID)${NC}"
        fi
        rm -f "$STRIPE_PID_FILE"
    fi
}

echo -e "${GREEN}🐳 Iniciando SecondBrain Backend com Docker Compose${NC}"
echo ""

# Verifica se docker-compose está instalado
if ! command -v docker-compose &> /dev/null && ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não está instalado${NC}"
    exit 1
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

echo -e "${YELLOW}📦 Verificando imagens...${NC}"
$DOCKER_COMPOSE build

echo ""
echo -e "${YELLOW}🚀 Iniciando serviços...${NC}"
$DOCKER_COMPOSE up -d

echo ""
echo -e "${GREEN}✅ Backend iniciado!${NC}"
echo ""
echo -e "${BLUE}📊 Status dos serviços:${NC}"
$DOCKER_COMPOSE ps

echo ""
echo -e "${GREEN}🌐 API disponível em:${NC}"
echo -e "   ${BLUE}http://localhost:8000${NC}"
echo -e "   ${BLUE}http://0.0.0.0:8000${NC}"
echo ""
echo -e "${YELLOW}📝 Logs:${NC}"
echo "   Para ver os logs: $DOCKER_COMPOSE logs -f api"
echo ""
echo -e "${YELLOW}🛑 Para parar:${NC}"
echo "   ./stop.sh"
echo ""

# Aguarda um pouco e verifica saúde
echo -e "${YELLOW}🔍 Verificando saúde da API...${NC}"
sleep 3

if curl -s --connect-timeout 3 --max-time 5 "http://localhost:8000/api/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API está respondendo!${NC}"
    echo ""
    
    # Inicia Stripe webhook listener automaticamente
    start_stripe_listener
else
    echo -e "${YELLOW}⚠️  API ainda não está respondendo (pode levar alguns segundos)${NC}"
    echo -e "${YELLOW}   Verifique os logs: $DOCKER_COMPOSE logs -f api${NC}"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  SecondBrain Backend está pronto!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"


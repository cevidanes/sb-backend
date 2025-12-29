#!/bin/bash

set -e

echo "🔧 Configurando PostgreSQL para acesso externo na VPS..."

# Senha gerada
POSTGRES_PASSWORD="Qm3jEuT1VtUSjubiBMil!z51f7iCjWPE"
POSTGRES_USER="postgres"
POSTGRES_DB="secondbrain"
VPS_IP="193.180.213.104"

echo "✅ Senha gerada: $POSTGRES_PASSWORD"
echo ""

# Criar diretório de configuração do PostgreSQL
echo "📁 Criando diretório de configuração..."
mkdir -p postgres-config

# Criar arquivo pg_hba.conf para permitir conexões externas
echo "📝 Criando pg_hba.conf..."
cat > postgres-config/pg_hba.conf << 'EOF'
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     trust
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             ::1/128                 scram-sha-256
host    all             all             0.0.0.0/0               scram-sha-256
host    all             all             ::/0                    scram-sha-256
EOF

# Criar arquivo postgresql.conf customizado
echo "📝 Criando postgresql.conf..."
cat > postgres-config/postgresql.conf << 'EOF'
listen_addresses = '*'
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 4MB
min_wal_size = 1GB
max_wal_size = 4GB
EOF

# Atualizar docker-compose.yml
echo "📝 Atualizando docker-compose.yml..."
if [ -f docker-compose.yml ]; then
    # Backup
    cp docker-compose.yml docker-compose.yml.backup
    
    # Verificar se já tem a configuração
    if ! grep -q "listen_addresses" docker-compose.yml; then
        # Adicionar volumes e command ao postgres
        sed -i '/postgres:/a\    command: >\n      postgres\n      -c listen_addresses='\''*'\''\n      -c max_connections=100' docker-compose.yml
        
        # Atualizar volumes do postgres
        if grep -q "volumes:" docker-compose.yml -A 1 | grep -q "postgres_data"; then
            sed -i '/postgres_data:\/var\/lib\/postgresql\/data/a\      - ./postgres-config:/docker-entrypoint-initdb.d' docker-compose.yml
        fi
        
        # Atualizar ports para 0.0.0.0
        sed -i 's/"${POSTGRES_PORT:-5432}:5432"/"0.0.0.0:${POSTGRES_PORT:-5432}:5432"/' docker-compose.yml
    fi
fi

# Atualizar .env com a senha
echo "📝 Atualizando .env..."
if [ -f .env ]; then
    if grep -q "POSTGRES_PASSWORD" .env; then
        sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$POSTGRES_PASSWORD/" .env
    else
        echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" >> .env
    fi
    
    if ! grep -q "POSTGRES_USER" .env; then
        echo "POSTGRES_USER=$POSTGRES_USER" >> .env
    fi
    
    if ! grep -q "POSTGRES_DB" .env; then
        echo "POSTGRES_DB=$POSTGRES_DB" >> .env
    fi
else
    cat > .env << EOF
POSTGRES_USER=$POSTGRES_USER
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=$POSTGRES_DB
POSTGRES_PORT=5432
EOF
fi

# Liberar porta no firewall (se usar ufw)
echo "🔥 Configurando firewall..."
if command -v ufw &> /dev/null; then
    sudo ufw allow 5432/tcp comment "PostgreSQL" || true
    echo "✅ Porta 5432 liberada no UFW"
fi

# Reiniciar containers
echo ""
echo "🔄 Reiniciando containers PostgreSQL..."
docker compose down postgres 2>/dev/null || true
docker compose up -d postgres

echo ""
echo "⏳ Aguardando PostgreSQL iniciar..."
sleep 10

# Verificar se está rodando
if docker ps | grep -q sb-postgres; then
    echo "✅ PostgreSQL está rodando!"
else
    echo "❌ Erro ao iniciar PostgreSQL. Verifique os logs:"
    echo "   docker logs sb-postgres"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ CONFIGURAÇÃO CONCLUÍDA!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "📋 INFORMAÇÕES DE CONEXÃO:"
echo ""
echo "🔐 Senha do PostgreSQL: $POSTGRES_PASSWORD"
echo ""
echo "🔗 STRINGS DE CONEXÃO:"
echo ""
echo "PostgreSQL Standard:"
echo "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$VPS_IP:5432/$POSTGRES_DB"
echo ""
echo "AsyncPG (Python):"
echo "postgresql+asyncpg://$POSTGRES_USER:$POSTGRES_PASSWORD@$VPS_IP:5432/$POSTGRES_DB"
echo ""
echo "DBeaver / pgAdmin / TablePlus:"
echo "  Host: $VPS_IP"
echo "  Port: 5432"
echo "  Database: $POSTGRES_DB"
echo "  User: $POSTGRES_USER"
echo "  Password: $POSTGRES_PASSWORD"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "⚠️  IMPORTANTE:"
echo "   - Guarde a senha em local seguro!"
echo "   - Considere usar VPN ou liberar apenas IPs específicos"
echo "   - A porta 5432 está aberta para acesso externo"
echo ""


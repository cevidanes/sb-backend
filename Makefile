.PHONY: up down build rebuild docker-open

run-docker:
	open -a Docker

up: 
	make run-docker
	@echo "Aguardando Docker iniciar..."
	@until docker info > /dev/null 2>&1; do sleep 1; done
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build

rebuild: 
	make run-docker
	@echo "Aguardando Docker iniciar..."
	@until docker info > /dev/null 2>&1; do sleep 1; done
	docker-compose down
	docker-compose build
	docker-compose up -d

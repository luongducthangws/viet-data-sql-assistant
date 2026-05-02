.PHONY: setup run test docker-up docker-down

# Bước 1: Tải Northwind SQL về
download-data:
	curl -o db/northwind.sql \
	  https://raw.githubusercontent.com/pthom/northwind_psql/master/northwind.sql

# Bước 2: Khởi động PostgreSQL (cần Docker)
db-up:
	docker compose up postgres -d
	@echo "Đợi PostgreSQL khởi động..."
	@sleep 3

# Bước 3: Load data + snapshot schema
setup: db-up
	python db/seed.py

# Chạy server locally
run:
	uvicorn src.api.main:app --reload --port 8000

# Chạy toàn bộ bằng Docker
docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

# Đo accuracy
test:
	python tests/eval.py

# Xem logs
logs:
	docker compose logs -f app

# Shortcut: setup hoàn chỉnh từ đầu
all: download-data setup run
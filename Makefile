.PHONY: install seed dev test lint run docker

install:
	python -m pip install -r requirements-dev.txt

seed:
	python scripts/seed_demo.py

dev:
	uvicorn app.main:app --reload

test:
	pytest

lint:
	ruff check .

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

docker:
	docker compose up --build

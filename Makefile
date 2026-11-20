.PHONY: install setup run test lint check

install:
	pip install -r requirements-dev.txt

setup:
	python manage.py migrate
	python manage.py load_fuel_stations

run:
	python manage.py runserver

test:
	pytest

lint:
	ruff check .

check: lint test
	python manage.py check
	python manage.py makemigrations --check --dry-run

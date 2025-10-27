.PHONY: test test-backend test-frontend test-backend-unit test-backend-integration test-coverage test-coverage-backend test-coverage-frontend clean help install-frontend-deps

# Default target
help:
	@echo "Available targets:"
	@echo "  test                      - Run all tests (backend + frontend)"
	@echo "  test-backend              - Run all backend tests (unit + integration)"
	@echo "  test-backend-unit         - Run backend unit tests only"
	@echo "  test-backend-integration  - Run backend integration tests only"
	@echo "  test-frontend             - Run frontend tests"
	@echo "  test-coverage             - Run all tests with coverage report"
	@echo "  test-coverage-backend     - Run backend tests with coverage"
	@echo "  test-coverage-frontend    - Run frontend tests with coverage"
	@echo "  install-frontend-deps     - Install frontend test dependencies"
	@echo "  clean                     - Clean up cache files and build artifacts"
	@echo "  help                      - Show this help message"

# Combined test targets
test: test-backend test-frontend

test-coverage: test-coverage-backend test-coverage-frontend

# Backend test targets
test-backend:
	python -m pytest tests/ src/

test-backend-unit:
	python -m pytest src/ -v

test-backend-integration:
	python -m pytest tests/integration/ -v

test-coverage-backend:
	python -m pytest tests/ src/ --cov=src --cov-report=html --cov-report=term

# Frontend test targets
test-frontend:
	cd frontend && npm test

test-coverage-frontend:
	cd frontend && npm run test:coverage

# Installation target
install-frontend-deps:
	cd frontend && npm install

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "*.pyd" -delete

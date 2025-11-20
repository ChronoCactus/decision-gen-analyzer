.PHONY: test test-backend test-frontend test-backend-unit test-backend-integration test-coverage test-coverage-backend test-coverage-frontend clean help install-frontend-deps docker-build docker-push-local docker-tag version test-version-script docker-buildx-setup docker-build-multiarch docker-push-local-multiarch docker-push-backend-multiarch docker-push-frontend-multiarch docker-push-frontend-multiarch-sequential docker-push-local-multiarch-sequential docker-buildx-reset

# Configuration
REGISTRY ?= localhost:5000
IMAGE_PREFIX ?= decision-analyzer
BACKEND_IMAGE = $(IMAGE_PREFIX)-backend
FRONTEND_IMAGE = $(IMAGE_PREFIX)-frontend
PLATFORMS ?= linux/amd64,linux/arm64

# Calculate version from git commits
VERSION := $(shell ./scripts/calculate-next-version.sh 2>/dev/null || echo "0.0.0")
GIT_SHA := $(shell git rev-parse --short HEAD)
VERSION_WITH_SHA := $(VERSION)_$(GIT_SHA)

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
	@echo ""
	@echo "Docker targets:"
	@echo "  docker-build                 - Build Docker images (backend + frontend)"
	@echo "  docker-build-multiarch       - Build multi-architecture images (amd64 + arm64)"
	@echo "                                 Requires: docker buildx"
	@echo "  docker-push-local            - Build and push images to local registry"
	@echo "                                 Usage: make docker-push-local REGISTRY=192.168.0.118:5000"
	@echo "  docker-push-local-multiarch  - Build and push multi-arch images to local registry"
	@echo "                                 Usage: make docker-push-local-multiarch REGISTRY=192.168.0.118:5000"
	@echo "                                 Note: Memory-intensive. See sequential build targets below."
	@echo "  docker-tag                   - Tag images with version and latest"
	@echo "  docker-buildx-setup          - Set up Docker buildx for multi-arch builds"
	@echo "  docker-buildx-reset          - Reset buildx builder (for config changes)"
	@echo "  version                      - Show the calculated next version"
	@echo "  test-version-script          - Run tests for version calculation script"
	@echo ""
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

# Docker targets
version:
	@echo "Current version: $(VERSION)"
	@echo "Git SHA: $(GIT_SHA)"
	@echo "Version with SHA: $(VERSION_WITH_SHA)"

docker-build:
	@echo "Building Docker images with version $(VERSION_WITH_SHA)..."
	docker build -t $(BACKEND_IMAGE):$(VERSION_WITH_SHA) -f Dockerfile.backend .
	docker build -t $(FRONTEND_IMAGE):$(VERSION_WITH_SHA) -f Dockerfile.frontend .
	@echo "Successfully built images:"
	@echo "  - $(BACKEND_IMAGE):$(VERSION_WITH_SHA)"
	@echo "  - $(FRONTEND_IMAGE):$(VERSION_WITH_SHA)"

docker-tag: docker-build
	@echo "Tagging images with version and latest..."
	docker tag $(BACKEND_IMAGE):$(VERSION_WITH_SHA) $(BACKEND_IMAGE):$(VERSION)
	docker tag $(BACKEND_IMAGE):$(VERSION_WITH_SHA) $(BACKEND_IMAGE):latest
	docker tag $(FRONTEND_IMAGE):$(VERSION_WITH_SHA) $(FRONTEND_IMAGE):$(VERSION)
	docker tag $(FRONTEND_IMAGE):$(VERSION_WITH_SHA) $(FRONTEND_IMAGE):latest

docker-push-local: docker-tag
	@echo "Pushing images to $(REGISTRY)..."
	docker tag $(BACKEND_IMAGE):$(VERSION_WITH_SHA) $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA)
	docker tag $(BACKEND_IMAGE):$(VERSION) $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION)
	docker tag $(BACKEND_IMAGE):latest $(REGISTRY)/$(BACKEND_IMAGE):latest
	docker tag $(FRONTEND_IMAGE):$(VERSION_WITH_SHA) $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)
	docker tag $(FRONTEND_IMAGE):$(VERSION) $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION)
	docker tag $(FRONTEND_IMAGE):latest $(REGISTRY)/$(FRONTEND_IMAGE):latest
	docker push $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA)
	docker push $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION)
	docker push $(REGISTRY)/$(BACKEND_IMAGE):latest
	docker push $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)
	docker push $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION)
	docker push $(REGISTRY)/$(FRONTEND_IMAGE):latest
	@echo "Successfully pushed images to $(REGISTRY):"
	@echo "  - $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA)"
	@echo "  - $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION)"
	@echo "  - $(REGISTRY)/$(BACKEND_IMAGE):latest"
	@echo "  - $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)"
	@echo "  - $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION)"
	@echo "  - $(REGISTRY)/$(FRONTEND_IMAGE):latest"

test-version-script:
	@echo "Running version calculation script tests..."
	@./scripts/test/test_calculate-next-version.sh

# Multi-architecture build targets
docker-buildx-setup:
	@echo "Setting up Docker buildx for multi-architecture builds..."
	@docker buildx create --name multiarch --config buildkitd.toml --use --driver docker-container 2>/dev/null || true
	@docker buildx inspect --bootstrap
	@echo "Buildx builder 'multiarch' is ready"

docker-buildx-reset:
	@echo "Resetting buildx builder to pick up new configuration..."
	@docker buildx rm multiarch 2>/dev/null || true
	@docker buildx create --name multiarch \
		--config buildkitd.toml \
		--driver docker-container \
		--driver-opt network=host \
		--driver-opt env.BUILDKIT_STEP_LOG_MAX_SIZE=10000000 \
		--driver-opt env.BUILDKIT_STEP_LOG_MAX_SPEED=10000000 \
		--driver-opt image=moby/buildkit:latest \
		--buildkitd-flags '--allow-insecure-entitlement security.insecure --allow-insecure-entitlement network.host' \
		--use
	@echo "Waiting for builder to start..."
	@sleep 2
	@echo "Increasing builder container memory limit to 8GB..."
	@docker update --memory=8g --memory-swap=8g buildx_buildkit_multiarch0 || echo "Note: Memory update may require Docker Desktop configuration"
	@docker buildx inspect --bootstrap
	@echo "Buildx builder 'multiarch' has been reset with 8GB memory limit"

docker-build-multiarch: docker-buildx-setup
	@echo "Building multi-architecture images ($(PLATFORMS)) with version $(VERSION_WITH_SHA)..."
	docker buildx build --platform $(PLATFORMS) \
		-t $(BACKEND_IMAGE):$(VERSION_WITH_SHA) \
		-t $(BACKEND_IMAGE):$(VERSION) \
		-t $(BACKEND_IMAGE):latest \
		--load \
		-f Dockerfile.backend .
	docker buildx build --platform $(PLATFORMS) \
		-t $(FRONTEND_IMAGE):$(VERSION_WITH_SHA) \
		-t $(FRONTEND_IMAGE):$(VERSION) \
		-t $(FRONTEND_IMAGE):latest \
		--load \
		-f Dockerfile.frontend .
	@echo "Successfully built multi-arch images:"
	@echo "  - $(BACKEND_IMAGE):$(VERSION_WITH_SHA) ($(PLATFORMS))"
	@echo "  - $(FRONTEND_IMAGE):$(VERSION_WITH_SHA) ($(PLATFORMS))"

docker-push-local-multiarch: docker-buildx-setup
	@echo "Building and pushing multi-architecture images to $(REGISTRY)..."
	docker buildx build --platform $(PLATFORMS) \
		-t $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA) \
		-t $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION) \
		-t $(REGISTRY)/$(BACKEND_IMAGE):latest \
		--push \
		-f Dockerfile.backend .
	docker buildx build --platform $(PLATFORMS) \
		-t $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA) \
		-t $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION) \
		-t $(REGISTRY)/$(FRONTEND_IMAGE):latest \
		--push \
		-f Dockerfile.frontend .
	@echo "Successfully pushed multi-arch images to $(REGISTRY):"
	@echo "  - $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA) ($(PLATFORMS))"
	@echo "  - $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION) ($(PLATFORMS))"
	@echo "  - $(REGISTRY)/$(BACKEND_IMAGE):latest ($(PLATFORMS))"
	@echo "  - $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA) ($(PLATFORMS))"
	@echo "  - $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION) ($(PLATFORMS))"
	@echo "  - $(REGISTRY)/$(FRONTEND_IMAGE):latest ($(PLATFORMS))"

docker-push-backend-multiarch: docker-buildx-setup
	@echo "Building and pushing backend multi-architecture image to $(REGISTRY)..."
	docker buildx build --platform $(PLATFORMS) \
		-t $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA) \
		-t $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION) \
		-t $(REGISTRY)/$(BACKEND_IMAGE):latest \
		--cache-from type=registry,ref=$(REGISTRY)/$(BACKEND_IMAGE):buildcache \
		--cache-to type=registry,ref=$(REGISTRY)/$(BACKEND_IMAGE):buildcache,mode=max \
		--push \
		-f Dockerfile.backend .
	@echo "Successfully pushed backend image to $(REGISTRY):"
	@echo "  - $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA) ($(PLATFORMS))"
	@echo "  - $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION) ($(PLATFORMS))"
	@echo "  - $(REGISTRY)/$(BACKEND_IMAGE):latest ($(PLATFORMS))"

docker-push-frontend-multiarch: docker-buildx-setup
	@echo "Building and pushing frontend multi-architecture image to $(REGISTRY)..."
	docker buildx build --platform $(PLATFORMS) \
		-t $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA) \
		-t $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION) \
		-t $(REGISTRY)/$(FRONTEND_IMAGE):latest \
		--push \
		-f Dockerfile.frontend .
	@echo "Successfully pushed frontend image to $(REGISTRY):"
	@echo "  - $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA) ($(PLATFORMS))"
	@echo "  - $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION) ($(PLATFORMS))"
	@echo "  - $(REGISTRY)/$(FRONTEND_IMAGE):latest ($(PLATFORMS))"

docker-push-frontend-multiarch-sequential: docker-buildx-setup
	@echo "Building frontend sequentially for each architecture to $(REGISTRY)..."
	@echo "Step 1/2: Building for linux/amd64..."
	docker buildx build --platform linux/amd64 \
		-t $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-amd64 \
		--cache-from type=registry,ref=$(REGISTRY)/$(FRONTEND_IMAGE):buildcache-amd64 \
		--cache-to type=registry,ref=$(REGISTRY)/$(FRONTEND_IMAGE):buildcache-amd64,mode=max \
		--push \
		-f Dockerfile.frontend .
	@echo "Step 2/2: Building for linux/arm64..."
	docker buildx build --platform linux/arm64 \
		-t $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-arm64 \
		--cache-from type=registry,ref=$(REGISTRY)/$(FRONTEND_IMAGE):buildcache-arm64 \
		--cache-to type=registry,ref=$(REGISTRY)/$(FRONTEND_IMAGE):buildcache-arm64,mode=max \
		--push \
		-f Dockerfile.frontend .
	@echo "Creating manifest lists..."
	docker buildx imagetools create -t $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA) \
		$(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-amd64 \
		$(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-arm64
	docker buildx imagetools create -t $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION) \
		$(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-amd64 \
		$(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-arm64
	docker buildx imagetools create -t $(REGISTRY)/$(FRONTEND_IMAGE):latest \
		$(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-amd64 \
		$(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-arm64
	@echo "Successfully pushed frontend multi-arch image to $(REGISTRY):"
	@echo "  - $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)"
	@echo "  - $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION)"
	@echo "  - $(REGISTRY)/$(FRONTEND_IMAGE):latest"

# Sequential multi-arch builds (lower memory usage)
docker-push-local-multiarch-sequential: docker-buildx-setup
	@echo "Building and pushing multi-arch images sequentially to $(REGISTRY)..."
	@echo "Step 1/4: Building backend for linux/amd64..."
	docker buildx build --platform linux/amd64 \
		-t $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA)-amd64 \
		--push \
		-f Dockerfile.backend .
	@echo "Step 2/4: Building backend for linux/arm64..."
	docker buildx build --platform linux/arm64 \
		-t $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA)-arm64 \
		--push \
		-f Dockerfile.backend .
	@echo "Step 3/4: Building frontend for linux/amd64..."
	docker buildx build --platform linux/amd64 \
		-t $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-amd64 \
		--push \
		-f Dockerfile.frontend .
	@echo "Step 4/4: Building frontend for linux/arm64..."
	docker buildx build --platform linux/arm64 \
		-t $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-arm64 \
		--push \
		-f Dockerfile.frontend .
	@echo "Creating manifest lists..."
	docker buildx imagetools create -t $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA) \
		$(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA)-amd64 \
		$(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA)-arm64
	docker buildx imagetools create -t $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION) \
		$(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA)-amd64 \
		$(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA)-arm64
	docker buildx imagetools create -t $(REGISTRY)/$(BACKEND_IMAGE):latest \
		$(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA)-amd64 \
		$(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA)-arm64
	docker buildx imagetools create -t $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA) \
		$(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-amd64 \
		$(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-arm64
	docker buildx imagetools create -t $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION) \
		$(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-amd64 \
		$(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-arm64
	docker buildx imagetools create -t $(REGISTRY)/$(FRONTEND_IMAGE):latest \
		$(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-amd64 \
		$(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA)-arm64
	@echo "Successfully pushed multi-arch images to $(REGISTRY):"
	@echo "  Backend: $(REGISTRY)/$(BACKEND_IMAGE):$(VERSION_WITH_SHA), :$(VERSION), :latest"
	@echo "  Frontend: $(REGISTRY)/$(FRONTEND_IMAGE):$(VERSION_WITH_SHA), :$(VERSION), :latest"

lint-backend:
	black src/ tests/
	isort src/ tests/
	ruff check src/ tests/ --fix

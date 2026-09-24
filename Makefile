UV ?= uv
BUN ?= bun
# Keep caches local so a clean checkout works in restricted workspaces too.
export UV_CACHE_DIR ?= $(CURDIR)/.cache/uv
export UV_PYTHON_DOWNLOADS := never
export BUN_INSTALL_CACHE_DIR ?= $(CURDIR)/.cache/bun

.PHONY: install check reproduce-fixture

# Installation may fetch pinned public dependencies; checks never fetch them.
install:
	$(UV) sync --frozen
	$(BUN) install --frozen-lockfile

# Discover tests, rather than maintaining a phase-specific command list.
check:
	$(UV) run --frozen --offline python scripts/check_repository.py
	$(UV) run --frozen --offline pytest
	$(BUN) run typecheck
	$(BUN) test ./tests

reproduce-fixture:
	$(UV) run --frozen --offline python scripts/check_repository.py --reproduce-fixture
	@if test -f scripts/reproduce_bio_fixture.py; then \
	  $(UV) run --frozen --offline python scripts/reproduce_bio_fixture.py --offline; \
	fi

.DEFAULT_GOAL := help

.PHONY: help install reinstall activate run run-demo run-dev console clean build publish del-env

help:
	@echo ""
	@echo "install  - install with poetry"
	@echo "reinstall - delete the virtual environment and install"
	@echo "activate - poetry shell"
	@echo "run      - same as using 'textualdon' "
	@echo "run-dev  - with textual run --dev"
	@echo "console  - textual console (requires dev tools)"
	@echo "clean    - delete dist and pycache"
	@echo "build    - clean then poetry build"
	@echo "publish  - build then poetry publish"
	@echo "del-env  - delete the virtual environment and lock file"
	@echo "del-secrets - delete all .secret files"
	@echo "tmux     - run tmux script"
	@echo ""

install:
	poetry install

reinstall: clean del-env install

activate:
	poetry shell

# note: python -m textualdon also works
run:
	textualdon

run-dev:
	textual run --dev textualdon:TextualDon

# Requires dev tools.
console:
	textual console -x EVENT -x SYSTEM -x WORKER

# Note: TextualDon's custom logging is quite robust.
# I turn off the base EVENT, SYSTEM, and WORKER messages to avoid
# cluttering the console.
# All workers in the app send custom log messages that are more concise.
# To make messages even MORE concise you can add '-x DEBUG' to turn off debug messages.

clean: del-secrets
	rm -rf build dist
	find . -name "*.pyc" -delete

# NOTE: Must be activated for build process because of this line:
update-version:
	python textualdon/version.py

build: clean update-version
	poetry build
	cp Roadmap.md textualdon/

publish: build
	poetry publish

del-env:
	rm -rf .venv
	rm -rf poetry.lock

del-secrets:
	find . -name "*.secret" -delete

# This will run the tmux script.
# see tmux.sh for more details.
tmux:
	chmod +x tmux.sh
	./tmux.sh

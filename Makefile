LIB_NAME = clever_config

test:
	@echo "--- RUNNING UNIT-TESTS: pytest"
	@PYTHONPATH=./$(LIB_NAME):${PYTHONPATH}:./tests poetry run pytest tests/unit_tests

coverage:
	@echo "--- CHECKING COVERAGE: pytest"
	@PYTHONPATH=./$(LIB_NAME):${PYTHONPATH}:./tests poetry run pytest tests/unit_tests --cov=./$(LIB_NAME)

doc:
	python3 ./docs/generate_docs.py

check-format:
	@echo "--- CHECKING FORMAT: isort"
	poetry run isort --profile=black --diff --check ./
	@echo "--- CHECKING FORMAT: black"
	poetry run black --config=pyproject.toml --check --diff ./

lint:
	@echo "--- LINTING: mypy"
	poetry run mypy --config-file=pyproject.toml ./clever_config
	poetry run mypy --config-file=pyproject.toml --disable-error-code=import ./tests

fmt:
	@echo "--- FORMATTING: isort"
	poetry run isort --profile=black ./
	@echo "--- FORMATTING: black"
	poetry run black --config=pyproject.toml ./

build:
	poetry build

init:
	git init
	git add .
	ln -sf ../../pre-commit.sh .git/hooks/pre-commit
	ln -sf ../../pre-push.sh .git/hooks/pre-push
	poetry install
	make clean

ci:
	poetry install --all-groups
	make all

all:
	make check-format
	make lint
	make coverage
	make clean

clean:
	@echo "--- clean: Removing *.pyc, *.pyo, __pycache__ recursively"
	find . -name '*.pyc' -delete
	find . -name '*.pyo' -delete
	find . -name '*.coverage' -delete
	find . -name 'dist' -type d  | xargs rm -rf
	find . -name '.pytest_cache' -type d  | xargs rm -rf
	find . -name 'htmlcov' -type d  | xargs rm -rf
	find . -name '__pycache__' -type d | xargs rm -rf
	find . -name '.mypy_cache' -type d | xargs rm -rf

.PHONY: smoke

PYTHON ?= python3

smoke:
	@PYTHONPATH=. $(PYTHON) -c "import engine, sys; print(getattr(engine, '__file__', None))"
	@PYTHONPATH=. $(PYTHON) scripts/smoke.py

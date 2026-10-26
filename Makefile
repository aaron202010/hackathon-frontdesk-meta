.PHONY: test dev

# stub mode: no key, no network, deterministic rule answers
test:
	FRONTDESK_STUB=1 python3 -m pytest -q tests

# live when MODEL_API_KEY is set in the shell, stub otherwise
dev:
	python3 -m uvicorn app.main:app --reload --port 8000

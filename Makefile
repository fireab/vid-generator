PY := .venv/bin/python

.PHONY: venv smoke validate radio film clean-cache

venv:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

validate:
	$(PY) pipeline/run.py --validate-only

smoke:
	$(PY) pipeline/smoke_test.py

radio:
	$(PY) pipeline/run.py --mode radio

film:
	$(PY) pipeline/run.py --mode film

clean-cache:
	rm -f outputs/.cache_manifest.json

.PHONY: keyframes shots music notebook merge-kaggle

keyframes:
	$(PY) pipeline/keyframes.py

shots:
	$(PY) pipeline/shots.py

music:
	$(PY) pipeline/music.py

notebook:
	$(PY) notebooks/build_notebook.py

merge-kaggle:
	$(PY) pipeline/merge_kaggle_log.py $(LOG)

.PHONY: build
build:
	rm -rf dist
	rm -rf energy_tariff_scheduler.egg-info
	.venv/bin/python -m build -v

.PHONY: test-go
test-go:
	pip uninstall energy_tariff_scheduler
	pip install dist/energy_tariff_scheduler-0.0.6-py3-none-any.whl
	python ./_test_go_script.py

.PHONY: test-agile
test-agile:
	pip uninstall energy_tariff_scheduler
	pip install dist/energy_tariff_scheduler-0.0.6-py3-none-any.whl
	python ./_test_agile_script.py

.PHONY: deploy
deploy:
	twine upload dist/*
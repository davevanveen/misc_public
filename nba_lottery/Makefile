.PHONY: all dataset validate feasibility power freeze tests results test clean

PYTHON ?= python3
N ?= 1000000
SEED ?= 0

all: results

dataset:
	$(PYTHON) scripts/build_dataset.py --raw-dir data/raw --out-dir data/processed

validate: dataset
	$(PYTHON) scripts/validate_probabilities.py --probs data/processed/lottery_probability_matrix.csv --n $(N) --seed $(SEED)

feasibility: validate
	$(PYTHON) scripts/run_feasibility_report.py --out docs/feasibility_report.md

power: feasibility
	$(PYTHON) scripts/run_power_validation.py --out docs/power_validation.md

freeze: power
	$(PYTHON) scripts/freeze_plan.py --docs docs/statistical_analysis_plan.md docs/hypotheses.md docs/multiple_testing_plan.md docs/estimand_choice.md --out docs/analysis_plan_hashes.txt

tests: freeze
	$(PYTHON) scripts/run_stat_tests.py --data data/processed/ --out outputs/tables/ --n $(N) --seed $(SEED)

results: tests
	$(PYTHON) scripts/export_results.py --tables outputs/tables/ --figures outputs/figures/ --out docs/results_summary.md

test:
	$(PYTHON) -m pytest tests/ -v

clean:
	rm -rf outputs/tables/*.csv outputs/tables/*.npz outputs/tables/_meta.json outputs/figures/*.png data/processed/*.csv docs/feasibility_report.md docs/power_validation.md docs/analysis_plan_hashes.txt docs/results_summary.md docs/figure_notes.md

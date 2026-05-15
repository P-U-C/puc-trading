.PHONY: validate test populate-convergence scan secret-scan merge-opportunity-seeds

validate:
	python3 scanner/run_live_scan.py --validate-convergence

test:
	python3 -m unittest discover -s corpus -p "test*.py"

populate-convergence:
	python3 corpus/populate_convergence.py

scan: validate
	python3 scanner/run_live_scan.py

# Local secret + operator-identifier + trade-action-field scan.
# Run before commits and before producing a review bundle.
secret-scan:
	python3 scripts/secret-scan.py .

merge-opportunity-seeds:
	python3 corpus/merge_convergence.py

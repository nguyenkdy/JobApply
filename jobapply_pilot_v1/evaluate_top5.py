"""Compatibility entrypoint; Top 5 is the default of the shared evaluator."""
from evaluate_topk import evaluate as evaluate, main

if __name__ == "__main__":
    main()

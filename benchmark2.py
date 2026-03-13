import time
from app.heuristics.logic_analyzer import LogicAnalyzer

def run_benchmark():
    analyzer = LogicAnalyzer()

    # Simulating long text with many potential missing info targets
    text = "Please use the database. The API needs to be configured. Include the schema. Also pass in the config file. " * 10

    # Warm up
    for _ in range(10):
        analyzer.detect_missing_info(text)

    start = time.time()
    for _ in range(1000):
        analyzer.detect_missing_info(text)
    end = time.time()

    print(f"Baseline Time: {end - start:.4f} seconds")

if __name__ == "__main__":
    run_benchmark()

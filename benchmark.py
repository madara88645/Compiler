import time
from app.heuristics.logic_analyzer import LogicAnalyzer

def run_benchmark():
    analyzer = LogicAnalyzer()

    text = "Please use the database. The API needs to be configured. Include the schema. Also pass in the config file. " * 100

    start = time.time()
    for _ in range(1000):
        analyzer.detect_missing_info(text)
    end = time.time()

    print(f"Baseline Time: {end - start:.4f} seconds")

if __name__ == "__main__":
    run_benchmark()

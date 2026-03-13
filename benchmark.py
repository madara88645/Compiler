import time
from app.heuristics.logic_analyzer import LogicAnalyzer

text = "the database " * 1000 + " the api " * 1000 + " the schema " * 1000 + " the config " * 1000

analyzer = LogicAnalyzer()

start_time = time.time()
for _ in range(100):
    analyzer.detect_missing_info(text)
end_time = time.time()

print(f"Time taken: {end_time - start_time:.4f} seconds")

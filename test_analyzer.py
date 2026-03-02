from app.analyzer.swarm_qa import SwarmAnalyzer
from app.llm_engine.schemas import SwarmAnalysisRequest

agents = [
    {"role": "planner", "prompt": "You are a planner. Outline the steps."},
    {"role": "executor", "prompt": "You are an executor. Write code based on the plan."},
    {"role": "validator", "prompt": "You are a validator. Review the code."}
]
request = SwarmAnalysisRequest(agents=agents, original_description="Write a python script that prints 'Hello World'", run_tests=True)
analyzer = SwarmAnalyzer()
report = analyzer.analyze_swarm(agents=request.agents, original_description=request.original_description, run_tests=request.run_tests)
print(f"Overall Quality Score: {report.quality_score}")
print(f"Issues: {report.issues}")

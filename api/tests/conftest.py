import os, sys
os.environ["STORAGE"] = "local"
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("MLFLOW_TRACKING_URI", "file:/tmp/agent-factory-test-mlruns")
sys.path.insert(0, os.path.dirname(__file__))

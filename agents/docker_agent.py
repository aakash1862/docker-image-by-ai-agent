from langchain.agents import Tool, initialize_agent
from langchain_community.llms import OpenAI  # or Ollama, DeepSeek, etc.
from tools.dockerfile_gen import generate_dockerfile
from tools.docker_build import build_image
from tools.docker_scan import run_trivy_scan

def get_agent():
    llm = OpenAI(temperature=0)  # Replace with Ollama if local model

    tools = [
        Tool(name="GenerateDockerfile", func=generate_dockerfile, description="Generate a Dockerfile for a given app"),
        Tool(name="BuildDockerImage", func=build_image, description="Build Docker image from Dockerfile"),
        Tool(name="ScanDockerImage", func=run_trivy_scan, description="Run Trivy scan on Docker image"),
    ]

    return initialize_agent(tools, llm, agent="zero-shot-react-description", verbose=True)

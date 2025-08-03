from langchain.agents import Tool, initialize_agent
from langchain_community.llms import OpenAI  # or Ollama, DeepSeek, etc.
from langchain_anthropic import ChatAnthropic
from langchain_anthropic import Anthropic
from langchain_together import Together
from tools.dockerfile_gen import generate_dockerfile
from tools.docker_build import build_image
from tools.docker_scan import run_trivy_scan
from dotenv import load_dotenv
load_dotenv()
import os

# api_key = os.getenv("OPENAI_API_KEY")
# api_key = os.getenv("ANTHROPIC_API_KEY")
api_key = os.getenv("TOGETHER_API_KEY")

def get_agent():
    # below is an example of how to initialize the agent with OpenAI
    # llm = OpenAI(temperature=0)  # Replace with Ollama if local model

    # below is an example of how to initialize the agent with Anthropic
    # llm = ChatAnthropic(
    #     model="claude-3-haiku-20240307",  # or another Claude model
    #     temperature=0,
    #     anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
    # )

    # below is an example of how to initialize the agent with Together
    llm = Together(
            model="meta-llama/Llama-3-70b-chat-hf",  # Or any supported Together model
            temperature=0,
            max_tokens=250,
            together_api_key=os.getenv("TOGETHER_API_KEY")
        )
    
    tools = [
        Tool(name="GenerateDockerfile", func=generate_dockerfile, description="Generate a Dockerfile for a given app"),
        # Tool(name="BuildDockerImage", func=build_image, description="Build Docker image from Dockerfile"),
        # Tool(name="ScanDockerImage", func=run_trivy_scan, description="Run Trivy scan on Docker image"),
    ]

    return initialize_agent(tools, llm, agent="zero-shot-react-description", verbose=True)

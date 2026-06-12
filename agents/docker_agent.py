from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from tools.dockerfile_gen import generate_dockerfile
from tools.docker_build import build_image
from tools.docker_scan import run_trivy_scan
from dotenv import load_dotenv
load_dotenv()
import os

api_key = os.getenv("GEMINI_API_KEY")


def get_agent():
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",  # or "gemini-1.5-pro" / "gemini-2.0-flash"
        temperature=0,
        google_api_key=api_key,
    )

    tools = [
        generate_dockerfile,
        # build_image,
        # run_trivy_scan,
    ]

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "You are a Docker expert. Use the available tools to help users "
            "generate Dockerfiles and build Docker images."
        ),
    )

    return agent


def run_agent(prompt: str) -> str:
    """Run the agent with a user prompt and return the final text response."""
    agent = get_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
    # result["messages"] is a list of BaseMessage; last one is the AI response
    return result["messages"][-1].content

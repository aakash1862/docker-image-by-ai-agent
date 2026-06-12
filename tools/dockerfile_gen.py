from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
load_dotenv()
import os


@tool
def generate_dockerfile(app_description: str) -> str:
    """Generate a Dockerfile for a given application description."""
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",  # or "gemini-1.5-pro" / "gemini-2.0-flash"
            temperature=0,
            google_api_key=os.getenv("GEMINI_API_KEY"),
        )

        prompt = (
            "You are an expert in writing secure and production-ready Dockerfiles.\n"
            "Generate a Dockerfile based on the following app description:\n\n"
            f"{app_description.strip()}\n\n"
            "Ensure the Dockerfile is:\n"
            "- Based on a minimal image (slim or alpine if possible)\n"
            "- Exposes necessary ports\n"
            "- Uses best practices (caching, working directory, .dockerignore awareness)\n"
            "- Suitable for deployment\n\n"
            "Return only the Dockerfile content without explanation."
        )

        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()

    except Exception as e:
        return f"# Error generating Dockerfile: {str(e)}"

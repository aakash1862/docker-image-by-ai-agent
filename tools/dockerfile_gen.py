# # def generate_dockerfile(prompt: str) -> str:
# #     # Replace with actual LLM call or mock for now
# #     if "flask" in prompt.lower():
# #         return """FROM python:3.10-slim
# # WORKDIR /app
# # COPY . .
# # RUN pip install -r requirements.txt
# # EXPOSE 5000
# # CMD ["python", "app.py"]"""
# #     return "FROM alpine"

# # tools/dockerfile_gen.py

# from langchain_community.llms import Ollama

# def generate_dockerfile(app_description: str) -> str:
#     """
#     Generates a Dockerfile based on the user's application description using an open-source LLM via Ollama.
    
#     Args:
#         app_description (str): Description of the application to containerize.
        
#     Returns:
#         str: A Dockerfile as a string.
#     """
#     try:
#         # Initialize Ollama LLM (make sure Ollama is running and model is downloaded)
#         llm = Ollama(model="codellama")  # or "deepseek-coder", "mistral", etc.

#         # Prepare the prompt for Dockerfile generation
#         prompt = (
#             "You are an expert in writing secure and production-ready Dockerfiles.\n"
#             "Generate a Dockerfile based on the following app description:\n\n"
#             f"{app_description.strip()}\n\n"
#             "Ensure the Dockerfile is:\n"
#             "- Based on a minimal image (slim or alpine if possible)\n"
#             "- Exposes necessary ports\n"
#             "- Uses best practices (caching, working directory, .dockerignore awareness)\n"
#             "- Suitable for deployment\n\n"
#             "Return only the Dockerfile content without explanation."
#         )

#         # Call the LLM to generate the Dockerfile
#         dockerfile = llm(prompt)
#         return dockerfile.strip()

#     except Exception as e:
#         return f"# Error generating Dockerfile: {str(e)}"

from langchain_community.llms import OpenAI  # or Ollama, DeepSeek, etc.
from langchain_anthropic import ChatAnthropic
from langchain_anthropic import Anthropic
from langchain_together import Together
from dotenv import load_dotenv
load_dotenv()
import os

def generate_dockerfile(app_description: str) -> str:
    """
    Generates a Dockerfile based on the user's application description using OpenAI's LLM.
    
    Args:
        app_description (str): Description of the application to containerize.
        
    Returns:
        str: A Dockerfile as a string.
    """
    try:
        # Initialize OpenAI LLM
        # llm = OpenAI(model="gpt-3.5-turbo", temperature=0, max_tokens=250, openai_api_key=os.getenv("OPENAI_API_KEY"))  # Adjust model and temperature as needed

        # Initialize Anthropic LLM if needed
        # llm = ChatAnthropic(
        #     model="claude-3-haiku-20240307",  # or another Claude model
        #     temperature=0,
        #     anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        # )
        
        # Initialize Together LLM if needed
        llm = Together(
                model="meta-llama/Llama-3-70b-chat-hf",  # Or any supported Together model
                temperature=0,
                max_tokens=250,
                together_api_key=os.getenv("TOGETHER_API_KEY")
            )

        # Prepare the prompt for Dockerfile generation
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

        # Call the LLM to generate the Dockerfile
        dockerfile = llm(prompt)
        return dockerfile.strip()

    except Exception as e:
        return f"# Error generating Dockerfile: {str(e)}"
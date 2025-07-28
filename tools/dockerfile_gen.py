# def generate_dockerfile(prompt: str) -> str:
#     # Replace with actual LLM call or mock for now
#     if "flask" in prompt.lower():
#         return """FROM python:3.10-slim
# WORKDIR /app
# COPY . .
# RUN pip install -r requirements.txt
# EXPOSE 5000
# CMD ["python", "app.py"]"""
#     return "FROM alpine"

# tools/dockerfile_gen.py

from langchain_community.llms import Ollama

def generate_dockerfile(app_description: str) -> str:
    """
    Generates a Dockerfile based on the user's application description using an open-source LLM via Ollama.
    
    Args:
        app_description (str): Description of the application to containerize.
        
    Returns:
        str: A Dockerfile as a string.
    """
    try:
        # Initialize Ollama LLM (make sure Ollama is running and model is downloaded)
        llm = Ollama(model="codellama")  # or "deepseek-coder", "mistral", etc.

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

# This file is for CLI-based interaction using Typer

from agents.docker_agent import run_agent
import typer
from tools.docker_build import build_image

app = typer.Typer()


@app.command()
def run(prompt: str):
    response = run_agent(prompt)
    print("\n🧠 Final Output:\n", response)


@app.command()
def build(tag: str = "custom-image", dockerfile: str = "Dockerfile"):
    result = build_image(tag, dockerfile)
    print("\n🔨 Build Result:\n", result)


if __name__ == "__main__":
    app()

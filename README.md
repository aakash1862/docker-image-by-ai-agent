# docker-image-by-ai-agent
This is a PoC I am trying to create, where the AI Agent will first generate the Dockerfile and then build the image.

# How to run the Agent:
`python main.py run "prompt"` -- CLI-based calling

`streamlit run app.py` -- recommended method as this will open a UI on your localhost:8501

### Phase -1
During this phase, I am trying to create an agent that will generate a Dockerfile that a user can review on the UI. I did vibe coding for this PoC.

We are working on:
  - Agent will build the reviewed Dockerfile.
  - Agent will scan the final build image.
  - More improvements on UI.

import streamlit as st
import tempfile
import os
from agents.docker_agent import get_agent
from tools.docker_build import build_image
from tools.docker_scan import run_trivy_scan
from dotenv import load_dotenv
import docker

load_dotenv()

agent = get_agent()

st.title("Dockerfile Generator & Image Builder")

# 1. User prompt
app_description = st.text_area("Describe your application (prompt)", height=150)

# 2. Base image selection
base_images = [
    "python:3.10-slim",
    "node:18-alpine",
    "ubuntu:22.04",
    "udi-rhel9",
    "alpine:latest",
    "custom (enter below)"
]
selected_base = st.selectbox("Select a base image", base_images)
custom_base = ""
if selected_base == "custom (enter below)":
    custom_base = st.text_input("Enter custom base image")

# 3. File upload
uploaded_files = st.file_uploader(
    "Upload files to include in the Docker image (requirements.txt, app.py, etc.)",
    accept_multiple_files=True
)

# 4. Export option
export_option = st.radio(
    "How do you want your Docker image?",
    ("Download as tar archive", "Push to registry")
)

registry_path = ""
if export_option == "Push to registry":
    registry_path = st.text_input("Enter Docker registry path (e.g., registry.hub.docker.com/username/repo:tag)")

# --- SESSION STATE LOGIC ---
if "dockerfile_str" not in st.session_state:
    st.session_state.dockerfile_str = ""
if "dockerfile_generated" not in st.session_state:
    st.session_state.dockerfile_generated = False
if "dockerhub_username" not in st.session_state:
    st.session_state.dockerhub_username = ""
if "dockerhub_password" not in st.session_state:
    st.session_state.dockerhub_password = ""
if "build_export_triggered" not in st.session_state:
    st.session_state.build_export_triggered = False
if "auth_required" not in st.session_state:
    st.session_state.auth_required = False

# --- STEP 1: GENERATE DOCKERFILE ---
if st.button("Generate Dockerfile"):
    base = custom_base if selected_base == "custom (enter below)" else selected_base
    dockerfile_prompt = f"Generate a Dockerfile for: {app_description}\nBase image: {base}"
    dockerfile_content = agent(dockerfile_prompt)
    import re

    def extract_dockerfile(text):
        # Remove markdown code block if present
        match = re.search(r"```(?:dockerfile)?\s*([\s\S]*?)```", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Remove any leading explanation lines before the first FROM
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.strip().upper().startswith("FROM"):
                return "\n".join(lines[i:]).strip()
        return text.strip()

    dockerfile_str = dockerfile_content
    if isinstance(dockerfile_content, dict):
        dockerfile_str = dockerfile_content.get("output") or dockerfile_content.get("text") or str(dockerfile_content)
    dockerfile_str = extract_dockerfile(dockerfile_str)
    st.session_state.dockerfile_str = dockerfile_str
    st.session_state.dockerfile_generated = True

# --- SHOW DOCKERFILE IF GENERATED ---
if st.session_state.dockerfile_generated:
    st.subheader("Generated Dockerfile")
    st.info("Please review the generated Dockerfile below. You can download it for manual inspection before proceeding.")
    st.code(st.session_state.dockerfile_str, language="dockerfile")
    st.download_button("Download Dockerfile", st.session_state.dockerfile_str, file_name="Dockerfile")

    reviewed = st.checkbox("I have reviewed the Dockerfile and want to proceed with the build.")

    # --- STEP 2: BUILD & EXPORT ---
    def normalize_registry_path(path):
    # Remove registry.hub.docker.com/ if present
        if path.startswith("registry.hub.docker.com/"):
            return path.replace("registry.hub.docker.com/", "")
        return path
    if reviewed:
        user_tag = st.text_input("Enter Docker image tag (default: latest)", value="", key="user_tag")
        if st.button("Build & Export Image"):
            st.session_state.build_export_triggered = True
            st.session_state.auth_required = False  # Reset auth flag

        if st.session_state.build_export_triggered:
            with tempfile.TemporaryDirectory() as build_dir:
                # Save Dockerfile
                dockerfile_path = os.path.join(build_dir, "Dockerfile")
                with open(dockerfile_path, "w") as f:
                    f.write(st.session_state.dockerfile_str)
                # Save uploaded files
                if uploaded_files:
                    for file in uploaded_files:
                        file_path = os.path.join(build_dir, file.name)
                        with open(file_path, "wb") as out_file:
                            out_file.write(file.getbuffer())

                tag_value = user_tag.strip() if user_tag.strip() else "latest"
                if export_option == "Download as tar archive":
                    image_tag = f"custom-image:{tag_value}"
                else:
                    registry_path = normalize_registry_path(registry_path)
                    # Ensure tag is present
                    if ":" in registry_path:
                        image_tag = registry_path
                    else:
                        image_tag = f"{registry_path}:{tag_value}"

                st.info(f"Building Docker image with tag: {image_tag} ...")
                build_result = build_image(tag=image_tag, dockerfile="Dockerfile", path=build_dir)
                st.text(build_result)

                st.info("Scanning image for vulnerabilities...")
                scan_result = run_trivy_scan(image_tag)
                st.subheader("Vulnerability Scan Result")
                st.code(scan_result)

                if export_option == "Download as tar archive":
                    st.info("Saving image as tar archive...")
                    import docker
                    client = docker.from_env()
                    try:
                        image = client.images.get(image_tag)
                        st.success(f"Found local image with tag: {image_tag}")
                    except Exception as e:
                        st.error(f"Local image with tag {image_tag} not found: {e}")

                    tar_path = os.path.join(build_dir, "image.tar")
                    with open(tar_path, "wb") as tar_file:
                        for chunk in image.save(named=True):
                            tar_file.write(chunk)
                    with open(tar_path, "rb") as tar_file:
                        st.download_button("Download Docker Image (tar)", tar_file, file_name="image.tar")
                    st.session_state.build_export_triggered = False  # Reset after done
                else:
                    st.info(f"Pushing image to registry: {registry_path}")
                    import docker
                    client = docker.from_env()
                    try:
                        push_logs = client.images.push(repository=image_tag)
                        if "denied" in push_logs.lower() or "authentication required" in push_logs.lower():
                            st.session_state.auth_required = True
                            raise PermissionError("Authentication required")
                        st.text(push_logs)
                        st.session_state.build_export_triggered = False  # Reset after done
                    except PermissionError:
                        st.warning("Authentication required. Please provide your Docker Hub username and password below and click 'Push Image'.")
                    except Exception as e:
                        st.error(f"Failed to push: {e}")
                        st.session_state.build_export_triggered = False

                # Show auth fields and push button if needed
                if st.session_state.auth_required:
                    if "docker.io" in registry_path or "hub.docker.com" in registry_path or registry_path.count("/") == 1:
                        cred_label = "Docker Hub"
                    else:
                        cred_label = "Registry"
                    dockerhub_username = st.text_input(f"{cred_label} Username", value=st.session_state.dockerhub_username, key="dockerhub_username")
                    dockerhub_password = st.text_input(f"{cred_label} Password", value=st.session_state.dockerhub_password, type="password", key="dockerhub_password")
                    if st.button("Push Image"):
                        try:
                            client.login(username=dockerhub_username, password=dockerhub_password)
                            st.success("Logged in to Docker Hub. Retrying push...")
                            push_logs = client.images.push(repository=image_tag)
                            # st.text(push_logs)
                            st.session_state.build_export_triggered = False
                            st.session_state.auth_required = False
                        except Exception as e:
                            st.error(f"Failed to login or push: {e}")
                st.info(f"About to push image with tag: {image_tag} to repository: {image_tag}")
                push_logs = client.images.push(repository=image_tag)
                st.text(push_logs)
import streamlit as st
import tempfile
import os
import re
import time
from agents.docker_agent import run_agent
from tools.docker_build import build_image
from tools.docker_scan import run_trivy_scan
from dotenv import load_dotenv
import docker

load_dotenv()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_dockerfile(text: str) -> str:
    """Strip markdown fences and leading prose, leaving only Dockerfile content."""
    match = re.search(r"```(?:dockerfile)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("FROM"):
            return "\n".join(lines[i:]).strip()
    return text.strip()


def normalize_registry_path(path: str) -> str:
    if path.startswith("registry.hub.docker.com/"):
        return path.replace("registry.hub.docker.com/", "")
    return path


def show_result_watermark(success: bool, error_code: str = ""):
    """
    Inject a full-screen watermark emoji that fades from fully opaque
    to invisible over ~2.5 seconds, then removes itself.
    On failure the error code is displayed below the thumbs-down.
    """
    emoji   = "👍" if success else "👎"
    color   = "#22c55e" if success else "#ef4444"   # green / red
    extra   = ""
    if not success and error_code:
        extra = f'<div class="wm-error-code">{error_code}</div>'

    html = f"""
<style>
@keyframes wmFadeOut {{
    0%   {{ opacity: 1; }}
    60%  {{ opacity: 0.9; }}
    100% {{ opacity: 0; }}
}}
.wm-overlay {{
    position: fixed;
    inset: 0;
    z-index: 99999;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    pointer-events: none;
    animation: wmFadeOut 2.5s ease-out forwards;
}}
.wm-emoji {{
    font-size: 12rem;
    line-height: 1;
    filter: drop-shadow(0 0 40px {color});
}}
.wm-error-code {{
    margin-top: 1rem;
    font-size: 1.4rem;
    font-weight: 700;
    color: {color};
    background: rgba(0,0,0,0.55);
    padding: 0.4rem 1.2rem;
    border-radius: 8px;
    font-family: monospace;
    animation: wmFadeOut 2.5s ease-out forwards;
}}
</style>
<div class="wm-overlay">
  <div class="wm-emoji">{emoji}</div>
  {extra}
</div>
"""
    st.markdown(html, unsafe_allow_html=True)
    # Keep it visible for the animation duration, then let Streamlit re-render clean
    time.sleep(2.6)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
defaults = {
    "dockerfile_str": "",
    "dockerfile_generated": False,
    "dockerfile_error": "",
    "dockerhub_username": "",
    "dockerhub_password": "",
    "build_export_triggered": False,
    "auth_required": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
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
    "custom (enter below)",
]
selected_base = st.selectbox("Select a base image", base_images)
custom_base = ""
if selected_base == "custom (enter below)":
    custom_base = st.text_input("Enter custom base image")

# 3. File upload
uploaded_files = st.file_uploader(
    "Upload files to include in the Docker image (requirements.txt, app.py, etc.)",
    accept_multiple_files=True,
)

# 4. Export option
export_option = st.radio(
    "How do you want your Docker image?",
    ("Download as tar archive", "Push to registry"),
)
registry_path = ""
if export_option == "Push to registry":
    registry_path = st.text_input(
        "Enter Docker registry path (e.g., registry.hub.docker.com/username/repo:tag)"
    )

# ---------------------------------------------------------------------------
# STEP 1 — Generate Dockerfile
# ---------------------------------------------------------------------------
if st.button("Generate Dockerfile"):
    base = custom_base if selected_base == "custom (enter below)" else selected_base
    dockerfile_prompt = f"Generate a Dockerfile for: {app_description}\nBase image: {base}"

    st.session_state.dockerfile_generated = False
    st.session_state.dockerfile_error = ""

    try:
        with st.spinner("🤖 AI is generating your Dockerfile — hang tight…"):
            raw = run_agent(dockerfile_prompt)

        dockerfile_str = extract_dockerfile(raw)
        st.session_state.dockerfile_str = dockerfile_str
        st.session_state.dockerfile_generated = True

        show_result_watermark(success=True)

    except Exception as exc:
        error_code = f"ERR_DOCKERFILE_GEN: {type(exc).__name__}"
        st.session_state.dockerfile_error = str(exc)
        show_result_watermark(success=False, error_code=error_code)
        st.error(f"Failed to generate Dockerfile\n\n`{error_code}`\n\n{exc}")

# ---------------------------------------------------------------------------
# STEP 2 — Show Dockerfile & Build
# ---------------------------------------------------------------------------
if st.session_state.dockerfile_generated:
    st.subheader("Generated Dockerfile")
    st.info(
        "Please review the generated Dockerfile below. "
        "You can download it for manual inspection before proceeding."
    )
    st.code(st.session_state.dockerfile_str, language="dockerfile")
    st.download_button(
        "Download Dockerfile", st.session_state.dockerfile_str, file_name="Dockerfile"
    )

    reviewed = st.checkbox(
        "I have reviewed the Dockerfile and want to proceed with the build."
    )

    if reviewed:
        user_tag = st.text_input(
            "Enter Docker image tag (default: latest)", value="", key="user_tag"
        )

        if st.button("Build & Export Image"):
            st.session_state.build_export_triggered = True
            st.session_state.auth_required = False

        if st.session_state.build_export_triggered:
            with tempfile.TemporaryDirectory() as build_dir:
                # Write Dockerfile
                with open(os.path.join(build_dir, "Dockerfile"), "w") as f:
                    f.write(st.session_state.dockerfile_str)

                # Write uploaded files
                if uploaded_files:
                    for file in uploaded_files:
                        with open(os.path.join(build_dir, file.name), "wb") as out:
                            out.write(file.getbuffer())

                tag_value = user_tag.strip() if user_tag.strip() else "latest"
                if export_option == "Download as tar archive":
                    image_tag = f"custom-image:{tag_value}"
                else:
                    rp = normalize_registry_path(registry_path)
                    image_tag = rp if ":" in rp else f"{rp}:{tag_value}"

                # --- Build ---
                try:
                    with st.spinner(f"🔨 Building Docker image `{image_tag}`…"):
                        build_result = build_image(
                            tag=image_tag, dockerfile="Dockerfile", path=build_dir
                        )
                    st.text(build_result)
                except Exception as exc:
                    error_code = f"ERR_DOCKER_BUILD: {type(exc).__name__}"
                    show_result_watermark(success=False, error_code=error_code)
                    st.error(f"Build failed\n\n`{error_code}`\n\n{exc}")
                    st.session_state.build_export_triggered = False
                    st.stop()

                # --- Scan ---
                with st.spinner("🔍 Scanning image for vulnerabilities…"):
                    scan_result = run_trivy_scan(image_tag)
                st.subheader("Vulnerability Scan Result")
                st.code(scan_result)

                client = docker.from_env()

                # --- Export / Push ---
                if export_option == "Download as tar archive":
                    try:
                        with st.spinner("📦 Saving image as tar archive…"):
                            image = client.images.get(image_tag)
                            tar_path = os.path.join(build_dir, "image.tar")
                            with open(tar_path, "wb") as tar_file:
                                for chunk in image.save(named=True):
                                    tar_file.write(chunk)

                        show_result_watermark(success=True)

                        with open(tar_path, "rb") as tar_file:
                            st.download_button(
                                "Download Docker Image (tar)", tar_file, file_name="image.tar"
                            )
                    except Exception as exc:
                        error_code = f"ERR_EXPORT_TAR: {type(exc).__name__}"
                        show_result_watermark(success=False, error_code=error_code)
                        st.error(f"Export failed\n\n`{error_code}`\n\n{exc}")

                    st.session_state.build_export_triggered = False

                else:
                    try:
                        with st.spinner(f"🚀 Pushing image to `{registry_path}`…"):
                            push_logs = client.images.push(repository=image_tag)

                        if "denied" in push_logs.lower() or "authentication required" in push_logs.lower():
                            st.session_state.auth_required = True
                            raise PermissionError("Authentication required")

                        show_result_watermark(success=True)
                        st.text(push_logs)
                        st.session_state.build_export_triggered = False

                    except PermissionError:
                        st.warning(
                            "Authentication required. "
                            "Enter your credentials below and click **Push Image**."
                        )
                    except Exception as exc:
                        error_code = f"ERR_PUSH: {type(exc).__name__}"
                        show_result_watermark(success=False, error_code=error_code)
                        st.error(f"Push failed\n\n`{error_code}`\n\n{exc}")
                        st.session_state.build_export_triggered = False

                # --- Auth retry ---
                if st.session_state.auth_required:
                    cred_label = (
                        "Docker Hub"
                        if (
                            "docker.io" in registry_path
                            or "hub.docker.com" in registry_path
                            or registry_path.count("/") == 1
                        )
                        else "Registry"
                    )
                    dh_user = st.text_input(
                        f"{cred_label} Username",
                        value=st.session_state.dockerhub_username,
                        key="dockerhub_username",
                    )
                    dh_pass = st.text_input(
                        f"{cred_label} Password",
                        value=st.session_state.dockerhub_password,
                        type="password",
                        key="dockerhub_password",
                    )
                    if st.button("Push Image"):
                        try:
                            with st.spinner("🔐 Logging in and pushing…"):
                                client.login(username=dh_user, password=dh_pass)
                                push_logs = client.images.push(repository=image_tag)

                            show_result_watermark(success=True)
                            st.success("Image pushed successfully.")
                            st.session_state.build_export_triggered = False
                            st.session_state.auth_required = False

                        except Exception as exc:
                            error_code = f"ERR_AUTH_PUSH: {type(exc).__name__}"
                            show_result_watermark(success=False, error_code=error_code)
                            st.error(f"Failed to login or push\n\n`{error_code}`\n\n{exc}")

import subprocess

def run_trivy_scan(image_name="custom-image"):
    try:
        result = subprocess.run(["trivy", "image", image_name], capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        return f"Error running scan: {e}"

import docker

def build_image(tag="custom-image:latest", dockerfile="Dockerfile", path="."):
    client = docker.from_env()
    image, logs = client.images.build(path=path, tag=tag, dockerfile=dockerfile)
    return "\n".join([str(log.get("stream", "")) for log in logs])

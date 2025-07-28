import docker

def build_image(tag="custom-image", dockerfile="Dockerfile"):
    client = docker.from_env()
    image, logs = client.images.build(path=".", tag=tag, dockerfile=dockerfile)
    return "\n".join([str(log.get("stream", "")) for log in logs])

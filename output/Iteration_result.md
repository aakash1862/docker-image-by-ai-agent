After first initial commit, when I passed openai api key, I got below error due to daily capacity:

`RateLimitError: Error code: 429 - {'error': {'message': 'You exceeded your current quota,     
please check your plan and billing details. For more information on this error, read the docs:
https://platform.openai.com/docs/guides/error-codes/api-errors.', 'type':
'insufficient_quota', 'param': None, 'code': 'insufficient_quota'}}`

<br>

Prompt:
As an expert, create a production ready docker image using the provided base image. Also include a message to be displayed after image run over any platform. Message should be "Welcome to the Docker image created by AI Agent"


1. Load the docker image provided as tarball file:
`docker load -i .\image.tar`

2. Pushing the image to registry:
* Do not forgot to do docker login from localhost


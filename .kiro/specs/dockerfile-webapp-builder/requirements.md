# Requirements Document

## Introduction

The Dockerfile Webapp Builder evolves an existing Streamlit proof-of-concept into a production-grade web application. It replaces the single-page Streamlit UI with a FastAPI backend and a React single-page application (SPA) frontend. The system guides users through the complete Docker image lifecycle: authenticate with DockerHub via OAuth, compose a Dockerfile through a structured form UI, generate a Dockerfile with AI assistance (LangChain + Together AI / Llama 3 70B), build the Docker image with live log streaming over WebSocket, scan the built image for vulnerabilities with Trivy, and download or publish the image to DockerHub — concluding with a completion confirmation screen.

The backend preserves and extends the existing Python tools (`dockerfile_gen.py`, `docker_build.py`, `docker_scan.py`) and the LangChain agent. The system is designed to run on OpenShift or any platform that can co-host a Docker engine alongside a web process, communicating with the host Docker engine via the Docker Python SDK over a Unix socket or TCP endpoint.

---

## Glossary

- **System**: The Dockerfile Webapp Builder application as a whole (FastAPI backend + React frontend).
- **Frontend**: The React SPA served to the user's browser.
- **Backend**: The FastAPI application that orchestrates all server-side operations.
- **Auth_Router**: The FastAPI router handling `/auth/*` endpoints and DockerHub OAuth flow.
- **Builder_Router**: The FastAPI router handling `/builder/*` endpoints.
- **WebSocket_Handler**: The FastAPI WebSocket endpoint at `/ws/build/{session_id}`.
- **AI_Agent**: The LangChain-based service that calls the Together AI LLM (Llama 3 70B) to generate Dockerfiles.
- **Docker_Service**: The Python service class wrapping the Docker Python SDK for build, export, and push operations.
- **Scan_Service**: The Python service class wrapping Trivy to scan built images for vulnerabilities.
- **Session_Manager**: The Python service that issues and validates JWT tokens and stores per-session state server-side.
- **DockerHub**: Docker's public container registry and OAuth identity provider (`hub.docker.com`).
- **DockerfileSpec**: The structured data model capturing `base_image`, ordered `instructions`, and optional `code_source`.
- **DockerfileInstruction**: A single Dockerfile directive — an instruction keyword and its value.
- **BuildLogEvent**: A typed dictionary representing one streaming log message from a Docker build (`type`, `data`, optional `image_id`).
- **ScanResult**: The structured output from a Trivy scan, containing vulnerability counts by severity.
- **Session**: Server-side state associated with an authenticated user, identified by a JWT.
- **Trivy**: An open-source vulnerability scanner for container images.
- **JWT**: JSON Web Token used as the session token.

---

## Requirements

### Requirement 1: DockerHub OAuth Authentication

**User Story:** As a user, I want to authenticate with my DockerHub account via OAuth, so that I can securely build and publish Docker images to my registry.

#### Acceptance Criteria

1. WHEN a user visits the app, THE Frontend SHALL call `GET /auth/status` and render a login page when the response indicates the user is not authenticated.
2. WHEN a user clicks "Login with DockerHub", THE Frontend SHALL call `GET /auth/login` and redirect the browser to the `redirect_url` returned by the Backend.
3. WHEN DockerHub redirects back to `GET /auth/callback` with an authorization code, THE Auth_Router SHALL exchange the code for an access token with DockerHub and create a new session.
4. IF the OAuth callback contains an error parameter or the token exchange with DockerHub fails, THEN THE Auth_Router SHALL clear any existing authentication state, return HTTP 400 with `{ "error": "oauth_failed", "message": "<details>" }`, and THE Frontend SHALL redirect the user to the login page with an error banner.
5. WHILE an OAuth failure has occurred and the user has not completed a successful re-authentication, THE Backend SHALL deny access to all protected pages and return HTTP 401 for any protected-route request.
6. WHEN a session is successfully created, THE Auth_Router SHALL set an `HttpOnly`, `Secure` session cookie containing the JWT and redirect the user to the builder page.
7. WHEN the user is authenticated, THE Frontend SHALL display the user's DockerHub username.

---

### Requirement 2: Session Management

**User Story:** As a user, I want my session to remain valid while I work and to be clearly notified when it expires, so that I never lose work unexpectedly.

#### Acceptance Criteria

1. WHEN THE Session_Manager creates a session for a DockerHubUser, THE Session_Manager SHALL store the session server-side and return a signed JWT using the HS256 algorithm.
2. WHEN THE Session_Manager receives a valid, non-expired JWT, THE Session_Manager SHALL return the associated Session object containing the original user's username.
3. WHEN THE Session_Manager receives a JWT whose TTL has elapsed, THE Session_Manager SHALL raise `SessionExpiredError`.
4. WHEN THE Session_Manager receives a JWT with an invalid or tampered signature, THE Session_Manager SHALL raise `InvalidTokenError`.
5. WHEN any protected Backend route receives a request with an expired or invalid session token, THE Backend SHALL return HTTP 401 with `{ "error": "session_expired" }`.
6. WHEN THE Frontend receives an HTTP 401 response, THE Frontend SHALL clear local session state and redirect the user to the login page.
7. WHILE a user has an active session and closes the browser without completing the flow, THE Frontend SHALL preserve the in-progress Dockerfile form data in `localStorage` so it can be auto-restored on next visit.

---

### Requirement 3: Dockerfile Form Composition

**User Story:** As a user, I want to compose a Dockerfile through a structured form with a dynamic instruction list, so that I can define my image without writing raw Dockerfile syntax.

#### Acceptance Criteria

1. THE Frontend SHALL provide a form with a required base image field, a dynamic list of Dockerfile instruction entries (instruction type + value), and an optional code source field.
2. WHEN a user submits the form with an empty base image, THE Frontend SHALL prevent submission and display a validation error.
3. WHEN a user adds a `DockerfileInstruction` with an empty value field, THE Frontend SHALL prevent submission and display a validation error.
4. WHEN a user submits a form, THE Backend SHALL independently validate that `base_image` is non-empty, raising a 422 error if it is not.
5. WHEN a user submits a form with a `DockerfileInstruction` whose value is empty or whitespace-only, THE Backend SHALL return HTTP 422.
6. WHEN a user specifies a `code_source` of type `github_url`, THE Backend SHALL validate that the value starts with `https://github.com/`; IF it does not, THEN THE Backend SHALL return HTTP 422.
7. THE Frontend SHALL support all 18 standard Dockerfile instruction types as selectable options: `ADD`, `ARG`, `CMD`, `COPY`, `ENTRYPOINT`, `ENV`, `EXPOSE`, `FROM`, `HEALTHCHECK`, `LABEL`, `MAINTAINER`, `ONBUILD`, `RUN`, `SHELL`, `STOPSIGNAL`, `USER`, `VOLUME`, `WORKDIR`.
8. THE Frontend SHALL allow the user to reorder instructions via drag-and-drop or move-up/move-down controls.

---

### Requirement 4: Dockerfile Instruction Order Validation

**User Story:** As a user, I want to receive advisory warnings when my instruction ordering may cause unexpected behavior, so that I can correct the Dockerfile before building.

#### Acceptance Criteria

1. WHEN `validate_instruction_order` is called with a list of instructions where a `COPY` or `ADD` instruction appears before any `WORKDIR` instruction, THE Backend SHALL include a warning message in the `GenerateResponse.warnings` list.
2. WHEN `validate_instruction_order` is called with a list of instructions containing more than one `CMD` instruction, THE Backend SHALL include a warning message stating that only the last `CMD` takes effect.
3. WHEN `validate_instruction_order` is called with a valid list of `DockerfileInstruction` objects (including an empty list), THE Backend SHALL return a list and SHALL NOT raise an exception.
4. WHEN `validate_instruction_order` is called with any list of instructions, THE Backend SHALL NOT modify the input list.
5. WHEN warnings are present in `GenerateResponse`, THE Frontend SHALL display them to the user as non-blocking advisory messages that do not prevent Dockerfile generation.

---

### Requirement 5: AI-Assisted Dockerfile Generation

**User Story:** As a user, I want the system to generate a complete, valid Dockerfile from my structured form input using AI, so that I get a production-ready starting point without manual Dockerfile authoring.

#### Acceptance Criteria

1. WHEN a user submits `POST /builder/generate` with a valid `DockerfileSpec`, THE AI_Agent SHALL build a prompt containing the `base_image`, each instruction in order, and any `code_source` context, then invoke the LLM.
2. WHEN THE AI_Agent receives the LLM response, THE AI_Agent SHALL extract the Dockerfile by stripping any markdown code fences and preamble text, returning a clean Dockerfile string.
3. WHEN the extracted Dockerfile does not start with a `FROM` instruction, THE AI_Agent SHALL raise `DockerfileExtractionError`.
4. WHEN `POST /builder/generate` succeeds, THE Backend SHALL return a `GenerateResponse` containing `session_id`, the `dockerfile` string, and a `warnings` list.
5. WHEN `POST /builder/generate` succeeds, THE Backend SHALL persist the raw Dockerfile string (as returned by the AI Agent before any response formatting) to the user's session as `session.dockerfile_content`, and THE GenerateResponse SHALL contain the same raw Dockerfile content.
6. IF the Dockerfile generation process fails for any reason (LLM call failure, timeout, extraction error, or other internal error), THEN THE Backend SHALL retry once internally before returning HTTP 502 with `{ "error": "generation_failed" }`.
7. WHEN a generated Dockerfile is returned to THE Frontend, THE Frontend SHALL display it in a syntax-highlighted code viewer.
8. WHEN THE Frontend displays a generated Dockerfile, THE Frontend SHALL provide a "Download Dockerfile" button that triggers a browser file download of the Dockerfile content.

---

### Requirement 6: Docker Image Build with Live Log Streaming

**User Story:** As a user, I want to build my Docker image and see real-time build logs in the browser, so that I can monitor progress and diagnose failures immediately.

#### Acceptance Criteria

1. WHEN a user clicks "Build Image", THE Frontend SHALL open a WebSocket connection to `/ws/build/{session_id}` before initiating the build.
2. WHEN THE WebSocket_Handler receives a connection, THE WebSocket_Handler SHALL accept it and begin forwarding `BuildLogEvent` messages as the Docker build progresses.
3. WHEN `POST /builder/build` is called with a valid `session_id` and `image_tag`, THE Docker_Service SHALL write the session's Dockerfile to a temporary directory and invoke the Docker API client in streaming mode.
4. WHILE the Docker build is in progress, THE WebSocket_Handler SHALL forward each `BuildLogEvent` with `type: "log"` to the connected Frontend client.
5. WHEN the Docker build completes successfully, THE Docker_Service SHALL yield a final `BuildLogEvent` with `type: "done"` and a non-empty `image_id`.
6. WHEN the Docker build fails, THE Docker_Service SHALL yield a `BuildLogEvent` with `type: "error"` containing the error message.
7. WHEN THE Frontend receives a `type: "done"` event, THE Frontend SHALL display a "Build successful" message and enable the download and push action buttons.
8. WHEN THE Frontend receives a `type: "error"` event, THE Frontend SHALL display the error in the log panel and disable the download and push action buttons.
9. WHEN the Docker build completes (successfully or with an error), THE Docker_Service SHALL delete the temporary directory used as the build context.
10. IF the Docker daemon is unreachable when a build is attempted, THEN THE Backend SHALL return HTTP 503 with `{ "error": "docker_unavailable" }`.

---

### Requirement 7: Vulnerability Scanning

**User Story:** As a user, I want my built Docker image to be automatically scanned for vulnerabilities, so that I can make an informed decision before publishing it.

#### Acceptance Criteria

1. WHEN a Docker image build completes successfully, THE Scan_Service SHALL automatically scan the built image using Trivy and return a `ScanResult`.
2. THE ScanResult SHALL contain integer counts for all five severity levels: `critical`, `high`, `medium`, `low`, and `unknown`.
3. WHEN a scan completes (including when Trivy encounters an error or crash), THE ScanResult SHALL contain a non-empty `raw_output` string; IF Trivy fails to produce output, THE Backend SHALL set `raw_output` to a descriptive error message and mark the scan as incomplete.
4. WHEN the `ScanResult` contains any `CRITICAL` or `HIGH` severity vulnerabilities, THE Frontend SHALL display a prominent warning to the user before allowing publish actions.
5. WHEN scanning completes, THE Frontend SHALL display the vulnerability counts by severity level.

---

### Requirement 8: Image Download

**User Story:** As a user, I want to download my built Docker image as a tar archive, so that I can use or distribute the image without publishing it to a registry.

#### Acceptance Criteria

1. WHEN `GET /builder/download/{session_id}` is called for a session with a successfully built image, THE Docker_Service SHALL stream the image as a tar archive in the HTTP response body using chunked transfer encoding.
2. WHEN the byte chunks yielded by `export_image_tar` are concatenated, THE result SHALL form a valid tar archive as determined by `tarfile.is_tarfile()`.
3. IF no built image exists for the given `session_id`, THEN THE Backend SHALL return HTTP 404.
4. WHEN THE Frontend provides a download option, THE Frontend SHALL trigger a browser file download named `image.tar`.

---

### Requirement 9: Image Publishing to DockerHub

**User Story:** As a user, I want to publish my built Docker image directly to DockerHub, so that it is available for others to use without manual push commands.

#### Acceptance Criteria

1. WHEN `POST /builder/push` is called with a valid `session_id` and `image_tag`, THE Docker_Service SHALL authenticate with DockerHub using the session's stored OAuth access token before pushing.
2. WHEN THE Docker_Service pushes an image, THE Docker_Service SHALL ensure the resolved image tag used for the push starts with the authenticated user's username followed by `/`.
3. WHEN the push completes successfully, THE Backend SHALL return a `PushResponse` with `success: true` and the `image_url` in the format `https://hub.docker.com/r/{username}/{repo}`.
4. WHEN the push completes successfully, THE Frontend SHALL display a "Congratulations" completion confirmation screen showing the published image URL.
5. IF DockerHub rejects the push due to any authentication-related reason (expired token, insufficient permissions, invalid credentials, account suspension, or other auth rejection), THEN THE Backend SHALL return HTTP 403 with `{ "error": "push_denied" }` and THE Frontend SHALL prompt the user to re-authenticate.
6. IF DockerHub rejects the push for any other reason, THEN THE Backend SHALL return HTTP 502 with `{ "error": "push_failed", "message": "<details>" }`.

---

### Requirement 10: Security and Configuration

**User Story:** As a platform operator, I want the application to follow security best practices, so that user credentials and Docker access are protected from abuse.

#### Acceptance Criteria

1. THE Backend SHALL store the DockerHub OAuth `access_token` only in server-side session state and SHALL NOT include it in any client-facing response body or cookie value beyond the session JWT.
2. THE Backend SHALL sign all JWTs using the HS256 algorithm with a secret loaded from an environment variable.
3. THE Backend SHALL restrict `Access-Control-Allow-Origin` CORS headers to the configured frontend origin only.
4. WHEN a request is received from an origin not in the allowed CORS list, THE Backend SHALL reject it with a CORS error response.
5. WHEN a user exceeds 10 build or generate requests per hour, THE Backend SHALL return HTTP 429 with `{ "error": "rate_limit_exceeded" }`.
6. WHEN accepting a `DockerfileInstruction` value, THE Backend SHALL reject values containing shell meta-characters (backtick sequences, unescaped `$()` command substitutions, environment variable injection patterns such as `${VAR:-...}` with embedded commands, or multi-stage build references used for injection) and return HTTP 422.

---

### Requirement 11: Prompt Construction and Dockerfile Extraction

**User Story:** As a developer, I want the prompt builder and Dockerfile extractor to be deterministic and verifiable, so that the AI pipeline produces consistent, usable outputs.

#### Acceptance Criteria

1. WHEN `build_llm_prompt` is called with a non-empty `base_image` and a list of instructions, THE AI_Agent SHALL return a non-empty prompt string that contains the `base_image` value.
2. WHEN `build_llm_prompt` is called with a list of instructions, THE AI_Agent SHALL include each instruction keyword and its value in the prompt in the same order as the input list.
3. WHEN `build_llm_prompt` is called with a `code_source`, THE AI_Agent SHALL include the code source location context in the returned prompt.
4. WHEN `extract_dockerfile` receives an LLM output string containing a markdown-fenced code block (` ```dockerfile ` or ` ``` `), THE AI_Agent SHALL strip the fences and return only the Dockerfile content.
5. WHEN `extract_dockerfile` receives an LLM output string containing no `FROM` instruction after stripping, THE AI_Agent SHALL raise `DockerfileExtractionError`.
6. THE return value of `extract_dockerfile` SHALL contain no leading or trailing whitespace.

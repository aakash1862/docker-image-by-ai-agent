# Implementation Plan: Dockerfile Webapp Builder

## Overview

Evolve the existing Streamlit PoC into a production-grade FastAPI + React SPA that guides users through DockerHub OAuth authentication, structured Dockerfile composition, AI-assisted Dockerfile generation (LangChain + Together AI / Llama 3 70B), Docker image building with live WebSocket log streaming, Trivy vulnerability scanning, and image download / publish to DockerHub.

The implementation is broken into sequential milestones: project scaffolding, backend data models and services, API routers, WebSocket handler, security middleware, React frontend, and integration wiring.

---

## Tasks

- [ ] 1. Project scaffolding and configuration
  - Create the backend directory structure: `backend/` with sub-packages `routers/`, `services/`, `models/`, `middleware/`, and `tests/`
  - Create the frontend scaffold with Vite + React + TypeScript: `frontend/` with `src/components/`, `src/hooks/`, `src/api/`
  - Add `backend/requirements.txt` pinning `fastapi>=0.110`, `uvicorn[standard]>=0.29`, `python-jose[cryptography]>=3.3`, `httpx>=0.27`, `docker>=7.0`, `langchain>=0.2`, `langchain-together>=0.1`, `pydantic>=2.0`, `python-dotenv>=1.0`, `hypothesis>=6.0`, `pytest>=8.0`, `pytest-asyncio>=0.23`, `respx>=0.20`, `slowapi>=0.1`
  - Add `frontend/package.json` with dependencies: `react@^18`, `vite@^5`, `axios@^1.6`, `@monaco-editor/react@^4`, `react-beautiful-dnd@^13` (or `@dnd-kit/core`), `react-router-dom@^6`
  - Create `backend/main.py` with the FastAPI app instance, CORS middleware mount, rate-limiter mount, and router includes (stubs only)
  - Create `.env.example` documenting required variables: `JWT_SECRET`, `TOGETHER_API_KEY`, `DOCKERHUB_CLIENT_ID`, `DOCKERHUB_CLIENT_SECRET`, `DOCKERHUB_REDIRECT_URI`, `FRONTEND_ORIGIN`, `SESSION_TTL_SECONDS`
  - _Requirements: 10.2, 10.3_

- [ ] 2. Data models
  - [ ] 2.1 Implement Pydantic models in `backend/models/schemas.py`
    - `DockerfileInstruction` with `Literal` instruction field and `value` validator rejecting empty/whitespace
    - `CodeSource` with `source_type` and GitHub URL validator
    - `DockerfileSpec` with `base_image` validator and `instructions` + `code_source` fields
    - `GenerateRequest`, `GenerateResponse` (with `session_id`, `dockerfile`, `warnings`)
    - `BuildRequest`, `BuildResponse` (with `success`, `image_id`, `scan_result`, `error`)
    - `PushRequest`, `PushResponse` (with `success`, `image_url`, `error`)
    - `AuthStatus`, `DockerHubUser`, `Session`
    - `ScanResult` with `critical`, `high`, `medium`, `low`, `unknown`, `raw_output` fields
    - `BuildLogEvent` as `TypedDict` with `type`, `data`, `image_id`
    - `SessionExpiredError`, `InvalidTokenError`, `DockerfileExtractionError`, `PushError` custom exception classes
    - _Requirements: 3.1, 3.7, 5.4, 6.5, 6.6, 7.2, 8.1, 9.3_

  - [ ]* 2.2 Write unit tests for Pydantic model validators
    - Test `DockerfileInstruction` rejects empty `value`
    - Test `CodeSource` rejects non-GitHub URLs when `source_type == "github_url"`
    - Test `DockerfileSpec` rejects empty `base_image`
    - Test `ScanResult` defaults all counts to 0
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 3. Session Manager
  - [ ] 3.1 Implement `SessionManager` in `backend/services/session_manager.py`
    - `create_session(user: DockerHubUser) -> str`: sign HS256 JWT with configurable TTL, store session in an in-memory dict keyed by `session_id`
    - `get_session(token: str) -> Session`: decode and verify JWT; raise `SessionExpiredError` on expired token, `InvalidTokenError` on bad signature
    - `update_session(token: str, **kwargs) -> None`: patch mutable session fields (`dockerfile_content`, `built_image_tag`)
    - `delete_session(token: str) -> None`: remove session from store
    - Load `JWT_SECRET` and `SESSION_TTL_SECONDS` from environment variables
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 10.2_

  - [ ]* 3.2 Write property test for session round-trip identity (Property 3)
    - **Property 3: Session round-trip identity**
    - **Validates: Requirements 2.1, 2.2**
    - Generate arbitrary `DockerHubUser` objects via Hypothesis `@given`; assert `get_session(create_session(user)).user.username == user.username`

  - [ ]* 3.3 Write unit tests for Session Manager error paths
    - Test `get_session` raises `SessionExpiredError` when token TTL has elapsed (mock `datetime.now`)
    - Test `get_session` raises `InvalidTokenError` when JWT signature is tampered
    - _Requirements: 2.3, 2.4_

- [ ] 4. Auth Router
  - [ ] 4.1 Implement `GET /auth/status` in `backend/routers/auth.py`
    - Read session cookie; if valid return `AuthStatus(authenticated=True, username=...)`; if missing/expired return `AuthStatus(authenticated=False)`
    - _Requirements: 1.1_

  - [ ] 4.2 Implement `GET /auth/login` in `backend/routers/auth.py`
    - Build DockerHub OAuth authorization URL from `DOCKERHUB_CLIENT_ID` and `DOCKERHUB_REDIRECT_URI`
    - Return `{ "redirect_url": "https://hub.docker.com/oauth/..." }`
    - _Requirements: 1.2_

  - [ ] 4.3 Implement `GET /auth/callback` in `backend/routers/auth.py`
    - Exchange `code` query param for `access_token` via `httpx` POST to DockerHub token endpoint
    - On success: call `session_manager.create_session`, set `HttpOnly; Secure` session cookie, redirect to `/builder`
    - On error (error param present or token exchange fails): return HTTP 400 `{ "error": "oauth_failed", "message": "<details>" }`
    - _Requirements: 1.3, 1.4, 1.5, 1.6, 10.1_

  - [ ]* 4.4 Write integration tests for Auth Router using `respx`
    - Mock DockerHub token exchange success path and verify cookie is set
    - Mock DockerHub token exchange failure and verify HTTP 400 response body
    - _Requirements: 1.3, 1.4_

- [ ] 5. AI Agent Service
  - [ ] 5.1 Implement `build_llm_prompt` in `backend/services/ai_agent.py`
    - Accept `base_image: str`, `instructions: List[DockerfileInstruction]`, `code_source: Optional[CodeSource]`
    - Return a non-empty string that contains `base_image`, each instruction keyword+value in input order, and `code_source` context if provided
    - _Requirements: 11.1, 11.2, 11.3_

  - [ ]* 5.2 Write property test for prompt containing base image (Property 7)
    - **Property 7: Prompt contains base image**
    - **Validates: Requirements 11.1**
    - `@given(base_image=text(min_size=1), instructions=lists(dockerfile_instructions()))` — assert `base_image in build_llm_prompt(base_image, instructions, None)`

  - [ ]* 5.3 Write property test for prompt preserving instruction order (Property 8)
    - **Property 8: Prompt contains all instructions in order**
    - **Validates: Requirements 11.2**
    - `@given(instructions=lists(dockerfile_instructions(), min_size=1))` — assert positions of instruction keywords are non-decreasing in prompt

  - [ ] 5.4 Implement `extract_dockerfile` in `backend/services/ai_agent.py`
    - Strip markdown code fences (` ```dockerfile ` / ` ``` `)
    - Strip leading preamble before first `FROM`
    - Strip leading/trailing whitespace from result
    - Raise `DockerfileExtractionError` if result does not start with `FROM`
    - _Requirements: 5.2, 5.3, 11.4, 11.5, 11.6_

  - [ ]* 5.5 Write property test for extract_dockerfile stripping fences (Property 9)
    - **Property 9: extract_dockerfile strips markdown fences**
    - **Validates: Requirements 11.4**
    - `@given(dockerfile_body=valid_dockerfile_bodies())` — wrap in fences, assert result has no fence markers and starts with `FROM`

  - [ ] 5.6 Implement `AIAgentService.generate_dockerfile` in `backend/services/ai_agent.py`
    - Compose `Together` LLM (Llama 3 70B) via LangChain using `TOGETHER_API_KEY`
    - Call `build_llm_prompt`, invoke LLM, call `extract_dockerfile` on response
    - Retry once internally on any exception; raise `DockerfileExtractionError` or propagate after second failure
    - _Requirements: 5.1, 5.2, 5.6_

  - [ ]* 5.7 Write unit tests for AIAgentService with mocked LLM
    - Test clean Dockerfile returned when LLM output is markdown-fenced
    - Test `DockerfileExtractionError` raised when LLM output has no `FROM`
    - Test retry logic: first call raises, second call succeeds
    - _Requirements: 5.2, 5.3, 5.6_

- [ ] 6. Instruction order validation
  - [ ] 6.1 Implement `validate_instruction_order` in `backend/services/validation.py`
    - Accept `List[DockerfileInstruction]` (may be empty)
    - Return list of warning strings; never raise; never mutate input list
    - Warn when `COPY` or `ADD` appears before any `WORKDIR`
    - Warn when more than one `CMD` instruction is present (only once, not per duplicate)
    - Warn when `RUN` immediately follows `CMD`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 6.2 Write property test for non-mutating validation (Property 2)
    - **Property 2: Instruction validation is non-mutating**
    - **Validates: Requirements 4.4**
    - `@given(instructions=lists(dockerfile_instructions()))` — assert list is unchanged after call

  - [ ]* 6.3 Write property test for validation always returning a list (Property 5)
    - **Property 5: Instruction validation always returns a list**
    - **Validates: Requirements 4.3**
    - `@given(instructions=lists(dockerfile_instructions()))` — assert result is a non-None list

  - [ ]* 6.4 Write property test for COPY/ADD before WORKDIR warning (Property 10)
    - **Property 10: COPY/ADD before WORKDIR produces a warning**
    - **Validates: Requirements 4.1**
    - Use custom Hypothesis strategy `instruction_lists_with_copy_before_workdir()` — assert `len(warnings) >= 1`

  - [ ]* 6.5 Write property test for multiple CMD warning (Property 11)
    - **Property 11: Multiple CMD instructions produce a warning**
    - **Validates: Requirements 4.2**
    - Use custom Hypothesis strategy `instruction_lists_with_multiple_cmd()` — assert `len(warnings) >= 1`

- [ ] 7. Docker Service
  - [ ] 7.1 Implement `DockerService.build_image_streaming` in `backend/services/docker_service.py`
    - Write Dockerfile to temp dir, invoke `docker.APIClient().build(decode=True, rm=True)` in streaming mode
    - Yield `BuildLogEvent(type="log", ...)` for each `stream` key, `BuildLogEvent(type="error", ...)` for `error` key, `BuildLogEvent(type="done", image_id=...)` for `aux` key
    - Clean up temp dir in `finally` block regardless of success or failure
    - Catch `docker.errors.DockerException` at the call site and propagate as HTTP 503
    - _Requirements: 6.3, 6.4, 6.5, 6.6, 6.9, 6.10_

  - [ ] 7.2 Implement `DockerService.export_image_tar` in `backend/services/docker_service.py`
    - Call `client.images.get(image_tag).save(named=True)` and yield byte chunks
    - Raise `ImageNotFound` (re-export docker SDK exception) if image does not exist
    - _Requirements: 8.1, 8.2_

  - [ ]* 7.3 Write property test for export producing a valid tar archive (Property 4)
    - **Property 4: Export produces a valid tar archive**
    - **Validates: Requirements 8.1, 8.2**
    - `@given(image_tag=sampled_from(local_image_tags()))` — concatenate chunks and assert `tarfile.is_tarfile(buf)`
    - Note: this test requires a real local Docker image; skip via `pytest.mark.skipif` when Docker daemon is not available

  - [ ] 7.4 Implement `DockerService.push_image` in `backend/services/docker_service.py`
    - Authenticate with `client.login(username, password=access_token, registry="https://index.docker.io/v1/")`
    - Ensure tag starts with `username/`; tag image if needed
    - Stream push output; raise `PushError` on `error` key in push event
    - _Requirements: 9.1, 9.2_

  - [ ]* 7.5 Write property test for push always prefixing username (Property 6)
    - **Property 6: Push always prefixes the authenticated username**
    - **Validates: Requirements 9.2**
    - Implement and test `normalize_pushed_tag(image_tag, username) -> str`; `@given(image_tag=text(), username=text(min_size=1))` — assert result starts with `f"{username}/"`

  - [ ] 7.6 Implement `DockerService.tag_image` and `DockerService.remove_image` in `backend/services/docker_service.py`
    - `tag_image(current_tag, new_tag)`: call `client.images.get(current_tag).tag(new_tag)`
    - `remove_image(image_tag, force=False)`: call `client.images.remove(image_tag, force=force)`
    - _Requirements: 9.2_

  - [ ]* 7.7 Write unit tests for DockerService with mocked Docker client
    - Mock `docker.APIClient` to yield known log objects; assert correct `BuildLogEvent` sequence
    - Mock push to yield `{"error": "..."}` event; assert `PushError` is raised
    - _Requirements: 6.5, 6.6, 9.1_

- [ ] 8. Scan Service
  - [ ] 8.1 Implement `ScanService.scan_image` in `backend/services/scan_service.py`
    - Run `trivy image <tag>` via `subprocess.run(capture_output=True, text=True, timeout=120)`
    - Parse stdout to extract `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `UNKNOWN` counts (regex on Trivy table output)
    - Return `ScanResult`; if Trivy fails or crashes, set `raw_output` to a descriptive error message, all counts to 0
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ]* 8.2 Write unit tests for ScanService
    - Test correct count parsing from a realistic Trivy stdout fixture
    - Test graceful fallback when `subprocess.run` raises `FileNotFoundError` (Trivy not installed)
    - _Requirements: 7.2, 7.3_

- [ ] 9. Builder Router
  - [ ] 9.1 Implement `POST /builder/generate` in `backend/routers/builder.py`
    - Validate JWT session cookie via `session_manager.get_session`
    - Call `validate_instruction_order` to collect warnings
    - Call `ai_agent_service.generate_dockerfile`; on failure after retry return HTTP 502 `{ "error": "generation_failed" }`
    - Persist raw Dockerfile to session via `session_manager.update_session`
    - Return `GenerateResponse(session_id, dockerfile, warnings)`
    - Apply rate limiter: 10 requests/hour per user
    - _Requirements: 5.1, 5.4, 5.5, 5.6, 4.5, 10.5_

  - [ ]* 9.2 Write property test for Dockerfile always begins with FROM (Property 1)
    - **Property 1: Dockerfile always begins with FROM**
    - **Validates: Requirements 5.1, 5.3**
    - `@given(spec=valid_dockerfile_specs())` — call `generate_dockerfile` with mocked LLM returning a valid Dockerfile; assert `response.dockerfile.strip().startswith("FROM")`

  - [ ] 9.3 Implement `POST /builder/build` in `backend/routers/builder.py`
    - Validate session and retrieve `dockerfile_content`
    - Validate `image_tag` for shell meta-characters (requirement 10.6)
    - Trigger `docker_service.build_image_streaming` in a background task
    - On `DockerException` return HTTP 503 `{ "error": "docker_unavailable" }`
    - After successful build, call `scan_service.scan_image` and store `built_image_tag` in session
    - Return `BuildResponse(success, image_id, scan_result)`
    - Apply rate limiter: 10 requests/hour per user
    - _Requirements: 6.3, 6.10, 7.1, 10.5, 10.6_

  - [ ] 9.4 Implement `GET /builder/download/{session_id}` in `backend/routers/builder.py`
    - Validate session and retrieve `built_image_tag`; return HTTP 404 if absent
    - Return `StreamingResponse` over `docker_service.export_image_tar(image_tag)` with `Content-Disposition: attachment; filename="image.tar"`
    - _Requirements: 8.1, 8.3_

  - [ ] 9.5 Implement `POST /builder/push` in `backend/routers/builder.py`
    - Validate session; retrieve `built_image_tag` and `dockerhub_token`
    - Call `docker_service.push_image`
    - On `PushError` due to auth, return HTTP 403 `{ "error": "push_denied" }`; on other errors return HTTP 502 `{ "error": "push_failed", "message": "<details>" }`
    - On success return `PushResponse(success=True, image_url="https://hub.docker.com/r/{username}/{repo}")`
    - _Requirements: 9.1, 9.2, 9.3, 9.5, 9.6_

  - [ ]* 9.6 Write integration tests for Builder Router endpoints
    - Mock `AIAgentService` and `DockerService`; test full generate → build → download → push request cycle
    - Assert correct HTTP status codes and response shapes for each success and error path
    - _Requirements: 5.4, 6.10, 8.3, 9.3_

- [ ] 10. WebSocket handler for live build logs
  - [ ] 10.1 Implement WebSocket endpoint `ws/build/{session_id}` in `backend/routers/ws.py`
    - Accept WebSocket connection; validate session from cookie or query param
    - Subscribe to an asyncio `Queue` keyed by `session_id` that `build_image_streaming` writes to
    - Forward each `BuildLogEvent` as a JSON-serialized WebSocket message
    - Close connection after `type: "done"` or `type: "error"` event
    - _Requirements: 6.1, 6.2, 6.4, 6.7, 6.8_

  - [ ] 10.2 Wire `build_image_streaming` generator to the WebSocket queue in `backend/services/docker_service.py`
    - Wrap generator in an `asyncio` task that puts each `BuildLogEvent` onto the session queue
    - Ensure `type: "done"` or `type: "error"` is always the final item pushed
    - _Requirements: 6.2, 6.4, 6.5, 6.6_

  - [ ]* 10.3 Write integration test for WebSocket log streaming
    - Use `pytest-asyncio` and FastAPI `TestClient` WebSocket support
    - Build a minimal `FROM scratch` Docker image and assert all expected event types are received in order
    - _Requirements: 6.2, 6.4, 6.5, 6.6_

- [ ] 11. Security middleware
  - [ ] 11.1 Add CORS middleware in `backend/main.py`
    - Configure `CORSMiddleware` with `allow_origins=[FRONTEND_ORIGIN]` loaded from env
    - _Requirements: 10.3, 10.4_

  - [ ] 11.2 Add rate limiting middleware in `backend/main.py`
    - Use `slowapi` with a `Limiter` keyed by session user; apply `@limiter.limit("10/hour")` to `/builder/generate` and `/builder/build`
    - Return HTTP 429 `{ "error": "rate_limit_exceeded" }` when limit is exceeded
    - _Requirements: 10.5_

  - [ ] 11.3 Implement shell meta-character input validation in `backend/services/validation.py`
    - Function `validate_instruction_value(value: str) -> None`
    - Reject values containing backtick sequences, `$()` command substitutions, `${VAR:-...}` with embedded commands, or multi-stage build injection patterns; raise `ValueError` with HTTP 422 response
    - Call from `DockerfileInstruction` validator and from builder endpoints
    - _Requirements: 10.6_

  - [ ]* 11.4 Write unit tests for security middleware
    - Test CORS rejection for disallowed origins
    - Test rate limiter returns 429 after 10 requests
    - Test `validate_instruction_value` rejects known shell injection patterns and accepts safe values
    - _Requirements: 10.3, 10.4, 10.5, 10.6_

- [ ] 12. Checkpoint — backend complete
  - Ensure all backend tests pass: `pytest backend/tests/ -v`
  - Verify FastAPI app starts cleanly with `uvicorn backend.main:app --reload`
  - Ask the user if questions arise before proceeding to the frontend.

- [ ] 13. React frontend — Login page
  - [ ] 13.1 Implement `LoginPage` component in `frontend/src/components/LoginPage.tsx`
    - On mount, call `GET /auth/status`; redirect to `/builder` if authenticated
    - Render DockerHub username from `AuthStatus.username` if present
    - Render "Login with DockerHub" button that calls `GET /auth/login` and redirects browser to `redirect_url`
    - Display error banner if URL contains `?error=oauth_failed`
    - _Requirements: 1.1, 1.2, 1.4, 1.7_

  - [ ] 13.2 Implement `AuthContext` and `useAuth` hook in `frontend/src/hooks/useAuth.ts`
    - Expose `authenticated`, `username`, `logout` from context
    - On receiving any HTTP 401 response, clear local state and redirect to `/login`
    - _Requirements: 2.5, 2.6_

- [ ] 14. React frontend — Builder form
  - [ ] 14.1 Implement `BuilderForm` component in `frontend/src/components/BuilderForm.tsx`
    - Required base image field with client-side non-empty validation
    - Dynamic instruction list: add/remove rows, each row has instruction type select (18 options per Req 3.7) and value input
    - Drag-and-drop reorder via `@dnd-kit/core` (or move-up/move-down buttons)
    - Optional code source field (type select + value input with GitHub URL validation)
    - Submit calls `POST /builder/generate`; prevent submit on empty base image or empty instruction value
    - Persist form state to `localStorage` on every change; restore on mount
    - Display advisory warnings from `GenerateResponse.warnings` as non-blocking banners
    - _Requirements: 3.1, 3.2, 3.3, 3.7, 3.8, 2.7, 4.5_

  - [ ] 14.2 Implement `DockerfileViewer` component in `frontend/src/components/DockerfileViewer.tsx`
    - Display generated Dockerfile in Monaco Editor (read-only, `dockerfile` language)
    - Include "Download Dockerfile" button that triggers `<a download="Dockerfile">` with blob URL
    - _Requirements: 5.7, 5.8_

- [ ] 15. React frontend — Build log panel and controls
  - [ ] 15.1 Implement `BuildControls` component in `frontend/src/components/BuildControls.tsx`
    - "Build Image" button: opens WebSocket to `/ws/build/{session_id}` then calls `POST /builder/build`
    - Disable download and push buttons until `type: "done"` event received
    - On `type: "error"` event, display error in log panel and keep buttons disabled
    - _Requirements: 6.1, 6.7, 6.8_

  - [ ] 15.2 Implement `BuildLogPanel` component in `frontend/src/components/BuildLogPanel.tsx`
    - Auto-scrolling live log view that appends each `type: "log"` message
    - Display "Build successful" banner on `type: "done"`
    - Display error message on `type: "error"`
    - _Requirements: 6.4, 6.7, 6.8_

  - [ ] 15.3 Implement `ScanResultsPanel` component in `frontend/src/components/ScanResultsPanel.tsx`
    - Display counts for all five severity levels from `ScanResult`
    - Show prominent warning banner when `critical > 0 || high > 0`
    - _Requirements: 7.4, 7.5_

- [ ] 16. React frontend — Completion screen and download/push controls
  - [ ] 16.1 Implement `DownloadImageButton` in `frontend/src/components/DownloadImageButton.tsx`
    - On click, navigate browser to `GET /builder/download/{session_id}` triggering `image.tar` download
    - _Requirements: 8.4_

  - [ ] 16.2 Implement `PushToDockerHub` component in `frontend/src/components/PushToDockerHub.tsx`
    - On click, call `POST /builder/push`; on HTTP 403 prompt user to re-authenticate
    - On success, navigate to `CompletionScreen`
    - _Requirements: 9.4, 9.5_

  - [ ] 16.3 Implement `CompletionScreen` component in `frontend/src/components/CompletionScreen.tsx`
    - "Congratulations" page displaying the published image URL as a clickable link
    - _Requirements: 9.3, 9.4_

- [ ] 17. Integration and wiring
  - [ ] 17.1 Wire all backend routers into `backend/main.py`
    - Include `auth_router`, `builder_router`, WebSocket endpoint
    - Mount CORS middleware, rate limiter, and session dependency
    - Add global exception handlers for `SessionExpiredError` → 401, `InvalidTokenError` → 401, `DockerException` → 503
    - _Requirements: 2.5, 6.10, 10.3_

  - [ ] 17.2 Configure React Router in `frontend/src/App.tsx`
    - Route `/` and `/login` → `LoginPage`
    - Route `/builder` → `BuilderForm` + `DockerfileViewer` + `BuildControls` + `BuildLogPanel` + `ScanResultsPanel` (protected, redirect to `/login` if not authenticated)
    - Route `/complete` → `CompletionScreen`
    - _Requirements: 1.1, 2.6, 9.4_

  - [ ] 17.3 Configure Vite proxy in `frontend/vite.config.ts`
    - Proxy `/auth`, `/builder`, `/ws` to `http://localhost:8000` for local development
    - _Requirements: 10.3_

  - [ ] 17.4 Add `frontend/src/api/client.ts` Axios instance
    - Base URL from `VITE_API_BASE_URL` env var (or `/` in production)
    - Response interceptor: on HTTP 401 clear auth state and redirect to `/login`
    - _Requirements: 2.6_

- [ ] 18. Final checkpoint — full system
  - Ensure all backend tests pass: `pytest backend/tests/ -v`
  - Ensure frontend builds without type errors: `cd frontend && npm run build`
  - Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints (tasks 12 and 18) ensure incremental validation before moving to the next milestone
- Property tests use the `hypothesis` library and validate universal behavioral invariants
- Unit tests use `pytest` with mocked dependencies (no live Docker daemon required except where noted)
- The `export_image_tar` property test (7.3) requires a live Docker daemon and should be conditionally skipped in CI environments without one
- Session storage defaults to an in-memory dict; swap `SessionManager` to use Redis for multi-replica deployments without changing the interface

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1", "3.1"] },
    { "id": 1, "tasks": ["2.2", "3.2", "3.3", "5.1", "6.1"] },
    { "id": 2, "tasks": ["4.1", "4.2", "4.3", "5.2", "5.3", "5.4", "6.2", "6.3", "6.4", "6.5"] },
    { "id": 3, "tasks": ["4.4", "5.5", "5.6", "7.1", "7.2", "7.6", "8.1"] },
    { "id": 4, "tasks": ["5.7", "7.3", "7.4", "7.7", "8.2", "9.1", "9.2", "9.3", "9.4", "9.5", "10.1", "10.2", "11.1", "11.2", "11.3"] },
    { "id": 5, "tasks": ["9.6", "10.3", "11.4", "13.1", "13.2"] },
    { "id": 6, "tasks": ["14.1", "14.2", "15.1", "15.2", "15.3"] },
    { "id": 7, "tasks": ["16.1", "16.2", "16.3", "17.1", "17.3", "17.4"] },
    { "id": 8, "tasks": ["17.2"] }
  ]
}
```

# Greenhouse Job Board API access review

Review date: 2026-11-11

Scope: `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs`

This is an engineering access review, not legal advice.

## Evidence reviewed

- The official [Greenhouse Job Board API documentation](https://docs.greenhouse.io/job-board) states that Job Board data is publicly available and authentication is not required for GET endpoints. It documents the list-jobs endpoint and identifies the `id` field as the job-post identifier.
- `https://boards-api.greenhouse.io/robots.txt` returned `User-agent: *` with `Disallow: /embed/` on 2026-11-11. The reviewed `/v1/boards/.../jobs` endpoint is outside that disallowed path.
- The API documentation distinguishes public GET methods from the authenticated application-submission POST endpoint. JobSift does not call the POST endpoint.

## Enforced limits

- Only published job-listing data is requested.
- The source is configured for at most two requests per minute.
- Every request uses an identified `JobSift/0.1` user agent, a 20-second timeout, and at most three attempts.
- Retries are limited to transport failures and HTTP 408, 429, 500, 502, 503, or 504.
- JobSift honors numeric `Retry-After`; otherwise it uses capped exponential backoff.
- The adapter does not send credentials, cookies, applicant details, resumes, or application-form data.
- CI and unit tests use a synthetic JSON fixture with `httpx.MockTransport` and never contact the live service.

## Source attribution and disable boundary

The initial reviewed board is Anthropic's published Greenhouse board. Records retain `source=greenhouse-anthropic`, the employer name, the Greenhouse job-post ID, and the original application URL. The source has an explicit `enabled` switch and can be disabled without changing adapter code.

The review must be repeated if the endpoint, official documentation, robots policy, intended fields, request rate, or use case changes.

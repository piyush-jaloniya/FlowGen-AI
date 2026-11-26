# FlowGen API

The workbench and API share an origin. The v2 API accepts analysis requests without retaining files or executing source.

## Generate a diagram

Send `POST /api/analyze` with JSON.

```json
{
  "mode": "flowchart",
  "files": [
    {
      "path": "checkout.py",
      "language": "python",
      "content": "def checkout(member):\n    if member:\n        return 90\n    return 100\n"
    }
  ]
}
```

Modes are `flowchart`, `workflow`, and `overview`. The language is inferred from the path when omitted. Relative paths preserve package and module relationships. A report includes normalized `files`, analyzable `symbols`, `diagnostics`, `languages`, and an initial `graph`. Include files named `tsconfig.json` or `tsconfig.*.json` alongside TypeScript sources to resolve local path aliases. These files round-trip with `language: "config"` and have no symbols or module nodes.

For a different function or entry point, send the same files with a `symbolId` selected from the report and the desired mode. The response contains only `graph`. A graph has typed `nodes` and `edges`, source path and line ranges where applicable, and warnings when the analysis abstracts or omits part of the program.

Invalid syntax produces a diagnostic with a file and line. If no diagram can be built, `graph` is `null`. A workflow can still be generated from other valid files in a project.

## Upload a project

Send `POST /api/upload?mode=workflow` as multipart form data. Repeat the `files` field for multiple source files, or attach one ZIP using the same field. Directory paths may be included in multipart filenames. The response has the same report structure as JSON analysis.

## Other responses

- `GET /api/health` reports the running service, supported extensions, and upload limits.
- `GET /api/openapi.json` exposes request and response schemas, including the multipart upload contract.
- `400` indicates invalid file names, unsupported uploads, invalid archives, or duplicate paths.
- `413` indicates a request or source size over the configured limit.
- `422` indicates an invalid request shape or diagram scope. Request validation errors contain field locations, messages, and codes.
- `503` indicates that all analysis slots are busy. Wait for the interval in the `Retry-After` header before retrying.

The v2 response uses a structured graph with source references. The previous Mermaid-only endpoints and optional AI provider configuration were retired in this rebuild.

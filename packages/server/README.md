# tonedown-server

HTTP API for site operators and for the browser tools. One endpoint grades a batch of texts and
returns levels, categories and a pass / review / block action under a policy.

```
uv run tonedown-server                      # http://127.0.0.1:8080, docs at /docs
curl -s localhost:8080/v1/grade -H 'Content-Type: application/json' \
  -d '{"items":[{"id":"1","text":"楼主就是个傻X"}],"policy":"balanced"}'
```

Configuration is by environment variables; see `.env.example` at the repository root.

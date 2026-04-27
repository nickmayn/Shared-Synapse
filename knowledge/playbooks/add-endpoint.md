---
id: add-endpoint
title: Add API Endpoint Playbook
tags: [api, backend, playbook]
---

# Add API Endpoint Playbook

Step-by-step guide to adding a new REST API endpoint.

## Steps

1. Define the route in `src/api/routes.py`
2. Create request/response Pydantic models in `src/api/models.py`
3. Implement the handler function
4. Add input validation
5. Write unit tests in `tests/test_api.py`
6. Update OpenAPI spec
7. Deploy via CI/CD pipeline

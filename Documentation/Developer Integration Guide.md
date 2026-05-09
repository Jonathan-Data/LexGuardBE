# 👨‍💻 Developer Integration Guide

Integrating LexGuardBE into your workflow is designed to be seamless, following a "Compliance-as-Code" philosophy.

## Installation
```bash
pip install lexguard-sdk
```

## Basic Usage
Initialize the LexGuard client and submit a system for classification.

```python
from lexguard import LexClient

client = LexClient(api_key="your_api_key")

# Define your AI system profile
system_profile = {
    "name": "RecruitMaster-AI",
    "purpose": "Screening CVs for junior engineering roles",
    "domain": "HR/Employment",
    "deployment_region": "Belgium"
}

# Run compliance check
audit_result = client.check_compliance(system_profile)

if audit_result.risk_tier == "HIGH_RISK":
    print(f"Action Required: {audit_result.required_actions}")
```

## CI/CD Integration (GitHub Actions)
Add LexGuard to your pipeline to prevent the deployment of non-compliant models.

```yaml
jobs:
  compliance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: LexGuard Scan
        run: lexguard-cli scan --project-id ${PROJ_ID} --fail-on prohibited
```

## Best Practices
1. **Early Scanning**: Run LexGuard during the design phase, before any code is written.
2. **Metadata Accuracy**: The accuracy of the Categorizer Agent depends on the quality of the system description.
3. **Handle Exceptions**: Always have a fallback plan if the LexGuard API returns a `BLOCK` status.

---
[[Lexguard|← Back to Hub]]

# ⚖️ Regulatory Mapping: Annex III & Risk Tiers

LexGuardBE automates the classification of AI systems based on the **EU AI Act's risk-based approach**.

## 🔴 Prohibited AI Systems (Art. 5)
Systems that pose an unacceptable risk are automatically flagged for immediate block.
- **Biometric Categorization**: Based on sensitive characteristics.
- **Social Scoring**: Evaluative systems that lead to detrimental treatment.
- **Dark Patterns**: Systems that manipulate human behavior to cause harm.

## 🟠 High-Risk AI Systems (Annex III)
High-Risk systems require a full conformity assessment. LexGuardBE focuses on the following Annex III categories:
1. **Critical Infrastructure**: AI in water, gas, electricity.
2. **Education & Vocational Training**: Systems determining access to education.
3. **Employment & HR**: Recruitment, promotion, and termination (CV screening).
4. **Law Enforcement**: Risk assessment and polygraphs.
5. **Migration & Border Control**: Verification of travel documents.

### High-Risk Requirements:
- **Technical Documentation** (Art. 11)
- **Record-Keeping** (Art. 12)
- **Transparency & Provision of Information** (Art. 13)
- **Human Oversight** (Art. 14)

## 🟡 Limited-Risk AI Systems
Systems like chatbots or generative AI (that are not high-risk) must adhere to transparency obligations.
- **Disclosure**: Users must be notified they are interacting with an AI.
- **Watermarking**: AI-generated content must be detectable.

## 🟢 Minimal/No Risk
Standard AI (e.g., spam filters, video game AI). No additional legal obligations under the AI Act, though GDPR still applies.

---
**LexGuard Logic Flow:**
`System Metadata` → `Categorizer Agent` → `Legal RAG Lookup` → `Risk Tier Assignment`

[[Lexguard|← Back to Hub]]

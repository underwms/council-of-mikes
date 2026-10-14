# Corporate Architecture Rules & Governance Guidelines

Source Context: Extracted from Domain Architecture (DARCH) ADRs.

## 1. API Design & Versioning
- MUST include major version in API endpoint paths: `/base-url/v1/endpoint`.
- MUST designate non-public / experimental endpoints with `/v0` or `/vX-alpha`.
- MUST NOT introduce breaking changes within the same major version.
- MUST monitor `api-deprecated-versions` response headers in downstream consumers.
- MUST wrap third-party vendor APIs/SDKs behind internal facade interfaces.
- MUST align microservice boundaries with Bounded Context Domains (Customer, Product, Order).

## 2. Data & Security Rules
- MUST NOT allow direct cross-service database access. All data exchange MUST occur via service APIs.
- MUST NOT commit hardcoded secrets, tokens, or connection strings into source code.
- MUST inject sensitive configuration at runtime via secrets management (Vault / Kubernetes Secrets).
- MUST enforce PII protection standards for sensitive customer attributes.
- MUST use Microsoft Entra ID (Azure AD) for associate authentication.
- MUST enforce Principle of Least Privilege (PoLP) across service identities and user roles.

## 3. Deployment & DevOps
- Teams MUST own their deployment and rollback execution (via Octopus Deploy).
- MUST integrate code into the `Main` branch frequently (Continuous Integration).
- Lower environments (Dev/QA) MUST mirror Production topology and configuration.
- Application configuration MUST use externalized ConfigMaps separate from secret stores.
- Architectural implementations SHOULD remain cloud-agnostic to prevent provider lock-in.

## 4. Code Standards & Reusability
- All code and infrastructure configurations MUST reside in Git source control.
- Utility libraries MUST be published as versioned internal NuGet/NPM packages following `Crate.<Domain>.<Feature>` naming conventions.
- Customer-facing applications MUST return human-readable error messages and suppress internal stack details.
- Requirements SHOULD be expressed using Gherkin syntax (BDD) for customer-focused test validation.

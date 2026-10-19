---
title: Security Incident Runbook
allowed_roles: [admin]
---
# Security Incident Runbook

Classification: Restricted.

## Severity levels
- **SEV1:** confirmed unauthorized access to customer data.
- **SEV2:** suspected unauthorized access, or a compromised employee account.
- **SEV3:** a policy violation with no evidence of data access.

## First steps
1. Page the security on-call engineer.
2. Contain the issue: disable affected accounts and revoke their active sessions.
3. Preserve logs before making any further changes.
4. Rotate any credentials that may have been exposed.

## Notification
For SEV1 incidents involving personal data, Legal decides on customer and regulator notification. Notification must happen within 72 hours of confirming the incident.

## Closing the incident
Write a post-incident review within 10 business days and track every follow-up action to completion.

# Security Policy

## Reporting a Vulnerability
Please open a private security advisory on GitHub or email the maintainers.
Do not file public issues for vulnerabilities.

## Supported Versions
Main branch is supported. Pin dependencies for production deployments.

## API Key Security

### Protecting Your API Keys
- **Never commit** `.env` files containing actual API keys to version control
- Use `.env.example` as a template and create your own `.env` file locally
- The `.env` file is included in `.gitignore` to prevent accidental commits
- Rotate API keys immediately if they are accidentally exposed

### If You Exposed an API Key
1. **Immediately revoke/rotate** the exposed API key through your provider
2. Update your local `.env` file with the new key
3. Report the incident if you believe others may have accessed it

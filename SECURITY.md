# Security Policy

## Supported Versions

We only support the latest major version of the Zedd Weather Dashboard. Please ensure your Raspberry Pi 5 is running the most recent stable release to receive security updates.

| Version | Supported          |
| ------- | ------------------ |
| v2.x.x  | :white_check_mark: |
| v1.x.x  | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within Zedd Weather, please send an e-mail to the security team at `security@zeddweather.local`. All security vulnerabilities will be promptly addressed.

Please do not report security vulnerabilities through public GitHub issues.

## Edge Node Security (Raspberry Pi 5)

When deploying this application on a Raspberry Pi 5 in an industrial environment, you must adhere to the following security practices:

1. **Change Default Credentials**: Immediately change the default `pi` user password.
2. **Disable Unused Services**: Disable SSH if not needed, or configure it to use key-based authentication only. Disable Bluetooth and Wi-Fi if using a hardwired Ethernet connection.
3. **Firewall**: Configure `ufw` or `iptables` to only allow incoming traffic on necessary ports (e.g., port 3000 for the web interface).
4. **Physical Security**: Ensure the weatherproof enclosure is physically secured (padlocked or tamper-evident seals) to prevent unauthorized access to the hardware or SD card.
5. **API Key Management**: Never hardcode the `GEMINI_API_KEY` or Minima node credentials in the source code. Always use environment variables (`.env` file) and ensure the file has strict read permissions (`chmod 600 .env`).
6. **Data Integrity**: The system relies on the Minima network for cryptographic attestation. Ensure the local Minima node is properly synced and secured to prevent spoofing of telemetry data.

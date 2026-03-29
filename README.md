# Zedd Weather Dashboard

Zedd Weather is a decentralized edge cloud operating system and telemetry dashboard designed for industrial construction sites. It leverages real-time micro-climate data, Gemini 3.1 Pro AI for automated risk analysis, and the Minima network for cryptographic attestation of environmental conditions.

This application is built to be deployed on a **Raspberry Pi 5 (16GB)** as an edge node, ensuring high-performance local processing and AI inference.

## Features

- **Live Telemetry Monitoring**: Real-time tracking of Temperature, Humidity, Pressure, Precipitation, Tide Level, UV Index, and AQI.
- **Automated AI Risk Analysis**: Uses Gemini 3.1 Pro to continuously analyze telemetry and generate color-coded risk levels (Green, Amber, Red, Black) and mitigation directives.
- **Visual Context Integration**: Upload images or videos to cross-reference visual data with live telemetry.
- **Site Map & Logistics Grounding**: Dynamically fetches local emergency services, hardware stores, and safe zones based on the site's geolocation.
- **ZeddProof Ledger**: Cryptographically signs and logs all telemetry and mitigation directives to the Minima network for immutable auditing.

## Hardware Requirements & Shopping List

To deploy this system as a standalone edge weather station, you will need the following hardware:

### Core Computing
- **Raspberry Pi 5 (16GB RAM)**: Required for running the React frontend, Node.js orchestrator, and local AI inference tasks smoothly.
- **MicroSD Card (128GB+ Class 10/U3)**: For the OS, application, and local data buffering.
- **Raspberry Pi 5 Active Cooler**: Essential to prevent thermal throttling during intensive AI operations.
- **27W USB-C Power Supply**: Official Raspberry Pi power supply recommended for stability.

### Sensors & HATs
- **Sense HAT (v2)**: Provides built-in sensors for Temperature, Humidity, and Barometric Pressure.
- **Pimoroni Enviro+ for Raspberry Pi**: Excellent alternative/addition for advanced air quality (AQI), gas, and particulate matter sensing.
- **Waveshare RS485 CAN HAT**: If interfacing with industrial-grade external anemometers (wind speed) or rain gauges via Modbus/RS485.
- **Adafruit VEML6075 UV Sensor Breakout**: For accurate UV Index measurements.
- **External Rain Gauge (Tipping Bucket)**: Connects via GPIO for precise precipitation tracking.

### Weatherproof Enclosure
- **Recommended Enclosure**: **BUD Industries NBF-32016 Plastic ABS NEMA Economy Box** (or similar IP67-rated enclosure).
  - *Why*: It's fully weatherproof (IP67), UV-resistant, and transparent/opaque options are available. You will need to drill holes for cable glands (for external sensors/power) and ensure proper ventilation (using waterproof vents like Gore-Tex patches) to prevent condensation and heat buildup from the Pi 5.

## Deployment on Raspberry Pi 5

### 1. System Preparation
Ensure your Raspberry Pi 5 is running the latest 64-bit Raspberry Pi OS (Bookworm or later).

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install curl git build-essential
```

### 2. Install Node.js
Install Node.js (v20+ recommended):

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 3. Clone and Setup
Clone the repository and install dependencies:

```bash
git clone <repository-url> zedd-weather
cd zedd-weather
npm install
```

### 4. Environment Configuration
Create a `.env` file in the root directory and add your Gemini API key:

```env
GEMINI_API_KEY=your_api_key_here
```

### 5. Build and Run
Build the application for production:

```bash
npm run build
```

Start the server:

```bash
npm start
```
*Note: The application runs on port 3000 by default.*

## Policies & Security

- **Data Immutability**: All critical telemetry and AI directives are hashed (SHA-256) and submitted to the Minima network. This ensures that historical environmental data cannot be tampered with, providing a verifiable audit trail for insurance and safety compliance.
- **Edge Processing**: To minimize latency and reliance on external networks during critical events, the system is designed to perform initial risk assessments locally on the Pi 5 where possible, falling back to cloud APIs (Gemini) when a connection is available.
- **Fail-Safe Operation**: If the AI analysis fails or the network drops, the system defaults to displaying raw telemetry and triggers local visual/auditory alarms via the Pi's GPIO pins if thresholds are breached.

## License
MIT License

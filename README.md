# AioGram + Webhook Template with Docker

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This template provides a ready-to-use setup for creating Telegram bots using the AioGram library with webhook integration. The project includes Docker configuration for easy deployment and scaling.

## Features

- AioGram 3.x implementation
- Webhook setup (no polling)
- Docker and docker-compose configuration
- Environment-based configuration
- Structured project layout
- Easy to customize and extend

## Prerequisites

- Docker and docker-compose
- ngrok (for local development)
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/aiogram-webhook-template.git
cd aiogram-webhook-template
```

2. Copy the environment template and configure your variables:
```bash
cp .env.dist .env
```

3. Edit the `.env` file with your Telegram Bot Token and other configurations:
```
ADMINS=""
BOT_TOKEN=""
api_key=""
ip=localhost
WEBHOOK_HOST=
WEBHOOK_PATH=/webhook
WEBAPP_HOST=0.0.0.0
WEBAPP_PORT=8001

```

## Development Setup

1. Start ngrok to create a tunnel to your local server:
```bash
ngrok http 8001
```

2. Copy the HTTPS URL provided by ngrok (e.g., `https://abc123.ngrok-free.app`)

3. Update the webhook URL in your configuration:
```
WEBHOOK_HOST=https://abc123.ngrok-free.app
WEBHOOK_PATH=/webhook
```

4. Build and start the Docker containers:
```bash
docker-compose up --build
```

## Project Structure

```
├── app/
│   ├── __init__.py
│   ├── bot.py              # Bot initialization
│   ├── handlers/           # Message handlers
│   │   ├── __init__.py
│   │   ├── common.py       # Common commands (start, help)
│   │   └── ...
│   ├── middlewares/        # AioGram middlewares
│   ├── services/           # Business logic
│   └── utils/              # Utility functions
├── docker/                 # Docker configuration files
├── .env.dist              # Environment template
├── docker-compose.yml     # Docker Compose configuration
├── Dockerfile             # Docker build instructions
└── requirements.txt       # Python dependencies
```

## Production Deployment

For production deployment:

1. Set up a server with Docker installed
2. Configure your domain with proper SSL certificates
3. Update the `.env` file with your production domain:
```
WEBHOOK_HOST=https://your-domain.com
WEBHOOK_PATH=/webhook
```

4. Deploy using Docker Compose:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `BOT_TOKEN` | Telegram Bot API Token | - |
| `ADMIN_ID` | Telegram User ID of the admin | - |
| `WEBHOOK_HOST` | Host for webhook (domain or ngrok URL) | - |
| `WEBHOOK_PATH` | Path for webhook | /webhook |
| `WEBAPP_HOST` | Web app host | 0.0.0.0 |
| `WEBAPP_PORT` | Web app port | 8001 |

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
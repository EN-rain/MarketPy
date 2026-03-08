# OpenClaw Architecture

## Overview

OpenClaw adds a conversational autonomous layer on top of MarketPy with:

1. Discord input/output (`DiscordBridge`)
2. Natural-language parsing (`NaturalLanguageProcessor`)
3. LLM intent extraction (`KimiK2Client`)
4. Command execution (`CommandExecutor`)
5. Persistent memory (`ContextManager`)
6. Autonomous agents (`MarketMonitor`, `RiskAdvisor`)
7. Strategy and portfolio assistance (`StrategyAssistant`, `PortfolioOptimizer`)
8. Extensibility (`SkillExtensionSystem`)

## Runtime flow

1. Incoming message enters `DiscordBridge`.
2. Message is authorized and queued in `AutonomousAgent`.
3. Worker parses command via NLP + Kimi context.
4. Risk checks run before any execution command.
5. MarketPy APIs are called via `MarketPyApiClient`.
6. Structured result/error is returned to Discord.
7. Conversation context is persisted and backed up.

## Service endpoints

- `GET /health` – full component health + queue/uptime
- `GET /metrics` – Prometheus-style metrics
- `POST /command` – local command injection (testing/automation)

## Security controls

- User whitelist authorization in Discord bridge
- Optional request signing for MarketPy API calls
- Secrets masking in logs
- AES-256-GCM context encryption at rest
- Per-user and upstream rate limiting

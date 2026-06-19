#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

ruby -ryaml -e '
  config = YAML.safe_load(File.read(ARGV.fetch(0)), permitted_classes: [], permitted_symbols: [], aliases: false)
  services = config.fetch("services")
  api = services.find { |service| service["name"] == "edu-demo-api" }
  web = services.find { |service| service["name"] == "edu-demo-web" }

  abort "missing edu-demo-api" unless api
  abort "missing edu-demo-web" unless web
  abort "Blueprint must not provision Render Postgres" if config.key?("databases")
  abort "backend must use paid starter plan" unless api["plan"] == "starter"
  abort "backend migration gate missing" unless api["preDeployCommand"] == "uv run alembic upgrade head"
  abort "initial embedding seed missing" unless api["initialDeployHook"] == "uv run python -m scripts.seed_embeddings"
  abort "backend health check missing" unless api["healthCheckPath"] == "/healthz"
  abort "frontend must be static" unless web["runtime"] == "static"
  abort "frontend SPA rewrite missing" unless web.fetch("routes").any? { |route|
    route == {"type" => "rewrite", "source" => "/*", "destination" => "/index.html"}
  }
  env = api.fetch("envVars").to_h { |item| [item.fetch("key"), item] }
  abort "Supabase DATABASE_URL must be prompted" unless env.dig("DATABASE_URL", "sync") == false
  abort "async grading must be disabled" unless env.dig("GRADING_ASYNC_ENABLED", "value") == "false"
  abort "cache pubsub must be disabled" unless env.dig("CURRICULUM_CACHE_PUBSUB_ENABLED", "value") == "false"
  abort "Anthropic key must be prompted" unless env.dig("ANTHROPIC_API_KEY", "sync") == false
' "$repo_root/render.yaml"

echo "Render Blueprint checks passed"

#!/bin/bash

set -e

if [ -z "$WEBHOOK_URL" ]; then
  echo "❌ WEBHOOK_URL is not set."
  exit 1
fi

# Read and format vulnerabilities
NEW_VULNERABILITIES=$(cat new-found.json | jq -c '[.[] | {
  title: .title,
  text: "Severity: \(.severity)\nProgram: \(.program)\nDate: \(.date)\n[View Report](\(.url))",
  color: "warning"
}]')

echo "📝 Formatted Slack attachments:"
echo "$NEW_VULNERABILITIES" | jq .

if [[ "$(echo "$NEW_VULNERABILITIES" | jq length)" -gt 0 ]]; then
  echo "📤 Sending to Slack..."
  curl -X POST -H 'Content-type: application/json' --data "{
    \"text\": \"*New Android vulnerability reports*\",
    \"attachments\": $NEW_VULNERABILITIES
  }" "$WEBHOOK_URL"
else
  echo "✅ No new vulnerabilities found."
fi

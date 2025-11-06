#!/bin/bash

# Scrape all websites from config.yaml
# Usage: ./scrape_all.sh

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Starting webscraper from config.yaml..."
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Run the webscraper
python3 scripts/run_webscraper.py

echo ""
echo "Webscraping completed!"
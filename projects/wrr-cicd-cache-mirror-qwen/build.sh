#!/bin/bash
set -e

# BUG: no cache configuration
# BUG: no mirror source for dependencies
echo "Installing dependencies..."
npm install

echo "Building..."
npm run build

echo "Running tests..."
npm test

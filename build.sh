#!/bin/bash
# Build script for Render

set -o errexit

# Install backend dependencies
pip install -r backend/requirements.txt

# Run migrations
python backend/manage.py migrate

# Collect static files
python backend/manage.py collectstatic --no-input

# Install and build frontend
cd frontend
npm install
npm run build
cd ..

echo "Build complete!"

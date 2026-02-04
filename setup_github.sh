#!/bin/bash
# GitHub Repository Setup Script
# Run this script to push your code to GitHub

echo "🚀 Bot-TiendaLasMotos - GitHub Setup"
echo "===================================="
echo ""

# Check if GitHub username is provided
if [ -z "$1" ]; then
    echo "❌ Error: GitHub username required"
    echo ""
    echo "Usage: ./setup_github.sh YOUR_GITHUB_USERNAME"
    echo ""
    echo "Example: ./setup_github.sh tobiasgaitan"
    exit 1
fi

GITHUB_USERNAME=$1
REPO_NAME="Bot-TiendaLasMotos"

echo "📝 Configuration:"
echo "   GitHub User: $GITHUB_USERNAME"
echo "   Repository: $REPO_NAME"
echo ""

# Add remote
echo "🔗 Adding GitHub remote..."
git remote add origin "https://github.com/$GITHUB_USERNAME/$REPO_NAME.git" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "⚠️  Remote already exists, updating URL..."
    git remote set-url origin "https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"
fi

# Rename branch to main
echo "🌿 Setting branch to 'main'..."
git branch -M main

# Push to GitHub
echo "📤 Pushing to GitHub..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SUCCESS! Code pushed to GitHub"
    echo ""
    echo "📋 Next Steps:"
    echo "   1. View repository: https://github.com/$GITHUB_USERNAME/$REPO_NAME"
    echo "   2. Open Google Cloud Shell"
    echo "   3. Clone repository:"
    echo "      git clone https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"
    echo "   4. Navigate to project:"
    echo "      cd $REPO_NAME"
    echo "   5. Initialize V6.0 configuration:"
    echo "      python3 scripts/init_v6_config.py"
    echo "   6. Deploy to Cloud Run:"
    echo "      ./deploy.sh"
    echo ""
else
    echo ""
    echo "❌ Push failed. Please check:"
    echo "   1. Repository exists on GitHub: https://github.com/$GITHUB_USERNAME/$REPO_NAME"
    echo "   2. You have push permissions"
    echo "   3. Your GitHub credentials are configured"
    echo ""
    echo "💡 Create repository manually:"
    echo "   1. Go to: https://github.com/new"
    echo "   2. Repository name: $REPO_NAME"
    echo "   3. DO NOT initialize with README"
    echo "   4. Run this script again"
    exit 1
fi

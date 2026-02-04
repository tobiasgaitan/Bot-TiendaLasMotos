# 🔄 Git Repository Setup & GitHub Sync Guide

## ✅ Local Git Repository Initialized

Your V6.0 code has been committed to a local Git repository.

---

## 📤 Step 1: Push to GitHub

### Option A: Create New Repository via GitHub CLI (Recommended)

If you have GitHub CLI installed:

```bash
# Authenticate with GitHub (if not already)
gh auth login

# Create repository and push
cd /Users/tobiasgaitangallego/Bot-TiendaLasMotos
gh repo create Bot-TiendaLasMotos --public --source=. --remote=origin --push
```

### Option B: Create Repository Manually via GitHub Web

1. **Go to GitHub**: https://github.com/new

2. **Create Repository**:
   - Repository name: `Bot-TiendaLasMotos`
   - Description: "V6.0 Enterprise WhatsApp Bot - Tienda Las Motos"
   - Visibility: Public (or Private)
   - **DO NOT** initialize with README, .gitignore, or license

3. **Push your code**:

```bash
cd /Users/tobiasgaitangallego/Bot-TiendaLasMotos

# Add GitHub as remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/Bot-TiendaLasMotos.git

# Push to GitHub
git branch -M main
git push -u origin main
```

**Replace `YOUR_USERNAME`** with your actual GitHub username.

---

## 📥 Step 2: Clone in Google Cloud Shell

Once pushed to GitHub, open **Google Cloud Shell** and run:

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/Bot-TiendaLasMotos.git

# Navigate to the project
cd Bot-TiendaLasMotos

# Verify files are present
ls -la
ls -la scripts/
ls -la app/core/

# Initialize V6.0 configuration in Firestore
python3 scripts/init_v6_config.py
```

---

## 🔄 Step 3: Establish Sync Workflow

### From Local (Mac) → GitHub → Cloud Shell

**When you make changes locally**:

```bash
# On your Mac
cd /Users/tobiasgaitangallego/Bot-TiendaLasMotos

# Stage changes
git add .

# Commit with descriptive message
git commit -m "feat: description of changes"

# Push to GitHub
git push origin main
```

**Then in Cloud Shell**:

```bash
# Pull latest changes
cd ~/Bot-TiendaLasMotos
git pull origin main

# Deploy updated code
./deploy.sh
```

---

## 🔐 Step 4: Configure Git in Cloud Shell (First Time Only)

Before making commits in Cloud Shell, configure Git:

```bash
git config --global user.name "Tobias Gaitan"
git config --global user.email "your-email@example.com"
```

---

## 📊 Verify Repository Status

Check what was committed:

```bash
# View commit history
git log --oneline

# View files in repository
git ls-files

# Check repository status
git status
```

---

## 🎯 Quick Reference Commands

### Local Development (Mac)
```bash
# Check status
git status

# Add all changes
git add .

# Commit changes
git commit -m "description"

# Push to GitHub
git push origin main
```

### Cloud Shell Deployment
```bash
# Pull latest code
git pull origin main

# Deploy to Cloud Run
./deploy.sh

# Check logs
gcloud run services logs read bot-tiendalasmotos --limit=50
```

---

## 🔗 Repository Structure

```
Bot-TiendaLasMotos/
├── .git/                          # Git repository data
├── .gitignore                     # Files to ignore
├── app/
│   ├── core/
│   │   ├── config_loader.py      ✅ V6.0
│   │   └── ...
│   ├── services/
│   └── routers/
├── scripts/
│   └── init_v6_config.py         ✅ V6.0
├── main.py                        ✅ V6.0 (modified)
├── requirements.txt
├── Dockerfile
├── deploy.sh
├── V6_DEPLOYMENT_GUIDE.md        ✅ V6.0
└── V6_EXECUTIVE_SUMMARY.md       ✅ V6.0
```

---

## ✅ Next Steps

1. **Create GitHub repository** (Option A or B above)
2. **Push your code** to GitHub
3. **Clone in Cloud Shell**
4. **Run init_v6_config.py** in Cloud Shell
5. **Deploy with ./deploy.sh**

---

## 🆘 Troubleshooting

### Error: "remote origin already exists"
```bash
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/Bot-TiendaLasMotos.git
```

### Error: "Permission denied (publickey)"
Use HTTPS instead of SSH:
```bash
git remote set-url origin https://github.com/YOUR_USERNAME/Bot-TiendaLasMotos.git
```

### Error: "Updates were rejected"
```bash
git pull origin main --rebase
git push origin main
```

---

## 📞 Support

If you encounter issues:
1. Check GitHub repository was created successfully
2. Verify your GitHub username in the remote URL
3. Ensure you have push permissions to the repository
4. Check Cloud Shell has internet access to GitHub

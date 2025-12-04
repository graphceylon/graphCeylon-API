# Git Repository Setup Guide

This guide will help you push the GraphCeylon-API project to a new GitHub repository.

## 📋 Prerequisites

- GitHub account
- Git installed and configured locally
- Terminal/PowerShell access

## 🚀 Step-by-Step Guide

### Step 1: Create a New Repository on GitHub

1. Go to [GitHub](https://github.com)
2. Click the **"+"** icon in the top-right corner
3. Select **"New repository"**
4. Configure your repository:
   - **Repository name**: `graphCeylon-API` (or your preferred name)
   - **Description**: `Microservices-based tourism intelligence platform for Sri Lanka`
   - **Visibility**: Choose **Private** (for team development) or **Public**
   - **DO NOT** initialize with README, .gitignore, or license (we already have these)
5. Click **"Create repository"**
6. **Copy the repository URL** (you'll need this in Step 3)

### Step 2: Prepare Your Local Repository

Open PowerShell/Terminal in your project directory (`D:\projects\graphCeylon-API`) and run:

```powershell
# Verify you're in the correct directory
pwd
# Should show: D:\projects\graphCeylon-API

# Check Git status
git status
```

### Step 3: Add All Files to Git

```powershell
# Stage all files
git add .

# Check what will be committed
git status

# You should see all your project files in green
```

### Step 4: Create Your Initial Commit

```powershell
# Create the initial commit
git commit -m "feat: initial project setup with microservices architecture

- Add 4 microservices: Language Service, KG Service, Recommender Service, Orchestrator
- Configure Docker and docker-compose for all services
- Set up uv package manager for dependency management
- Add comprehensive documentation and team onboarding guides
- Configure CI/CD pipeline with GitHub Actions
- Add issue templates and PR templates
- Set up project structure for production deployment"
```

### Step 5: Connect to GitHub Repository

Replace `<YOUR-GITHUB-USERNAME>` and `<REPOSITORY-NAME>` with your actual values:

```powershell
# Add remote repository
git remote add origin https://github.com/<YOUR-GITHUB-USERNAME>/<REPOSITORY-NAME>.git

# Verify remote was added
git remote -v
```

Example:
```powershell
git remote add origin https://github.com/yourusername/graphCeylon-API.git
```

### Step 6: Create and Switch to Main Branch

```powershell
# Rename current branch to main (if needed)
git branch -M main
```

### Step 7: Push to GitHub

```powershell
# Push to GitHub
git push -u origin main
```

**Note**: You may be prompted to authenticate with GitHub. Use one of these methods:
- **Personal Access Token** (recommended)
- **GitHub CLI** (`gh auth login`)
- **SSH Key**

### Step 8: Create Development Branch

```powershell
# Create and push develop branch
git checkout -b develop
git push -u origin develop
```

### Step 9: Set Default Branch (Optional)

On GitHub:
1. Go to your repository
2. Click **"Settings"** → **"Branches"**
3. Set **"develop"** as the default branch
4. This ensures all PRs target `develop` by default

### Step 10: Protect Important Branches (Recommended)

On GitHub:
1. Go to **"Settings"** → **"Branches"**
2. Add branch protection rules for `main` and `develop`:
   - ✅ Require pull request reviews before merging
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - ✅ Include administrators (optional)

## 🎯 Verification Checklist

After completing the steps above, verify:

- [ ] Repository is visible on GitHub
- [ ] All files and folders are present
- [ ] README.md displays correctly
- [ ] Both `main` and `develop` branches exist
- [ ] `.gitignore` is working (no `.venv/`, `__pycache__/`, etc.)
- [ ] GitHub Actions workflows are visible in "Actions" tab

## 👥 Invite Team Members

### For Private Repository:

1. Go to repository **"Settings"** → **"Collaborators"**
2. Click **"Add people"**
3. Enter their GitHub username or email
4. Choose access level:
   - **Write**: Can push to branches, create PRs
   - **Admin**: Full access
5. Send invitation

### Share Repository URL

Send your team the repository URL:
```
https://github.com/<YOUR-USERNAME>/graphCeylon-API
```

## 📧 Message Template for Team

Once your repo is set up, send this to your team:

---

**Subject: GraphCeylon-API Repository is Live! 🚀**

Hi Team,

The project repository is now live on GitHub! 

**Repository URL**: https://github.com/<YOUR-USERNAME>/graphCeylon-API

**Getting Started:**

1. **Accept the invitation** (check your email/GitHub notifications)
2. **Clone the repository**:
   ```bash
   git clone https://github.com/<YOUR-USERNAME>/graphCeylon-API.git
   cd graphCeylon-API
   ```
3. **Read the onboarding guide**: Open `TEAM_ONBOARDING.md` in the repository
4. **Follow the setup instructions** (takes ~5 minutes)
5. **Start coding!**

**Important Documents:**
- 📘 [TEAM_ONBOARDING.md](./TEAM_ONBOARDING.md) - Start here!
- 📖 [README.md](./README.md) - Project overview
- 🤝 [CONTRIBUTING.md](./CONTRIBUTING.md) - How to contribute
- 📦 [docs/uv-guide.md](./docs/uv-guide.md) - Package manager guide

**Your Component Assignments:**
- Language Service (Port 8001): [Names]
- Knowledge Graph (Port 8000): [Names]  
- Recommender Service (Port 8003): [Names]
- Orchestrator (Port 8002): [Names]

**Questions?** Check the docs first, then ask in [team chat]!

Let's build something amazing! 💪

---

## 🔧 Troubleshooting

### Issue: "remote origin already exists"

```powershell
# Remove existing remote and add again
git remote remove origin
git remote add origin https://github.com/<YOUR-USERNAME>/<REPOSITORY-NAME>.git
```

### Issue: Authentication Failed

**Option 1: Use Personal Access Token**
1. Go to GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token (classic) with `repo` scope
3. Use token as password when prompted

**Option 2: Use GitHub CLI**
```powershell
# Install GitHub CLI
winget install --id GitHub.cli

# Login
gh auth login
```

### Issue: Large Files Won't Push

Check if you accidentally included large model files:
```powershell
# See file sizes
git ls-files --stage | awk '$2 > 52428800'

# Remove large files from git
git rm --cached path/to/large/file
git commit -m "chore: remove large file"
```

### Issue: Wrong Files Committed

```powershell
# Remove file from staging but keep locally
git rm --cached path/to/file

# Update .gitignore
echo "path/to/file" >> .gitignore

# Commit the changes
git add .gitignore
git commit -m "chore: update gitignore"
```

## 📚 Useful Git Commands

```powershell
# Check current branch
git branch

# Switch branch
git checkout develop

# See commit history
git log --oneline

# See changes
git diff

# Undo last commit (keep changes)
git reset --soft HEAD~1

# See remote info
git remote -v

# Pull latest changes
git pull origin develop
```

## 🎉 Next Steps

After pushing to GitHub:

1. ✅ Verify repository on GitHub
2. ✅ Invite team members
3. ✅ Set up branch protection rules
4. ✅ Send repository URL to team with TEAM_ONBOARDING.md link
5. ✅ Schedule kickoff meeting
6. ✅ Start first sprint!

## 📞 Need Help?

If you encounter issues:
- Check GitHub's [documentation](https://docs.github.com/)
- Search [Stack Overflow](https://stackoverflow.com/questions/tagged/git)
- Contact your Git-savvy team member

---

**Ready to share with your team? They have everything they need in TEAM_ONBOARDING.md! 🚀**

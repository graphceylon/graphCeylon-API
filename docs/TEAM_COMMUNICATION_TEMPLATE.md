# Team Communication Template

Use this template to notify your team members about the repository.

---

**Subject: GraphCeylon-API Repository Ready - Let's Start Building! 🚀**

Hi Team,

The GraphCeylon-API repository is now set up and ready for development! Here's everything you need to get started:

## 📍 Repository

- **URL**: [Add your GitHub repository URL here]
- **Main Branch**: `main` (production)
- **Development Branch**: `develop` (for active development)

## 🎯 Your Component Assignments

Please confirm which component you'll be working on:

1. **Language Service (Port 8001)** - Multilingual NLP Processing

   - Team Members: [Names]

2. **Knowledge Graph Service (Port 8000)** - Graph & Knowledge Management

   - Team Members: [Names]

3. **Recommender Service (Port 8003)** - AI-Powered Recommendations

   - Team Members: [Names]

4. **Orchestrator (Port 8002)** - API Gateway & Service Coordination
   - Team Members: [Names]

## ⚡ Quick Start (3 Steps)

1. **Read the onboarding guide**: [TEAM_ONBOARDING.md](./TEAM_ONBOARDING.md)
2. **Clone the repo**: `git clone <repo-url>`
3. **Set up your service**: Follow the guide in TEAM_ONBOARDING.md

## 📚 Important Documents

- **[TEAM_ONBOARDING.md](./TEAM_ONBOARDING.md)** - START HERE! Complete setup guide
- **[README.md](./README.md)** - Project overview and architecture
- **[CONTRIBUTING.md](./CONTRIBUTING.md)** - Contribution guidelines
- **[docs/uv-guide.md](./docs/uv-guide.md)** - Package manager guide
- **[PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md)** - Detailed structure

## 🛠️ What You Need to Install

1. **uv** (Package Manager):

   - Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - Linux/macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`

2. **Git**: https://git-scm.com/

3. **Docker** (optional, for running all services): https://www.docker.com/

## 📋 First Week Tasks

**Everyone:**

1. ✅ Complete environment setup (Day 1)
2. ✅ Clone repo and run your service locally (Day 1)
3. ✅ Create your first branch and make a test commit (Day 2)
4. ✅ Add your required dependencies to requirements.txt (Day 2-3)
5. ✅ Implement a basic API endpoint (Day 3-5)
6. ✅ Write a test for your endpoint (Day 5)
7. ✅ Create your first Pull Request (End of Week 1)

## 🤝 Collaboration

**Communication Channels:**

- GitHub Issues: For bugs and feature requests
- Pull Requests: For code reviews
- [Add your team chat/Slack/Discord]: For quick questions
- [Add meeting schedule]: For sync meetings

**Working Hours & Availability:**

- Please update your availability in [location/document]
- Respond to PR reviews within 24 hours when possible

## 🔄 Development Workflow

```
1. Pick a task → 2. Create branch → 3. Code → 4. Test → 5. Commit → 6. Push → 7. PR → 8. Review → 9. Merge
```

**Branch naming:**

- `feature/service-name-feature-description`
- `fix/service-name-bug-description`
- Example: `feature/language-tamil-support`

**Commit messages:**

- `feat(service): description` - New feature
- `fix(service): description` - Bug fix
- Example: `feat(language): add Tamil text processing`

## 📊 Service Ports

- Language Service: 8001
- Knowledge Graph: 8000
- Orchestrator: 8002
- Recommender: 8003

When running locally, access:

- Your service: http://localhost:800X
- API docs: http://localhost:800X/docs
- Health check: http://localhost:800X/health

## 🆘 Need Help?

- **Setup issues**: Check TEAM_ONBOARDING.md troubleshooting section
- **Git questions**: [Add Git expert name]
- **Technical questions**: Create a GitHub issue or ask in [team chat]
- **Urgent**: Contact [project lead name/email]

## 🎓 Learning Resources

**New to FastAPI?** https://fastapi.tiangolo.com/tutorial/
**New to Git?** https://learngitbranching.js.org/
**New to uv?** See docs/uv-guide.md in the repo

## 📅 Important Dates

- **Kickoff Meeting**: [Date/Time]
- **First Sprint Demo**: [Date]
- **Code Freeze**: [Date]
- **Production Launch**: [Target Date]

## ✅ Action Items

Please complete by [DATE]:

1. [ ] Read TEAM_ONBOARDING.md
2. [ ] Install prerequisites (uv, Git)
3. [ ] Clone the repository
4. [ ] Set up your assigned service
5. [ ] Run your service successfully
6. [ ] Confirm your component assignment (reply to this message)
7. [ ] Add yourself to the "Team" section in README.md

## 🎉 Let's Build Something Great!

This is a research project with real-world impact. Your contributions will help revolutionize tourism in Sri Lanka using AI and NLP technologies.

Looking forward to working with you all!

---

**Questions?** Reply to this message or reach out in [team chat channel].

Best regards,
[Your Name]
Project Lead - GraphCeylon-API

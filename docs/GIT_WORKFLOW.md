# Git Workflow Guide

Complete guide for clean GitHub repository management with GraphCeylon-API.

## Table of Contents

- [Branch Management](#branch-management)
- [Commit Message Convention](#commit-message-convention)
- [Pull Request Workflow](#pull-request-workflow)
- [Git Commands Cheatsheet](#git-commands-cheatsheet)
- [Common Scenarios](#common-scenarios)

---

## Branch Management

### Branch Naming Convention

**Format:** `<username>/<type>/<short-description>`

#### Branch Types

| Type       | Purpose                  | Example                            |
| ---------- | ------------------------ | ---------------------------------- |
| `feat`     | New features             | `john/feat/add-search-endpoint`    |
| `fix`      | Bug fixes                | `sarah/fix/memory-leak-kg-service` |
| `docs`     | Documentation only       | `mike/docs/api-documentation`      |
| `refactor` | Code restructuring       | `jane/refactor/optimize-queries`   |
| `test`     | Adding/updating tests    | `alex/test/recommender-unit-tests` |
| `chore`    | Maintenance tasks        | `lisa/chore/update-dependencies`   |
| `perf`     | Performance improvements | `david/perf/cache-implementation`  |
| `style`    | Code style/formatting    | `emma/style/fix-linting-errors`    |

#### Main Branches

```
main (production-ready code)
  ↓
develop (integration branch)
  ↓
feature branches (your work)
```

- **`main`**: Production-ready code. Protected. Deploy from here.
- **`develop`**: Integration branch. All features merge here first. Branch from here for new work.
- **Feature branches**: Individual work branches. Always created from `develop`.

### Creating Branches

#### Step 1: Update your local repository

```bash
git checkout develop
git pull origin develop
```

#### Step 2: Create your branch

```bash
# Format: git checkout -b <username>/<type>/<description>
git checkout -b john/feat/multilingual-search
```

#### Step 3: Push branch to GitHub

```bash
git push -u origin john/feat/multilingual-search
```

### Branch Examples

```bash
# Good branch names ✅
sarah/feat/knowledge-graph-api
mike/fix/orchestrator-timeout
alex/docs/setup-instructions
jane/refactor/database-connections
david/test/integration-tests

# Bad branch names ❌
feature1                    # Not descriptive
john-new-stuff             # No type prefix
fix_bug                    # No username, vague
FEAT/sarah/new-endpoint    # Wrong case (use lowercase)
feat/sarah/new-endpoint    # Wrong order (username should come first)
```

---

## Commit Message Convention

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Structure Breakdown

#### 1. **Type** (Required)

What kind of change this is:

| Type       | Description                | Example                                     |
| ---------- | -------------------------- | ------------------------------------------- |
| `feat`     | New feature                | `feat(kg): add location search endpoint`    |
| `fix`      | Bug fix                    | `fix(orchestrator): handle timeout errors`  |
| `docs`     | Documentation              | `docs(readme): update setup instructions`   |
| `style`    | Formatting, no code change | `style(language): fix indentation`          |
| `refactor` | Code restructuring         | `refactor(recommender): simplify algorithm` |
| `test`     | Adding tests               | `test(kg): add unit tests for queries`      |
| `chore`    | Maintenance                | `chore(deps): update fastapi to 0.104.0`    |
| `perf`     | Performance improvement    | `perf(kg): add caching layer`               |
| `ci`       | CI/CD changes              | `ci(github): add deployment workflow`       |
| `build`    | Build system changes       | `build(docker): optimize image size`        |
| `revert`   | Revert previous commit     | `revert: revert "feat(kg): add search"`     |

#### 2. **Scope** (Optional but Recommended)

Which service/part is affected:

- `kg` - KG Service
- `language` - Language Service
- `orchestrator` - Orchestrator
- `recommender` - Recommender Service
- `docker` - Docker configurations
- `ci` - CI/CD pipeline
- `docs` - Documentation
- `api` - API changes across services

#### 3. **Subject** (Required)

- Use imperative mood: "add" not "added" or "adds"
- Don't capitalize first letter
- No period at the end
- Maximum 50 characters
- Be specific and concise

#### 4. **Body** (Optional)

- Explain **what** and **why**, not **how**
- Wrap at 72 characters
- Separate from subject with blank line

#### 5. **Footer** (Optional)

- Reference issues: `Closes #123`
- Breaking changes: `BREAKING CHANGE: ...`

### Commit Examples

#### Simple commit (most common)

```bash
git commit -m "feat(kg): add place search endpoint"
```

#### Commit with body

```bash
git commit -m "fix(orchestrator): handle service timeout errors

- Add retry logic for service calls
- Implement exponential backoff
- Log timeout events for monitoring

Closes #45"
```

#### Multiple changes (staged separately)

```bash
# Stage and commit related changes together
git add services/kg_service/src/api.py
git commit -m "feat(kg): implement search functionality"

git add services/kg_service/tests/test_api.py
git commit -m "test(kg): add tests for search endpoint"
```

### Real-World Examples

```bash
# Feature commits
feat(language): add Sinhala tokenization
feat(recommender): implement collaborative filtering
feat(orchestrator): add request rate limiting

# Bug fixes
fix(kg): resolve database connection leak
fix(language): handle empty translation input
fix(docker): correct uv installation path

# Documentation
docs(api): add endpoint documentation
docs(readme): update contribution guidelines
docs(setup): add troubleshooting section

# Refactoring
refactor(kg): extract query logic to separate class
refactor(recommender): simplify recommendation algorithm
refactor(orchestrator): improve error handling

# Tests
test(language): add translation unit tests
test(kg): add integration tests for queries
test(recommender): add edge case tests

# Chores
chore(deps): update dependencies
chore(ci): fix linting configuration
chore(docker): optimize image layers

# Performance
perf(kg): add Redis caching for queries
perf(language): optimize translation pipeline
perf(orchestrator): implement connection pooling
```

---

## Pull Request Workflow

### Step-by-Step PR Process

#### 1. **Complete Your Work**

```bash
# Make sure all changes are committed
git status

# Update with latest develop
git checkout develop
git pull origin develop
git checkout feat/john/multilingual-search
git merge develop

# Resolve conflicts if any
# Run tests locally
docker compose up
pytest services/kg_service/tests/
```

#### 2. **Push Your Branch**

```bash
git push origin feat/john/multilingual-search
```

#### 3. **Create Pull Request on GitHub**

**PR Title Format:** Same as commit message

```
feat(language): add multilingual search support
```

**PR Description Template:**

```markdown
## Description

Brief description of what this PR does.

## Changes

- Added multilingual tokenization
- Implemented language detection
- Updated API documentation

## Testing

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] CI/CD pipeline passes

## Related Issues

Closes #123
Related to #456

## Screenshots (if applicable)

[Add screenshots for UI changes]

## Checklist

- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No breaking changes (or documented if present)
```

#### 4. **Code Review Process**

**Reviewer checks:**

- [ ] Code quality and readability
- [ ] Tests are comprehensive
- [ ] No security vulnerabilities
- [ ] Performance considerations
- [ ] Documentation updated

**Author actions:**

- Address review comments
- Make requested changes
- Push updates (will update PR automatically)
- Re-request review

#### 5. **Merge PR**

**Merge Strategy:**

```bash
# Squash and merge (recommended for feature branches)
# - Combines all commits into one
# - Keeps main/develop history clean

# Or merge commit (for complex features)
# - Preserves individual commits
```

#### 6. **After Merge**

```bash
# Delete remote branch (GitHub does this automatically)
# Delete local branch
git checkout develop
git pull origin develop
git branch -d john/feat/multilingual-search
```

---

## Git Commands Cheatsheet

### Daily Workflow

```bash
# Check status
git status

# Stage files
git add <file>                    # Stage specific file
git add .                         # Stage all changes
git add services/kg_service/      # Stage directory

# Commit
git commit -m "feat(kg): add endpoint"
git commit --amend                # Edit last commit

# Push
git push origin <branch-name>
git push -u origin <branch-name>  # First push (set upstream)

# Pull latest changes
git pull origin develop

# Switch branches
git checkout <branch-name>
git checkout -b <username>/<type>/<description>  # Create and switch
```

### Branch Management

```bash
# List branches
git branch                        # Local branches
git branch -r                     # Remote branches
git branch -a                     # All branches

# Create branch
git checkout -b john/feat/new-feature

# Delete branch
git branch -d <branch-name>       # Delete local (safe)
git branch -D <branch-name>       # Force delete local
git push origin --delete <branch> # Delete remote

# Rename branch
git branch -m <old-name> <new-name>
```

### Syncing with Remote

```bash
# Fetch changes without merging
git fetch origin

# Update from develop
git checkout develop
git pull origin develop
git checkout john/feat/my-feature
git merge develop

# Rebase (alternative to merge)
git rebase develop
```

### Undoing Changes

```bash
# Discard changes in working directory
git checkout -- <file>
git restore <file>                # Git 2.23+

# Unstage files
git reset HEAD <file>
git restore --staged <file>       # Git 2.23+

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes)
git reset --hard HEAD~1

# Revert commit (creates new commit)
git revert <commit-hash>
```

### Stashing Changes

```bash
# Save work temporarily
git stash
git stash save "work in progress"

# List stashes
git stash list

# Apply stash
git stash apply                   # Keep stash
git stash pop                     # Apply and remove

# Delete stash
git stash drop stash@{0}
git stash clear                   # Delete all
```

### Viewing History

```bash
# View commit history
git log
git log --oneline                 # Compact view
git log --graph --all             # Visual branch graph
git log -p <file>                 # Changes to specific file

# View changes
git diff                          # Unstaged changes
git diff --staged                 # Staged changes
git diff develop                  # Compare with develop
```

---

## Common Scenarios

### Scenario 1: Starting New Feature

```bash
# 1. Update develop
git checkout develop
git pull origin develop

# 2. Create feature branch
git checkout -b john/feat/user-authentication

# 3. Make changes and commit
git add services/orchestrator/src/auth.py
git commit -m "feat(orchestrator): add JWT authentication"

# 4. Push to GitHub
git push -u origin john/feat/user-authentication

# 5. Create PR on GitHub
```

### Scenario 2: Fixing a Bug

```bash
# 1. Create fix branch from develop
git checkout develop
git pull origin develop
git checkout -b sarah/fix/memory-leak-kg

# 2. Fix the bug and test
git add services/kg_service/src/database.py
git commit -m "fix(kg): resolve database connection leak

- Close connections properly in finally block
- Add connection pooling
- Add unit tests for connection lifecycle

Closes #87"

# 3. Push and create PR
git push -u origin sarah/fix/memory-leak-kg
```

### Scenario 3: Updating from Develop (Conflicts)

```bash
# You're on john/feat/search-feature
git checkout develop
git pull origin develop
git checkout john/feat/search-feature
git merge develop

# If conflicts occur:
# 1. Open conflicted files
# 2. Resolve conflicts (remove <<<<<<, ======, >>>>>> markers)
# 3. Stage resolved files
git add <resolved-files>
git commit -m "merge: resolve conflicts with develop"
git push origin john/feat/search-feature
```

### Scenario 4: Made Commit to Wrong Branch

```bash
# You committed to develop instead of feature branch
git log  # Note the commit hash

# Create new branch with current state
git checkout -b john/feat/correct-branch

# Go back to develop and reset
git checkout develop
git reset --hard origin/develop

# Your commit is now on john/feat/correct-branch
```

### Scenario 5: Need to Update Last Commit

```bash
# Add forgotten files to last commit
git add forgotten-file.py
git commit --amend --no-edit       # Keep same message

# Or change commit message
git commit --amend -m "feat(kg): improved commit message"

# Push (force if already pushed)
git push --force-with-lease origin john/feat/my-feature
```

### Scenario 6: Emergency Hotfix for Production

```bash
# 1. Branch from main (not develop)
git checkout main
git pull origin main
git checkout -b emergency/fix/critical-bug

# 2. Fix and test
git add <files>
git commit -m "fix(orchestrator): resolve critical production bug"

# 3. PR to main (fast-track review)
git push -u origin emergency/fix/critical-bug

# 4. After merge, also merge to develop
git checkout develop
git pull origin develop
git merge main
git push origin develop
```

### Scenario 7: Working on Multiple Features

```bash
# Switch between features using stash
git stash save "WIP: search feature"
git checkout john/feat/other-feature

# Work on other feature...

# Come back to search
git checkout john/feat/search-feature
git stash pop
```

---

## Best Practices

### ✅ Do's

1. **Commit Often**: Small, focused commits are better than large ones
2. **Pull Before Push**: Always update your branch before pushing
3. **Write Clear Messages**: Future you will thank present you
4. **Test Before Commit**: Ensure code works before committing
5. **One Feature Per Branch**: Keep branches focused on single task
6. **Review Your Own Code**: Check diff before creating PR
7. **Keep Branches Short-Lived**: Merge within a few days
8. **Delete Merged Branches**: Clean up after PR is merged

### ❌ Don'ts

1. **Don't Commit Directly to Main**: Always use feature branches
2. **Don't Commit Secrets**: No API keys, passwords, tokens
3. **Don't Commit Generated Files**: Build artifacts, logs, .env
4. **Don't Force Push Shared Branches**: Use `--force-with-lease` if needed
5. **Don't Mix Unrelated Changes**: One concern per commit
6. **Don't Use Vague Messages**: "fix stuff", "update" are not helpful
7. **Don't Skip CI Checks**: Fix failing tests before merging
8. **Don't Leave Broken Code**: Every commit should work

---

## Quick Reference

### Commit Message Template

```bash
git commit -m "feat(scope): add feature description

- Bullet point of what changed
- Another change detail
- Why this change was needed

Closes #123"
```

### Branch Naming Template

```bash
git checkout -b <username>/<type>/<short-description>

# Examples:
john/feat/add-caching
sarah/fix/resolve-timeout
mike/docs/update-readme
```

### PR Checklist

- [ ] Branch name follows convention
- [ ] Commits are clear and focused
- [ ] Tests pass locally
- [ ] Code is self-reviewed
- [ ] Documentation updated
- [ ] No merge conflicts
- [ ] CI/CD pipeline passes

---

## Help and Resources

### Getting Help

```bash
# Git command help
git help <command>
git commit --help

# Check Git version
git --version
```

### Useful Aliases (Optional)

Add to `~/.gitconfig`:

```ini
[alias]
    st = status
    co = checkout
    br = branch
    cm = commit -m
    lg = log --oneline --graph --all
    undo = reset --soft HEAD~1
```

Usage:

```bash
git st           # Instead of git status
git lg           # Pretty log view
```

---

## Questions?

If you're unsure about any Git operation:

1. Check `git status` to see current state
2. Test on a backup branch first
3. Ask team members in Slack/Discord
4. Refer back to this guide

**Remember**: Git is forgiving - most mistakes can be undone! 🚀

<<<<<<< HEAD
# PM-OS

Product Manager Operating System — a Claude Code skill suite that takes a business statement and runs it through a 7-stage product definition pipeline.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/pingmepi/pm-os/main/install.sh | bash
```

## Usage

```bash
# Create a new project
/pm-new <slug> "<business statement>"

# Run stages sequentially
/pm-stage-01-brief
/pm-stage-02-scope
# ... through stage 07

# Approve a stage
/pm-approve 01

# Check project state
/pm-status

# Capture feedback
/pm-feedback 01
```

## Requirements

- Claude Code >= latest
- Python 3.11+
- `PM_OS_USER` environment variable set to your PM identifier
- `PM_OS_FEEDBACK_REPO` environment variable set to the feedback repo URL
=======
# pm-os
>>>>>>> origin/main

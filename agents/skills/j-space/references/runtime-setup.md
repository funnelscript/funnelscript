# Runtime Requirements & Pre-Flight Setup

Before running the optional `jspace.py` state controller or ledger operations, verify that the local Python environment is available.

## Pre-Flight Verification

```bash
# 1. Check Python 3 availability (Python >= 3.8 required)
python3 --version || echo "ERROR: Python 3 not found"

# 2. Check controller script readability and syntax
python3 -m py_compile scripts/jspace.py && echo "J-Space Controller: OK" || echo "ERROR: jspace.py syntax issue"
```

## Workspace State Storage

The `jspace.py` controller stores task-local state in `.jspace/` within the active working directory. This directory is automatically created upon invoking `note` or `seam`.

## Fail-Safe Behaviors

If Python is not available in the execution environment, all J-Space operations (the sixty-second awakening, the gate, the three registers, and invariants) operate fully without filesystem or tool dependencies directly inside the inner reasoning and conversation register.

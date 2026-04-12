# -----------------------------------------------------------
# Sandbox runner — Dockerfile
# -----------------------------------------------------------
# Minimal Python image used to execute untrusted student code
# inside an ephemeral container.  The image contains ONLY the
# standard library; no pip packages are installed.
#
# Security measures applied at build-time:
#   • Non-root user (sandbox, uid 1000)
#   • No package manager cache left on disk
#   • Read-only root filesystem recommended at run-time (--read-only)
# -----------------------------------------------------------
FROM python:3.11-slim AS sandbox

# Remove apt lists to reduce attack surface & image size.
RUN rm -rf /var/lib/apt/lists/*

# Create a non-root user to run student code.
RUN groupadd -r sandbox && useradd -r -g sandbox -d /home/sandbox -s /sbin/nologin sandbox

WORKDIR /home/sandbox

# Copy the runner script that orchestrates execution + test cases.
COPY runner.py /home/sandbox/runner.py

# Ensure the runner script is owned by root and is read-only for the
# sandbox user so the student code cannot tamper with it.
RUN chown root:root /home/sandbox/runner.py && chmod 444 /home/sandbox/runner.py

USER sandbox

# The runner reads JSON from stdin and writes JSON to stdout.
ENTRYPOINT ["python", "-u", "/home/sandbox/runner.py"]

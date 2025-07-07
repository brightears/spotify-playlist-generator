"""Gunicorn configuration file for production deployment."""

# Workers configuration
workers = 2  # Number of worker processes
worker_class = 'sync'  # Use sync workers for simplicity
worker_connections = 1000

# Timeout configuration
timeout = 120  # Increase timeout to 120 seconds (2 minutes) to handle multiple YouTube sources
graceful_timeout = 30  # Grace period for workers to finish serving requests

# Logging
accesslog = '-'  # Log to stdout
errorlog = '-'  # Log to stderr
loglevel = 'info'

# Server mechanics
daemon = False  # Don't daemonize (Render handles process management)
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Server socket
bind = '0.0.0.0:10000'  # Render uses port 10000 by default
backlog = 2048

# Process naming
proc_name = 'brightears'

# Server hooks
def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def worker_abort(worker):
    worker.log.info("Worker received SIGABRT signal")
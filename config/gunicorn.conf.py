import multiprocessing

bind = "0.0.0.0:8080"
workers = 1
worker_class = "eventlet"
threads = 2  # Increase if needed

# Logging configuration
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = "debug"

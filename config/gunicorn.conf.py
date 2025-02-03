import multiprocessing

bind = "0.0.0.0:8080"
workers = 4 # multiprocessing.cpu_count() * 2 + 1
threads = 2

# Logging configuration
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = "debug"  # Log level: debug, info, warning, error, critical

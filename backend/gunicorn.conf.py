import multiprocessing

bind = '0.0.0.0:8000'

workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync" 
max_requests = 100
max_requests_jitter = 10
preload_app = True
timeout = 120
keepalive = 5

# Logging
accesslog = '-'
loglevel = 'info'
capture_output = True
enable_stdio_inheritance = True
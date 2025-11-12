# Increase timeout and worker settings for larger requests
timeout = 120
keepalive = 5
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100

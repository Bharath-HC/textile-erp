import os
workers = 1
threads = 2
timeout = 120
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
worker_class = "sync"
preload_app = True

import os
import django
from aiohttp import web

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blog_api.settings')
django.setup()

# Import socket server after Django is configured
from communications.socket_server import sio

if __name__ == '__main__':
    # Create aiohttp application
    app = web.Application()
    sio.attach(app)
    
    print("Socket.io server running on http://127.0.0.1:8001")
    web.run_app(app, host='127.0.0.1', port=8001) 
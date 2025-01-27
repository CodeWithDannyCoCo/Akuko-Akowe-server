import os
import requests
from django.conf import settings
from datetime import datetime, timedelta

def get_turn_credentials():
    """
    Get TURN server credentials from Metered.ca API using the chronicle subdomain.
    Falls back to default credentials if API call fails.
    """
    if settings.METERED_API_KEY:
        try:
            # Fetch temporary credentials from Metered.ca using chronicle subdomain
            response = requests.get(
                f'https://chronicle.metered.live/api/v1/turn/credentials?apiKey={settings.METERED_API_KEY}'
            )
            response.raise_for_status()
            data = response.json()
            
            # Update the TURN server configuration with temporary credentials
            turn_config = settings.WEBRTC_CONFIG['iceServers'][1].copy()
            turn_config.update({
                'urls': [
                    'turn:chronicle.metered.live:80',
                    'turn:chronicle.metered.live:443',
                    'turn:chronicle.metered.live:443?transport=tcp'
                ],
                'username': data['username'],
                'credential': data['credential']
            })
            return turn_config
        except Exception as e:
            print(f"Error fetching TURN credentials: {e}")
            return settings.WEBRTC_CONFIG['iceServers'][1]
    else:
        # Return default configuration if no API key is set
        return settings.WEBRTC_CONFIG['iceServers'][1] 
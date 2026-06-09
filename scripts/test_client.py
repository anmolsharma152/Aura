#!/usr/bin/env python3
"""
Test client for Aura daemon - simulates PAM module socket communication
"""

import os
import sys
import socket

# Use dev socket
SOCKET_PATH = "/home/anmol/Projects/Aura/run/aura.sock"
AUTH_SUCCESS = b"\x01"
AUTH_FAILURE = b"\x00"

def test_auth(username):
    """Send username to aura daemon and get result"""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(10.0)  # Longer timeout for testing
        sock.connect(SOCKET_PATH)

        # Send username with newline
        sock.sendall(f"{username}\n".encode('utf-8'))

        # Read response
        response = sock.recv(1)
        sock.close()

        if response == AUTH_SUCCESS:
            return True, "SUCCESS"
        elif response == AUTH_FAILURE:
            return False, "FAILURE"
        else:
            return False, f"UNKNOWN: {response}"

    except Exception as e:
        return False, f"ERROR: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_client.py <username>")
        sys.exit(1)

    username = sys.argv[1]
    print(f"Testing authentication for user: {username}")
    success, msg = test_auth(username)
    print(f"Result: {msg}")
    sys.exit(0 if success else 1)
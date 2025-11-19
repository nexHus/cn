import socket
import struct
import msgpack
import threading
from cryptography.fernet import Fernet

# Generate a fixed key for the "university project" simplicity scope
# In real production, you would exchange public keys.
DEFAULT_KEY = b'WnZo5y1XoXFzZ2_gTq3yF6X-Yt4ou9kEz2wV2xY1l8c='
cipher = Fernet(DEFAULT_KEY)

PORT = 5050
HEADER_LENGTH = 4  # 4 bytes for message length
BUFFER_SIZE = 4096
ADDR = ('0.0.0.0', PORT) # Listen on all interfaces
DISCONNECT_MSG = "!DISCONNECT"

# --- PACKET TYPES ---
CMD_LOGIN = "LOGIN"
CMD_MSG = "MSG"
CMD_PRIVATE = "PVT"
CMD_ROOM_JOIN = "JOIN_ROOM"
CMD_FILE = "FILE"
CMD_VIDEO = "VIDEO_FRAME"
CMD_AUDIO = "AUDIO_CHUNK"
CMD_LIST_UPDATE = "LIST"
CMD_ACCEPT_CALL = "ACCEPT_CALL"
CMD_END_CALL = "END_CALL"

def send_packet(sock, cmd_type, data_dict, is_encrypted=True):
    """
    Packs a message:
    1. Payload = msgpack(dictionary)
    2. Encrypted Payload
    3. Header = length(Encrypted Payload)
    4. Send Header + Encrypted Payload
    """
    try:
        # Check if socket is valid
        if sock is None or sock.fileno() == -1:
            return False
            
        payload = {'type': cmd_type, 'data': data_dict}
        packed_payload = msgpack.packb(payload)
        
        final_payload = packed_payload
        if is_encrypted:
             final_payload = cipher.encrypt(packed_payload)
        
        length = len(final_payload)
        # >I means Big-Endian Unsigned Integer (Standard Network Byte Order)
        header = struct.pack('>I', length) 
        
        sock.sendall(header + final_payload)
        return True
    except OSError as e:
        # Socket-specific errors (including WinError 10038)
        if e.errno == 10038:
            print("[PROTOCOL] Socket is not valid (already closed)")
        else:
            print(f"[PROTOCOL SEND ERROR] {e}")
        return False
    except Exception as e:
        print(f"[PROTOCOL SEND ERROR] {e}")
        return False

def receive_packet(sock, is_encrypted=True):
    """
    Reads exact header size, then exact payload size.
    Prevents packet corruption.
    """
    try:
        # Read Header
        header = b''
        while len(header) < HEADER_LENGTH:
            chunk = sock.recv(HEADER_LENGTH - len(header))
            if not chunk: return None
            header += chunk
        
        payload_length = struct.unpack('>I', header)[0]
        
        # Read Body
        payload = b''
        while len(payload) < payload_length:
            to_read = payload_length - len(payload)
            # Cap read size to buffer to prevent RAM spike on large files
            read_size = min(to_read, BUFFER_SIZE)
            chunk = sock.recv(read_size)
            if not chunk: return None
            payload += chunk
            
        if is_encrypted:
            payload = cipher.decrypt(payload)
            
        return msgpack.unpackb(payload, raw=False) # unpack to python dict
    except Exception as e:
        return None
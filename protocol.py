import socket
import struct
import msgpack
import threading
from cryptography.fernet import Fernet

# Default encryption key for Fernet cipher
DEFAULT_KEY = b"WnZo5y1XoXFzZ2_gTq3yF6X-Yt4ou9kEz2wV2xY1l8c="
cipher = Fernet(DEFAULT_KEY)

# Network configuration constants
PORT = 5050
HEADER_LENGTH = 4  # Size of the header containing payload length
BUFFER_SIZE = 4096
ADDR = ("0.0.0.0", PORT)
DISCONNECT_MSG = "!DISCONNECT"

# Command constants for different protocol actions
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
    # Sends a packet to the specified socket.

    # Args:
    #     sock: The socket object to send data to.
    #     cmd_type: The type of command (e.g., CMD_MSG, CMD_LOGIN).
    #     data_dict: A dictionary containing the data payload.
    #     is_encrypted: Boolean flag to determine if payload should be encrypted.

    # Returns:
    #     True if successful, False otherwise.
    try:
        if sock is None or sock.fileno() == -1:
            return False

        # Prepare the payload
        payload = {"type": cmd_type, "data": data_dict}
        packed_payload = msgpack.packb(payload)

        final_payload = packed_payload
        if is_encrypted:
            final_payload = cipher.encrypt(packed_payload)

        # Create header with payload length
        length = len(final_payload)
        header = struct.pack(">I", length)

        # Send header followed by payload
        sock.sendall(header + final_payload)
        return True
    except OSError as e:
        if e.errno == 10038:
            print("[PROTOCOL] Socket is not valid (already closed)")
        else:
            print(f"[PROTOCOL SEND ERROR] {e}")
        return False
    except Exception as e:
        print(f"[PROTOCOL SEND ERROR] {e}")
        return False


def receive_packet(sock, is_encrypted=True):
    
    # Receives a packet from the specified socket.

    # Args:
    #     sock: The socket object to receive data from.
    #     is_encrypted: Boolean flag to indicate if the incoming payload is encrypted.

    # Returns:
    #     The unpacked payload dictionary, or None if an error occurs.
    
    try:
        # Read the header to get payload length
        header = b""
        while len(header) < HEADER_LENGTH:
            chunk = sock.recv(HEADER_LENGTH - len(header))
            if not chunk:
                return None
            header += chunk

        payload_length = struct.unpack(">I", header)[0]

        # Read the payload based on the length
        payload = b""
        while len(payload) < payload_length:
            to_read = payload_length - len(payload)
            read_size = min(to_read, BUFFER_SIZE)
            chunk = sock.recv(read_size)
            if not chunk:
                return None
            payload += chunk

        if is_encrypted:
            payload = cipher.decrypt(payload)

        return msgpack.unpackb(payload, raw=False)
    except Exception as e:
        return None

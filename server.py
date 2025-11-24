import socket
import threading
import protocol


class ChatServer:
    
    # Main server class handling client connections, message routing, and room management.
    

    def __init__(self):
        # Initialize server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(protocol.ADDR)
        self.server_socket.listen()

        # Data structures for managing clients and rooms
        self.clients = {}  # Map socket -> username
        self.username_to_socket = {}  # Map username -> socket
        self.rooms = {"General": {"users": [], "password": None}}

        self.lock = threading.Lock()  # Thread safety lock

        print(f"[SERVER] Running on port {protocol.ADDR[1]}")
        print(f"[SERVER] Local IP Address: {self.get_local_ip()}")
        self.receive()

    def get_local_ip(self):
        # Retrieves the local IP address of the server.
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def broadcast(self, msg_packet, exclude_socket=None, target_room=None):
        # Broadcasts a message to multiple clients.

        # Args:
        #     msg_packet: The message packet to send.
        #     exclude_socket: Socket to exclude from broadcast (e.g., sender).
        #     target_room: Specific room to broadcast to. If None, broadcasts to all.
        with self.lock:
            targets = []
            if target_room:
                room_data = self.rooms.get(target_room)
                if room_data:
                    users = room_data["users"]
                    for user in users:
                        sock = self.username_to_socket.get(user)
                        if sock:
                            targets.append(sock)
            else:
                targets = list(self.clients.keys())

        for client_socket in targets:
            if client_socket != exclude_socket:
                try:
                    if client_socket and client_socket.fileno() != -1:
                        protocol.send_packet(
                            client_socket, msg_packet["type"], msg_packet["data"]
                        )
                except Exception as e:
                    print(f"[BROADCAST ERROR] {e}")

    def handle_private_msg(self, sender, target_user, text):
        # Handles sending a private message between two users.
        target_socket = self.username_to_socket.get(target_user)
        if target_socket:
            data = {"from": sender, "text": text, "is_private": True}
            protocol.send_packet(target_socket, protocol.CMD_MSG, data)
            protocol.send_packet(
                self.username_to_socket[sender], protocol.CMD_MSG, data
            )

    def send_active_list(self):
        # Sends the updated list of active users and rooms to all clients.
        users = list(self.username_to_socket.keys())
        rooms_list = list(self.rooms.keys())

        packet = {"users": users, "rooms": rooms_list}
        self.broadcast({"type": protocol.CMD_LIST_UPDATE, "data": packet})

    def handle_client(self, client_socket):
        
        # Handles the communication loop for a connected client.

        # Args:
        #     client_socket: The socket object for the connected client.
        
        username = ""
        current_room = "General"

        try:
            while True:
                packet = protocol.receive_packet(client_socket)
                if not packet:
                    break

                cmd = packet["type"]
                data = packet["data"]

                if cmd == protocol.CMD_LOGIN:
                    username = data["username"]
                    with self.lock:
                        self.clients[client_socket] = username
                        self.username_to_socket[username] = client_socket
                        self.rooms["General"]["users"].append(username)

                    print(f"[NEW CONN] {username} connected.")
                    self.send_active_list()

                elif cmd == protocol.CMD_MSG:
                    msg_text = data["text"]
                    to_user = data.get("to")

                    if to_user and to_user != "All":
                        self.handle_private_msg(username, to_user, msg_text)
                    else:
                        # Broadcast to room
                        payload = {
                            "from": username,
                            "text": msg_text,
                            "room": current_room,
                        }
                        self.broadcast(
                            {"type": protocol.CMD_MSG, "data": payload},
                            target_room=current_room,
                        )

                elif cmd == protocol.CMD_ROOM_JOIN:
                    new_room = data["room"]
                    password = data.get("password")

                    with self.lock:
                        # Check if room exists
                        if new_room in self.rooms:
                            # Verify password if one is set
                            room_pass = self.rooms[new_room]["password"]
                            if room_pass and room_pass != password:
                                protocol.send_packet(
                                    client_socket,
                                    protocol.CMD_MSG,
                                    {
                                        "from": "System",
                                        "text": f"Incorrect password for {new_room}",
                                    },
                                )
                                continue  # Skip joining
                        else:
                            # Create new room
                            self.rooms[new_room] = {"users": [], "password": password}

                        # Remove from old room
                        old_room_data = self.rooms.get(current_room)
                        if old_room_data and username in old_room_data["users"]:
                            old_room_data["users"].remove(username)

                        # Add to new room
                        self.rooms[new_room]["users"].append(username)
                        current_room = new_room

                    self.send_active_list()
                    # System msg
                    protocol.send_packet(
                        client_socket,
                        protocol.CMD_MSG,
                        {"from": "System", "text": f"Joined {new_room}"},
                    )

                elif cmd == protocol.CMD_FILE:
                    # Route file to room or user
                    target_user = data.get("to")
                    payload = data  # Forward entire file payload
                    payload["from"] = username

                    if target_user:
                        target_sock = self.username_to_socket.get(target_user)
                        if target_sock:
                            protocol.send_packet(
                                target_sock, protocol.CMD_FILE, payload
                            )
                    else:
                        self.broadcast(
                            {"type": protocol.CMD_FILE, "data": payload},
                            exclude_socket=client_socket,
                            target_room=current_room,
                        )

                # MEDIA ROUTING (Audio/Video Frames)
                # Highly efficient routing for "Calling"
                elif cmd in [protocol.CMD_VIDEO, protocol.CMD_AUDIO]:
                    target = data.get("target")
                    if target:
                        target_sock = self.username_to_socket.get(target)
                        if target_sock:
                            try:
                                # Check if target socket is still valid
                                if target_sock.fileno() != -1:
                                    # Forward directly to target
                                    packet_to_send = packet
                                    # Inject Sender
                                    packet_to_send["data"]["sender"] = username
                                    protocol.send_packet(
                                        target_sock,
                                        cmd,
                                        packet_to_send["data"],
                                        is_encrypted=True,
                                    )
                            except Exception as e:
                                print(f"[MEDIA ROUTING ERROR] {e}")

                elif cmd == protocol.CMD_END_CALL:
                    # Forward end call notification
                    target = data.get("target")
                    if target:
                        target_sock = self.username_to_socket.get(target)
                        if target_sock:
                            try:
                                protocol.send_packet(
                                    target_sock, protocol.CMD_END_CALL, {}
                                )
                            except Exception as e:
                                print(f"[END CALL ERROR] {e}")

        except Exception as e:
            print(f"[ERROR] {username}: {e}")
        finally:
            # Cleanup
            with self.lock:
                if client_socket in self.clients:
                    del self.clients[client_socket]
                if username in self.username_to_socket:
                    del self.username_to_socket[username]

                room_data = self.rooms.get(current_room)
                if room_data and username in room_data["users"]:
                    room_data["users"].remove(username)

            client_socket.close()
            self.send_active_list()
            print(f"[DISCONN] {username}")

    def receive(self):
        # Accepts incoming connections and starts a new thread for each client.
        while True:
            client, address = self.server_socket.accept()
            thread = threading.Thread(target=self.handle_client, args=(client,))
            thread.start()


if __name__ == "__main__":
    ChatServer()

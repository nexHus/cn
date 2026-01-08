import tkinter as tk
from tkinter import scrolledtext, simpledialog, filedialog, messagebox
from PIL import Image, ImageTk
import socket
import threading
import os
import time
import io

import protocol
from media_utils import VideoCamera, AudioRecorder, AudioPlayer


class ClientApp: 
    # This is the main class for our application. It handles everything the user sees (the GUI)
    # and everything happening behind the scenes (networking, sending messages, calls).

    def __init__(self, root):
        self.root = root
        self.root.title("PyChat Pro - University Edition")
        self.root.geometry("900x600")

        # Network and user state
        self.client_socket = None
        self.username = ""
        self.is_connected = False
        self.target_user = "All"  # Default to broadcast
        self.send_lock = threading.Lock()
        
        # Chat State
        self.chat_history = {} # {context_id: [message_lines]}
        self.active_chat_id = "General" # Currently displayed chat
        self.my_current_room = "General" # Room I am currently in on server

        # Call state
        self.in_call = False
        self.call_window = None
        self.call_partner = None
        self.last_call_partner = None
        self.last_call_end_time = 0
        self.sending_video = False
        
        # Media State
        self.mic_on = True
        self.camera_on = True

        self.setup_ui()

        self.connect_to_server()

    def setup_ui(self):
        # Initializes the GUI components.
        left_frame = tk.Frame(self.root, width=600)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Chat display area
        self.chat_area = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD)
        self.chat_area.config(state="disabled")
        self.chat_area.pack(fill=tk.BOTH, expand=True)

        # Input area
        input_frame = tk.Frame(left_frame)
        input_frame.pack(fill=tk.X, pady=5)

        self.msg_entry = tk.Entry(input_frame, font=("Arial", 12))
        self.msg_entry.bind("<Return>", self.send_msg)
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        send_btn = tk.Button(
            input_frame, text="Send", command=self.send_msg, bg="#4CAF50", fg="white"
        )
        send_btn.pack(side=tk.LEFT, padx=5)

        # Toolbar for additional actions
        tool_frame = tk.Frame(left_frame)
        tool_frame.pack(fill=tk.X)

        tk.Button(tool_frame, text="Attach File", command=self.send_file).pack(
            side=tk.LEFT
        )
        tk.Button(tool_frame, text="Create Room", command=self.create_room).pack(
            side=tk.LEFT
        )
        tk.Button(tool_frame, text="Leave Room", command=self.leave_room).pack(
            side=tk.LEFT
        )

        tk.Button(
            tool_frame,
            text="Video Call",
            command=lambda: self.start_call("video"),
            bg="#2196F3",
            fg="white",
        ).pack(side=tk.RIGHT, padx=2)
        tk.Button(
            tool_frame,
            text="Voice Call",
            command=lambda: self.start_call("voice"),
            bg="#FF9800",
            fg="white",
        ).pack(side=tk.RIGHT, padx=2)

        # Right sidebar for users and rooms
        right_frame = tk.Frame(self.root, width=200, bg="lightgray")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(right_frame, text="Online Users", bg="lightgray").pack(pady=5)
        self.user_listbox = tk.Listbox(right_frame, height=15)
        self.user_listbox.pack(padx=5, fill=tk.X)
        self.user_listbox.bind("<<ListboxSelect>>", self.select_user)

        tk.Label(right_frame, text="Available Rooms", bg="lightgray").pack(pady=15)
        self.room_listbox = tk.Listbox(right_frame, height=10)
        self.room_listbox.pack(padx=5, fill=tk.X)
        self.room_listbox.bind("<Double-1>", self.join_room)

    def connect_to_server(self):
        # Prompts for server IP and username, then establishes connection.
        host = simpledialog.askstring(
            "Server", "Enter Server IP:", initialvalue="127.0.0.1"
        )
        if not host:
            host = "127.0.0.1"

        self.username = simpledialog.askstring("Login", "Choose Username:")
        if not self.username:
            self.root.quit()

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((host, protocol.PORT))

            with self.send_lock:
                protocol.send_packet(
                    self.client_socket, protocol.CMD_LOGIN, {"username": self.username}
                )

            self.is_connected = True

            # Start listening thread
            threading.Thread(target=self.listen_server, daemon=True).start()
            self.root.title(f"PyChat Pro - Logged in as {self.username}")

        except Exception as e:
            messagebox.showerror("Error", f"Could not connect: {e}")
            self.root.quit()

    def select_user(self, event):
        # Handles user selection from the listbox for private messaging
        selection = self.user_listbox.curselection()
        if selection:
            user = self.user_listbox.get(selection[0])
            if user == self.username:
                messagebox.showinfo("Info", "You cannot message yourself!")
                return
            
            # Switch context to Private Chat with User
            self.target_user = user
            self.active_chat_id = user
            self.refresh_chat_display()
            
            self.msg_entry.config(bg="#ffffcc")  # Yellow tint for private mode
            self.root.title(f"PyChat Pro - {self.username} → Private Chat with {user}")
        else:
            # Switch context back to Room
            self.target_user = "All"
            self.active_chat_id = self.my_current_room
            self.refresh_chat_display()
            
            self.msg_entry.config(bg="white")
            self.root.title(f"PyChat Pro - Logged in as {self.username}")

    def refresh_chat_display(self):
        self.chat_area.config(state="normal")
        self.chat_area.delete(1.0, tk.END)
        
        history = self.chat_history.get(self.active_chat_id, [])
        for line in history:
            # We need to parse the stored line to re-apply tags if needed
            # For simplicity, we store tuples: (text, tag)
            if isinstance(line, tuple):
                text, tag = line
                self.chat_area.insert(tk.END, text, tag)
            else:
                self.chat_area.insert(tk.END, line)
                
        self.chat_area.see(tk.END)
        self.chat_area.config(state="disabled")

    def send_msg(self, event=None):
        # Sends a text message to the selected target (All or Private).
        text = self.msg_entry.get()
        if not text:
            return

        with self.send_lock:
            if self.target_user == "All":
                protocol.send_packet(
                    self.client_socket, protocol.CMD_MSG, {"text": text, "to": "All"}
                )
                # Store in current room history
                self.store_message(self.my_current_room, "text", "Me", text)
            else:
                protocol.send_packet(
                    self.client_socket,
                    protocol.CMD_MSG,
                    {"text": text, "to": self.target_user},
                )
                # Store in private chat history
                self.store_message(self.target_user, "private", "Me", text)

        self.msg_entry.delete(0, tk.END)

    def create_room(self):
        # Prompts user to create a new chat room
        room_name = simpledialog.askstring("Room", "New Room Name:")
        if room_name:
            password = simpledialog.askstring(
                "Password", "Set Room Password (optional):", show="*"
            )
            with self.send_lock:
                protocol.send_packet(
                    self.client_socket,
                    protocol.CMD_ROOM_JOIN,
                    {"room": room_name, "password": password},
                )

    def join_room(self, event):
        # Handles joining an existing room from the listbox.
        selection = self.room_listbox.curselection()
        if selection:
            room = self.room_listbox.get(selection[0])
            password = simpledialog.askstring(
                "Password", f"Enter Password for {room} (if any):", show="*"
            )
            with self.send_lock:
                protocol.send_packet(
                    self.client_socket,
                    protocol.CMD_ROOM_JOIN,
                    {"room": room, "password": password},
                )
            
            # We wait for server confirmation in listen_server to update my_current_room
            # But we can clear the selection to indicate action
            self.room_listbox.selection_clear(0, tk.END)

    def append_message(self, msg_type, sender, content):
        # Legacy method wrapper - now delegates to store_message
        # We need to infer context. 
        # If private, context is sender. If room, context is room.
        # This method is called from listen_server, which has better context.
        pass 

    def store_message(self, context_id, msg_type, sender, content):
        timestamp = time.strftime("%H:%M")
        formatted_line = ""
        tag = None
        
        if msg_type == "text":
            formatted_line = f"[{timestamp}] {sender}: {content}\n"
        elif msg_type == "private":
            formatted_line = f"[{timestamp}] (PVT) {sender}: {content}\n"
            tag = "private"
        elif msg_type == "file":
            formatted_line = f"[{timestamp}] {sender} sent a file: {content}\n"
            tag = "file"
            
        if context_id not in self.chat_history:
            self.chat_history[context_id] = []
            
        entry = (formatted_line, tag) if tag else formatted_line
        self.chat_history[context_id].append(entry)
        
        # If this context is currently active, update UI immediately
        if context_id == self.active_chat_id:
            self.chat_area.config(state="normal")
            if tag:
                self.chat_area.insert(tk.END, formatted_line, tag)
                if tag == "private": self.chat_area.tag_config("private", foreground="red")
                if tag == "file": self.chat_area.tag_config("file", foreground="blue")
            else:
                self.chat_area.insert(tk.END, formatted_line)
            self.chat_area.see(tk.END)
            self.chat_area.config(state="disabled")

    def send_file(self):
        # Opens file dialog and sends selected file.
        filepath = filedialog.askopenfilename()
        if not filepath:
            return

        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)

        with open(filepath, "rb") as f:
            file_bytes = f.read()

        data = {
            "filename": filename,
            "size": file_size,
            "content": file_bytes,
            "to": self.target_user if self.target_user != "All" else None,
        }

        with self.send_lock:
            protocol.send_packet(self.client_socket, protocol.CMD_FILE, data)
        
        context = self.target_user if self.target_user != "All" else self.my_current_room
        self.store_message(context, "text", "Me", f"Sent file: {filename}")

    def save_incoming_file(self, filename, content):
        # Saves received file content to the downloads directory.
        if not os.path.exists("downloads"):
            os.makedirs("downloads")
        save_path = os.path.join("downloads", f"received_{filename}")
        with open(save_path, "wb") as f:
            f.write(content)
        return save_path

    def start_call(self, mode="video"):
        # Initiates a video or voice call with the selected user.
        if self.target_user == "All":
            messagebox.showwarning("Call", "Select a user from the list to call.")
            return

        self.setup_call_window(target=self.target_user, incoming=False, mode=mode)

        if mode == "video":
            self.sending_video = True
            threading.Thread(
                target=self.send_video_stream, args=(self.target_user,), daemon=True
            ).start()

        threading.Thread(
            target=self.send_audio_stream, args=(self.target_user,), daemon=True
        ).start()

    def setup_call_window(self, target, incoming=False, mode="video"):
        # Creates the call window UI.
        if self.call_window:
            # If window exists but we want video and currently don't have it, try to upgrade
            if mode == "video" and not hasattr(self, 'btn_cam'):
                self.ensure_video_ui()
            return

        self.in_call = True
        self.call_partner = target
        self.call_window = tk.Toplevel(self.root)

        call_type = "Video" if mode == "video" else "Voice"
        title = f"{call_type} Call with {target}"
        self.call_window.title(title)
        self.call_window.protocol("WM_DELETE_WINDOW", self.end_call)

        self.call_window.geometry("500x400")

        if mode == "video":
            self.video_label = tk.Label(
                self.call_window, text="Waiting for video...", bg="black", fg="white"
            )
            self.video_label.pack(fill=tk.BOTH, expand=True)
        else:
            self.video_label = tk.Label(
                self.call_window,
                text=f"Voice Call in Progress\n\n{target}",
                bg="#333",
                fg="white",
                font=("Arial", 16),
            )
            self.video_label.pack(fill=tk.BOTH, expand=True)

        end_btn = tk.Button(
            self.call_window,
            text="End Call",
            command=self.end_call,
            bg="#f44336",
            fg="white",
            font=("Arial", 12, "bold"),
        )
        end_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=5, padx=5)
        
        # Control Buttons Frame
        ctrl_frame = tk.Frame(self.call_window, bg="black")
        ctrl_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        
        self.btn_mic = tk.Button(ctrl_frame, text="Mic: ON", command=self.toggle_mic, bg="#4CAF50", fg="white")
        self.btn_mic.pack(side=tk.LEFT, padx=20, expand=True)
        
        if mode == "video":
            self.btn_cam = tk.Button(ctrl_frame, text="Cam: ON", command=self.toggle_camera, bg="#4CAF50", fg="white")
            self.btn_cam.pack(side=tk.RIGHT, padx=20, expand=True)

    def ensure_video_ui(self):
        # Upgrades the call window to include video controls if they are missing
        if not self.in_call:
            return

        if not self.call_window: 
            # Window not ready yet, retry in 100ms
            self.root.after(100, self.ensure_video_ui)
            return
        
        # Check if camera button exists by checking attribute
        if not hasattr(self, 'btn_cam'):
            # Wait for btn_mic to be ready if it's not there yet (race condition)
            if not hasattr(self, 'btn_mic'):
                 self.root.after(100, self.ensure_video_ui)
                 return

            ctrl_frame = self.btn_mic.master
            self.btn_cam = tk.Button(ctrl_frame, text="Cam: ON", command=self.toggle_camera, bg="#4CAF50", fg="white")
            self.btn_cam.pack(side=tk.RIGHT, padx=20, expand=True)
            
            # Also update the label text if it says "Voice Call"
            if hasattr(self, 'video_label'):
                self.video_label.config(text="Video Call Active", font=("Arial", 10))

    def toggle_mic(self):
        self.mic_on = not self.mic_on
        status = "ON" if self.mic_on else "OFF"
        color = "#4CAF50" if self.mic_on else "#f44336"
        if self.call_window:
            self.btn_mic.config(text=f"Mic: {status}", bg=color)

    def toggle_camera(self):
        self.camera_on = not self.camera_on
        status = "ON" if self.camera_on else "OFF"
        color = "#4CAF50" if self.camera_on else "#f44336"
        if self.call_window and hasattr(self, 'btn_cam'):
            self.btn_cam.config(text=f"Cam: {status}", bg=color)

    def end_call(self):
        # Ends the current call and closes the call window.
        if self.call_partner:
            if self.client_socket:
                try:
                    with self.send_lock:
                        protocol.send_packet(
                            self.client_socket,
                            protocol.CMD_END_CALL,
                            {"target": self.call_partner},
                        )
                except:
                    pass

            self.last_call_partner = self.call_partner
            self.last_call_end_time = time.time()

        self.in_call = False
        self.sending_video = False
        if self.call_window:
            try:
                self.call_window.destroy()
            except:
                pass
            self.call_window = None
        self.call_partner = None

    def send_video_stream(self, target):
        # Captures and sends video frames to the call partner
        try:
            camera = VideoCamera()
        except Exception as e:
            print(f"[ERROR] Failed to initialize camera: {e}")
            return

        while self.in_call and self.is_connected:
            try:
                if not self.camera_on:
                    time.sleep(0.1)
                    continue
                    
                frame_bytes = camera.get_frame_bytes()
                if frame_bytes and self.client_socket:
                    data = {"target": target, "frame": frame_bytes}
                    with self.send_lock:
                        if not protocol.send_packet(
                            self.client_socket,
                            protocol.CMD_VIDEO,
                            data,
                            is_encrypted=True,
                        ):
                            print("[VIDEO] Failed to send frame")
                            break
                time.sleep(0.1)
            except Exception as e:
                print(f"[VIDEO ERROR] {e}")
                break
        camera.cleanup()

    def send_audio_stream(self, target):
        # Captures and sends audio chunks to the call partner
        print(f"[AUDIO] Starting audio stream to {target}")
        try:
            mic = AudioRecorder()
            if mic.audio is None:
                print("[WARNING] Audio device not available")
                return
            mic.start()
            if mic.stream is None:
                print("[WARNING] Failed to start audio stream")
                return
        except Exception as e:
            print(f"[ERROR] Failed to initialize microphone: {e}")
            return

        while self.in_call and self.is_connected:
            try:
                if not self.mic_on:
                    time.sleep(0.1)
                    continue

                chunk = mic.get_chunk()
                if chunk and self.client_socket:
                    data = {"target": target, "chunk": chunk}
                    with self.send_lock:
                        if not protocol.send_packet(
                            self.client_socket,
                            protocol.CMD_AUDIO,
                            data,
                            is_encrypted=True,
                        ):
                            print("[AUDIO] Failed to send chunk")
                            break
                else:
                    time.sleep(0.01)
            except Exception as e:
                print(f"[AUDIO ERROR] {e}")
                break
        mic.stop()

    def update_call_video(self, frame_bytes):
        # Updates the video label with the received frame
        if not self.in_call or not self.call_window:
            return
        try:
            image = Image.open(io.BytesIO(frame_bytes))
            photo = ImageTk.PhotoImage(image)
            self.video_label.configure(image=photo, text="")
            self.video_label.image = photo
        except Exception as e:
            print(f"[GUI ERROR] Update video failed: {e}")

    def listen_server(self):
        # Listens for incoming packets from the server and handles them.
        # Runs in a separate thread

        try:
            player = AudioPlayer()
        except Exception as e:
            print(f"[WARNING] Audio player initialization failed: {e}")
            player = None

        while self.is_connected:
            try:
                packet = protocol.receive_packet(self.client_socket)
                if not packet:
                    print("Disconnected from server")
                    self.is_connected = False
                    break
            except OSError as e:
                if e.errno == 10054:
                    print("Connection forcibly closed by server.")
                else:
                    print(f"Socket Error: {e}")
                self.is_connected = False
                break
            except Exception as e:
                print(f"Receive Error: {e}")
                self.is_connected = False
                break

            cmd = packet["type"]
            data = packet["data"]

            if cmd == protocol.CMD_LIST_UPDATE:
                users = data["users"]
                rooms = data["rooms"]

                self.user_listbox.delete(0, tk.END)
                self.user_listbox.insert(tk.END, "All")
                for u in users:
                    self.user_listbox.insert(tk.END, u)

                self.room_listbox.delete(0, tk.END)
                for r in rooms:
                    self.room_listbox.insert(tk.END, r)

            elif cmd == protocol.CMD_MSG:
                sender = data["from"]
                text = data["text"]
                
                # Ignore echo messages (we store them locally for better UX)
                if sender == self.username:
                    continue

                is_pvt = data.get("is_private", False)
                room = data.get("room") # Server sends room for broadcast msgs

                msg_type = "private" if is_pvt else "text"
                
                # Determine context
                if is_pvt:
                    context = sender if sender != "Me" else data.get("to")
                elif room:
                    context = room
                    # If we receive a message for a room, we must be in it (or it's a system msg)
                    if sender == "System" and "Joined" in text:
                        # Update my current room tracking
                        self.my_current_room = room
                        # Auto-switch view to new room
                        self.active_chat_id = room
                        self.target_user = "All"
                        self.root.after(0, self.refresh_chat_display)
                        self.root.after(0, lambda: self.root.title(f"PyChat Pro - {self.username} in {room}"))
                else:
                    context = "General"

                self.store_message(context, msg_type, sender, text)

            elif cmd == protocol.CMD_FILE:
                # We received a file. Save it and tell the user.
                sender = data["from"]
                filename = data["filename"]
                path = self.save_incoming_file(filename, data["content"])
                
                # Context logic similar to MSG
                is_pvt = data.get("to") is not None # If 'to' is set, it was directed
                # Files don't always have 'room' in payload in current server impl, 
                # but broadcast usually implies current room. 
                # For simplicity, if not private, assume current room or General.
                context = sender if is_pvt else self.my_current_room
                
                self.store_message(context, "file", sender, f"{filename} (Saved in downloads/)")

            elif cmd == protocol.CMD_VIDEO:
                # We received a video frame for a call.
                sender = data.get("sender")
                if not self.in_call:
                    # If we aren't in a call yet, this is a new incoming call.
                    if (
                        sender == self.last_call_partner
                        and (time.time() - self.last_call_end_time) < 3.0
                    ):
                        continue

                    self.root.after(
                        0,
                        lambda: self.setup_call_window(
                            target=sender, incoming=True, mode="video"
                        ),
                    )
                    self.in_call = True

                    threading.Thread(
                        target=self.send_audio_stream, args=(sender,), daemon=True
                    ).start()
                else:
                    # We are already in call (maybe started as voice), ensure UI has video controls
                    print("[VIDEO] Upgrading to video UI")
                    self.root.after(0, self.ensure_video_ui)

                if not self.sending_video:
                    self.sending_video = True
                    threading.Thread(
                        target=self.send_video_stream, args=(sender,), daemon=True
                    ).start()

                frame = data["frame"]
                self.root.after(0, lambda: self.update_call_video(frame))

            elif cmd == protocol.CMD_AUDIO:
                # We received audio data. Play it.
                if not self.in_call:
                    sender = data.get("sender")

                    if (
                        sender == self.last_call_partner
                        and (time.time() - self.last_call_end_time) < 3.0
                    ):
                        continue

                    self.root.after(
                        0,
                        lambda: self.setup_call_window(
                            target=sender, incoming=True, mode="voice"
                        ),
                    )
                    self.in_call = True

                    threading.Thread(
                        target=self.send_audio_stream, args=(sender,), daemon=True
                    ).start()

                if player and player.stream:
                    chunk = data["chunk"]
                    player.play(chunk)

            elif cmd == protocol.CMD_END_CALL:
                # The other person hung up.
                self.root.after(0, self.end_call)
                self.root.after(
                    0,
                    lambda: messagebox.showinfo("Call Ended", "Call Ended."),
                )

        if player:
            player.cleanup()
        try:
            if self.client_socket:
                self.client_socket.close()
        except:
            pass
        try:
            self.root.quit()
        except:
            pass

    def leave_room(self):
        # Leaves the current room and returns to the General lobby.
        with self.send_lock:
            protocol.send_packet(
                self.client_socket,
                protocol.CMD_ROOM_JOIN,
                {"room": "General", "password": None},
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = ClientApp(root)
    root.mainloop()

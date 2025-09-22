import sys
import socket
import json
import threading


from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QTextEdit, QListWidget, QComboBox, QRadioButton,
                            QButtonGroup, QProgressBar, QMessageBox, QStackedWidget)
from PyQt5.QtCore import QTimer, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QFont

class MessageReceiver(QObject):
    message_received = pyqtSignal(dict)
    disconnected = pyqtSignal()

class NetworkThread(QThread):
    def __init__(self, socket, receiver):
        super().__init__()
        self.socket = socket
        self.receiver = receiver
        self.running = True
        
    def run(self):
        buffer = ""
        try:
            while self.running:
                data = self.socket.recv(1024).decode('utf-8')
                if not data:
                    break
                    
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            message = json.loads(line.strip())
                            self.receiver.message_received.emit(message)
                        except json.JSONDecodeError:
                            pass
        except:
            pass
        finally:
            self.receiver.disconnected.emit()
            
    def stop(self):
        self.running = False

class QuizClient(QMainWindow):
    def __init__(self):
        super().__init__()
        self.socket = None
        self.nickname = None
        self.current_room = None
        self.network_thread = None
        self.receiver = MessageReceiver()
        self.timer = QTimer()
        self.time_left = 0
        
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        """Setup the main UI"""
        self.setWindowTitle("Quiz Client")
        self.setGeometry(100, 100, 800, 600)
        
        # Apply dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                font-family: Arial;
                font-size: 12px;
            }
            QPushButton {
                background-color: #0084ff;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0066cc;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
            QPushButton#deleteBtn {
                background-color: #f44336;
            }
            QPushButton#deleteBtn:hover {
                background-color: #d32f2f;
            }
            QLineEdit, QTextEdit {
                background-color: #404040;
                border: 1px solid #606060;
                padding: 8px;
                border-radius: 3px;
            }
            QListWidget {
                background-color: #404040;
                border: 1px solid #606060;
                border-radius: 3px;
            }
            QComboBox {
                background-color: #404040;
                border: 1px solid #606060;
                padding: 5px;
                border-radius: 3px;
            }
            QRadioButton {
                padding: 5px;
            }
            QProgressBar {
                border: 1px solid #606060;
                border-radius: 3px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0084ff;
            }
        """)
        
        # Create stacked widget for different screens
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        self.setup_login_screen()
        self.setup_lobby_screen()
        self.setup_room_screen()
        
    def setup_login_screen(self):
        """Setup login screen"""
        login_widget = QWidget()
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Quiz Game Client")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setStyleSheet("margin: 50px; qproperty-alignment: AlignCenter;")
        
        # Server connection
        server_layout = QHBoxLayout()
        server_layout.addWidget(QLabel("Server:"))
        self.server_input = QLineEdit("localhost:8888")
        server_layout.addWidget(self.server_input)
        
        # Nickname input
        nick_layout = QHBoxLayout()
        nick_layout.addWidget(QLabel("Nickname:"))
        self.nickname_input = QLineEdit()
        nick_layout.addWidget(self.nickname_input)
        
        # Connect button
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_to_server)
        
        # Status label
        self.status_label = QLabel("Enter your nickname and click Connect")
        self.status_label.setStyleSheet("color: #888888; margin: 10px;")
        
        layout.addWidget(title)
        layout.addLayout(server_layout)
        layout.addLayout(nick_layout)
        layout.addWidget(self.connect_btn)
        layout.addWidget(self.status_label)
        layout.addStretch()
        
        login_widget.setLayout(layout)
        self.stacked_widget.addWidget(login_widget)
        
    def setup_lobby_screen(self):
        """Setup lobby screen"""
        lobby_widget = QWidget()
        layout = QHBoxLayout()
        
        # Left panel - Room management
        left_panel = QVBoxLayout()
        
        # Available rooms
        rooms_header_layout = QHBoxLayout()
        rooms_header_layout.addWidget(QLabel("Available Rooms (click to select):"))
        
        # Add refresh button
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh_lobby)
        self.refresh_btn.setMaximumWidth(80)
        rooms_header_layout.addWidget(self.refresh_btn)
        
        left_panel.addLayout(rooms_header_layout)
        
        self.rooms_list = QListWidget()
        self.rooms_list.itemClicked.connect(self.on_room_clicked)
        left_panel.addWidget(self.rooms_list)
        
        # Join room by code
        join_layout = QHBoxLayout()
        join_layout.addWidget(QLabel("Room Code:"))
        self.room_code_input = QLineEdit()
        self.join_room_btn = QPushButton("Join")
        self.join_room_btn.clicked.connect(self.join_room)
        join_layout.addWidget(self.room_code_input)
        join_layout.addWidget(self.join_room_btn)
        left_panel.addLayout(join_layout)
        
        # Create room
        create_layout = QHBoxLayout()
        create_layout.addWidget(QLabel("Topic:"))
        self.topic_combo = QComboBox()
        self.create_room_btn = QPushButton("Create Room")
        self.create_room_btn.clicked.connect(self.create_room)
        create_layout.addWidget(self.topic_combo)
        create_layout.addWidget(self.create_room_btn)
        left_panel.addLayout(create_layout)
        
        # Right panel - Chat
        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Lobby Chat:"))
        
        self.lobby_chat = QTextEdit()
        self.lobby_chat.setReadOnly(True)
        right_panel.addWidget(self.lobby_chat)
        
        # Chat input
        chat_layout = QHBoxLayout()
        self.lobby_chat_input = QLineEdit()
        self.lobby_chat_input.returnPressed.connect(self.send_lobby_chat)
        self.send_chat_btn = QPushButton("Send")
        self.send_chat_btn.clicked.connect(self.send_lobby_chat)
        chat_layout.addWidget(self.lobby_chat_input)
        chat_layout.addWidget(self.send_chat_btn)
        right_panel.addLayout(chat_layout)
        
        # Add panels to main layout
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        
        layout.addWidget(left_widget, 1)
        layout.addWidget(right_widget, 1)
        
        lobby_widget.setLayout(layout)
        self.stacked_widget.addWidget(lobby_widget)

    def update_rooms_display(self, rooms):
        """Update the rooms list display"""
        # Clear existing rooms list
        self.rooms_list.clear()
        
        # Add new room items to the list
        for room in rooms:
            # Create display text with status icons
            status_icon = "🟢" if room['status'] == 'Waiting' else "🔴" if room['status'] == 'In Progress' else "⚫"
            item_text = f"{room['code']} - {room['topic']} ({room['players']} players) {status_icon} {room['status']}"
            self.rooms_list.addItem(item_text)
            
    def create_room_item(self, room):
        """Create a visual room item"""
        room_widget = QWidget()
        room_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.1);
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 12px;
                padding: 15px;
                margin: 5px;
            }
            QWidget:hover {
                background-color: rgba(255, 255, 255, 0.15);
                border: 2px solid rgba(255, 255, 255, 0.3);
            }
        """)
        
        layout = QHBoxLayout(room_widget)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # Room info
        info_layout = QVBoxLayout()
        
        # Room code (large)
        code_label = QLabel(room['code'])
        code_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #ffffff;")
        info_layout.addWidget(code_label)
        
        # Topic
        topic_label = QLabel(room['topic'])  
        topic_label.setStyleSheet("font-size: 18px; color: rgba(255, 255, 255, 0.8);")
        info_layout.addWidget(topic_label)
        
        # Players and status
        details_label = QLabel(f"{room['players']} players • {room['status']}")
        details_label.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.6);")
        info_layout.addWidget(details_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # Quick join button
        if room['status'] == 'Waiting':
            join_btn = QPushButton("Join")
            join_btn.setStyleSheet("min-width: 60px; padding: 6px 12px; font-size: 12px;")
            join_btn.clicked.connect(lambda: self.quick_join_room(room['code']))
            layout.addWidget(join_btn)
        
        return room_widget
        
    def quick_join_room(self, room_code):
        """Quick join room from room display"""
        self.send_message({
            "type": "JOIN_ROOM",
            "user": self.nickname,
            "data": {"room_code": room_code}
        })
        
    def show_create_room_dialog(self):
        """Show create room dialog"""
        if not hasattr(self, 'available_topics'):
            QMessageBox.warning(self, "Error", "No topics available!")
            return
            
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Create New Room")
        dialog.setStyleSheet(self.styleSheet())
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Select a topic for your quiz room:"))
        
        topic_combo = QComboBox()
        topic_combo.addItems(self.available_topics)
        layout.addWidget(topic_combo)
        
        buttons_layout = QHBoxLayout()
        create_btn = QPushButton("Create")
        cancel_btn = QPushButton("Cancel") 
        
        create_btn.clicked.connect(lambda: self.create_room_with_topic(topic_combo.currentText(), dialog))
        cancel_btn.clicked.connect(dialog.reject)
        
        buttons_layout.addWidget(create_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)
        
        dialog.setLayout(layout)
        dialog.exec_()
        
    def create_room_with_topic(self, topic, dialog):
        """Create room with selected topic"""
        self.send_message({
            "type": "CREATE_ROOM",
            "user": self.nickname,
            "data": {"topic": topic}
        })
        dialog.accept()
        
    def show_join_room_dialog(self):
        """Show join room dialog"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Join Room")
        dialog.setStyleSheet(self.styleSheet())
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Enter room code:"))
        
        code_input = QLineEdit()
        code_input.setPlaceholderText("Enter 5-digit room code...")
        layout.addWidget(code_input)
        
        buttons_layout = QHBoxLayout()
        join_btn = QPushButton("Join")
        cancel_btn = QPushButton("Cancel")
        
        join_btn.clicked.connect(lambda: self.join_room_with_code(code_input.text().strip(), dialog))
        cancel_btn.clicked.connect(dialog.reject)
        
        buttons_layout.addWidget(join_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)
        
        dialog.setLayout(layout)
        dialog.exec_()
        
    def join_room_with_code(self, room_code, dialog):
        """Join room with entered code"""
        if not room_code:
            QMessageBox.warning(dialog, "Error", "Please enter a room code!")
            return
            
        self.send_message({
            "type": "JOIN_ROOM", 
            "user": self.nickname,
            "data": {"room_code": room_code}
        })
        dialog.accept()
        
    def setup_room_screen(self):
        """Setup quiz room screen"""
        room_widget = QWidget()
        layout = QVBoxLayout()
        
        # Room info
        room_info_layout = QHBoxLayout()
        self.room_info_label = QLabel("Room: ")
        self.room_info_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.leave_room_btn = QPushButton("Leave Room")
        self.leave_room_btn.clicked.connect(self.leave_room)
        room_info_layout.addWidget(self.room_info_label)
        room_info_layout.addStretch()
        room_info_layout.addWidget(self.leave_room_btn)
        layout.addLayout(room_info_layout)
        
        # Players list
        self.players_label = QLabel("Players: ")
        layout.addWidget(self.players_label)
        
        # Quiz area
        self.quiz_area = QWidget()
        quiz_layout = QVBoxLayout()
        
        # Question
        self.question_label = QLabel("Waiting for quiz to start...")
        self.question_label.setFont(QFont("Arial", 16))
        self.question_label.setWordWrap(True)
        self.question_label.setStyleSheet("padding: 20px; background-color: #404040; border-radius: 5px;")
        quiz_layout.addWidget(self.question_label)
        
        # Timer
        self.timer_bar = QProgressBar()
        self.timer_bar.setVisible(False)
        quiz_layout.addWidget(self.timer_bar)
        
        # Answer area
        self.answer_area = QWidget()
        self.answer_layout = QVBoxLayout()
        
        # Multiple choice buttons
        self.mcq_group = QButtonGroup()
        self.mcq_buttons = []
        for i in range(4):
            btn = QRadioButton()
            self.mcq_buttons.append(btn)
            self.mcq_group.addButton(btn)
            self.answer_layout.addWidget(btn)
            btn.setVisible(False)
            
        # Short answer input
        self.short_answer_input = QLineEdit()
        self.short_answer_input.setPlaceholderText("Enter your answer...")
        self.short_answer_input.setVisible(False)
        self.answer_layout.addWidget(self.short_answer_input)
        
        # Submit button
        self.submit_btn = QPushButton("Submit Answer")
        self.submit_btn.clicked.connect(self.submit_answer)
        self.submit_btn.setVisible(False)
        self.answer_layout.addWidget(self.submit_btn)
        
        self.answer_area.setLayout(self.answer_layout)
        quiz_layout.addWidget(self.answer_area)
        
        # Start quiz button
        self.start_quiz_btn = QPushButton("Start Quiz")
        self.start_quiz_btn.clicked.connect(self.start_quiz)
        quiz_layout.addWidget(self.start_quiz_btn)
        
        self.quiz_area.setLayout(quiz_layout)
        layout.addWidget(self.quiz_area)
        
        # Room chat
        layout.addWidget(QLabel("Room Chat:"))
        self.room_chat = QTextEdit()
        self.room_chat.setReadOnly(True)
        self.room_chat.setMaximumHeight(150)
        layout.addWidget(self.room_chat)
        
        # Room chat input
        room_chat_layout = QHBoxLayout()
        self.room_chat_input = QLineEdit()
        self.room_chat_input.returnPressed.connect(self.send_room_chat)
        self.send_room_chat_btn = QPushButton("Send")
        self.send_room_chat_btn.clicked.connect(self.send_room_chat)
        room_chat_layout.addWidget(self.room_chat_input)
        room_chat_layout.addWidget(self.send_room_chat_btn)
        layout.addLayout(room_chat_layout)
        
        room_widget.setLayout(layout)
        self.stacked_widget.addWidget(room_widget)
        
    def setup_connections(self):
        """Setup signal connections"""
        self.receiver.message_received.connect(self.handle_message)
        self.receiver.disconnected.connect(self.handle_disconnect)
        self.timer.timeout.connect(self.update_timer)
        
    def connect_to_server(self):
        """Connect to the quiz server"""
        server_addr = self.server_input.text().split(':')
        if len(server_addr) != 2:
            self.status_label.setText("Invalid server address format")
            return
            
        host, port = server_addr[0], int(server_addr[1])
        nickname = self.nickname_input.text().strip()
        
        if not nickname:
            self.status_label.setText("Please enter a nickname")
            return
            
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.nickname = nickname
            
            # Start network thread
            self.network_thread = NetworkThread(self.socket, self.receiver)
            self.network_thread.start()
            
            # Join lobby
            self.send_message({
                "type": "JOIN_LOBBY",
                "user": self.nickname,
                "data": {}
            })
            
            self.status_label.setText("Connected! Joining lobby...")
            
        except Exception as e:
            self.status_label.setText(f"Connection failed: {e}")
            
    def send_message(self, message):
        """Send message to server"""
        if self.socket:
            try:
                json_msg = json.dumps(message) + '\n'
                self.socket.send(json_msg.encode('utf-8'))
            except:
                pass
                
    def handle_message(self, message):
        """Handle incoming messages from server"""
        msg_type = message.get("type")
        data = message.get("data", {})
        user = message.get("user")
        
        if msg_type == "LOBBY_INFO":
            self.stacked_widget.setCurrentIndex(1)  # Switch to lobby screen
            
            # Update rooms list
            self.rooms_list.clear()
            for room in data.get("rooms", []):
                item_text = f"{room['code']} - {room['topic']} ({room['players']} players) [{room['status']}]"
                self.rooms_list.addItem(item_text)
                
            # Update topics combo
            self.topic_combo.clear()
            self.topic_combo.addItems(data.get("topics", []))
            
        elif msg_type == "ROOM_CREATED":
            room_code = data.get("room_code")
            topic = data.get("topic")
            self.lobby_chat.append(f"<b>System:</b> Room {room_code} created for {topic}")
            # Automatically join the room we just created
            self.room_code_input.setText(room_code)
            self.join_room()
            
        elif msg_type == "CREATE_ERROR":
            error_msg = data.get("message", "Failed to create room")
            QMessageBox.warning(self, "Create Room Error", error_msg)
            
        elif msg_type == "ROOM_JOINED":
            # We successfully joined a room
            self.current_room = message.get("room_code")
            topic = data.get("topic", "Unknown")
            players = data.get("players", [])
            
            self.stacked_widget.setCurrentIndex(2)  # Switch to room screen
            self.room_info_label.setText(f"Room: {self.current_room} - Topic: {topic}")
            self.players_label.setText(f"Players: {', '.join(players)}")
            self.room_chat.append(f"<b>System:</b> Joined room {self.current_room}")
            
        elif msg_type == "JOIN_ERROR":
            # Failed to join room
            error_msg = data.get("message", "Failed to join room")
            QMessageBox.warning(self, "Join Room Error", error_msg)
            
        elif msg_type == "USER_JOINED":
            if message.get("room_code") == self.current_room:
                players = data.get("players", [])
                self.players_label.setText(f"Players: {', '.join(players)}")
                if data.get('user') != self.nickname:
                    self.room_chat.append(f"<b>System:</b> {data.get('user')} joined the room")
                    
        elif msg_type == "USER_LEFT":
            if message.get("room_code") == self.current_room:
                players = data.get("players", [])
                self.players_label.setText(f"Players: {', '.join(players)}")
                self.room_chat.append(f"<b>System:</b> {data.get('user')} left the room")
                
        elif msg_type == "LOBBY_CHAT":
            self.lobby_chat.append(f"<b>{user}:</b> {data.get('message', '')}")
            
        elif msg_type == "ROOM_CHAT":
            self.room_chat.append(f"<b>{user}:</b> {data.get('message', '')}")
            
        elif msg_type == "QUESTION":
            self.display_question(data)
            
        elif msg_type == "SCORE_UPDATE":
            self.handle_score_update(data)
            
        elif msg_type == "LEADERBOARD":
            self.display_leaderboard(data)
            
        elif msg_type == "SERVER_SHUTDOWN":
            # Handle server shutdown
            QMessageBox.critical(self, "Server Shutdown", "Server is shutting down. You will be disconnected.")
            self.stacked_widget.setCurrentIndex(0)  # Return to login screen
            
        elif msg_type == "ROOM_DELETED":
            # Room was deleted, return to lobby
            QMessageBox.information(self, "Room Deleted", data.get("message", "Room was deleted"))
            
        elif msg_type == "KICKED":
            # Player was kicked by admin
            QMessageBox.warning(self, "Kicked", data.get("message", "You have been kicked from the server"))
            self.stacked_widget.setCurrentIndex(0)  # Return to login screen
            
        elif msg_type == "ADMIN_MESSAGE":
            # Message from server admin
            admin_msg = data.get("message", "")
            QMessageBox.information(self, "Message from Admin", admin_msg)
            
        elif msg_type == "QUIZ_END":
            self.display_final_results(data)
            
    def display_question(self, data):
        """Display a quiz question"""
        question_text = f"Question {data['question_num']}/{data['total_questions']}: {data['question']}"
        self.question_label.setText(question_text)
        
        # Hide start button
        self.start_quiz_btn.setVisible(False)
        
        # Setup answer interface based on question type
        if data['type'] == 'mcq':
            # Show multiple choice buttons
            options = data.get('options', [])
            for i, btn in enumerate(self.mcq_buttons):
                if i < len(options):
                    btn.setText(options[i])
                    btn.setVisible(True)
                    btn.setChecked(False)
                else:
                    btn.setVisible(False)
            self.short_answer_input.setVisible(False)
        else:
            # Show short answer input
            for btn in self.mcq_buttons:
                btn.setVisible(False)
            self.short_answer_input.setVisible(True)
            self.short_answer_input.clear()
            self.short_answer_input.setFocus()
            
        self.submit_btn.setVisible(True)
        self.submit_btn.setEnabled(True)
        
        # Start timer
        self.time_left = data.get('time_limit', 30)
        self.timer_bar.setVisible(True)
        self.timer_bar.setMaximum(self.time_left)
        self.timer_bar.setValue(self.time_left)
        self.timer.start(1000)  # Update every second
        
    def update_timer(self):
        """Update countdown timer"""
        self.time_left -= 1
        self.timer_bar.setValue(self.time_left)
        
        if self.time_left <= 0:
            self.timer.stop()
            self.submit_btn.setEnabled(False)
            
    def submit_answer(self):
        """Submit answer to server"""
        answer = ""
        
        # Get answer based on question type
        if any(btn.isVisible() for btn in self.mcq_buttons):
            # Multiple choice
            for btn in self.mcq_buttons:
                if btn.isChecked():
                    answer = btn.text()
                    break
        else:
            # Short answer
            answer = self.short_answer_input.text().strip()
            
        if not answer:
            QMessageBox.warning(self, "Warning", "Please provide an answer!")
            return
            
        self.send_message({
            "type": "ANSWER",
            "room_code": self.current_room,
            "user": self.nickname,
            "data": {"answer": answer}
        })
        
        self.submit_btn.setEnabled(False)
        self.timer.stop()
        
    def handle_score_update(self, data):
        """Handle score update after answering"""
        correct = data.get('correct', False)
        points = data.get('points', 0)
        correct_answer = data.get('correct_answer', '')
        
        if correct:
            msg = f"Correct! +{points} points"
            color = "green"
        else:
            msg = f"Incorrect. Correct answer: {correct_answer}"
            color = "red"
            
        # Show result temporarily
        result_label = QLabel(msg)
        result_label.setStyleSheet(f"color: {color}; font-weight: bold; padding: 10px;")
        self.answer_layout.addWidget(result_label)
        
        # Remove after 3 seconds
        QTimer.singleShot(3000, lambda: result_label.deleteLater())
        
    def display_leaderboard(self, data):
        """Display current leaderboard"""
        scores = data.get('scores', [])
        is_final = data.get('is_final', False)
        
        leaderboard_text = "LEADERBOARD:\n"
        for i, (player, score) in enumerate(scores, 1):
            leaderboard_text += f"{i}. {player}: {score} points\n"
            
        # Show leaderboard in a message box
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Leaderboard" if not is_final else "Final Results")
        msg_box.setText(leaderboard_text)
        msg_box.setStyleSheet(self.styleSheet())
        
        if not is_final:
            QTimer.singleShot(3000, msg_box.close)
            
        msg_box.exec_()
        
    def display_final_results(self, data):
        """Display final quiz results"""
        final_scores = data.get('final_scores', [])
        
        result_text = "QUIZ COMPLETED!\n\nFinal Results:\n"
        for i, (player, score) in enumerate(final_scores, 1):
            result_text += f"{i}. {player}: {score} points\n"
            
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Quiz Complete")
        msg_box.setText(result_text)
        msg_box.setStyleSheet(self.styleSheet())
        msg_box.exec_()
        
        # Reset UI
        self.question_label.setText("Quiz completed! You can chat or leave the room.")
        self.timer_bar.setVisible(False)
        for btn in self.mcq_buttons:
            btn.setVisible(False)
        self.short_answer_input.setVisible(False)
        self.submit_btn.setVisible(False)
        
    def refresh_lobby(self):
        """Refresh lobby data (rooms and topics)"""
        if self.socket and self.nickname:
            self.send_message({
                "type": "JOIN_LOBBY",
                "user": self.nickname,
                "data": {}
            })
            print("Refreshing lobby data...")  # Debug
        
    def on_room_clicked(self, item):
        """Handle room list item click"""
        room_text = item.text()
        # Extract room code from the text (format: "12345 - Topic (X players) [Status]")
        room_code = room_text.split(' - ')[0].strip()
        
        # Set the room code in the input field
        self.room_code_input.setText(room_code)
        
        # Optional: Show which room was selected
        self.rooms_list.setCurrentItem(item)
        
    def join_room(self):
        """Join a room by code"""
        room_code = self.room_code_input.text().strip()
        if not room_code:
            QMessageBox.warning(self, "Error", "Please enter a room code!")
            return
            
        print(f"Attempting to join room: {room_code}")  # Debug
        
        self.send_message({
            "type": "JOIN_ROOM",
            "user": self.nickname,
            "data": {"room_code": room_code}
        })
        
    def create_room(self):
        """Create a new room"""
        topic = self.topic_combo.currentText()
        if not topic:
            return
            
        self.send_message({
            "type": "CREATE_ROOM",
            "user": self.nickname,
            "data": {"topic": topic}
        })
        
    def delete_room(self):
        """Delete the current room"""
        reply = QMessageBox.question(self, 'Delete Room', 
                                   'Are you sure you want to delete this room? This will kick out all players.',
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.send_message({
                "type": "DELETE_ROOM",
                "room_code": self.current_room,
                "user": self.nickname,
                "data": {}
            })

    def start_quiz(self):
        """Start the quiz in current room"""
        self.send_message({
            "type": "START_QUIZ",
            "room_code": self.current_room,
            "user": self.nickname,
            "data": {}
        })
        
    def leave_room(self):
        """Leave current room and return to lobby"""
        self.send_message({
            "type": "LEAVE_ROOM",
            "room_code": self.current_room,
            "user": self.nickname,
            "data": {}
        })
        
        self.current_room = None
        
        # Reset room UI
        self.question_label.setText("Waiting for quiz to start...")
        self.timer_bar.setVisible(False)
        self.start_quiz_btn.setVisible(True)
        for btn in self.mcq_buttons:
            btn.setVisible(False)
        self.short_answer_input.setVisible(False)
        self.submit_btn.setVisible(False)
        self.room_chat.clear()
        
    def send_lobby_chat(self):
        """Send message to lobby chat"""
        message = self.lobby_chat_input.text().strip()
        if not message:
            return
            
        self.send_message({
            "type": "LOBBY_CHAT",
            "user": self.nickname,
            "data": {"message": message}
        })
        
        self.lobby_chat.append(f"<b>{self.nickname}:</b> {message}")
        self.lobby_chat_input.clear()
        
    def send_room_chat(self):
        """Send message to room chat"""
        message = self.room_chat_input.text().strip()
        if not message:
            return
            
        self.send_message({
            "type": "ROOM_CHAT",
            "room_code": self.current_room,
            "user": self.nickname,
            "data": {"message": message}
        })
        
        self.room_chat.append(f"<b>{self.nickname}:</b> {message}")
        self.room_chat_input.clear()
        
    def handle_disconnect(self):
        """Handle server disconnection"""
        QMessageBox.critical(self, "Disconnected", "Connection to server lost!")
        self.stacked_widget.setCurrentIndex(0)  # Return to login screen
        
    def closeEvent(self, event):
        """Handle application close"""
        if self.network_thread:
            self.network_thread.stop()
            self.network_thread.wait()
        if self.socket:
            self.socket.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    client = QuizClient()
    client.show()
    sys.exit(app.exec_())
import sys
import socket
import threading
import json
import time
from typing import Dict, List, Any, Optional
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QTextEdit, QTabWidget, QTableWidget,
                            QTableWidgetItem, QMessageBox, QGroupBox,
                            QHeaderView, QAbstractItemView)
from PyQt5.QtCore import QTimer, pyqtSignal, QObject, QThread, Qt
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

class ServerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.socket = None
        self.network_thread = None
        self.receiver = MessageReceiver()
        self.update_timer = QTimer()
        self.clients_data = []
        self.rooms_data = []
        self.client_count = 0
        self.room_count = 0
        
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        self.setWindowTitle("Quiz Server Admin Panel")
        self.setGeometry(200, 200, 1000, 700)
        
        # Apply dark theme (unchanged)
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
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #0066cc;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
            QPushButton#dangerBtn {
                background-color: #f44336;
            }
            QPushButton#dangerBtn:hover {
                background-color: #d32f2f;
            }
            QPushButton#successBtn {
                background-color: #4CAF50;
            }
            QPushButton#successBtn:hover {
                background-color: #45a049;
            }
            QLineEdit, QTextEdit {
                background-color: #404040;
                border: 1px solid #606060;
                padding: 8px;
                border-radius: 3px;
            }
            QTableWidget {
                background-color: #404040;
                border: 1px solid #606060;
                border-radius: 3px;
                gridline-color: #606060;
            }
            QTabWidget::pane {
                border: 1px solid #606060;
                background-color: #404040;
            }
            QTabBar::tab {
                background-color: #555555;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #0084ff;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #606060;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QHeaderView::section {
                background-color: #555555;
                color: #ffffff;
                padding: 4px;
                border: 1px solid #606060;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Connection section
        status_group = QGroupBox("Connection Status")
        status_layout = QVBoxLayout()
        
        # Server settings
        settings_layout = QHBoxLayout()
        settings_layout.addWidget(QLabel("Server:"))
        self.server_input = QLineEdit("localhost:8888")  # Replace with your cloud server IP
        settings_layout.addWidget(self.server_input)
        
        # Connect/Disconnect buttons
        controls_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("successBtn")
        self.connect_btn.clicked.connect(self.connect_to_server)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setObjectName("dangerBtn")
        self.disconnect_btn.clicked.connect(self.disconnect_from_server)
        self.disconnect_btn.setEnabled(False)
        
        controls_layout.addLayout(settings_layout)
        controls_layout.addStretch()
        controls_layout.addWidget(self.connect_btn)
        controls_layout.addWidget(self.disconnect_btn)
        
        status_layout.addLayout(controls_layout)
        
        # Status info
        self.status_label = QLabel("Status: Disconnected")
        self.status_label.setFont(QFont("Arial", 14, QFont.Bold))
        status_layout.addWidget(self.status_label)
        
        self.info_label = QLabel("Clients: 0 | Rooms: 0")
        status_layout.addWidget(self.info_label)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Tabs for admin functions
        self.tab_widget = QTabWidget()
        
        self.setup_clients_tab()
        self.setup_rooms_tab()
        self.setup_log_tab()
        
        layout.addWidget(self.tab_widget)
        
    def setup_clients_tab(self):
        clients_widget = QWidget()
        layout = QVBoxLayout()
        
        self.clients_table = QTableWidget()
        self.clients_table.setColumnCount(4)
        self.clients_table.setHorizontalHeaderLabels(["Nickname", "Address", "Room", "Status"])
        self.clients_table.horizontalHeader().setStretchLastSection(True)
        self.clients_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        layout.addWidget(QLabel("Connected Clients:"))
        layout.addWidget(self.clients_table)
        
        client_actions_layout = QHBoxLayout()
        
        self.kick_client_btn = QPushButton("Kick Selected Client")
        self.kick_client_btn.setObjectName("dangerBtn")
        self.kick_client_btn.clicked.connect(self.kick_client)
        self.kick_client_btn.setEnabled(False)
        
        self.message_client_btn = QPushButton("Send Message to Client")
        self.message_client_btn.clicked.connect(self.message_client)
        self.message_client_btn.setEnabled(False)
        
        client_actions_layout.addWidget(self.kick_client_btn)
        client_actions_layout.addWidget(self.message_client_btn)
        client_actions_layout.addStretch()
        
        layout.addLayout(client_actions_layout)
        
        clients_widget.setLayout(layout)
        self.tab_widget.addTab(clients_widget, "Clients")
        
        self.clients_table.itemSelectionChanged.connect(self.on_client_selection_changed)
        
    def setup_rooms_tab(self):
        rooms_widget = QWidget()
        layout = QVBoxLayout()
        
        self.rooms_table = QTableWidget()
        self.rooms_table.setColumnCount(5)
        self.rooms_table.setHorizontalHeaderLabels(["Room Code", "Topic", "Players", "Status", "Progress"])
        self.rooms_table.horizontalHeader().setStretchLastSection(True)
        self.rooms_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        layout.addWidget(QLabel("Active Quiz Rooms:"))
        layout.addWidget(self.rooms_table)
        
        room_actions_layout = QHBoxLayout()
        
        self.delete_room_btn = QPushButton("Delete Selected Room")
        self.delete_room_btn.setObjectName("dangerBtn")
        self.delete_room_btn.clicked.connect(self.delete_room)
        self.delete_room_btn.setEnabled(False)
        
        self.force_start_btn = QPushButton("Force Start Quiz")
        self.force_start_btn.clicked.connect(self.force_start_quiz)
        self.force_start_btn.setEnabled(False)
        
        self.broadcast_btn = QPushButton("Broadcast to Room")
        self.broadcast_btn.clicked.connect(self.broadcast_to_room)
        self.broadcast_btn.setEnabled(False)
        
        room_actions_layout.addWidget(self.delete_room_btn)
        room_actions_layout.addWidget(self.force_start_btn)
        room_actions_layout.addWidget(self.broadcast_btn)
        room_actions_layout.addStretch()
        
        layout.addLayout(room_actions_layout)
        
        rooms_widget.setLayout(layout)
        self.tab_widget.addTab(rooms_widget, "Rooms")
        
        self.rooms_table.itemSelectionChanged.connect(self.on_room_selection_changed)
        
    def setup_log_tab(self):
        log_widget = QWidget()
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Server Log:"))
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        log_actions_layout = QHBoxLayout()
        
        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self.clear_log)
        
        self.save_log_btn = QPushButton("Save Log")
        self.save_log_btn.clicked.connect(self.save_log)
        
        log_actions_layout.addWidget(self.clear_log_btn)
        log_actions_layout.addWidget(self.save_log_btn)
        log_actions_layout.addStretch()
        
        layout.addLayout(log_actions_layout)
        
        log_widget.setLayout(layout)
        self.tab_widget.addTab(log_widget, "Server Log")
        
    def setup_connections(self):
        self.receiver.message_received.connect(self.handle_message)
        self.receiver.disconnected.connect(self.handle_disconnect)
        
    def connect_to_server(self):
        server_addr = self.server_input.text().split(':')
        if len(server_addr) != 2:
            self.log_message("Invalid server address format")
            return
            
        host, port = server_addr[0], int(server_addr[1])
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            
            self.network_thread = NetworkThread(self.socket, self.receiver)
            self.network_thread.start()
            
            self.send_message({
                "type": "ADMIN_LOGIN",
                "user": "ADMIN",
                "data": {}
            })
            
            self.status_label.setText(f"Status: Connecting to {host}:{port}...")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.server_input.setEnabled(False)
            
        except Exception as e:
            self.log_message(f"Connection failed: {e}")
            self.status_label.setText("Status: Disconnected")
            
    def disconnect_from_server(self):
        if self.network_thread:
            self.network_thread.stop()
            self.network_thread.wait()
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.socket = None
        self.network_thread = None
        self.clients_data = []
        self.rooms_data = []
        self.client_count = 0
        self.room_count = 0
        self.update_display()
        self.status_label.setText("Status: Disconnected")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.server_input.setEnabled(True)
        self.log_message("Disconnected from server")
        
    def send_message(self, message):
        if self.socket:
            try:
                json_msg = json.dumps(message) + '\n'
                self.socket.send(json_msg.encode('utf-8'))
            except:
                self.handle_disconnect()
                
    def handle_message(self, message):
        msg_type = message.get("type")
        data = message.get("data", {})
        
        if msg_type == "ADMIN_LOGIN_SUCCESS":
            self.status_label.setText(f"Status: Connected as Admin")
            self.log_message("Admin login successful")
            
        elif msg_type == "ADMIN_LOGIN_ERROR":
            self.log_message(f"Admin login failed: {data.get('message')}")
            self.disconnect_from_server()
            QMessageBox.critical(self, "Error", data.get("message"))
            
        elif msg_type == "ADMIN_UPDATE":
            self.clients_data = data.get("clients", [])
            self.rooms_data = data.get("rooms", [])
            self.client_count = data.get("client_count", 0)
            self.room_count = data.get("room_count", 0)
            self.update_display()
            
        elif msg_type == "ADMIN_ERROR":
            self.log_message(f"Admin command error: {data.get('message')}")
            QMessageBox.warning(self, "Error", data.get("message"))
            
        elif msg_type == "SERVER_SHUTDOWN":
            self.log_message("Server is shutting down")
            QMessageBox.critical(self, "Server Shutdown", data.get("message"))
            self.disconnect_from_server()
            
    def handle_disconnect(self):
        self.disconnect_from_server()
        QMessageBox.critical(self, "Disconnected", "Connection to server lost")
        
    def update_display(self):
        self.info_label.setText(f"Clients: {self.client_count} | Rooms: {self.room_count}")
        self.update_clients_table()
        self.update_rooms_table()
        
    def update_clients_table(self):
        self.clients_table.setRowCount(len(self.clients_data))
        for i, client in enumerate(self.clients_data):
            self.clients_table.setItem(i, 0, QTableWidgetItem(client["nickname"]))
            self.clients_table.setItem(i, 1, QTableWidgetItem(client["address"]))
            self.clients_table.setItem(i, 2, QTableWidgetItem(client["room"]))
            self.clients_table.setItem(i, 3, QTableWidgetItem(client["status"]))
            
    def update_rooms_table(self):
        self.rooms_table.setRowCount(len(self.rooms_data))
        for i, room in enumerate(self.rooms_data):
            self.rooms_table.setItem(i, 0, QTableWidgetItem(room["code"]))
            self.rooms_table.setItem(i, 1, QTableWidgetItem(room["topic"]))
            self.rooms_table.setItem(i, 2, QTableWidgetItem(str(room["players"])))
            self.rooms_table.setItem(i, 3, QTableWidgetItem(room["status"]))
            self.rooms_table.setItem(i, 4, QTableWidgetItem(room["progress"]))
            
    def on_client_selection_changed(self):
        has_selection = len(self.clients_table.selectedItems()) > 0
        self.kick_client_btn.setEnabled(has_selection and self.socket is not None)
        self.message_client_btn.setEnabled(has_selection and self.socket is not None)
        
    def on_room_selection_changed(self):
        has_selection = len(self.rooms_table.selectedItems()) > 0
        self.delete_room_btn.setEnabled(has_selection and self.socket is not None)
        self.force_start_btn.setEnabled(has_selection and self.socket is not None)
        self.broadcast_btn.setEnabled(has_selection and self.socket is not None)
        
    def kick_client(self):
        selected_row = self.clients_table.currentRow()
        if selected_row < 0:
            return
        nickname = self.clients_data[selected_row]["nickname"]
        reply = QMessageBox.question(self, 'Kick Client', 
                                   f'Are you sure you want to kick {nickname}?',
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.send_message({
                "type": "ADMIN_KICK",
                "user": "ADMIN",
                "data": {"nickname": nickname}
            })
            self.log_message(f"Kick command sent for client: {nickname}")
            
    def message_client(self):
        selected_row = self.clients_table.currentRow()
        if selected_row < 0:
            return
        nickname = self.clients_data[selected_row]["nickname"]
        from PyQt5.QtWidgets import QInputDialog
        message, ok = QInputDialog.getText(self, f'Message to {nickname}', 
                                         'Enter message:')
        if ok and message.strip():
            self.send_message({
                "type": "ADMIN_MESSAGE",
                "user": "ADMIN",
                "data": {"nickname": nickname, "message": message.strip()}
            })
            self.log_message(f"Sent message to {nickname}: {message}")
            
    def delete_room(self):
        selected_row = self.rooms_table.currentRow()
        if selected_row < 0:
            return
        room_code = self.rooms_data[selected_row]["code"]
        reply = QMessageBox.question(self, 'Delete Room', 
                                   f'Are you sure you want to delete room {room_code}? This will kick out all {self.rooms_data[selected_row]["players"]} players.',
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.send_message({
                "type": "ADMIN_DELETE_ROOM",
                "user": "ADMIN",
                "data": {"room_code": room_code}
            })
            self.log_message(f"Delete room command sent for room: {room_code}")
            
    def force_start_quiz(self):
        selected_row = self.rooms_table.currentRow()
        if selected_row < 0:
            return
        room_code = self.rooms_data[selected_row]["code"]
        self.send_message({
            "type": "ADMIN_FORCE_START",
            "user": "ADMIN",
            "data": {"room_code": room_code}
        })
        self.log_message(f"Force start quiz command sent for room: {room_code}")
            
    def broadcast_to_room(self):
        selected_row = self.rooms_table.currentRow()
        if selected_row < 0:
            return
        room_code = self.rooms_data[selected_row]["code"]
        from PyQt5.QtWidgets import QInputDialog
        message, ok = QInputDialog.getText(self, f'Broadcast to Room {room_code}', 
                                         'Enter message:')
        if ok and message.strip():
            self.send_message({
                "type": "ADMIN_BROADCAST",
                "user": "ADMIN",
                "data": {"room_code": room_code, "message": message.strip()}
            })
            self.log_message(f"Broadcasted to room {room_code}: {message}")
            
    def log_message(self, message):
        timestamp = time.strftime("[%H:%M:%S] ")
        self.log_text.append(timestamp + message)
        
    def clear_log(self):
        self.log_text.clear()
        
    def save_log(self):
        from PyQt5.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Log", f"server_log_{time.strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                QMessageBox.information(self, "Success", f"Log saved to {filename}")
                self.log_message(f"Log saved to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save log: {e}")
                
    def closeEvent(self, event):
        self.disconnect_from_server()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Quiz Server Admin")
    app.setApplicationVersion("1.0")
    server_gui = ServerGUI()
    server_gui.show()
    sys.exit(app.exec_())
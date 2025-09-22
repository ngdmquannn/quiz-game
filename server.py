import socket
import threading
import json
import time
import random
import os
import signal
import sys
from typing import Dict, List, Any, Optional

class QuizRoom:
    def __init__(self, code: str, topic: str, questions: List[Dict]):
        self.code = code
        self.topic = topic
        self.questions = questions
        self.clients = []
        self.status = "Waiting"
        self.current_question_index = 0
        self.scores = {}
        self.question_start_time = None
        self.answers_received = {}
        
    def add_client(self, client):
        self.clients.append(client)
        self.scores[client.nickname] = 0
        
    def remove_client(self, client):
        if client in self.clients:
            self.clients.remove(client)
        if client.nickname in self.scores:
            del self.scores[client.nickname]
            
    def start_quiz(self):
        self.status = "In Progress"
        self.current_question_index = 0
        self.send_next_question()
        
    def send_next_question(self):
        if self.current_question_index >= len(self.questions):
            self.end_quiz()
            return
            
        question = self.questions[self.current_question_index]
        self.question_start_time = time.time()
        self.answers_received = {}
        
        message = {
            "type": "QUESTION",
            "room_code": self.code,
            "user": "SERVER",
            "data": {
                "question_num": self.current_question_index + 1,
                "total_questions": len(self.questions),
                "question": question["question"],
                "type": question["type"],
                "options": question.get("options", []),
                "time_limit": 30
            }
        }
        
        for client in self.clients:
            client.send_message(message)
            
        self.question_timer = threading.Timer(35.0, self.force_next_question)
        self.question_timer.start()
            
    def force_next_question(self):
        if hasattr(self, 'question_timer'):
            try:
                self.question_timer.cancel()
            except:
                pass
                
        for client in self.clients:
            if client.nickname not in self.answers_received:
                self.answers_received[client.nickname] = {
                    "answer": "No Answer",
                    "correct": False,
                    "points": 0
                }
                
                score_message = {
                    "type": "SCORE_UPDATE",
                    "room_code": self.code,
                    "user": "SERVER",
                    "data": {
                        "correct": False,
                        "points": 0,
                        "correct_answer": self.questions[self.current_question_index]["answer"]
                    }
                }
                client.send_message(score_message)
        
        self.send_leaderboard_and_next()
            
    def process_answer(self, client, answer):
        if client.nickname in self.answers_received:
            return
            
        question = self.questions[self.current_question_index]
        correct_answer = question["answer"]
        
        is_correct = False
        if question["type"] == "mcq":
            is_correct = answer.lower() == correct_answer.lower()
        else:
            is_correct = answer.lower().strip() == correct_answer.lower().strip()
            
        time_taken = time.time() - self.question_start_time
        max_time = 30
        speed_bonus = max(0, (max_time - time_taken) / max_time * 500)
        
        points = 0
        if is_correct:
            points = 1000 + int(speed_bonus)
            
        self.scores[client.nickname] += points
        self.answers_received[client.nickname] = {
            "answer": answer,
            "correct": is_correct,
            "points": points
        }
        
        score_message = {
            "type": "SCORE_UPDATE",
            "room_code": self.code,
            "user": "SERVER",
            "data": {
                "correct": is_correct,
                "points": points,
                "correct_answer": correct_answer
            }
        }
        client.send_message(score_message)
        
        if len(self.answers_received) >= len(self.clients):
            if hasattr(self, 'question_timer'):
                try:
                    self.question_timer.cancel()
                except:
                    pass
            threading.Timer(3.0, self.send_leaderboard_and_next).start()
            
    def send_leaderboard_and_next(self):
        sorted_scores = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
        leaderboard_message = {
            "type": "LEADERBOARD",
            "room_code": self.code,
            "user": "SERVER",
            "data": {
                "scores": sorted_scores,
                "is_final": False
            }
        }
        
        for client in self.clients:
            client.send_message(leaderboard_message)
            
        threading.Timer(3.0, self.next_question).start()
        
    def next_question(self):
        self.current_question_index += 1
        self.send_next_question()
        
    def end_quiz(self):
        self.status = "Finished"
        sorted_scores = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
        
        final_message = {
            "type": "QUIZ_END",
            "room_code": self.code,
            "user": "SERVER",
            "data": {
                "final_scores": sorted_scores
            }
        }
        
        for client in self.clients:
            client.send_message(final_message)

class Client:
    def __init__(self, socket, address):
        self.socket = socket
        self.address = address
        self.nickname = None
        self.current_room = None
        self.is_admin = False
        
    def send_message(self, message):
        try:
            json_msg = json.dumps(message) + '\n'
            self.socket.send(json_msg.encode('utf-8'))
        except:
            pass
            
    def receive_message(self):
        try:
            buffer = ""
            while True:
                data = self.socket.recv(1024).decode('utf-8')
                if not data:
                    break
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        return json.loads(line.strip())
        except:
            return None

class QuizServer:
    def __init__(self, host='127.0.0.1', port=8888):
        self.host = host
        self.port = port
        self.clients = []
        self.rooms = {}
        self.quiz_data = {}
        self.running = False
        self.server_socket = None
        self.admin_client = None
        self.load_quiz_data()
        
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def check_quiz_files(self):
        print("\n" + "="*60)
        print("QUIZ FILES DIAGNOSTIC")
        print("="*60)
        expected_files = [
            'questions_linux.json',
            'questions_networking.json', 
            'questions_python.json',
            'questions_security.json'
        ]
        for file in expected_files:
            if os.path.exists(file):
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        print(f"✓ {file} - {len(data)} questions")
                except Exception as e:
                    print(f"✗ {file} - ERROR: {e}")
            else:
                print(f"✗ {file} - NOT FOUND")
        all_files = [f for f in os.listdir('.') if f.startswith('questions_') and f.endswith('.json')]
        other_files = [f for f in all_files if f not in expected_files]
        if other_files:
            print(f"\nOther quiz files found:")
            for file in other_files:
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        print(f"✓ {file} - {len(data)} questions")
                except Exception as e:
                    print(f"✗ {file} - ERROR: {e}")
        print("="*60)
        
    def load_quiz_data(self):
        print("=" * 50)
        print("LOADING QUIZ QUESTIONS")
        print("=" * 50)
        current_dir = os.getcwd()
        print(f"Current directory: {current_dir}")
        all_files = os.listdir('.')
        print(f"All files in directory: {all_files}")
        quiz_files = [f for f in all_files if f.startswith('questions_') and f.endswith('.json')]
        print(f"Found quiz files: {quiz_files}")
        self.quiz_data.clear()
        for file in quiz_files:
            topic = file.replace('questions_', '').replace('.json', '').title()
            print(f"\nProcessing file: {file} -> Topic: {topic}")
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    questions = json.load(f)
                    valid_questions = []
                    for i, q in enumerate(questions):
                        if 'type' in q and 'question' in q and 'answer' in q:
                            if q['type'] == 'mcq' and 'options' in q:
                                valid_questions.append(q)
                            elif q['type'] == 'short':
                                valid_questions.append(q)
                            else:
                                print(f"  ✗ Question {i+1} has invalid format")
                        else:
                            print(f"  ✗ Question {i+1} missing required fields")
                    if valid_questions:
                        self.quiz_data[topic] = valid_questions
                        print(f"  ✓ Loaded {len(valid_questions)} questions for {topic}")
                    else:
                        print(f"  ✗ No valid questions found in {file}")
            except FileNotFoundError:
                print(f"  ✗ File not found: {file}")
            except json.JSONDecodeError as e:
                print(f"  ✗ Invalid JSON in {file}: {e}")
            except Exception as e:
                print(f"  ✗ Error loading {file}: {e}")
        if 'Security' not in self.quiz_data:
            self.quiz_data['Security'] = [
                {"type": "mcq", "question": "What does SSL stand for?", "options": ["Secure Socket Layer", "System Security Layer", "Safe Socket Link", "Secure System Layer"], "answer": "Secure Socket Layer"},
                {"type": "short", "question": "What port does SSH use by default?", "answer": "22"},
                {"type": "mcq", "question": "Which encryption is symmetric?", "options": ["RSA", "AES", "DSA", "ECC"], "answer": "AES"}
            ]
            print("  ✓ Added default Security questions")
        print("=" * 50)
        print(f"FINAL RESULT: {len(self.quiz_data)} topics loaded")
        print(f"Available topics: {list(self.quiz_data.keys())}")
        print("=" * 50)
        if not self.quiz_data:
            print("❌ WARNING: No quiz questions loaded!")
            print("   Make sure you have questions_*.json files in the same directory as the server.")
            print("   Current directory:", os.getcwd())
        return len(self.quiz_data)
    
    def signal_handler(self, signum, frame):
        print(f"\nReceived signal {signum}. Shutting down server...")
        self.shutdown_server()
        
    def shutdown_server(self):
        print("=== SERVER SHUTDOWN INITIATED ===")
        self.running = False
        shutdown_message = {
            "type": "SERVER_SHUTDOWN",
            "user": "SERVER",
            "data": {"message": "Server is shutting down"}
        }
        print(f"Notifying {len(self.clients)} clients...")
        for client in self.clients[:]:
            try:
                client.send_message(shutdown_message)
                client.socket.close()
            except:
                pass
        print("Clearing server data...")
        self.clients.clear()
        self.rooms.clear()
        self.admin_client = None
        if self.server_socket:
            try:
                self.server_socket.close()
                print("Server socket closed")
            except:
                pass
        print("=== SERVER SHUTDOWN COMPLETE ===")
        print("All data cleared. Server stopped.")
        os._exit(0)
                
    def generate_room_code(self):
        while True:
            code = str(random.randint(10000, 99999))
            if code not in self.rooms:
                return code
                
    def send_admin_update(self):
        if self.admin_client and self.admin_client in self.clients:
            clients_data = [
                {
                    "nickname": client.nickname or "Not set",
                    "address": f"{client.address[0]}:{client.address[1]}",
                    "room": client.current_room or "Lobby",
                    "status": "In Room" if client.current_room else "In Lobby"
                }
                for client in self.clients if not client.is_admin
            ]
            rooms_data = [
                {
                    "code": code,
                    "topic": room.topic,
                    "players": len(room.clients),
                    "status": room.status,
                    "progress": f"{room.current_question_index + 1}/{len(room.questions)}" if room.status == "In Progress" else "N/A"
                }
                for code, room in self.rooms.items()
            ]
            update_message = {
                "type": "ADMIN_UPDATE",
                "user": "SERVER",
                "data": {
                    "clients": clients_data,
                    "rooms": rooms_data,
                    "client_count": len(self.clients) - (1 if self.admin_client else 0),
                    "room_count": len(self.rooms)
                }
            }
            self.admin_client.send_message(update_message)
            
    def start_server(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            print(f"Quiz Server started on {self.host}:{self.port}")
            print(f"Available topics: {list(self.quiz_data.keys())}")
            print("\n=== SERVER MONITOR ===")
            print("Commands:")
            print("  Ctrl+C or 'shutdown' - Gracefully stop the server")
            print("  'rooms' - List active rooms")
            print("  'clients' - List connected clients")
            print()
            
            threading.Thread(target=self.monitor_display, daemon=True).start()
            threading.Thread(target=self.command_input, daemon=True).start()
            threading.Thread(target=self.admin_update_thread, daemon=True).start()
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    client = Client(client_socket, address)
                    self.clients.append(client)
                    threading.Thread(target=self.handle_client, args=(client,), daemon=True).start()
                except socket.error:
                    break
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received...")
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.shutdown_server()
            
    def admin_update_thread(self):
        while self.running:
            self.send_admin_update()
            time.sleep(2)
            
    def command_input(self):
        while self.running:
            try:
                cmd = input().strip().lower()
                if cmd in ['shutdown', 'exit', 'quit']:
                    self.shutdown_server()
                    break
                elif cmd == 'rooms':
                    print(f"\n=== ACTIVE ROOMS ({len(self.rooms)}) ===")
                    if self.rooms:
                        for code, room in self.rooms.items():
                            print(f"Room {code}: {room.topic} - {len(room.clients)} players - {room.status}")
                    else:
                        print("No active rooms")
                    print()
                elif cmd == 'clients':
                    print(f"\n=== CONNECTED CLIENTS ({len(self.clients)}) ===")
                    for i, client in enumerate(self.clients, 1):
                        room_info = f" (Room: {client.current_room})" if client.current_room else " (Lobby)"
                        print(f"{i}. {client.nickname or 'Anonymous'}{room_info}")
                    print()
                elif cmd == 'help':
                    print("\nAvailable commands:")
                    print("  shutdown - Stop the server")
                    print("  rooms - List active rooms")  
                    print("  clients - List connected clients")
                    print("  reload - Reload quiz question files")
                    print("  topics - Show available topics")
                    print("  check - Run quiz files diagnostic")
                    print("  help - Show this help")
                    print()
                elif cmd == 'reload':
                    print("Reloading quiz question files...")
                    count = self.load_quiz_data()
                    print(f"Reload complete. {count} topics loaded.")
                elif cmd == 'topics':
                    print(f"\nAvailable topics ({len(self.quiz_data)}):")
                    for topic, questions in self.quiz_data.items():
                        print(f"  - {topic}: {len(questions)} questions")
                    print()
                elif cmd == 'check':
                    self.check_quiz_files()
            except EOFError:
                break
            except Exception:
                pass
            
    def handle_client(self, client):
        try:
            while self.running:
                message = client.receive_message()
                if not message:
                    break
                self.process_message(client, message)
        except Exception as e:
            print(f"Error handling client {client.address}: {e}")
        finally:
            self.disconnect_client(client)
            
    def process_message(self, client, message):
        msg_type = message.get("type")
        user = message.get("user")
        data = message.get("data", {})
        
        print(f"Processing message from {user}: {msg_type}")
        
        if msg_type == "ADMIN_LOGIN":
            if self.admin_client is None and user == "ADMIN":
                client.is_admin = True
                client.nickname = user
                self.admin_client = client
                response = {
                    "type": "ADMIN_LOGIN_SUCCESS",
                    "user": "SERVER",
                    "data": {"message": "Admin login successful"}
                }
                client.send_message(response)
                print(f"Admin client connected: {client.address}")
                self.send_admin_update()
            else:
                response = {
                    "type": "ADMIN_LOGIN_ERROR",
                    "user": "SERVER",
                    "data": {"message": "Admin login failed: Admin already connected or invalid credentials"}
                }
                client.send_message(response)
                self.disconnect_client(client)
                
        elif msg_type == "ADMIN_KICK":
            if client.is_admin:
                nickname = data.get("nickname")
                target_client = next((c for c in self.clients if c.nickname == nickname and not c.is_admin), None)
                if target_client:
                    kick_message = {
                        "type": "KICKED",
                        "user": "ADMIN",
                        "data": {"message": "You have been kicked by server admin"}
                    }
                    target_client.send_message(kick_message)
                    self.disconnect_client(target_client)
                    self.send_admin_update()
                else:
                    client.send_message({
                        "type": "ADMIN_ERROR",
                        "user": "SERVER",
                        "data": {"message": f"Client {nickname} not found"}
                    })
                    
        elif msg_type == "ADMIN_DELETE_ROOM":
            if client.is_admin:
                room_code = data.get("room_code")
                room = self.rooms.get(room_code)
                if room:
                    delete_message = {
                        "type": "ROOM_DELETED",
                        "room_code": room_code,
                        "user": "ADMIN",
                        "data": {"message": f"Room {room_code} was deleted by server admin"}
                    }
                    for c in room.clients[:]:
                        c.send_message(delete_message)
                        c.current_room = None
                        room_list = [
                            {"code": code, "topic": r.topic, "players": len(r.clients), "status": r.status}
                            for code, r in self.rooms.items() if code != room_code
                        ]
                        lobby_response = {
                            "type": "LOBBY_INFO",
                            "user": "SERVER",
                            "data": {
                                "rooms": room_list,
                                "topics": list(self.quiz_data.keys())
                            }
                        }
                        c.send_message(lobby_response)
                    del self.rooms[room_code]
                    self.send_admin_update()
                else:
                    client.send_message({
                        "type": "ADMIN_ERROR",
                        "user": "SERVER",
                        "data": {"message": f"Room {room_code} not found"}
                    })
                    
        elif msg_type == "ADMIN_BROADCAST":
            if client.is_admin:
                room_code = data.get("room_code")
                message_text = data.get("message")
                room = self.rooms.get(room_code)
                if room:
                    broadcast_message = {
                        "type": "ROOM_CHAT",
                        "room_code": room_code,
                        "user": "ADMIN",
                        "data": {"message": message_text}
                    }
                    for c in room.clients:
                        c.send_message(broadcast_message)
                else:
                    client.send_message({
                        "type": "ADMIN_ERROR",
                        "user": "SERVER",
                        "data": {"message": f"Room {room_code} not found"}
                    })
                    
        elif msg_type == "ADMIN_MESSAGE":
            if client.is_admin:
                nickname = data.get("nickname")
                message_text = data.get("message")
                target_client = next((c for c in self.clients if c.nickname == nickname and not c.is_admin), None)
                if target_client:
                    admin_message = {
                        "type": "ADMIN_MESSAGE",
                        "user": "ADMIN",
                        "data": {"message": message_text}
                    }
                    target_client.send_message(admin_message)
                else:
                    client.send_message({
                        "type": "ADMIN_ERROR",
                        "user": "SERVER",
                        "data": {"message": f"Client {nickname} not found"}
                    })
                    
        elif msg_type == "ADMIN_FORCE_START":
            if client.is_admin:
                room_code = data.get("room_code")
                room = self.rooms.get(room_code)
                if room and room.status == "Waiting" and len(room.clients) > 0:
                    room.start_quiz()
                    self.send_admin_update()
                else:
                    client.send_message({
                        "type": "ADMIN_ERROR",
                        "user": "SERVER",
                        "data": {"message": f"Cannot start quiz in room {room_code}: Invalid status or no players"}
                    })
             #CLIENT MESSAGES      
        elif msg_type == "JOIN_LOBBY" and not client.is_admin:
            client.nickname = user
            client.current_room = None
            current_topics = len(self.quiz_data)
            new_topics = self.load_quiz_data()
            if new_topics != current_topics:
                print(f"Quiz topics updated: {list(self.quiz_data.keys())}")
            room_list = [
                {"code": code, "topic": room.topic, "players": len(room.clients), "status": room.status}
                for code, room in self.rooms.items()
            ]
            response = {
                "type": "LOBBY_INFO",
                "user": "SERVER",
                "data": {
                    "rooms": room_list,
                    "topics": list(self.quiz_data.keys())
                }
            }
            client.send_message(response)
            self.send_admin_update()
            
        elif msg_type == "LOBBY_CHAT" and not client.is_admin:
            for c in self.clients:
                if c.current_room is None and c != client and not c.is_admin:
                    c.send_message(message)
                    
        elif msg_type == "CREATE_ROOM" and not client.is_admin:
            topic = data.get("topic")
            if topic in self.quiz_data:
                room_code = self.generate_room_code()
                questions = self.quiz_data[topic].copy()
                random.shuffle(questions)
                room = QuizRoom(room_code, topic, questions)
                self.rooms[room_code] = room
                print(f"Room {room_code} created for topic {topic} by {client.nickname}")
                response = {
                    "type": "ROOM_CREATED",
                    "user": "SERVER",
                    "data": {"room_code": room_code, "topic": topic}
                }
                client.send_message(response)
                self.send_admin_update()
            else:
                error_msg = {
                    "type": "CREATE_ERROR",
                    "user": "SERVER",
                    "data": {"message": f"Topic '{topic}' is not available"}
                }
                client.send_message(error_msg)
                
        elif msg_type == "JOIN_ROOM" and not client.is_admin:
            room_code = data.get("room_code")
            if room_code in self.rooms:
                room = self.rooms[room_code]
                if room.status == "Waiting":
                    if client.current_room:
                        current_room = self.rooms.get(client.current_room)
                        if current_room:
                            current_room.remove_client(client)
                    room.add_client(client)
                    client.current_room = room_code
                    room_info = {
                        "type": "ROOM_JOINED",
                        "room_code": room_code,
                        "user": "SERVER",
                        "data": {
                            "topic": room.topic,
                            "players": [c.nickname for c in room.clients],
                            "status": room.status
                        }
                    }
                    client.send_message(room_info)
                    room_message = {
                        "type": "USER_JOINED",
                        "room_code": room_code,
                        "user": "SERVER",
                        "data": {
                            "user": client.nickname,
                            "players": [c.nickname for c in room.clients]
                        }
                    }
                    for c in room.clients:
                        c.send_message(room_message)
                    self.send_admin_update()
                else:
                    error_msg = {
                        "type": "JOIN_ERROR",
                        "user": "SERVER",
                        "data": {"message": f"Room {room_code} is {room.status.lower()} and cannot be joined"}
                    }
                    client.send_message(error_msg)
            else:
                error_msg = {
                    "type": "JOIN_ERROR",
                    "user": "SERVER",
                    "data": {"message": f"Room {room_code} does not exist"}
                }
                client.send_message(error_msg)
                        
        elif msg_type == "START_QUIZ" and not client.is_admin:
            if client.current_room:
                room = self.rooms[client.current_room]
                if room.status == "Waiting" and len(room.clients) > 0:
                    room.start_quiz()
                    self.send_admin_update()
                    
        elif msg_type == "ANSWER" and not client.is_admin:
            if client.current_room:
                room = self.rooms[client.current_room]
                if room.status == "In Progress":
                    answer = data.get("answer")
                    room.process_answer(client, answer)
                    self.send_admin_update()
                    
        elif msg_type == "LEAVE_ROOM" and not client.is_admin:
            if client.current_room:
                room = self.rooms.get(client.current_room)
                if room:
                    room.remove_client(client)
                    if room.clients:
                        leave_message = {
                            "type": "USER_LEFT",
                            "room_code": room.code,
                            "user": "SERVER",
                            "data": {
                                "user": client.nickname,
                                "players": [c.nickname for c in room.clients]
                            }
                        }
                        for c in room.clients:
                            c.send_message(leave_message)
                    if len(room.clients) <= 1 and room.status != "In Progress":
                        print(f"Room {room.code} deleted (insufficient players)")
                        del self.rooms[room.code]
                client.current_room = None
                room_list = [
                    {"code": code, "topic": room.topic, "players": len(room.clients), "status": room.status}
                    for code, room in self.rooms.items()
                ]
                response = {
                    "type": "LOBBY_INFO",
                    "user": "SERVER",
                    "data": {
                        "rooms": room_list,
                        "topics": list(self.quiz_data.keys())
                    }
                }
                client.send_message(response)
                self.send_admin_update()
                
        elif msg_type == "DELETE_ROOM" and not client.is_admin:
            if client.current_room:
                room = self.rooms.get(client.current_room)
                if room and room.status == "Waiting":
                    delete_message = {
                        "type": "ROOM_DELETED",
                        "room_code": room.code,
                        "user": "SERVER",
                        "data": {"message": f"Room {room.code} was deleted by {client.nickname}"}
                    }
                    for c in room.clients[:]:
                        c.send_message(delete_message)
                        c.current_room = None
                        room_list = [
                            {"code": code, "topic": r.topic, "players": len(r.clients), "status": r.status}
                            for code, r in self.rooms.items() if code != room.code
                        ]
                        lobby_response = {
                            "type": "LOBBY_INFO",
                            "user": "SERVER",
                            "data": {
                                "rooms": room_list,
                                "topics": list(self.quiz_data.keys())
                            }
                        }
                        c.send_message(lobby_response)
                    del self.rooms[room.code]
                    self.send_admin_update()
                    
        elif msg_type == "ROOM_CHAT" and not client.is_admin:
            if client.current_room:
                room = self.rooms[client.current_room]
                for c in room.clients:
                    if c != client:
                        c.send_message(message)
                        
    def disconnect_client(self, client):
        if client in self.clients:
            self.clients.remove(client)
        if client.is_admin:
            self.admin_client = None
            print(f"Admin client disconnected: {client.address}")
        if client.current_room:
            room = self.rooms.get(client.current_room)
            if room:
                room.remove_client(client)
                if room.clients:
                    disconnect_message = {
                        "type": "USER_LEFT",
                        "room_code": room.code,
                        "user": "SERVER",
                        "data": {
                            "user": client.nickname,
                            "players": [c.nickname for c in room.clients]
                        }
                    }
                    for c in room.clients:
                        c.send_message(disconnect_message)
                if not room.clients and room.status != "In Progress":
                    del self.rooms[room.code]
        try:
            client.socket.close()
        except:
            pass
        self.send_admin_update()
            
    def monitor_display(self):
        while self.running:
            os.system('clear' if os.name == 'posix' else 'cls')
            print("=== QUIZ SERVER MONITOR ===")
            print(f"Connected Clients: {len(self.clients)}")
            print(f"Active Rooms: {len(self.rooms)}")
            print()
            if self.rooms:
                print("ROOMS:")
                print(f"{'Code':<8} {'Topic':<15} {'Players':<8} {'Status':<12}")
                print("-" * 50)
                for code, room in self.rooms.items():
                    print(f"{code:<8} {room.topic:<15} {len(room.clients):<8} {room.status:<12}")
            else:
                print("No active rooms")
            print()
            print("Press Ctrl+C to shutdown server")
            time.sleep(2)

if __name__ == "__main__":
    server = QuizServer()
    server.start_server()
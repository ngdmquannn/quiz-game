# Quiz Chat Project

## Introduction

This project is developed as the **final project for the course *Programming for Network Engineers*** at UIT.

The **Quiz Chat Project** is a multiplayer, interactive quiz system with built-in chat functionality. It is designed to run both on **local networks (LAN/localhost)** and in **cloud environments**, making it accessible to players from different machines and networks.

The project demonstrates practical applications of what I learned in the course, including: **client-server programming, network sockets, and GUI development**. It combines networking concepts with a real-world use case: a competitive quiz game where multiple users connect, communicate, and compete in real time, under the supervision of an administrator.

---

## How the Game Works

1. **Server Initialization**

   * The server hosts the quiz system and loads question banks from JSON files.
   * Topics (e.g., *Linux*, *Networking*, *Python*) are made available for quiz rooms.

2. **Admin Control**

   * The administrator connects as a special client via a dedicated GUI panel.
   * They can monitor clients, manage rooms, broadcast messages, kick/ban players, and force-start quizzes.

3. **Client Gameplay**

   * Players launch the client application, choose a nickname, and connect to the server lobby.
   * In the lobby, players can:

     * **Chat** with others
     * **Create** new quiz rooms
     * **Join** existing quiz rooms

4. **Quiz Flow**

   * Once a room is active, questions are presented sequentially.
   * Supported formats:

     * **Multiple Choice (MCQ)** – players select from options.
     * **Short Answer** – players type their answer.
   * Points are awarded for correct answers, with speed bonuses for quick responses.

5. **Leaderboard & Results**

   * Scores are updated in real time.
   * A live leaderboard shows rankings.
   * At the end of the quiz, final results are displayed for all players.

---

## Key Features

* 🎮 **Multiplayer quiz rooms** – Dynamic creation and joining of rooms.
* 💬 **Integrated chat** – Lobby and in-room messaging.
* 📂 **Custom topics** – Questions defined in `questions_<topic>.json`.
* 👨‍💼 **Admin panel** – Full control over rooms, players, and quizzes.
* 🖥️ **PyQt5 GUI** – Modern, dark-themed interface for admin and players.
* 🌍 **Flexible deployment** – Works locally or in the cloud.
* 📊 **Leaderboards** – Real-time scoring and final results.

---

## Requirements

* **Python 3.8+**
* **PyQt5** → install with:

  ```bash
  pip install PyQt5
  ```
* (Optional) **Docker** for containerized deployment

---

## Getting Started

### 1. Start the Server

```bash
python server.py
```

* Default host: `127.0.0.1`
* Default port: `8888`
* For cloud deployment: change the host IP in `server.py` and open the port on your server.

---

### 2. Launch the Admin Panel

```bash
python admin.py
```

* Enter the server IP/port (`localhost:8888` or `<server-ip>:8888`).
* The admin dashboard allows:

  * Viewing connected clients
  * Managing rooms
  * Broadcasting messages
  * Kicking/banning players
  * Force-starting quizzes
  * Viewing/saving logs

---

### 3. Run the Clients

```bash
python client.py
```

* Choose a nickname and connect.
* Clients can:

  * Chat in the lobby
  * Create or join quiz rooms
  * Answer questions and compete on the leaderboard

Multiple clients can be run at the same time.

---

## Customizing Quiz Questions

Questions are stored in JSON files with the naming pattern:

```
questions_<topic>.json
```

### Example

```json
[
  {
    "type": "mcq",
    "question": "Which command lists directory contents?",
    "options": ["cd", "ls", "pwd", "rm"],
    "answer": "ls"
  },
  {
    "type": "short",
    "question": "What command updates package lists in Ubuntu?",
    "answer": "apt update"
  }
]
```

* **type**: `"mcq"` or `"short"`
* **options**: Required for `"mcq"`
* **answer**: Correct answer string

The server automatically loads all `questions_*.json` files when it starts.

---

## Docker Deployment

Build the Docker image:

```bash
docker build -t quiz-chat .
```

Run the container:

```bash
docker run -p 8888:8888 quiz-chat
```

Clients and admin can connect to `<server-ip>:8888`.

---

## Project Workflow

1. **Server** starts and loads quiz topics.
2. **Admin** connects and monitors activity.
3. **Clients** join the lobby, chat, and create/join quiz rooms.
4. **Quiz** runs with timed questions and scoring.
5. **Leaderboard** updates after each question, final results at the end.

---

Do you want me to add a **section highlighting which networking/programming concepts from your course** (like sockets, threading, GUI, JSON parsing) are applied in this project? It would make it clear how this ties back academically to *Programming for Network Engineers*.

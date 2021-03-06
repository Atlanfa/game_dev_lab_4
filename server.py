import socket
from _thread import *
import _pickle as pickle
import time
import random
import math

# setup sockets
S = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
S.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Set constants
PORT = 5556

BALL_RADIUS = 5
START_RADIUS = 7

ROUND_TIME = 10  # set time in seconds

MASS_LOSS_TIME = 7

W, H = 1200, 600

chunk = 200

chunks_num = math.ceil(W / chunk)

# HOST_NAME = socket.gethostname()
# SERVER_IP = socket.gethostbyname(HOST_NAME)
SERVER_IP = '127.0.0.1'

# try to connect to server
try:
    S.bind((SERVER_IP, PORT))
except socket.error as e:
    print(str(e))
    print("[SERVER] Server could not start")
    quit()

S.listen()  # listen for connections

print(f"[SERVER] Server Started with local ip {SERVER_IP}")

# dynamic variables
players = {}
balls = []
connections = 0
_id = 0
colors = [(255, 0, 0), (255, 128, 0), (255, 255, 0), (128, 255, 0), (0, 255, 0), (0, 255, 128), (0, 255, 255),
          (0, 128, 255), (0, 0, 255), (0, 0, 255), (128, 0, 255), (255, 0, 255), (255, 0, 128), (128, 128, 128),
          (0, 0, 0)]
start = False
start_time = 0
game_time = "Starting Soon"
nxt = 1


# FUNCTIONS

def release_mass(players):
    for player in players:
        p = players[player]
        if p["score"] > 8:
            p["score"] = math.floor(p["score"] * 0.95)


def check_collision(players, balls):
    to_delete = []
    for player in players:
        p = players[player]
        x = p["x"]
        y = p["y"]
        for ball in balls:
            bx = ball[0]
            by = ball[1]

            dis = math.sqrt((x - bx) ** 2 + (y - by) ** 2)
            if dis <= START_RADIUS + p["score"]:
                p["score"] = p["score"] + 0.5
                balls.remove(ball)


def player_collision(players):
    sort_players = sorted(players, key=lambda x: players[x]["score"])
    for x, player1 in enumerate(sort_players):
        for player2 in sort_players[x + 1:]:
            p1x = players[player1]["x"]
            p1y = players[player1]["y"]

            p2x = players[player2]["x"]
            p2y = players[player2]["y"]

            dis = math.sqrt((p1x - p2x) ** 2 + (p1y - p2y) ** 2)
            if dis < players[player2]["score"] - players[player1]["score"] * 0.85:
                players[player2]["score"] = math.sqrt(
                    players[player2]["score"] ** 2 + players[player1]["score"] ** 2)  # adding areas instead of radii
                players[player1]["score"] = 0
                players[player1]["x"], players[player1]["y"] = get_start_location(players)
                print(f"[GAME] " + players[player2]["name"] + " ATE " + players[player1]["name"])


def create_balls(balls, n):
    for i in range(n):
        while True:
            stop = True
            x = random.randrange(0, W)
            y = random.randrange(0, H)
            for player in players:
                p = players[player]
                dis = math.sqrt((x - p["x"]) ** 2 + (y - p["y"]) ** 2)
                if dis <= START_RADIUS + p["score"]:
                    stop = False
            if stop:
                break

        balls.append((x, y, random.choice(colors)))


def get_start_location(players):
    while True:
        stop = True
        x = random.randrange(0, W)
        y = random.randrange(0, H)
        for player in players:
            p = players[player]
            dis = math.sqrt((x - p["x"]) ** 2 + (y - p["y"]) ** 2)
            if dis <= START_RADIUS + p["score"]:
                stop = False
                break
        if stop:
            break
    return (x, y)


def get_player_chunk(player):
    x = player['x']
    y = player['y']
    return (y // chunk) * chunks_num + (x // chunk) + 1


def get_ball_chunk(ball):
    x = ball[0]
    y = ball[1]
    return (y // chunk) * chunks_num + (x // chunk) + 1


def get_players_in_chunk(chunk_num):
    players_in_chunk = {}
    for player_id in players.keys():
        if get_player_chunk(players[player_id]) == chunk_num:
            players_in_chunk[player_id] = players[player_id]
    return players_in_chunk


def get_balls_in_chunk(chunk_num):
    balls_in_chunk = []
    for ball in balls:
        if get_ball_chunk(ball) == chunk_num:
            balls_in_chunk.append(ball)
    return balls_in_chunk


def get_visible_chunks(player_id):
    curr = get_player_chunk(players[player_id])
    if curr % chunks_num == 0:
        return [curr - chunks_num - 1, curr - chunks_num, curr - 1, curr,
                curr + chunks_num - 1, curr + chunks_num]
    if curr % chunks_num == 1:
        return [curr - chunks_num, curr - chunks_num + 1, curr, curr + 1,
                curr + chunks_num, curr + chunks_num + 1]
    return [curr - chunks_num - 1, curr - chunks_num, curr - chunks_num + 1, curr - 1, curr, curr + 1,
            curr + chunks_num - 1, curr + chunks_num, curr + chunks_num + 1]


def get_visible_players(player_id):
    visible_players = {}
    for curr_chunk in get_visible_chunks(player_id):
        visible_players.update(get_players_in_chunk(curr_chunk))
    return visible_players


def get_visible_balls(player_id):
    visible_balls = []
    for curr_chunk in get_visible_chunks(player_id):
        visible_balls += get_balls_in_chunk(curr_chunk)
    return visible_balls


def restart_players():
    for player_id in players.keys():
        players[player_id] = {"x": players[player_id]['x'], "y": players[player_id]['y'],
                              "color": players[player_id]['color'], "score": 0, "name": players[player_id]['name']}


def threaded_client(conn, _id):
    global connections, players, balls, game_time, nxt, start, start_time

    get_balls = get_visible_balls
    get_players = get_visible_players
    flag = 0

    current_id = _id

    # receive a name from the client
    data = conn.recv(16)
    name = data.decode("utf-8")
    print("[LOG]", name, "connected to the server.")

    # Setup properties for each new player
    color = colors[current_id]
    x, y = get_start_location(players)
    players[current_id] = {"x": x, "y": y, "color": color, "score": 0, "name": name}  # x, y color, score, name

    # pickle data and send initial info to clients
    conn.send(str.encode(str(current_id)))

    # server will recieve basic commands from client
    # it will send back all of the other clients info
    while True:

        if start:
            game_time = round(time.time() - start_time)
            # if the game time passes the round time the game will stop
            if game_time >= ROUND_TIME:
                start = False
                get_balls = lambda player_id: balls
                get_players = lambda player_id: players
                restart_players()


                start = True
                start_time = time.time()
                print("[STARTED] Game Started")

            else:
                get_balls = get_visible_balls
                get_players = get_visible_players
                if game_time // MASS_LOSS_TIME == nxt:
                    nxt += 1
                    release_mass(players)
                    print(f"[GAME] {name}'s Mass depleting")
        try:
            # Recieve data from client
            data = conn.recv(32)

            if not data:
                break

            data = data.decode("utf-8")
            # print("[DATA] Recieved", data, "from client id:", current_id)

            # look for specific commands from recieved data
            if data.split(" ")[0] == "move":
                split_data = data.split(" ")
                x = int(split_data[1])
                y = int(split_data[2])
                players[current_id]["x"] = x
                players[current_id]["y"] = y

                # only check for collison if the game has started
                if start:
                    check_collision(players, balls)
                    player_collision(players)

                # if the amount of balls is less than 150 create more
                if len(balls) < 150:
                    create_balls(balls, random.randrange(100, 150))
                    print("[GAME] Generating more orbs")

                send_data = pickle.dumps((get_balls(current_id), get_players(current_id), game_time))

            elif data.split(" ")[0] == "id":
                send_data = str.encode(str(current_id))  # if user requests id then send it

            elif data.split(" ")[0] == "jump":
                send_data = pickle.dumps((get_balls(current_id), get_players(current_id), game_time))
            else:
                # any other command just send back list of players
                send_data = pickle.dumps((get_balls(current_id), get_players(current_id), game_time))

            # send data back to clients
            conn.send(send_data)

        except Exception as e:
            print(e)
            break  # if an exception has been reached disconnect client

        time.sleep(0.005)

    # When user disconnects
    print("[DISCONNECT] Name:", name, ", Client Id:", current_id, "disconnected")

    connections -= 1
    del players[current_id]  # remove client information from players list
    conn.close()  # close connection


# MAINLOOP

# setup level with balls
create_balls(balls, random.randrange(200, 250))

print("[GAME] Setting up level")
print("[SERVER] Waiting for connections")

# Keep looping to accept new connections
while True:

    host, addr = S.accept()
    print("[CONNECTION] Connected to:", addr)

    # start game when a client on the server computer connects

    if len(players) == 1 and not start:
        start = True
        start_time = time.time()
        print("[STARTED] Game Started")

    # increment connections start new thread then increment ids
    connections += 1
    start_new_thread(threaded_client, (host, _id))
    _id += 1

# when program ends
print("[SERVER] Server offline")

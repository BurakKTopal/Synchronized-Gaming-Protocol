import sys
import socket
import threading
import time
import pygame
from pygame.locals import *

####################################
# Constants
####################################

red = [255, 0, 0]
green = [0, 255, 0]
blue = [0, 0, 255]
white = [255, 255, 255]
black = [0, 0, 0]
grey = [150, 150, 150]
gold = [255, 215, 0]
brown = [210, 105, 30]


# Entity object.
class Entity(object):
    x = 0
    y = 0
    w = 0
    h = 0
    rect = Rect(x, y, w, h)
    color = [0, 0, 0]

    # Constructor
    def __init__(self, x, y, w, h, color):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.color = color
        # Set the boundary box of the object. Important for collisions
        self.rect = Rect(x, y, w, h)
        # By default, an entity has no collision and is not a collectible to pickup.
        self.hasCollision = False
        self.isCollectible = False

    # Update the rectangle used for collisions.
    def updateRect(self):
        self.rect = Rect(self.x, self.y, self.w, self.h)

    def draw(self):
        # Draw the object with a given color and position to the screen.
        pygame.draw.rect(screen, self.color, [self.x, self.y, self.w+3, self.h+3], 0)


class Player(Entity):
    """"
    A player is a client, it is the block that the person plays on his own pc
    """
    def __init__(self, x, y, w, h, color, identifier):
        Entity.__init__(self, x, y, w, h, color)
        self.origX = x
        self.origY = y
        self.hasCollision = True
        self.moveSpeed = 0.5  # speed of the player
        self.active = False
        self.score = 0
        self.ID = int(identifier)
        self.send_x = None  # x-position(absolute, or only direction) that is SENT to the server
        self.send_y = None  # y-position(absolute, or only direction) that is SENT to the server



    def reset(self):
        self.x = self.origX
        self.y = self.origY

    def update(self):
        # Keep the old positional x and y value.
        self.updateRect()

    def movement(self, deltaTime, msg):
        """"
        To spare on data being sent, only the direction is sent DURING a key is pressed. If a new key is pressed, then
        the exact(absolute) position is sent to the server. This is done to ensure that each client gets the right
        representation, and avoid that problems accumulate in case of high ping.

        The following encoding is used for the directions:
        (x_direction_key, y_direction_key) : meaning
            (5,5): the client is standing completely still
            (1,1): the y-value DECREASES(down-movement), while x does NOT change
            (2,2): the x-value INCREASES, while the y-value does NOT change
            (3,3): the y-value INCREASES, while the x-value does NOT change
            (4,4): the x-value DECREASES, while the y-value does NOT change

        """
        x_direction = {5: 0, 1: 0, 2: 1, 3: 0, 4: -1}
        y_direction = {5: 0, 1: -1, 2: 0, 3: 1, 4: 0}
        direction_x = x_direction[msg]
        direction_y = y_direction[msg]

        # Keep the old positional x and y value.
        self.xOld = self.x
        self.yOld = self.y

        self.x += self.moveSpeed * deltaTime*direction_x
        self.y += self.moveSpeed * deltaTime*direction_y

        # Updating rectangle, as position changed
        self.updateRect()


class CollisionBlock(Entity):
    def __init__(self, x, y, w, h, color):
        Entity.__init__(self, x, y, w, h, color)
        self.hasCollision = True


class Opponent(Entity):
    """""
    Generalization of 'player2' by defining an opponent, and identifying them by the ID attribute.
    With this, the number of players can be easily generalized to N-players, by which each identifies himself by his or
    her ID. This is distributed by the server
    """
    def __init__(self, x, y, w, h, color, identifier):
        Entity.__init__(self, x, y, w, h, color)
        self.origX = x
        self.origY = y
        self.score = 0
        self.hasCollision = True
        self.moveSpeed = 0.5  # Speed of movement
        self.active = False
        self.ID = identifier  # Each opponent has an id, so that the correct opponent should move


    def reset(self):
        self.x = self.origX
        self.y = self.origY


    def update(self):
        # Keep the old positional x and y value.
        self.xOld = self.x
        self.yOld = self.y
        self.updateRect()

    def movement(self, deltaTime, msg):
        """"
        Similarly, if directions are sent, then these must be too parsed. This is done by this function; it 'reads' maps
        the given coding to the correct displacement pattern.

        The SAME encoding is used for the directions:
        (x_direction_key, y_direction_key) : meaning
            (5,5): the client is standing completely still
            (1,1): the y-value DECREASES(down-movement), while x does NOT change
            (2,2): the x-value INCREASES, while the y-value does NOT change
            (3,3): the y-value INCREASES, while the x-value does NOT change
            (4,4): the x-value DECREASES, while the y-value does NOT change

        """
        x_direction = {5: 0, 1: 0, 2: 1, 3: 0, 4: -1}
        y_direction = {5: 0, 1: -1, 2: 0, 3: 1, 4: 0}
        direction_x = x_direction[msg]
        direction_y = y_direction[msg]
        # Keep the old positional x and y value.
        self.xOld = self.x
        self.yOld = self.y

        self.x += self.moveSpeed * deltaTime*direction_x
        self.y += self.moveSpeed * deltaTime*direction_y

        self.updateRect()

class PickupBlock(Entity):
    """"
    The pickup block is made a little bit bigger. This is done because of the discrete movement of the player. Because
    of this, it can happen that the pickupblock is just too close to a wall, and one of the contestants/players cannot
    grab it.
    """
    def __init__(self, x, y, w, h, color):
        Entity.__init__(self, x, y, w+8, h+8, color)
        self.hasCollision = False
        self.isCollectible = True


# Level
class Level:
    # Constructor
    def __init__(self, fileHandle):
        # Load level file and create objects. Not important for this assignment.
        self.f = open(fileHandle)
        self.tileRows = self.f.readlines()
        self.map = []
        self.entities = []
        self.player = None  # The player is predefined....
        self.opponents = {}  # Dictionary used to be able to set up multiple opponents, tested and works.
        self.fruit_x = 0  # x-Position of the fruit
        self.fruit_y = 0  # y-position of the fruit
        self.fruit_eaten = False  # Each client calculates for themselves if they've eaten the fruit or not. If they
        # conclude that they've eaten one, they sent this to the server.
        self.fruit_eatable = True  # Because the validation needs to come from the server, the fruit only needs
        # to be able to eaten once, and not multiple times while server validates
        self.all_players_active = False  # This is used to check if the game can be started. All players must be ready.
        self.connected = False  # This attribute serves to check if the TCP connection is set and running.
        self.deltaTime = 0
        self.currentCollectible = ''
        self.reset()
        self.direction = 5  # There are absolute positions, but also directions in which there is movement.
        self.all_opponents_left = False  # This is important, because game ends if all opponents left(player wins)
        self.waiting_move = False  # Due to the chosen configuration between server, and player, the player must
        # not give the possibility to send a new message, before getting a response from the server.

        i = 0
        for row in self.tileRows:
            j = 0
            for tile in row:
                self.loadItem(tile, j, i)
                j += 1
            i += 1


    def loadItem(self, tile, x, y):
        xPos = x * tileWidth
        yPos = y * tileWidth
        # Place the object tiles in the map. Not important for this assignment.
        if (tile == collisionTile):
            self.map.append(CollisionBlock(xPos, yPos, tileWidth, tileWidth, brown))
        elif (tile in playerTiles):
            PositionTiles.append((xPos, yPos))


    def getTimeLeft(self):
        return self.timeLeft

    def reset(self):
        """"
        Resetting the whole game
        """
        self.player = None
        # Total time in milliseconds.
        self.timeLeft = 40000
        # Set if the level ends.
        self.levelEnds = False
        self.opponents = {}
        self.fruit_x = 0
        self.fruit_y = 0
        self.fruit_seed = 100
        self.all_players_active = False
        self.connected = False
        self.deltaTime = 0
        self.currentCollectible = ''
        self.map = []
        self.entities = []
        self.all_opponents_left = False
        self.deltaTime = 0
        self.currentCollectible = ''
        self.client = None
        i = 0
        for row in self.tileRows:
            j = 0
            for tile in row:
                self.loadItem(tile, j, i)
                j += 1
            i += 1

    def update(self, deltaTime):
        """"
        Updating game
        """
        if (self.levelEnds):
            key = pygame.key.get_pressed()
            # Pressing SPACE when the level is finished, will reset the level.
            if (key[K_SPACE]):
                self.client.reset()
                self.reset()
            return

        # Check for all necessary collisions in the map.
        self.checkCollisions()

        # Update the positions of player 1 and player 2
        if self.player:
            self.player.update()

        for opponent_id in self.opponents.keys():
            self.opponents[opponent_id].update()
        # Update the total time that is left before the game ends.
        if level.all_players_active:
            self.timeLeft -= deltaTime
        if (self.timeLeft < 0):
            self.levelEnds = True

    def fruitEaten(self):
        """"
        Due to the dicrete space, we still need to account in case the fruit block is just on the wall."""
        if abs(self.player.x - self.fruit_x) <= 30 and abs(self.player.y - self.fruit_y) <= 30:
            return True
        return False


    def checkCollisions(self):
        """"
        If there is a collision, the player does NOT send any data to the server, avoiding extra data being send.
        Beside the collision, there is also checked by the client itself if he has taken a fruit or not, if so
        he sets  self.fruit_eaten on True, and notifies, by specific msg id, the server that it has eaten a fruit.
        """
        recollide = True
        illegal_move = False
        self.fruit_eaten = False
        while recollide:
            recollide = False
            # Check collision of Player vs collectible objects(each client does it for himself, thus client does
            # only need to look to his player!).
            for tile in self.map:
                # Does this tile have collision and its rectangle collides with the rectangle of player 1 ?
                if tile.hasCollision and tile.rect.colliderect(self.player.rect):
                    # Because player 1 has changed its position, we have to recalculate the collisions.
                    illegal_move = True
                    break
                if tile.isCollectible and tile.rect.colliderect(self.player.rect) and level.fruit_eatable:
                    self.fruit_eaten = True
                    level.fruit_eatable = False
        # Is this tile a collectible and does it collide with the player?
        if self.fruitEaten():
            # Remove the collectible from the map.
            self.fruit_eaten = True
            level.fruit_eatable = False
        return illegal_move

    def LegalMoveAdaptation(self):
        """"
        For synchronously play, there has been chosen to send every change first to the server, which sends it to the
        other clients, but echoes it back to the player. This may seem obsolete, but in this way it keeps the difference
        in PING of the different clients in mind; it makes inner calculations so that each client(including the player)
        gets at the same time the position displacement. This way there is no need(expect to very edge cases) for the
        server to keep a buffer, and to 'reload' previous positions on each client in case there is lag. In this way,
        the (multiple) clients are also playing on the same 'internet quality', meaning the same ping. In this manner,
        the game is made equal, which does punishes the player with the better internet, but this seemed for me as the
        best option, as otherwise it wouldn't be a 'square' game anyway.

        To distribute the calculations, each client makes his own check on legal moves on his own host device, and this
        is not done by the server(avoiding extra 'validation' data send to the server).
        This is done by introducing the 'fake move'. By this, it 'plays' the move on his screen, then
        it checks if the move is legal(NO collisions with wall), and then reverts the move, but sends the data to
        position change to the server. The server sends back this position(while keeping other clients' ping). The
        player receives this message, and plays the move.
        This principle is also used(at least I did it) in other games, such as chess: each move is played(by doing a
        fake move) and check if this results in any illegal move. If so, the move is not taken in the list of possible
        moves.
        """
        self.player.xOld = self.player.x  # Saving the initial position, to revert back after fake move played
        self.player.yOld = self.player.y  # Saving the initial position, to revert back after fake move played

        self.player.x = self.player.send_x  # Playing the fake move
        self.player.y = self.player.send_y  # Playing the fake move

        self.player.updateRect()  # Updating the fake move

        if self.checkCollisions():
            # Redoing fake move
            self.player.send_x = self.player.xOld
            self.player.send_y = self.player.yOld
            self.player.x = self.player.xOld
            self.player.y = self.player.yOld
            level.direction = 5
            level.direction = 5
            self.player.updateRect()
            return True
        else:
            # Redoing fake move
            self.player.x = self.player.xOld
            self.player.y = self.player.yOld
            self.player.updateRect()
            return False

    def draw(self):
        for tile in self.map:
            tile.draw()
        if self.player.active:
            self.player.draw()
        for opponent in self.opponents.values():
            if opponent.active:
                opponent.draw()


    def getPlayer(self):
        return self.player

    def getOpponent(self, opponent_id):
        return self.opponents[opponent_id]

    def isLevelFinished(self):
        return self.levelEnds

    def legalKeyPresses(self, key):
        """"
        Only these four keys are possible to press, others are not legal
        """
        return key[K_RIGHT] or key[K_LEFT] or key[K_UP] or key[K_DOWN]



####################################
# Globals
####################################

# Display
pygame.init()
screenSize = [1280, 600]
screenBGColor = grey

# Tiles
tileWidth = 15
playerTiles = ['A', 'B', 'C', 'D']
playerColors = [red, blue, black, gold]
PositionTiles = []
collisionTile = '#'

# Level map (1-1.txt)
levelHandle = "1-1.txt"
level = Level(levelHandle)


# Game
running = True


def render():
    # Fill the whole screen with one color.
    screen.fill(screenBGColor)

    textUIP1 = textFont.render(f"Score P{level.player.ID}(YOU): " + str(level.player.score), True, [0, 0, 0])
    screen.blit(textUIP1, (20, 560))
    y_translation = 30  # Showing points of other players
    x_translation = 30  # Showing points of other players. This is only useful if n_of_players > 4

    if len(level.opponents.values()) < client.n_of_players - 1:
        warningmessage = textFont.render(f"WAITING FOR OPPONENTS",True, [200, 0, 0]) # Game only starts if all players are there
        screen.blit(warningmessage, (20, 480))

    for opponent_id in level.opponents.keys():
        if not level.opponents[opponent_id].active:
            # If player is not active, a P(<opponent_id>)(LEFT) will be displayed on the other screens of the clients.
            textOpponent = textFont.render(f"Score P{opponent_id}(LEFT): " + str(level.opponents[opponent_id].score), True, [0, 0, 0])
        else:
            textOpponent = textFont.render(f"Score P{opponent_id}: " + str(level.opponents[opponent_id].score), True, [0, 0, 0])
        screen.blit(textOpponent, (20 + x_translation, 560 - y_translation))
        y_translation += 30
        if y_translation%90 == 0:
            x_translation += 30

    # Draw the total time left.
    textTimeLeft = textFont.render("Time left: " + str(round(level.getTimeLeft()/1000)) + " s", True, [0, 0, 0])
    screen.blit(textTimeLeft, (900, 530))
    # Only if the level is not finished (timer has not run out yet), then we draw the complete level.
    if level.opponents:
        # If all opponents left, the player that is left over, will win automatically.
        if not any(level.opponents[opponent_id].active for opponent_id in level.opponents.keys()) and level.timeLeft > 0:
            level.levelEnds = True
            level.all_opponents_left = True
            textWin = textFont.render("YOU WON! All players left", True, [0, 0, 0])
            screen.blit(textWin, (540, 250))

    if (not level.isLevelFinished()):
        # Draw the complete level while not finished.
        level.draw()

    elif level.isLevelFinished() and not level.all_opponents_left:
        if all(level.player.score > opponent.score for opponent in level.opponents.values()):
            textWin = textFont.render("You WON! Press SPACE to play again.", True, [0, 0, 0])
        elif any(level.player.score < opponent.score for opponent in level.opponents.values()):
            textWin = textFont.render("You LOST :<! Press SPACE to play again.", True, [0, 0, 0])
        else:
            textWin = textFont.render("It's a tie ... Press SPACE to play again.", True, [0, 0, 0])
        screen.blit(textWin, (540, 250))

    # Switch framebuffers. This should be called after every draw.
    pygame.display.flip()


def tick():
    """"
    Because the speed is actually given by deltatime TIMES moveSpeed, to reduce the amount of data, we can DIVIDE the
    number of FPS by two, if we only too multiply moveSpeed by two. But this slightly reduces the user experience(less
    smoothly play), so we kept it at 30.
    """
    # We run our game at 30 FPS.
    level.deltaTime = clock.tick(30)
    level.update(level.deltaTime)



class Client():
    """"
    This class handles the client, more specifically:
        -Socket
        -The messages received from the server, @handleServer()
        -Before the game starts, all players are pinged, the game starts only if probing is finished.
        -Simulating a ping, given via terminal
        -Keeping track of the number of players, on default this is equal to 2
    """
    def __init__(self):
        self.socket_connection = None
        self.total_message = bytes()
        self.RTT_probing_finished = False
        self.simulated_ping = 0
        self.n_of_players = 2

    def setupTCPConnection(self):
        """
        Setting up the TCP connection.
        TCP is chosen to get the reliable data transfer, and also because we are working with time sensitive and Pinging
        system. Losing one ping could result to big delays.
        The extra RTT that TCP gives, is an issue, but this is something that we get for the reliability."""

        if len(sys.argv) == 4:
            try:
                if not 0 <= int(sys.argv[3]) <= 500:
                    print("Usage: python", sys.argv[0], "<port>", "<host>",
                          "<[OPTIONAL]additional ping(min:0, max: 500, DEFAULT:0)>")
                    sys.exit(1)

                else:
                    self.simulated_ping = int(sys.argv[3])
            except:
                print("Usage: python", sys.argv[0], "<port>", "<host>",
                      "<[OPTIONAL]additional ping(min:0, max: 500, DEFAULT:0)>")
                sys.exit(1)

        elif not 1 < len(sys.argv) < 4:
            print("Usage: python", sys.argv[0], "<port>", "<host>", "<[OPTIONAL]additional ping(min:0, max: 500, DEFAULT:0)>")
            sys.exit(1)

        PORT = int(sys.argv[1])
        HOST = str(sys.argv[2])

        self.socket_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_connection.connect((HOST, PORT))
        return

    def createRequestSpecificCo(self, level, x, y, msg_id):
        """
        There is only send the specific/absolute position of the player, if he presses a key DOWN, once. If the key
        is being pressed, then the direction(relative position change) is sent to reduce data transfer
        from client <-> server.

        waiting_move is set on True, so that the player cannot send another message while the server echoes back his
        move.
        """
        leading_zeros_2_bit = {1: '0',
                               2: ''}  # Leading zeros fall of if number is too small, but assigned id, and msg_id
        leading_zeros_3_bit = {1: '00', 2: '0',
                               3: ''}  # Leading zeros fall of if number is too small, but assigned id, and msg_id

        player_id = leading_zeros_2_bit[len(bin(level.player.ID)[2:])] + bin(level.player.ID)[2:]
        msg_id = leading_zeros_3_bit[len(bin(msg_id)[2:])] + bin(msg_id)[2:]
        header = str(msg_id + player_id + '000')

        header = int(header, 2).to_bytes(1, byteorder='big')
        pos_x = round(x).to_bytes(2, byteorder='big')
        pos_y = round(y).to_bytes(2, byteorder='big')

        data = pos_x + pos_y
        request = header + data

        level.waiting_move = True
        self.socket_connection.sendall(request)
        return

    def createRequestDirection(self, level, direction, msg_id):
        """
        Specific request if there is only send a direction.
        """
        leading_zeros_2_bit = {1: '0', 2: ''}  # Leading zeros fall of if number is too small, but assigned id, and msg_id
        leading_zeros_3_bit = {1: '00', 2: '0', 3: ''}  # Leading zeros fall of if number is too small, but assigned id, and msg_id

        player_id = leading_zeros_2_bit[len(bin(level.player.ID)[2:])] + bin(level.player.ID)[2:]
        msg_id = leading_zeros_3_bit[len(bin(msg_id)[2:])] + bin(msg_id)[2:]
        direction = leading_zeros_3_bit[len(bin(direction)[2:])] + bin(direction)[2:]

        header = str(msg_id + player_id + direction)
        header = int(header, 2).to_bytes(1, byteorder='big')
        request = header
        level.waiting_move = True
        self.socket_connection.sendall(request)
        return

    def reset(self):
        """
        If player disconnects, all other players are notified.
        """

        header = int('10000000', 2).to_bytes(1, byteorder='big')  # msg id is 4, thus 100 in front, all the others are
                                                                    # zero in the header

        response = header
        self.socket_connection.sendall(response)
        self.socket_connection.close()
        self.socket_connection = None
        self.total_message = ''
        self.RTT_probing_finished = False




def parseMessage(level, client, msg):
    header_string = ''
    header = msg[0]
    for bit in range(7, -1, -1):
        header_string += str((header & (1 << bit)) >> bit)
    msg_id = int(header_string[:3], 2)
    contestant_id = int(header_string[3:5], 2)
    direction = int(header_string[5:8], 2)


    if msg_id == 1:
        assigned_id = contestant_id
        print("ASSIGNED_ID", assigned_id)
        level.player = Player(PositionTiles[assigned_id][0], PositionTiles[assigned_id][1],
                              tileWidth, tileWidth, playerColors[assigned_id], assigned_id)
        level.player.active = True
        return msg[1:]  # Returning the rest of the message

    elif msg_id == 2:
        if len(msg) < 7:
            # In case the message was not fully done
            print("MESSAGE NOT TOTAL", len(msg))
            return -1
        time_left = int.from_bytes(msg[1:3], byteorder='big', signed=False)
        fruit_x = int.from_bytes(msg[3:5], byteorder='big', signed=False)
        fruit_y = int.from_bytes(msg[5:7], byteorder='big', signed=False)

        n_opponents = contestant_id # in case id=2, the contestant ID resembles the number of opponents
        client.n_of_players = n_opponents + 1
        for id in range(0, client.n_of_players):
            if not id == level.player.ID:
                level.opponents[id] = Opponent(PositionTiles[id][0], PositionTiles[id][1],
                                               tileWidth, tileWidth, playerColors[id], id)
                level.opponents[id].active = True
                level.opponents[id].score = 0
                # Based on current RTT, the game is going to be made faster. If no delay, than low speed suffice.
                level.opponents[id].moveSpeed = {0: 0.4, 1: 0.6, 2: 0.8}[direction]
                print("active!")
        level.player.moveSpeed = {0: 0.4, 1: 0.6, 2: 0.8}[direction]
        print("SPEED CHOSEN AS:", {0: 0.4, 1: 0.6, 2: 0.8}[direction])
        level.all_players_active = True
        client.RTT_probing_finished = True
        level.player.score = 0
        level.timeLeft = time_left
        level.fruit_x = fruit_x
        level.fruit_y = fruit_y
        level.currentCollectible = PickupBlock(level.fruit_x, level.fruit_y, 25, 25, green)
        level.map.append(level.currentCollectible)
        return msg[7:]  # Returning the rest of the message

    elif msg_id == 3 or msg_id == 6:  # Movement, but without speed control
        # last byte.
        if contestant_id == level.player.ID:
            level.waiting_move = False

            if direction in [1, 2, 3, 4, 5]:
                level.player.movement(level.deltaTime, direction)
                last_byte_position = 0

            else:
                if len(msg) < 5:
                    print("MESSAGE NOT TOTOAL")

                    return -1
                level.player.x = int.from_bytes(msg[1:3], byteorder='big', signed=False)
                level.player.y = int.from_bytes(msg[3:5], byteorder='big', signed=False)
                last_byte_position = 4


        else:
            opponent = level.opponents[contestant_id]
            if direction in [1, 2, 3, 4, 5]:
                opponent.movement(level.deltaTime, direction)
                last_byte_position = 0

            else:
                if len(msg) < 5:
                    print("MESSAGE NOT TOTAL")
                    return -1
                opponent.x = int.from_bytes(msg[1:3], byteorder='big', signed=False)
                opponent.y = int.from_bytes(msg[3:5], byteorder='big', signed=False)
                last_byte_position = 4


        if msg_id == 6:
            if contestant_id == level.player.ID:
                level.player.score += 1
            else:
                opponent = level.opponents[contestant_id]
                opponent.score += 1

            if level.currentCollectible:
                level.map.remove(level.currentCollectible)
                level.currentCollectible = ''
            if direction in [1, 2, 3, 4, 5]:
                if len(msg) < 5:
                    print("MESSAGE NOT TOTAL")

                    return -1
                level.fruit_x = int.from_bytes(msg[1:3], byteorder='big', signed=False)
                level.fruit_y = int.from_bytes(msg[3:5], byteorder='big', signed=False)
                last_byte_position = 4

            else:
                if len(msg) < 9:
                    print("MESSAGE NOT TOTAL")

                    return -1
                level.fruit_x = int.from_bytes(msg[5:7], byteorder='big', signed=False)
                level.fruit_y = int.from_bytes(msg[7:9], byteorder='big', signed=False)
                last_byte_position = 8
            level.currentCollectible = PickupBlock(level.fruit_x, level.fruit_y, 25, 25, green)
            level.map.append(level.currentCollectible)
            level.fruit_eatable = True

        return msg[last_byte_position + 1:]


    elif msg_id == 4:  # A player is leaving
        if level.opponents:
            opponent = level.opponents[contestant_id]
            opponent.active = False
        return msg[1:]

    if msg_id == 5:
        # In case of a pong, the message consists of 3 bytes(header(1 byte) + time stamp(2 bytes))
        if len(msg) < 3:
            print("MESSAGE NOT TOTAL")

            # Check if whole message came in
            return -1
        client.socket_connection.sendall(msg)  # Sending back for ping
        level.waiting_move = False
        return msg[3:]


def handleServer(level, client):
    """
    By making use of Threading, the client handles the server.
    """
    client.total_message = bytes()
    if level.connected:
        try:
            if client.socket_connection:
                msg = client.socket_connection.recv(1024)
                if msg:
                    time.sleep(client.simulated_ping/1000)
                    client.total_message += msg
        except Exception:
            return


    while client.total_message:
        """"
        TCP is stream oriented based, so it can happen that two messages comes at once, so we loop through these two.
        """
        output = parseMessage(level, client, client.total_message)
        if output == -1:
            #client.total_message = bytes()
            break
        else:
            client.total_message = output

    return





####################################
# Main loop
####################################
screen = pygame.display.set_mode(screenSize)
clock = pygame.time.Clock()
textFont = pygame.font.SysFont('Comic Sans MS', 40)
pygame.display.set_caption("CN Assignment: Networked 2D Game")

while running:
    key_pressed = False

    if not level.connected:
        client = Client()
        level.client = client
        client_connection = client.setupTCPConnection()
        level.connected = True
        if client_connection:
            screen = pygame.display.set_mode(screenSize)
            clock = pygame.time.Clock()
            textFont = pygame.font.SysFont('Comic Sans MS', 40)
            pygame.display.set_caption("CN Assignment: Networked 2D Game")
        else:
            # Waiting lobby

            # Clear the screen
            screen.fill(grey)
            font = pygame.font.Font(None, 36)
            # Render the text
            text = font.render("Waiting for opponent...", True, black)
            text_rect = text.get_rect(center=(screenSize[0] // 2, screenSize[1] // 2))
            screen.blit(text, text_rect)
            # Update the display
            pygame.display.flip()
        continue
    try:

        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
                break
            if event.type == KEYDOWN and event.key == K_ESCAPE:
                running = False
                break
            if event.type == KEYDOWN and client.RTT_probing_finished and not level.waiting_move and not level.all_opponents_left:
                # Only sending if probing is finished, and we are not waiting on our move
                key_pressed = True  # This is necessary so that
                if event.key == pygame.K_RIGHT:
                    level.player.send_x = level.player.x + level.player.moveSpeed * level.deltaTime
                    level.player.send_y = level.player.y
                elif event.key == pygame.K_LEFT:
                    level.player.send_x = level.player.x - level.player.moveSpeed * level.deltaTime
                    level.player.send_y = level.player.y
                elif event.key == pygame.K_UP:
                    level.player.send_y = level.player.y - level.player.moveSpeed * level.deltaTime
                    level.player.send_x = level.player.x
                elif event.key == pygame.K_DOWN:
                    level.player.send_y = level.player.y + level.player.moveSpeed * level.deltaTime
                    level.player.send_x = level.player.x
                else:
                    break

                if not level.LegalMoveAdaptation():
                    # Only sending move, if move is legal.
                    if level.fruit_eaten:
                        request = client.createRequestSpecificCo(level, level.player.send_x, level.player.send_y, 6)
                        level.fruit_eaten = False
                    else:
                        request = client.createRequestSpecificCo(level, level.player.send_x, level.player.send_y, 3)


        threading.Thread(target=handleServer, args=(level, client)).start()
        if running and client.socket_connection and not key_pressed and not level.waiting_move and not level.all_opponents_left:
            key = pygame.key.get_pressed()

            if level.legalKeyPresses(key) and client.RTT_probing_finished and level.timeLeft > 0:
                if key[K_RIGHT]:
                    level.player.send_x = level.player.x + level.player.moveSpeed * level.deltaTime
                    level.player.send_y = level.player.y
                    level.direction = 2
                if key[K_LEFT]:
                    level.player.send_x = level.player.x - level.player.moveSpeed * level.deltaTime
                    level.player.send_y = level.player.y
                    level.direction = 4
                if key[K_UP]:
                    level.player.send_y = level.player.y - level.player.moveSpeed * level.deltaTime
                    level.player.send_x = level.player.x
                    level.direction = 1
                if key[K_DOWN]:
                    level.player.send_y = level.player.y + level.player.moveSpeed * level.deltaTime
                    level.player.send_x = level.player.x
                    level.direction = 3

                if not level.LegalMoveAdaptation():
                    if level.fruit_eaten:
                        level.fruit_eaten = False
                        request = client.createRequestDirection(level, level.direction, 6)
                    else:
                        request = client.createRequestDirection(level, level.direction, 3)

        if level.player:
            if not 0 < level.player.x < 1280 or not 0 < level.player.y < 600:
                # If player jumps by a miracle out of the map, it spawns back in the middle.
                level.player.x = screenSize[0]//2
                level.player.y = screenSize[1]//2
            tick()
            if level.connected:
                # Only if connected the map is rendered
                render()  # Render the map.

    except KeyboardInterrupt:

        header = int('10000000', 2).to_bytes(1, byteorder='big')  # msg id is 4, thus 100 in front, all the others are
        # zero in the header

        response = header
        client.socket_connection.sendall(response)
        client.socket_connection.close()



pygame.quit()
if level.player and client.socket_connection:
    header = int('10000000', 2).to_bytes(1, byteorder='big')  # msg id is 4, thus 100 in front, all the others are
    # zero in the header
    response = header
    client.socket_connection.sendall(response)
    client.socket_connection.close()
    level.connected = False
level.reset()

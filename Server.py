import random
import time
import sys
import socket
import threading
from HelperFunctions import HistogramBitSend, PlotCombined

total_game_time = 40_000
FRAMES_S = 30
TIME_FRAME_MODULO = 65536  # Because we know that our game is 40 seconds long, we can work modulo 2^{16}. The more precision
# is not needed. If we get a negative remainder in Modulo 2^{16}, then we simply add this number to get a pos remainder.


class Server():
    def __init__(self):
        self.running = True # Server is running
        self.server_socket = None  # Socket of server
        self.connected_sockets = []  # List of connected sockets
        self.N_OF_PLAYERS = 2
        self.assignable_ids = list(range(0, self.N_OF_PLAYERS))  # Each player gets an ID assigned by the server
        self.assigned_id = {}  # The server also keeps track of the id that is assigned to each client(socket)
        self.assigned_id_history = {}  # To make the plot of the RTT etc. we need to identify each player by his id
        self.all_players_active = False  # True: if all players' clock, assigned id etc., False if not.
        self.messages = {}  # To avoid that messages are getting 'mixed' from other clients, each client socket has
        # his 'mailbox'
        self.RTT_clients = {}  # The RTT(ping time) of each client is saved by the server.
        self.n_of_RTT_clients = {}  # The number of client is too saved.
        self.alpha = 0.125  # Updating rate of the RTT by the new RTT value
        self.game_started = False  # If every client has gotten the 'start shot', the server enters another 'phase'
        self.waiting_ping = {}  # For each client, it is saved if there are waiting for a ping or not. If waiting,
        # they don't send a new ping.
        self.n_of_message = {}  # The number of message is needed for updating the ping.
        self.fruit_x = random.randrange(45, 78 * 15)  # Fruit position is given by server to clients.
        self.fruit_y = random.randrange(60, 28 * 15)
        self.RTT_SAVED_DICT = {}  # To make the plot of the RTTs after the game, these needs to be saved per client.
        self.N_RTT_SAVED_DICT = {}  # To make the plot of the RTTs after the game, the 'sequence' number of the
        # RTT is needed per client
        self.ping_update_rate = {}  # Each client updates his ping according to his rate
        self.average_bits_send = {} # Keeps track of the LIST of each client, representing the AVERAGE bytes send per message
        self.n_of_probing_ping = 20  # The number of pings sent before the game starts. This is done to probe the connections
        self.totalBytesSend = {}  # Keeps track of the number of total bytes per client.
        self.ByteSend = {}  # Keeps track of the LIST of each client, representing the bytes send per message
        self.plot = False  # True if server will give plot of the average bytes send, the RTT values, and a message-bit distribution
                            # False if server won't give any plot


    def CreateResponse(self, msg_id, connection_socket, client_msg=bytes(), total_game_time=40000,
                       leaving_id=0):
        leading_zeros_2_bit = {1: '0', 2: ''} # Leading zeros fall of if number is too small, but assigned id, and msg_id
        leading_zeros_3_bit = {1: '00', 2: '0', 3: ''} # Leading zeros fall of if number is too small, but assigned id, and msg_id
        # both have a fixed bit length.
        response = ''
        if msg_id == 1:
            assigned_id = self.assigned_id[connection_socket]
            assigned_id = leading_zeros_2_bit[len(bin(assigned_id)[2:])] + bin(assigned_id)[2:]
            msg_id = leading_zeros_3_bit[len(bin(msg_id)[2:])] + bin(msg_id)[2:]

            header = str(msg_id + assigned_id + '000')
            response = int(header, 2).to_bytes(1, byteorder='big')  # There is no data send, thus only the header is needed in this case.


        elif msg_id == 2:

            assigned_id = {2: '01', 3: '10', 4: '11'}[self.N_OF_PLAYERS]  # To start game, the assigned ID will be used to notify the clients how many OPPONENTS there
            # will be active.
            msg_id = leading_zeros_3_bit[len(bin(msg_id)[2:])] + bin(msg_id)[2:]

            # Making game faster in case of high RTT values
            if max(self.RTT_clients.values()) < 40:
                direction = '000'
            elif 40 <= max(self.RTT_clients.values()) < 80:
                direction = '001'
            else:
                direction = '010'

            header = str(msg_id + assigned_id + direction)
            header = int(header, 2).to_bytes(1, byteorder='big')  # There is no data send, thus only the header is needed in this case.

            total_time = round(total_game_time).to_bytes(2, byteorder='big')
            fruit_x_pos = round(self.fruit_x).to_bytes(2, byteorder='big')
            fruit_y_pos = round(self.fruit_y).to_bytes(2, byteorder='big')
            data = total_time + fruit_x_pos + fruit_y_pos
            response = header + data

        elif msg_id == 3:
            response = client_msg


        elif msg_id == 4:
            msg_id = leading_zeros_3_bit[len(bin(msg_id)[2:])] + bin(msg_id)[2:]
            leaving_id = leading_zeros_2_bit[len(bin(leaving_id)[2:])] + bin(leaving_id)[2:]
            header = str(msg_id + leaving_id + '000')
            response = int(header, 2).to_bytes(1, byteorder='big')  # There is no data send, thus only the header is needed in this case.


        elif msg_id == 5:
            msg_id = leading_zeros_3_bit[len(bin(msg_id)[2:])] + bin(msg_id)[2:]

            header = str(msg_id + '00' + '000')
            header = int(header, 2).to_bytes(1, byteorder='big')

            time_stamp = int(time.time()*1000)%TIME_FRAME_MODULO
            time_stamp = round(time_stamp).to_bytes(2, byteorder='big')

            data = time_stamp

            response = header + data


        elif msg_id == 6:
            header_plus_data = client_msg
            fruit_x_pos = round(self.fruit_x).to_bytes(2, byteorder='big')
            fruit_y_pos = round(self.fruit_y).to_bytes(2, byteorder='big')
            extra_data = fruit_x_pos + fruit_y_pos
            response = header_plus_data + extra_data

        self.totalBytesSend[self.assigned_id[connection_socket]] += len(response)
        self.ByteSend[self.assigned_id[connection_socket]].append(len(response))

        self.average_bits_send[self.assigned_id[connection_socket]].append(round(
            (self.totalBytesSend[self.assigned_id[connection_socket]]) / (
                        len(self.average_bits_send[self.assigned_id[connection_socket]]) + 1), 4))


        return response

    def initialize(self):
        if len(sys.argv) == 4:
            try:
                if int(sys.argv[3]) in [2, 3, 4]:
                    self.N_OF_PLAYERS = int(sys.argv[3])
                    self.assignable_ids = list(
                        range(0, self.N_OF_PLAYERS))  # Each player gets an ID assigned by the server
                else:
                    print("Max 4 players! Usage: python", sys.argv[0], "<port>", "<host>", "<[OPTIONAL]n_of_player>(default 2) <[OPTIONAL]plot? (y/n)>(default: 'n')")
                    sys.exit(1)
            except:
                print("Usage: python", sys.argv[0], "<port>", "<host>", "<[OPTIONAL]n_of_player>(default 2) <[OPTIONAL]plot? (y/n)>(default: 'n')")
                sys.exit(1)

        if len(sys.argv) == 5:
            try:
                if int(sys.argv[3]) in [2, 3, 4]:
                    self.N_OF_PLAYERS = int(sys.argv[3])
                    self.assignable_ids = list(
                        range(0, self.N_OF_PLAYERS))  # Each player gets an ID assigned by the server
                else:
                    print("Max 4 players! Usage: python", sys.argv[0], "<port>", "<host>",
                          "<[OPTIONAL]n_of_player>(default 2) <[OPTIONAL]plot? (y/n)>(default: 'n')")
                    sys.exit(1)
            except:
                print("Usage: python", sys.argv[0], "<port>", "<host>",
                      "<[OPTIONAL]n_of_player>(default 2) <[OPTIONAL]plot? (y/n)>(default: 'n')")
                sys.exit(1)

            if sys.argv[4] == "y":
                self.plot = True
            elif sys.argv[4] == "n":
                self.plot = False
            else:
                print("Usage: python", sys.argv[0], "<port>", "<host>", "<[OPTIONAL]n_of_player>(default 2) <[OPTIONAL]plot? (y/n)>(default: 'n')")
                sys.exit(1)

        elif len(sys.argv) > 5 or len(sys.argv) < 2:
            print("Usage: python", sys.argv[0], "<port>", "<host>", "<[OPTIONAL]n_of_player>(default 2) <[OPTIONAL]plot? (y/n)>(default: 'n')")
            sys.exit(1)

        PORT = int(sys.argv[1])

        HOST = str(sys.argv[2])
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((HOST, PORT))
        self.server_socket.settimeout(1)
        print("[SERVER RUNNING]")
        return

    def initializeClient(self, client_socket):
        """
        Initializing parameters that will be needed for each client.
        """
        self.connected_sockets += [client_socket]
        self.RTT_clients[client_socket] = 0
        self.n_of_RTT_clients[client_socket] = 0
        self.waiting_ping[client_socket] = False
        self.n_of_message[client_socket] = 1
        self.ping_update_rate[client_socket] = self.n_of_probing_ping*2  # the ping update rate is chosen
        assigned_id = self.assignable_ids[0]
        self.assignable_ids.remove(assigned_id)
        self.assigned_id[client_socket] = assigned_id

        self.RTT_SAVED_DICT[self.assigned_id[client_socket]] = []
        self.N_RTT_SAVED_DICT[self.assigned_id[client_socket]] = []
        self.totalBytesSend[self.assigned_id[client_socket]] = 0
        self.ByteSend[self.assigned_id[client_socket]] = []
        self.average_bits_send[self.assigned_id[client_socket]] = []

        response = self.CreateResponse(1, connection_socket=client_socket)
        client_socket.sendall(response)  # Sending client his assigned id
        client_socket.settimeout(0.1)
        return


    def disconnectClient(self, connection_socket):
        """"
        Handling the disconnect of client
        """
        assigned_id = self.assigned_id[connection_socket]  # Assigned of leaving player
        self.assignable_ids.append(assigned_id)
        self.assigned_id_history[connection_socket] = assigned_id  # This needs to be done, to be able to name each player
                                                                    # on the plots that will follow later on.
        try:
            self.connected_sockets.remove(connection_socket)
            connection_socket.close()
            del self.messages[connection_socket]
            del self.RTT_clients[connection_socket]
            del self.n_of_RTT_clients[connection_socket]
            del self.n_of_message[connection_socket]
        except:
            # If socket is closed, then the keys won't match anymore.
            for con in self.connected_sockets:
                con.close()
            self.connected_sockets = {}


        for con in self.connected_sockets:
            # Notifying all other client of disconnect
            response = self.CreateResponse(4, con, leaving_id=assigned_id)
            con.sendall(response)


        if len(self.connected_sockets) == 1:
            self.all_players_active = False
            self.game_started = False
            # If there is only one player left, game ends.
            if self.plot:
                try:
                    PlotCombined(self.N_RTT_SAVED_DICT, self.RTT_SAVED_DICT, self.average_bits_send, 10, self.totalBytesSend)
                    time.sleep(1)
                    HistogramBitSend(self.ByteSend)
                except RuntimeError:
                    print('the plotting did not work')

            # The already obtained values for the left socket must be reset
            left_socket = self.connected_sockets[0]
            self.RTT_SAVED_DICT[self.assigned_id[left_socket]] = []
            self.N_RTT_SAVED_DICT[self.assigned_id[left_socket]] = []
            self.totalBytesSend[self.assigned_id[left_socket]] = 0
            self.average_bits_send[self.assigned_id[left_socket]] = []
        return


    def sendingPing(self, connection_socket):
        """"
        Ping is sent:
        -before the game start
        -during the game, after every 20 messages
        """
        self.waiting_ping[connection_socket] = True
        response = self.CreateResponse(5, connection_socket)
        connection_socket.sendall(response)
        self.n_of_message[connection_socket] = 1  # Resetting number of messages till next ping.
        return


    def receivingPing(self, connection_socket, msg, time_received):
        """"
        Handling ping. The RTT is handled in two different manners:
            1. Before the game starts: the average of RTT is taken
            2. Once the game starts, we follow a similar trend as done in the congestion control, where the RTT
                estimated is done by considering estimatedRTT + alpha*estimatedRTT. Here alpha is too chosen to be
                0.125
        """

        time_stamp = int.from_bytes(msg[1:3], byteorder='big', signed=False)
        self.waiting_ping[connection_socket] = False  # This connection socket could handle a new ping message.
        RTT = (time_received - time_stamp)
        if RTT < 0:
            # If remainder is negative(remember we work in module 655356!)
            RTT += TIME_FRAME_MODULO
        if not self.game_started:

            total_RTT = (self.RTT_clients[connection_socket] * self.n_of_RTT_clients[connection_socket] + RTT)
            n_of_total_RTT = self.n_of_RTT_clients[connection_socket] + 1
            self.RTT_clients[connection_socket] = total_RTT / n_of_total_RTT
        else:
            self.RTT_clients[connection_socket] = (1 - self.alpha) * self.RTT_clients[
                connection_socket] + self.alpha * RTT
        self.n_of_RTT_clients[connection_socket] += 1

        # Saving number of RTT, together with RTT for later plotting:
        self.N_RTT_SAVED_DICT[self.assigned_id[connection_socket]].append(self.n_of_RTT_clients[connection_socket])
        self.RTT_SAVED_DICT[self.assigned_id[connection_socket]].append(self.RTT_clients[connection_socket])
        return

    def startGame(self):
        """
        Game is started. The already calculated ping is incorporated so that the clients start with the same amount of
        time.
        """
        for con in self.connected_sockets:
            self.ping_update_rate[con] = max(100//self.RTT_clients[con], 70)  # We would like to update the ping every 200 ms

            time_delay = self.RTT_clients[con]/2  # Estimated time it takes the message from server, to reach client.
            response = self.CreateResponse(2, con, total_game_time=round(total_game_time - time_delay))
            con.sendall(response)
            self.game_started = True
            print("[GAME STARTS]")
        return

    def MovementAndFruitUpdate(self, msg, connection_socket, msg_id):
        """
        For synchronously play, there has been chosen to send every change first to the server, which sends it to the
        other clients, but echoes it back to the player. This may seem obsolete, but in this way it keeps the difference
        in PING of the different clients in mind; it makes inner calculations so that all client(including the player)
        gets at the SAME time the position displacement. This way there is no need(expect to extreme edge cases) for the
        server to keep a buffer, and to 'reload' previous positions on each client in case there is lag. In this way,
        the (multiple) clients are also playing on the same 'internet quality', meaning the same latency. In this manner,
        the game is made equal, which does punish the player(s) with the better connection, but this seemed for me as the
        best option, as otherwise it wouldn't be a 'square' game anyway.

        The calculation is done as follows:
        There is created a list of the clients based on their RTT, in descending order(this is sorted_clients_on_RTT).
        The max RTT is also fetched out of self.RTT_clients.values(). To synschronize the time the different clients
        get the message, we first send the person with the biggest RTT(RTT_{max}). The message two the second highest
        RTT(call it RTT_{2}) is sent after there has been waited for (RTT_{max} - RTT_{2})/2(dividing by two because
        RTT is two-way, but we only consider the one-way in this case). If there is also a third client,
        then we also take the RTT of this one(RTT_{3}). To synchronize this one, we let the program wait for
        (RTT_{2} - RTT_{3})/2. In this way, all client 3 and 2 would get (ideally) at the same time the message, but
        because client 2 and 1 too (ideally) got the message at the same time; all clients get it at the same time!
        Note that the variable previous connection takes care of taking the difference in RTT between previous and
        current client.

        Apart from this, we also take into the account of the customer that 'echo' back their own position to the
        server. In this case, if client 1 has a high ping, but client 2 a low one then client 2 will get a faster
        response to his moves compared to the positions that client 1 gets from himself. This essentially makes
        client 2 faster; undermining our 'square game'! To account for this, we need to 'slow down' the faster clients.
        This is done by adding the difference in time it takes client 1 to send something to the server, compared to
        that of client 2 sending it.

        NOTE: in the 2-player case, there time_delay = time_wait always, but this gets more interesting in the n-player
        implementation. For which this protocol is designed.
        """
        sorted_clients_on_RTT = sorted(self.RTT_clients, key=self.RTT_clients.get, reverse=True)
        client_with_highest_RTT = sorted_clients_on_RTT[0]
        max_RTT = max(self.RTT_clients.values())  # Taking out the highest RTT out of the list.

        if msg_id == 6:
            self.fruit_x = random.randrange(45, 78 * 15)
            self.fruit_y = random.randrange(60, 28 * 15)

        # Delay, to ensure that each client has the same 'echo' position update.
        time_delay = (max_RTT - self.RTT_clients[connection_socket]) / 2
        time.sleep(time_delay / 1000)

        previous_connection = client_with_highest_RTT
        for con in sorted_clients_on_RTT:
            time_wait = (self.RTT_clients[previous_connection] - self.RTT_clients[con])/2
            time.sleep(time_wait / 1000)
            response = self.CreateResponse(msg_id, con, client_msg=msg)
            con.sendall(response)
            previous_connection = con
        return

    def identifyTypeOfMessage(self, msg):
        """
        Because TCP is stream-oriented, and we work with bytes, there is no 'endpoint' indication. This can only be done
        with looking at the msg_id in the header, look up how long the message would be with this msg_id, and cut it off
        the message coming in. If the message is missing a part, we return False so that the server can continue to take
        the next part. If there is no missing part, then we return the extracted message.

        Server only gets three type of messages from the client:
            -message with ID equal to 3: this is position change. In this id, there are two variants:
                1. The absolute position. This one contains the header, AND the x and y position, which are 4 bytes.
                2. The relative position difference(direction). This one has only the header, no data
            -message with ID equal to 6. This message is apart from the message ID, identical to the ID 3. The only
            difference is that his id notifies the server that a fruit was taken.
            -message ID equal to 5: this is the ping message. This contains the header(1 byte), and the timestamp.
            This timestamp is 16-bit, thus 2 byte long.
            -message ID 4; the client leaves the game. This has only the header(1 byte)

        :return:
        1.The length of the message, in bytes
        2.The message ID
        """
        header_string = ''
        header = msg[0]
        for bit in range(7, -1, -1):
            header_string += str((header & (1 << bit)) >> bit)
        msg_id = int(header_string[0:3], 2)
        direction = int(header_string[5:8], 2)

        if msg_id == 3 or msg_id == 6:
            if direction == 0:
                # If direction is 0, thus absolute pos is sent, then the msg is 1(header) + 4(data) = 5 bytes long
                if len(msg) < 5:
                    # In case data has come partially in
                    return -1, -1
                return 5, msg_id
            else:
                # there is only a message sent, thus the header only.
                return 1, msg_id
        elif msg_id == 5:
            # Ping only has the header, and time stamp(data), which in total has 3 bytes.
            if len(msg) < 3:
                # in case the data has come partially
                return -1, -1
            return 3, msg_id
        elif msg_id == 4:
            # If client is leaving game, then only the header is sent
            return 1, msg_id
def main():
    server = Server()
    server.initialize()

    while server.running:
        try:
            try:
                server.server_socket.listen()
                if len(server.assignable_ids) == 0:
                    # If all ids are already distributed(meaning max players achieved) then newly coming in sockets
                    # will need to wait.
                    continue

                connection, addr = server.server_socket.accept()

                server.initializeClient(connection)

                if len(server.connected_sockets) == server.N_OF_PLAYERS:
                    # All players are active.
                    server.all_players_active = True
                threading.Thread(target=handleClient, args=(connection, server)).start()

            except socket.timeout:
                continue
        except Exception as error:
            server.server_socket.close()
            break

    server.running = False
    server.server_socket.close()




def handleClient(connection_socket, server):
    server.messages[connection_socket] = b''
    while server.running:
        try:
            try:
                msg = connection_socket.recv(1024)
                if msg:
                    time_received = (time.time()*1000)%TIME_FRAME_MODULO
                    server.messages[connection_socket] += msg  # In case message comes in parts(TCP is stream-oriented)
                    server.n_of_message[connection_socket] += 1

                    n_of_bytes, msg_id = server.identifyTypeOfMessage(server.messages[connection_socket])

                    if n_of_bytes < 0:
                        # If message is not complete, then we need to look if new has come in.
                        continue
                    number_of_bytes = n_of_bytes
                    server.totalBytesSend[server.assigned_id[connection_socket]] += number_of_bytes
                    server.ByteSend[server.assigned_id[connection_socket]].append(number_of_bytes)

                    server.average_bits_send[server.assigned_id[connection_socket]].append(round(server.totalBytesSend[server.assigned_id[connection_socket]]/(len(server.average_bits_send[server.assigned_id[connection_socket]])+1), 4))

                    msg = server.messages[connection_socket][:n_of_bytes]
                    server.messages[connection_socket] = server.messages[connection_socket][n_of_bytes:]
                    if msg_id == 4:  # Closing connection with player
                        server.disconnectClient(connection_socket)
                        break

                    if server.all_players_active:  # Only sending position of Player through if server is initialized.

                        if (server.n_of_message[connection_socket]) >= server.ping_update_rate[connection_socket] and not server.waiting_ping[connection_socket]:
                            server.sendingPing(connection_socket)
                            continue

                        if server.waiting_ping[connection_socket]:
                            if msg_id == 5:
                                server.receivingPing(connection_socket, msg, time_received)

                            if min(list(server.n_of_RTT_clients.values())) == server.n_of_probing_ping and not server.game_started:
                                time.sleep(0.2)
                                server.startGame()


                        elif min(list(server.n_of_RTT_clients.values())) >= server.n_of_probing_ping:
                            # Handling other messages, if the probing is finished.
                            server.MovementAndFruitUpdate(msg, connection_socket, msg_id)


            except socket.timeout:
                """"
                To not create another thread, the ping before the game(thus game_started = False)
                is done one by one, by each time looking at
                the client which has the smallest number of RTTs gotten. This way the server builds it way up to the
                probing number of RTTs.
                """

                if not server.game_started:
                    min_RTT_client = min(server.n_of_RTT_clients, key=server.n_of_RTT_clients.get)
                    if (server.n_of_RTT_clients[min_RTT_client]) < server.n_of_probing_ping and not server.waiting_ping[min_RTT_client] and server.all_players_active:
                        server.sendingPing(min_RTT_client)
                continue



        except Exception as e:
            server.disconnectClient(connection_socket)
            return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[SERVER STOPPED]")
        sys.exit()

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import numpy as np


def moving_average(data, window_size):
    """"
    Because the data received will fluctuate often between absolute position send(5 bytes), and the relative
    displacement sent(1 byte) we smooth the graph.
    """
    weights = np.repeat(1.0, window_size) / window_size
    return np.convolve(data, weights, 'valid')


def HistogramBitSend(bytes_dict):
    """
    Shows histogram of the frequency of messages send, classified by number of bytes. The histogram is made
    for each player
    """
    # Create subplots for each client
    fig, axs = plt.subplots(len(bytes_dict), 1, figsize=(10, 5 * len(bytes_dict)), sharex=False)

    # Iterating over each client
    for i, (player_id, rtt_values) in enumerate(bytes_dict.items()):
        bin_edges = np.arange(min(rtt_values) - 0.5, max(rtt_values) + 1.5, 1)

        n, bins, patches = axs[i].hist(rtt_values, bins=bin_edges, edgecolor='black')

        # Calculating bin centers
        bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

        # Adding counts as text annotations at the center of each bin
        for count, bin_center in zip(n, bin_centers):
            axs[i].text(bin_center, count, f"{str(round(100 * count / sum(n), 2))}%", ha='center', va='bottom')

        axs[i].set_title(f'Histogram for PLAYER {player_id}')
        axs[i].set_xlabel('Number of bytes')
        axs[i].set_ylabel('Frequency')

    plt.tight_layout()

    plt.show()
    return

def PlotCombined(num_rtt_dict, rtt_dict, bytes_dict, window_size, total_bytes):
    """"
    Combined plot of:
        -RTT of each client in function the index/number of the ping message.
        -Plot of average byte send/received from client<->server(smoothed with window size 10).
    """
    # Creating a single figure with two subplots
    fig, axs = plt.subplots(2, 1, figsize=(10, 8), sharex=False)

    for player_id, rtt_values in rtt_dict.items():
        num_rtt_values = num_rtt_dict[player_id]
        axs[0].plot(num_rtt_values, rtt_values, label=f"PLAYER {player_id}")

    axs[0].set_ylabel('RTT values(ms)')
    axs[0].set_xlabel('Number of ping message')
    axs[0].legend()

    # Plotting smoothed, window size 10, byte values
    for player_id, byte_values in bytes_dict.items():
        smoothed_data = moving_average(byte_values, window_size)
        axs[1].plot(smoothed_data, label=f'PLAYER {player_id} (total data transfer: {round(total_bytes[player_id]/1000, 2)} KB)')

    axs[1].set_xlabel('Message number')
    axs[1].set_ylabel('AVERAGE byte values')


    axs[1].legend()

    plt.suptitle('Combined Plot of RTT, and average Bytes(smoothed) send/received')

    plt.tight_layout()

    plt.show()

    return

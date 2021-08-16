import tornado.ioloop
import tornado.web


import copy
import time
import threading
from acconeer.exptool import configs
from acconeer.exptool.clients import UARTClient
from multiprocessing import Process, Value

import sys
from signal import signal, SIGINT
from sys import exit
import numpy as np

distance_measurement = 0.0

distrance = 0
max_value = 0

dead_thread = False

def handler(signal_received, frame):
    global dead_thread
    dead_thread = True
    print('SIGINT or CTRL-C detected. Exiting gracefully')
    exit(0)


def getDistLabels(start, end, length):
    # range(start, end, step=step)
    step = (end - start) / length
    arr = []
    for i in range(0, length):
        dist = start + step * i
        arr.append(dist)
    return arr


def loop_distance_getter(port, start, end, rate, out_value=None, out_max_global=None,
                         out_array_global=None, out_array_distance=None):
    global distance_measurement
    global distance_at
    global max_value
    try:
        client = UARTClient(port)
        config = configs.EnvelopeServiceConfig()
        config.sensor = [1]
        config.range_interval = [start, end]
        config.update_rate = rate

        session_info = client.setup_session(config)
        print("Session info:\n", session_info, "\n")

        client.start_session()
        info, data = client.get_next()
        labels = getDistLabels(start, end, data.size)

        window_position = 0
        window_width = 10

        while True:
            info, data = client.get_next()
            max = np.amax(data)
            index = np.where(data == max)[0][0]
            print("max:", max, "at:", labels[index])
            distance_at = labels[index]
            max_value = max
            if out_array_distance is not None:
                out_array_distance[window_position] = copy.copy(labels[index])
                out_array_distance[window_position + 1] = max
            if out_max_global is not None:
                out_max_global.value = max
            if out_array_global is not None:
                out_array_global[:data.size] = copy.copy(data.tolist())
                print("array size", data.size)
            if out_value is not None:
                out_value.value = copy.copy(labels[index])
            time.sleep(0.01)
            window_position += 2
            if window_position >= window_width * 2:
                window_position = 0

            if dead_thread:
                print("stoping thread measure")
                break
        print("Disconnecting...")
        client.disconnect()

    except Exception as e:
        print(e)


class RadarHandler(tornado.web.RequestHandler):
    def get(self):
        global max_value
        global distance_at
        self.write({"distance": distance_at, "max_value": max_value})

def make_app():
    return tornado.web.Application([
        (r"/radar", RadarHandler),
    ])

if __name__ == "__main__":
    signal(SIGINT, handler)
    print("running, press CTRL-C to exit...")
    # loop_distance_getter(sys.argv[1], start=1, end=7, rate=2)
    x = threading.Thread(target=loop_distance_getter, args=(sys.argv[1], 1, 7, 2,))
    x.start()
    app = make_app()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()

import os
import sys
from PyQt6.QtCore import QCoreApplication, QByteArray, QProcess
from PyQt6.QtNetwork import QLocalSocket

HOST = 'localhost'
SERVER_PATH = './firefox_go.exe'

class ClientApp(QCoreApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.client_socket = QLocalSocket()

        # Connect to server
        print("Attempting to connect to server...")
        self.client_socket.errorOccurred.connect(self.handle_socket_error)
        self.client_socket.connectToServer(HOST)

        # Once connected, send a signal to the server
        self.client_socket.connected.connect(self.send_ping)

    def send_ping(self):
        print("Connected to server, sending ping...")
        data = b"1"
        self.client_socket.write(data)
        self.shutdown()

    def handle_socket_error(self, socket_error):
        if socket_error == QLocalSocket.LocalSocketError.ConnectionRefusedError:
            print("Could not connect to server. Starting server...")
            self.start_server()
        else:
            print("Socket error: ", socket_error)
            self.shutdown()

    def start_server(self):
        # Use QProcess to start the server
        self.server_process = QProcess(self)
        self.server_process.start(SERVER_PATH)

        # Check the process status
        if self.server_process.state() != QProcess.ProcessState.Starting:
            print("Server process failed to start. State: ", self.server_process.state())
            self.shutdown()

        # Print any output from the server process
        self.server_process.readyReadStandardOutput.connect(self.print_server_output)

    def print_server_output(self):
        print("Server output: ", self.server_process.readAllStandardOutput().data().decode('utf-8'))
        self.shutdown()

    def shutdown(self):
        print("Shutting down...")
        if self.client_socket:
            print("Closing client socket...")
            self.client_socket.close()

        if hasattr(self, 'server_process'):
            print("Killing server process...")
            self.server_process.kill()
        
        self.quit()

if __name__ == '__main__':
    app = ClientApp(sys.argv)
    sys.exit(app.exec())

import socket
import threading
import select
import signal
import sys
import time
import getopt

# Listen
LISTENING_ADDR = '0.0.0.0'
if len(sys.argv) > 1:
    LISTENING_PORT = sys.argv[1]
else:
    LISTENING_PORT = 80  
# Pass
PASS = ''

# CONST
BUFLEN = 4096 * 4
TIMEOUT = 60
DEFAULT_HOST = '127.0.0.1:22'
RESPONSE = ''  # Cambiado a bytes para Python 3

class Server(threading.Thread):
    def __init__(self, host, port):
        threading.Thread.__init__(self)
        self.running = False
        self.host = host
        self.port = port
        self.threads = []
        self.threadsLock = threading.Lock()
        self.logLock = threading.Lock()

    def run(self):
        self.soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.soc.settimeout(2)
        intport = int(self.port)
        self.soc.bind((self.host, intport))
        self.soc.listen(0)
        self.running = True

        try:
            while self.running:
                try:
                    c, addr = self.soc.accept()
                    c.setblocking(1)
                except socket.timeout:
                    continue

                conn = ConnectionHandler(c, self, addr)
                conn.start()
                self.addConn(conn)
        finally:
            self.running = False
            self.soc.close()

    def printLog(self, log):
        with self.logLock:
            print(log)

    def addConn(self, conn):
        with self.threadsLock:
            if self.running:
                self.threads.append(conn)

    def removeConn(self, conn):
        with self.threadsLock:
            self.threads.remove(conn)

    def close(self):
        self.running = False
        with self.threadsLock:
            threads = list(self.threads)
            for c in threads:
                c.close()


class ConnectionHandler(threading.Thread):
    def __init__(self, socClient, server, addr):
        threading.Thread.__init__(self)
        self.clientClosed = False
        self.targetClosed = True
        self.client = socClient
        self.client_buffer = b''
        self.server = server
        self.log = 'Connection: ' + str(addr)

    def close(self):
        if not self.clientClosed:
            try:
                self.client.shutdown(socket.SHUT_RDWR)
                self.client.close()
            except Exception as e:
                print(f"Error closing client socket: {e}")
            finally:
                self.clientClosed = True

        if not self.targetClosed:
            try:
                self.target.shutdown(socket.SHUT_RDWR)
                self.target.close()
            except Exception as e:
                print(f"Error closing target socket: {e}")
            finally:
                self.targetClosed = True

    def run(self):
        try:
            self.client_buffer = self.client.recv(BUFLEN)

            hostPort = self.findHeader(self.client_buffer.decode(), 'X-Real-Host')

            if hostPort == '':
                hostPort = DEFAULT_HOST

            split = self.findHeader(self.client_buffer.decode(), 'X-Split')

            if split != '':
                _ = self.client.recv(BUFLEN)

            if hostPort != '':
                passwd = self.findHeader(self.client_buffer.decode(), 'X-Pass')
                
                if len(PASS) != 0 and passwd == PASS:
                    self.method_CONNECT(hostPort)
                elif len(PASS) != 0 and passwd != PASS:
                    self.client.send(b'HTTP/1.1 400 WrongPass!\r\n\r\n')
                elif hostPort.startswith('127.0.0.1') or hostPort.startswith('localhost'):
                    self.method_CONNECT(hostPort)
                else:
                    self.client.send(b'HTTP/1.1 403 Forbidden!\r\n\r\n')
            else:
                print('- No X-Real-Host!')
                self.client.send(b'HTTP/1.1 400 NoXRealHost!\r\n\r\n')

        except Exception as e:
            self.log += ' - error: ' + str(e)
            self.server.printLog(self.log)
        finally:
            self.close()
            self.server.removeConn(self)

    def findHeader(self, head, header):
        aux = head.find(header + ': ')
        
        if aux == -1:
            return ''

        aux = head.find(':', aux)
        head = head[aux + 2:]
        aux = head.find('\r\n')

        if aux == -1:
            return ''

        return head[:aux]

    def connect_target(self, host):
        i = host.find(':')
        
        if i != -1:
            port = int(host[i + 1:])
            host = host[:i]
        else:
            port = 443 if hasattr(self, 'method') and self.method == 'CONNECT' else int(sys.argv[1])

        (soc_family, soc_type, proto, _, address) = socket.getaddrinfo(host, port)[0]

        self.target = socket.socket(soc_family, soc_type, proto)
        self.targetClosed = False
        self.target.connect(address)

    def method_CONNECT(self, path):
        self.log += ' - CONNECT ' + path

        # Cambiar RESPONSE a bytes si es necesario.
        response_bytes = RESPONSE or b'HTTP/1.1 200 Connection established\r\n\r\n'
        
        # Enviar respuesta al cliente.
        try:
            # Enviar respuesta inicial.
            if isinstance(response_bytes, str):
                response_bytes.encode()  # Asegúrate de que sea bytes.
                
            # Enviar respuesta al cliente.
            sent_bytes_count = 0
            
            while sent_bytes_count < len(response_bytes):
                sent_bytes_count += self.client.send(response_bytes[sent_bytes_count:])
                
            # Limpiar el buffer del cliente.
            self.client_buffer = b''

            # Log de conexión.
            print(f"Log: {self.log}")
            
            # Iniciar el método doCONNECT.
            return (self.doCONNECT())
        
        except Exception as e:
          print(f"Error in method_CONNECT: {e}")

    def doCONNECT(self):
        
         socs = [self.client, getattr(self,'target', None)]
         count=0 
         error=False 
         while True: 
             count+=1 
             (recv, _, err) = select.select(socs,[ ], socs ,3) 
             if err: 
                 error=True 
             if recv: 
                 for in_ in recv: 
                     try: 
                         data=in_.recv(BUFLEN) 
                         if data: 
                             if in_ is getattr(self,'target', None): 
                                 sent_bytes_count=0 
                                 while sent_bytes_count < len(data): 
                                     sent_bytes_count+=self.client.send(data[sent_bytes_count:]) 
                             else: 
                                 sent_bytes_count=0 
                                 while sent_bytes_count < len(data): 
                                     sent_bytes_count+=self.target.send(data[sent_bytes_count:]) 

                             count=0 
                         else: break 

                     except Exception as e: 
                         error=True 
                         break 

             if count==TIMEOUT: error=True 

             if error: break 


def print_usage():
    print('Usage: proxy.py -p <port>')
    print('       proxy.py -b <bindAddr> -p <port>')
    print('       proxy.py -b 0.0.0.0 -p 80')

def parse_args(argv):
    global LISTENING_ADDR
    global LISTENING_PORT
    
    try:
        opts, args = getopt.getopt(argv,"hb:p:",["bind=","port="])
    except getopt.GetoptError:
        print_usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print_usage()
            sys.exit()
        
		elif opt in ("-b", "--bind"):
			LISTENING_ADDR=arg
		
		elif opt in ("-p", "--port"):
			LISTENING_PORT=int(arg)


def main(host=LISTENING_ADDR, port=LISTENING_PORT):
    print("\n:-------PythonProxy-------:\n")
    print("Listening addr: " + LISTENING_ADDR)
    print("Listening port: " + str(LISTENING_PORT) + "\n")
    print(":-------------------------:\n")
    
	server=Server(LISTENING_ADDR,LISTENING_PORT) 
	server.start() 

	while True: 
		try: 
			time.sleep(2) 
		
		except KeyboardInterrupt: 
			print('Stopping...') 
			server.close() 
			break


if __name__ == '__main__':
	parse_args(sys.argv[1:])
	main()

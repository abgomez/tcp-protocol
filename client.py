import sys
import argparse
import traceback
import re
import random
import time
from select import *
from socket import *

#Global variables
filename = ""                                        #file to process
debug = 0                                            #verbose mode default off
sockNames = {}                                       #map sockets to name
nextClientNumber = 0                                 #each client is assigned a unique id
liveClients = set()                                  #set of live clients
deadClients = set()                                  #set of dead clients
mode = 'u'                                           #client mode, get or put file

#map socket:object
def lookupSocknames(socks):
    return [ sockName(s) for s in socks ]

#client class
#the class will create an object of type client, it will handle the functions
#to communicate with the server.
class Client:
    def __init__(self, af, socktype, saddr):
        global nextClientNumber
        global liveClients, deadClients
        global filename

        self.serverAddr = saddr
        self.numSent, self.numRecv = 0,0
        self.allSent = 0
        self.error = 0
        self.isDone = 0
        self.clientIndex = clientIndex = nextClientNumber
        nextClientNumber += 1
        self.serverSocket = serverSocket = socket(af, socktype)
        if debug:
            print "New client #%d to %s" %(clientIndex, repr(saddr))
        serverSocket.setblocking(False)
        serverSocket.connect_ex(saddr)
        liveClients.add(self)
    def doSend(self):
        try:
            #detect mode of operations
            if mode == 'g':
                    message = "get:"+filename
                    if debug:
                        print "Message to Server: %s" % message
                    self.numSent += self.serverSocket.send(message)
                    self.allSent = 1
                    self.serverSocket.shutdown(SHUT_WR)
            #open file
            #if debug:
            #    print "Sending file: %s" % filename
            #sendFile = open(filename)
            #readFile = sendFile.read(1024)
            #while readFile:
                #print readFile
            #    self.numSent += self.serverSocket.send(readFile)
        #        readFile = sendFile.read(1024)
        #        time.sleep (1)
        #    sendFile.close()
        #    self.allSent = 1
        #    self.serverSocket.shutdown(SHUT_WR)

            #if not os.path.exists(fileName):
            #    print "Input File does not exists in current directory: %s" % fileName
            #    sys.exit(1)
            #self.numSent += self.serverSocket.send("a"*(random.randrange(1,2048)))
        except Exception as e:
            self.errorAbort("can't send: %s" % e)
            return
        if random.randrange(0,200) == 0:
            self.allSent = 1
            self.serverSocket.shutdown(SHUT_WR)
    def doRecv(self):
        try:
            serverMessage = self.serverSocket.recv(1024)
            if debug:
                print "\n\nMessage received: %s" % serverMessage
            #figure out what type of message we got
            typeMsg = serverMessage[0:3]
            if typeMsg == 'err':
                self.errorAbort("Incorrect File Requested")
            n = len(serverMessage)
        except Exception as e:
            print "doRecv on dead socket"
            print e
            self.done()
            return
        self.numRecv += n
        #if self.numRecv > self.numSent:
        #    self.errorAbort("sent=%d < recd=%d" %  (self.numSent, self.numRecv))
        if n != 0:
            return
        if debug: print "client %d: zero length read" % self.clientIndex
        # zero length read (done)
        self.done()
        #if self.numRecv == self.numSent:
        #    self.done()
        #if self.numRecv == 8080:
        #    self.done()
        #else:
        #    self.errorAbort("sent=%d but recd=%d" %  (self.numSent, self.numRecv))
    def doErr(self, msg=""):
        error("socket error")
    def checkWrite(self):
        if self.allSent:
            return None
        else:
            return self.serverSocket
    def checkRead(self):
        if self.isDone:
            return None
        else:
            return self.serverSocket
    def done(self):
        self.isDone = 1
        self.allSent =1
        #if self.numSent != self.numRecv: self.error = 1
        try:
            self.serverSocket(close)
        except:
            pass
        print "client %d done (error=%d)" % (self.clientIndex, self.error)
        deadClients.add(self)
        try: liveClients.remove(self)
        except: pass
    def errorAbort(self, msg):
        self.allSent =1
        self.error = 1
        print "FAILURE client %d: %s" % (self.clientIndex, msg)
        self.done()


#parse arguments
def format_server_addr(address):
    addr, port = address.split(":")
    return (addr, int(port))

parser = argparse.ArgumentParser(
        prog='client',
        description='TCP file transfer protocol')
parser.add_argument('--serverAddr', '-s',
                    metavar='host:port',
                    dest='server',
                    type=format_server_addr,
                    default=('localhost',50001),
                    help='address of the server in format: serverIP:port')
parser.add_argument('--debug', '-d',
                    dest='debug',
                    action='store_true',
                    help='show verbose logs when performing operations')
parser.add_argument('--numClient', '-nc',
                    dest='clients',
                    type=int,
                    default=1,
                    help='Number of clients that will connect to the server')
#the client can only perform one operation
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--get', '-g',
                    metavar='filename',
                    dest='get',
                    type=str,
                    help='flag to get any file from the server')
group.add_argument('--put', '-p',
                    metavar='filename',
                    dest='put',
                    type=str,
                    help='flag to sent any file from the server')


args = parser.parse_args(sys.argv[1:])
if args.server:
    serverAddr = args.server
if args.clients:
    numClients = args.clients
if args.debug:
    debug = 1
if args.get:
    filename = args.get
    mode = 'g'
else:
    filename = args.put
    mode = 'p'
if debug:
    print "Proccessing File: %s" % filename
    print "Server at: %s , port: %d" % ( serverAddr[0], serverAddr[1] )
    print "Number of Clients: %d" % numClients

###########################################
################ MAIN #####################
###########################################

#create clients and connect to server
for client in range(numClients):
    liveClients.add(Client(AF_INET, SOCK_STREAM, serverAddr))

#connection alive, listen for any update in the client port
while len(liveClients):
    rmap, wmap, xmap = {},{},{}  #socket:object mapping for select
    for client in liveClients:
        sock = client.checkRead()
        if (sock): rmap[sock] = client
        sock = client.checkWrite()
        if (sock): wmap[sock] = client
        xmap[client.serverSocket] = client
    #if debug:
        #print "select parms (r,w,x):", [ repr([ sockNames[s] for s in sset] ) for sset in rmap.keys() ]
        #print "select parms (r,w,x):", [ repr([ sockNames[s] for s in sset] ) for sset in [rmap.keys(), wmap.keys(), xmap.keys()] ]
    rset, wset, xset = select(rmap.keys(), wmap.keys(), xmap.keys(),60)
    #if debug:
        #print "select returned (r,w,x):", [ repr([ sockNames[s] for s in sset] ) for sset in [rset,wset,xset] ]
    for sock in xset:
        xmap[sock].doErr()
    for sock in rset:
        rmap[sock].doRecv()
    for sock in wset:
        wmap[sock].doSend()


numFailed = 0
for client in deadClients:
    err = client.error
    print "Client %d Succeeded=%s, Bytes sent=%d, rec'd=%d" % (client.clientIndex, not err, client.numSent, client.numRecv)
    if err:
        numFailed += 1
print "%d Clients failed." % numFailed

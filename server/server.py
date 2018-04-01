import sys, os
import traceback
import argparse
import time
from select import *
from socket import *

import re

#fileName = ""                # file to process
sockNames = {}               # from socket to name
nextConnectionNumber = 0     # each connection is assigned a unique id
debug = 0                    #verbose mode default off
connections = set()          #set of open connetions


class Fwd:
    def __init__(self, conn, inSock, outSock, bufCap = 1000):
        self.conn, self.inSock, self.outSock, self.bufCap = conn, inSock, outSock, bufCap
        self.inClosed, self.buf = 0, ""
        self.messageToClient, self.fileName, self.action = "", "", ""
        self.errFlag = 0
    def checkRead(self):
        if len(self.buf) < self.bufCap and not self.inClosed:
            return self.inSock
        else:
            return None
    def checkWrite(self):
        if len(self.buf) > 0:
            return self.outSock
        else:
            return None
    def doRecv(self):
        #global fileName
        #global messageToClient

        b = ""
        clientMessage = ""
        messageToClient = ""
        print "inside doRec"
        try:
            b = self.inSock.recv(self.bufCap - len(self.buf))
            clientMessage = b
            #figure out what we need to do
            #we know that the first three character represent the action requested
            self.action = clientMessage[0:3]
            if self.action == "get":
                if debug: print "Mode: %s" % self.action
                #the client is requesting a file we can safely get the file name
                #open file requested
                self.fileName = clientMessage[4:]
                if debug:
                    print "File: %s" % self.fileName
                if not os.path.exists(self.fileName):
                    print "Input File does not exists in curren t directory: %s" % self.fileName
                    #send error message, set errFlag to 1
                    self.messageToClient = "err:Sorry my child wrong file"
                    self.errFlag = 1
                print "OK on rec"
            else:
                if debug: print "Mode: %s" % action
            if debug:
                print "Message Recieved from client: %s" % clientMessage
            #print "after action"
        except:
            self.conn.die()
        if len(b):
            self.buf += b
        else:
            self.inClosed = 1
        self.checkDone()
    def doSend(self):
        try:
            if self.errFlag:
                if debug:
                    print "Message to Client: %s" % self.messageToClient
                n = self.outSock.send(self.messageToClient)
            else:
                if self.action == "get":
                    #open file
                    if debug:
                        print "Sending file: %s" % self.fileName
                    sendFile = open(self.fileName)
                    readFile = sendFile.read(1024)
                    while readFile:
                        if debug:
                            print readFile
                        n = self.outSock.send(readFile)
                        readFile = sendFile.read(1024)
                        time.sleep(1)
                    #done sending, close connection
                    try:
                        self.outSock.shutdown(SHUT_WR)
                    except:
                        pass
                    self.conn.fwdDone(self)
                    #    self.numSent += self.serverSocket.send(readFile)
                #        readFile = sendFile.read(1024)
                #        time.sleep (1)
            #n = self.outSock.send(self.buf)
            self.buf = self.buf[n:]
        except:
            self.conn.die()
        #self.checkDone()
    def checkDone(self):
        print "checking done"
        print "buf: %d" % len(self.buf)
        print "closed: %d" % self.inClosed
        if len(self.buf) == 0 and self.inClosed:
            try:
                self.outSock.shutdown(SHUT_WR)
            except:
                pass
            self.conn.fwdDone(self)



#class Conn
#class created by Dr. Freudenthal
#the class process connections from clients.
class Conn:
    def __init__(self, csock, caddr): # manage state of client connection
        global nextConnectionNumber
        self.csock = csock      # to client
        self.caddr = caddr
        self.connIndex = connIndex = nextConnectionNumber
        nextConnectionNumber += 1
        self.forwarders = forwarders = set()
        print "New connection #%d from %s" % (connIndex, repr(caddr))
        sockNames[csock] = "C%d:ToClient" % connIndex
        forwarders.add(Fwd(self, csock, csock))
        connections.add(self) #add current connection to the set of connections. for every client we have one connection which contains one forwarder
    def fwdDone(self, forwarder):
        forwarders = self.forwarders
        forwarders.remove(forwarder)
        print "forwarder %s ==> %s from connection %d shutting down" % (sockNames[forwarder.inSock], sockNames[forwarder.outSock], self.connIndex)
        if len(forwarders) == 0:
            self.die()
    def die(self):
        print "connection %d shutting down" % self.connIndex
        for s in [self.csock]:
            del sockNames[s]
            try:
                s.close()
            except:
                pass
        connections.remove(self)
    def doErr(self):
        print "forwarder from client %s failing due to error" % repr(self.caddr)
        die()

#class listener
#class created by Dr. Freudenthal
#the class creates a listener which handles incomming connections from clients.
class Listener:
    def __init__(self, bindaddr, addrFamily=AF_INET, socktype=SOCK_STREAM):
        self.bindaddr = bindaddr
        self.addrFamily, self.socktype = addrFamily, socktype
        self.lsock = lsock = socket(addrFamily, socktype)
        sockNames[lsock] = "listener"
        lsock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        lsock.bind(bindaddr)
        lsock.setblocking(False)
        lsock.listen(2)
    def doRecv(self):
        try:
            csock, caddr = self.lsock.accept() # socket connected to client
            conn = Conn(csock, caddr)
        except:
            print "weird.  listener readable but can't accept!"
            traceback.print_exc(file=sys.stdout)
    def doErr(self):
        print "listener socket failed!!!!!"
        sys.exit(2)
    def checkRead(self):
        return self.lsock
    def checkWrite(self):
        return None
    def checkErr(self):
        return self.lsock

def lookupSocknames(socks):
    return [ sockName(s) for s in socks ]

#parse arguments
parser = argparse.ArgumentParser(
        prog='server',
        description='TCP file transfer protocol')
parser.add_argument('--serverAddr', '-s',
                    metavar='port',
                    dest='server',
                    type=int,
                    default=50001,
                    help='address of thse server in format: serverIP:port')
parser.add_argument('--debug', '-d',
                    dest='debug',
                    action='store_true',
                    help='show verbose logs when performing operations')

args = parser.parse_args(sys.argv[1:])
if args.debug:
    debug = 1
if args.server:
    listenPort = args.server

###########################################
################ MAIN #####################
###########################################

#create listener
l = Listener(("0.0.0.0", listenPort))

while 1:
    rmap,wmap,xmap = {},{},{}   # socket:object mappings for select
    xmap[l.checkErr()] = l
    rmap[l.checkRead()] = l
    for conn in connections:
        for sock in [conn.csock]:
            xmap[sock] = conn
            for fwd in conn.forwarders:
                sock = fwd.checkRead()
                if (sock): rmap[sock] = fwd
                sock = fwd.checkWrite()
                if (sock): wmap[sock] = fwd
    rset, wset, xset = select(rmap.keys(), wmap.keys(), xmap.keys(),60)
    #print "select r=%s, w=%s, x=%s" %
    if debug: print [ repr([ sockNames[s] for s in sset]) for sset in [rset,wset,xset] ]
    for sock in rset:
        #print "new connection"
        #print socket
        rmap[sock].doRecv()
    for sock in wset:
        wmap[sock].doSend()
    for sock in xset:
        xmap[sock].doErr()

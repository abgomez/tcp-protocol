################################################################################
# Program: server.py                                                           #
################################################################################
# Description: This server is a small representation of the TCP protocol,      #
#              the server response to clients requests through TCP sockets.    #
#              It has the ability to perform two operation:                    #
#              get - get a file from the server                                #
#              put - send a file to the server                                 #
#              Multiple clients:                                               #
#                   In the get mode multiple clients can read the same file    #
#                   each file gets a unique object.                            #
#                   In the put mode: multiple clients can send a put request   #
#                   to avoid race conditions the server appends the client's   #
#                   index to each file.                                        #
################################################################################
# TCP protocol: the server implements a custom for full details refer to README#
#               the protocol is devide it on multiple section by ":",          #
#               each section must have text and the expected lenght.           #
#               the lenght of the whole is added at the beginning.             #
# Example: 2053:dta:2044:filedata                                              #
################################################################################
# How to use:  python server.py -d                                             #
################################################################################
# Modification Log                                                           ###
#------------------------------------------------------------------------------#
# --/--/----     Dr. Freudenthal   Intial Deployment of fwd functionality      #
# 04/04/2018     Abel Gomez        Modified structure to inclue get/pu   t     #
################################################################################

import sys, os
import traceback
import argparse
import time
from select import *
from socket import *

import re

sockNames = {}               # from socket to name
nextConnectionNumber = 0     # each connection is assigned a unique id
debug = 0                    #verbose mode default off
connections = set()          #set of open connetions


#class: clientAgent
#Description: the class handles get and put functionality.
#             it identifies the type of request and it sends an appropiate response
class Agent:
    def __init__(self, conn, inSock, outSock, bufCap = 1000):
        self.conn, self.inSock, self.outSock, self.bufCap = conn, inSock, outSock, bufCap
        self.inClosed = 0               #flag to detect when to stop reading
        self.messageToClient = ""       #message that we want to send
        self.action = ""                #action requested by client
        self.readFile = ""
        self.clientMessage = ""         #message from client
        self.fileName = ""              #file name
        self.openFile = None            #pointer to file
        self.messageLen = 0             #total message's lenght
        self.numRecv = 0                #number of bytes received
        self.strFound = 0               #index of delimiter
        self.sectionLen = 0             #lenght of text

    #Function: checkRead
    #Description: figure out if we are done reading.
    def checkRead(self):
        if not self.inClosed:
            return self.inSock
        else:
            return None
    #Function: checkWrite
    #Description: figure out if we are done writing.
    def checkWrite(self):
        if self.action:
            return self.outSock
        else:
            return None
    #Function: doRecv
    #Description: read incomming data
    #             the server is using a custom protocol, it will keep reading until
    #             the variable messageLen is set. The server can receive two types
    #             of messages get (send a file) or put (receive a file).
    #             the receive function will parse the received messages.
    def doRecv(self):
        message = ""
        #messageToClient = ""
        try:
            message = self.inSock.recv(1024)                 #receive a limit amount of bytes.
            self.numRecv += len(message)                     #we need to know how many bytes did we recieved

            if debug:
                print "#Bytes received: %d" % self.numRecv
                print "Message from client: %s" % message
                print "Client: %s" % self.conn.connIndex
        except:
            self.conn.die()
        #if we receive something, figure out what
        if len(message):
            self.clientMessage += message                    #save data to buffer
            if debug:
                print "Server Buffer: %s" %self.clientMessage

            #the below block will look for the full message's lenght.
            #we know the protocol, the first section should always be the full message's lenght
            #each section is delimiter by ":"
            if not self.messageLen: #only look for the message length once
                self.strFound = self.clientMessage.find(":") #look for the first ":"
                #if found, we know our delimiter ":" and the first section is always the total message length
                if self.strFound > 0:
                    self.numRecv -= self.strFound + 1
                    self.messageLen = int(self.clientMessage[0:self.strFound])  #save message's lenght

            #at this point we know how many bytes should we get, check if we get them all
            #if not keep reading.
            if self.messageLen == self.numRecv:
                self.inClosed = 1 #stop reading we got everything
                #figure out what kind of message we received
                #remove the message length
                b = self.clientMessage[(self.strFound+1):]
                self.clientMessage = ""
                self.clientMessage += b
                if debug:
                    print "Server Buffer: %s" %self.clientMessage
                #figure out if we got a request.
                #the first three characters identify the message type
                self.action = self.clientMessage[0:4]
                if self.action == "get:":
                    if debug: print "Mode: %s" % self.action
                    #we know the client is requesting a file,
                    b = self.clientMessage[5:] #remove action, we know the lenght of our type section
                    self.clientMessage = ""
                    self.clientMessage += b
                    #at this point we know we are processing a get request.
                    #the client must send all get request in the same format, we know the file name is the last section
                    self.strFound = self.clientMessage.find(":") #look for the first ":"
                    #get file name,
                    self.fileName = self.clientMessage[(self.strFound+1):len(self.clientMessage)]
                    if debug:
                        print "File: %s" % self.fileName
                #we got a put request.
                #the put request is most complex request, the client sends only one packet which includes all information.
                #we need to parse the packet.
                elif self.action == "put:":
                    if debug:
                        print "Mode: %s" % self.action
                        print "\n\n\nServer Buffer: %s" % self.clientMessage

                    #we know the client is sending a file,
                    b = self.clientMessage[4:] #remove action, we know the lenght of the type section.
                    self.clientMessage = ""
                    self.clientMessage += b

                    #our buffer now starts at the lenght of the file name
                    self.strFound = self.clientMessage.find(":") #look for the first ":", and get the index
                    #figure out how many bytes is the file name
                    self.sectionLen = self.clientMessage[0:self.strFound]
                    #pull file name
                    #we know the current buffer, we know where the file name starts and we know how long is it.
                    #using the above values we need to pull the file name.
                    self.fileName = self.clientMessage[(self.strFound+1):( int(self.sectionLen) + (self.strFound+1) ) ]
                    if debug:
                        print "File: %s" % self.fileName

                    #remove the file name from the buffer.
                    # we know where the file name ends: int(self.sectionLen) + (self.strFound+1) + 1 to inlcude delimiter
                    # and we know we want to get everything from that point to the end.
                    self.clientMessage = self.clientMessage[( int(self.sectionLen) + (self.strFound+1) ) + 1 : ]
                    if debug:
                        print "\n\n\nServer Buffer: %s" % self.clientMessage

                    #our buffer now starts at the lenght of the file name
                    self.strFound = self.clientMessage.find(":") #look for the first ":", and get the index
                    #figure out how many bytes are for actual data
                    self.sectionLen = self.clientMessage[0:self.strFound]
                    #pull data
                    #we know the current buffer, we know where the data starts and we know how long is it.
                    #using the above values we need to pull the data.
                    self.clientMessage = self.clientMessage[(self.strFound+1):( int(self.sectionLen) + (self.strFound+1) ) ]
                    if debug:
                        print "\n\n\nServer Buffer: %s" % self.clientMessage

                    #create file, to avoid race conditions append the client index at the start
                    self.openFile = open( str(self.conn.connIndex) + self.fileName, 'w+')
                    self.openFile.write(self.clientMessage)
                    self.openFile.close()
                    if debug:
                        print "File created: %s" % str(self.conn.connIndex) + self.fileName
                    self.closeConn() #close connection
        else:
            self.inClosed = 1
    #Function DoSend
    #Description: the function doSend will handle the actual sending part, the server only response to the get requests
    #             if the file does not exit an error message get send.
    def doSend(self):
        try:
            #identify action Requested
            if self.action == "get:":
                #open file
                #if file does not exists send error message.
                if not os.path.exists(self.fileName):
                    print "Input File does not exists in current directory: %s" % self.fileName
                    #construct message, the server and client use custom protocols which have sections devide it by ":"
                    textLen = len("Sorry my child wrong file")
                    msgLen = len("err:" + str(textLen) + ":Sorry my child wrong file")
                    self.messageToClient = str(msgLen) + ":err:" + str(textLen) + ":Sorry my child wrong file"
                    if debug:
                        print "Message to Client: %s" % self.messageToClient
                    self.outSock.send(self.messageToClient) #send message
                    self.action = "" # done reading

                #open file and send data
                else:
                    if debug:
                         print "Sending file: %s" % self.fileName
                    #open file
                    self.openFile = open(self.fileName)
                    self.readFile = self.openFile.read()
                    self.openFile.close()
                    #construct message, the server and client use custom protocols which have sections devide it by ":"
                    textLen = len(self.readFile)
                    msgLen = len("dta:" + str(textLen) + ":" + self.readFile)
                    self.messageToClient = str(msgLen) + ":dta:" + str(textLen) + ":" + self.readFile
                    if debug:
                        print "Message to Client: %s" % self.messageToClient
                    self.outSock.send(self.messageToClient) #send message
                    self.action = "" #we don't want to read again
                self.closeConn() #close connection
        except:
            self.conn.die()
            print "checking done"

    #Function: closeConn
    #Description: Function to close connection.
    def closeConn(self):
        try:
            self.outSock.shutdown(SHUT_WR)
        except:
            pass
        self.conn.clientAgentDone(self)

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
        self.agents = agents = set()
        print "New connection #%d from %s" % (connIndex, repr(caddr))
        sockNames[csock] = "C%d:ToClient" % connIndex
        agents.add(Agent(self, csock, csock))
        connections.add(self) #add current connection to the set of connections. for every client we have one connection which contains one agent
    def clientAgentDone(self, agent):
        agents = self.agents
        agents.remove(agent)
        print "Agent %s ==> %s from connection %d shutting down" % (sockNames[agent.inSock], sockNames[agent.outSock], self.connIndex)
        if len(agents) == 0:
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
        print "client %s failing due to error" % repr(self.caddr)
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

#Function: lookupSocknames
#Description: function created by Dr.Freudenthal, this function maps sockets with client
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

#the below block of code was written by Dr. Freudenthal
# i did not modify any of the lines below.

#create listener
l = Listener(("0.0.0.0", listenPort))

while 1:
    rmap,wmap,xmap = {},{},{}   # socket:object mappings for select
    xmap[l.checkErr()] = l
    rmap[l.checkRead()] = l
    for conn in connections:
        for sock in [conn.csock]:
            xmap[sock] = conn
            for agent in conn.agents:
                sock = agent.checkRead()
                if (sock): rmap[sock] = agent
                sock = agent.checkWrite()
                if (sock): wmap[sock] = agent
    rset, wset, xset = select(rmap.keys(), wmap.keys(), xmap.keys(),60)
    if debug: print [ repr([ sockNames[s] for s in sset]) for sset in [rset,wset,xset] ]
    for sock in rset:
        rmap[sock].doRecv()
    for sock in wset:
        wmap[sock].doSend()
    for sock in xset:
        xmap[sock].doErr()

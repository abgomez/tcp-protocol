################################################################################
# Program: client.py                                                           #
################################################################################
# Description: This client is a small representation of the TCP protocol,      #
#              the client talks with a server through TCP sockets.             #
#              It has the ability to perform two operation:                    #
#              get - get a file from the server                                #
#              put - send a file to the server                                 #
#              Multiple clients:                                               #
#               client.py has an option to enable multiple clients,            #
#               the number of clients can be controlled with the arg: nc       #
################################################################################
# TCP protocol: the client implements a custom for full details refer to README#
#               the protocol is devide it on multiple section by ":",          #
#               each section must have text and the expected lenght.           #
#               the lenght of the whole is added at the beginning.             #
# Example: 23:get:16:filename.txt                                              #
################################################################################
# How to use:  python client.py -d <action g/p> <filename>                     #
################################################################################
# Modification Log                                                           ###
#------------------------------------------------------------------------------#
# --/--/----     Dr. Freudenthal   Intial Deployment of fwd functionality      #
# 04/04/2018     Abel Gomez        Modified structure to inclue get/pu   t     #
################################################################################

import sys
import argparse
import traceback
import re
import random
import time
from select import *
from socket import *

#Global variables
filename = ""           #file to process
debug = 0               #verbose mode default off
sockNames = {}          #map sockets to name
nextClientNumber = 0    #each client is assigned a unique id
liveClients = set()     #set of live clients
deadClients = set()     #set of dead clients
mode = 'u'              #client mode, get or put file


#Function: lookupSocknames
#Description: function created by Dr.Freudenthal, this function maps sockets with clients
def lookupSocknames(socks):
    return [ sockName(s) for s in socks ]

#client class
#Description: the class will create an object of type client,
#             it will handle the functions to communicate with the server.
#             clients can get a file or put a file.
class Client:
    def __init__(self, af, socktype, saddr):
        #global variables
        global nextClientNumber             #number of clients.
        global liveClients, deadClients     #keep track of live or dead clients.
        global filename                     #which file the client want to get or send.

        self.serverAddr = saddr
        self.numSent, self.numRecv = 0,0                           #log how many bytes the client sends or receives..
        self.allSent = 0                                           #flag to know when to write.
        self.error = 0                                             #flag to detect errors.
        self.allRead = 0                                           #flag to know when to read.
        self.clientIndex = clientIndex = nextClientNumber          #number of client that is currently working.
        nextClientNumber += 1
        self.serverSocket = serverSocket = socket(af, socktype)    #socket to communicate.
        self.clientFile = filename                                 #each instance of the client has a is own file variable.
        self.openFile = None                                       #open file to process.
        self.readFile = ""                                         #read file
        self.clientFileName = ""                                   #each clients appends its index to the file name.
        self.serverMessage = ""                                    #message received from server.
        self.typeMsg = ""                                          #the server could send two types of messages: err, data.
        self.strFound = 0                                          #flag to detect our delimiter.
        self.messageLen = 0                                        #we want to know how how many bytes should we get.

        if debug:
            print "New client #%d to %s" %(clientIndex, repr(saddr))

        #if en get mode, open output file
        if mode == 'g':
            #to avoid race conditions, each client adds its index to the file name.
            self.clientFileName = str(self.clientIndex)+self.clientFile
            self.openFile = open(self.clientFileName, 'w+')
        serverSocket.setblocking(False)                           #set socket to non blocking
        serverSocket.connect_ex(saddr)                            #connect new client
        liveClients.add(self)                                     #add client to live list

    #Function DoSend
    #Description: the function doSend will handle the actual sending part, the client is the one that initiates the connection.
    #             it can send two types of request, get (get file) or put (send file).
    def doSend(self):
        try:
            #detect mode of operations, we need to know what we want to do.
            if mode == 'g':
                    #the client uses a custom protocol, full details on README
                    #construct message
                    nameLen = len(self.clientFile)                                          #get lenght file's name
                    msgLen = len("get:" + str(nameLen) + ":" + self.clientFile)             #calculate full message's lenght
                    message = str(msgLen) + ":get:" + str(nameLen) + ":" + self.clientFile  #append message's lenght at the beginning

                    if debug:
                        print "Total length of message: %d" % msgLen
                        print "Message to Server: %s" % message

                    self.numSent += self.serverSocket.send(message)                          #send message
                    self.allSent = 1                                                         #we are done sending, wait for response.
            #we want to send a file: open file, construct the full message, and close connection.
            elif mode == 'p':
                if debug:
                     print "Sending file: %s" % self.clientFile

                #open file
                self.openFile = open(self.clientFile)
                self.readFile = self.openFile.read()      #read file
                self.openFile.close()

                #construct message, custom protocol
                textLen = len(self.readFile)
                nameLen = len(self.clientFile)
                msgLen = len("put:" + str(nameLen) + ":" + self.clientFile + ":" + str(textLen) + ":" + self.readFile)
                #concatenate lenghts and text
                message = str(msgLen) + ":put:" + str(nameLen) + ":" + self.clientFile + ":" + str(textLen) + ":" + self.readFile

                if debug:
                    print "Message to Server: %s" % message

                #send file to server
                self.numSent += self.serverSocket.send(message)
                self.allSent = 1                                #we are done sending.
                self.serverSocket.shutdown(SHUT_WR)             #TCP will make sure that our message gets send, shutdown

        except Exception as e:
            self.errorAbort("can't send: %s" % e)
            return

    #Function: doRecv
    #Description: function to handle all incomming messages,
    #we know the server only send somehting when the client requests a file.
    #This means that we should only get data from the server after a get request.
    def doRecv(self):
        #global filename
        message = ""   #temporal buffer
        try:
            message = self.serverSocket.recv(1024) #receive message
            self.numRecv += len(message)           #we want to log how many bytes we received

            if debug:
                print "#Bytes received: %d" % self.numRecv
                print "Client Buffer: %s" % message

            self.serverMessage += message                                       #save message to client buffer

            #the below block will look for the full message's lenght.
            #we know the protocol, the first section should always be the full message's lenght
            #each section is delimiter by ":"
            if not self.messageLen:                                             #only look for the message length once
                #within the current buffer search for the message's lenght
                self.strFound = self.serverMessage.find(":")                    #look for the first ":". return index.
                #if found we know our delimiter ":" and the first section is always the total lenght
                if self.strFound > 0:
                    self.numRecv -= self.strFound + 1                           #remove the message's lenght from the bytes received
                    self.messageLen = int(self.serverMessage[0:self.strFound])  #save the message's lenght

            #at this point we know how many bytes should we get, check if we get them all
            #if not keep reading.
            if self.messageLen == self.numRecv:
                #we are done reading, now we need to figure out what kind of message we recieved

                #remove the message lenght, we don't care for the message's lenght
                b = self.serverMessage[(self.strFound+1):]   #ignore the message's lenght and the first ":"
                self.serverMessage = ""
                self.serverMessage += b

                if debug:
                    print "Client Buffer: %s" % self.serverMessage

                #we have a clean buffer, the first three characters after the message's lenght identify the type of message
                #err = error
                #dat = data
                self.typeMsg = self.serverMessage[0:4] #go and get the type, we know the lenght
                #something is wrong, close connection.
                if self.typeMsg =="err:":
                    if debug: print "Type: %s" % self.typeMsg
                    #we know the client is requesting a file, and we know how long is the section type.
                    b = self.serverMessage[5:] #remove type
                    self.serverMessage = ""
                    self.serverMessage += b

                    #we know the server sent us the message lenght, but we also know that the message is the last section.
                    #just go and look for the delimiter.
                    self.strFound = self.serverMessage.find(":") #look for the first ":"
                    #display error message, and close connection.
                    errorMsg = self.serverMessage[(self.strFound+1):len(self.serverMessage)]
                    self.errorAbort(errorMsg)

                #ok, we got data.
                elif self.typeMsg =="dta:":
                    if debug: print "Type: %s" % self.typeMsg
                    #we know the client is requesting a file,
                    b = self.serverMessage[5:] #remove type
                    self.serverMessage = ""
                    self.serverMessage += b
                    #we know the server sent us the message lenght, but we also know that the message is the last section.
                    #just go and look for the delimiter
                    self.strFound = self.serverMessage.find(":") #look for the first ":"
                    #write output file and close connection.
                    self.openFile.write(self.serverMessage[(self.strFound+1):len(self.serverMessage)])
                    self.openFile.close()
                self.done()
        except Exception as e:
            print "doRecv on dead socket"
            print e
            self.done()
            return
    #Function: doErr
    #Description: display error message
    def doErr(self, msg=""):
        error("socket error")
    #Function: checkWrite
    #Description: check if we have something to write
    def checkWrite(self):
        if self.allSent:
            return None
        else:
            return self.serverSocket
    #Function: checkRead
    #Description: check if we have something to read
    def checkRead(self):
        if self.allRead:
            return None
        else:
            return self.serverSocket
    #Function: checkDone
    #Description: check if we are done sending/receiving if yes close connection
    def done(self):
        self.allRead = 1
        self.allSent = 1
        try:
            self.serverSocket(close)
        except:
            pass
        print "client %d done (error=%d)" % (self.clientIndex, self.error)
        deadClients.add(self)
        try: liveClients.remove(self)
        except: pass
    #Function: errorAbort
    #Description: something horrible happen, we need to close the connection
    def errorAbort(self, msg):
        self.allSent =1
        self.error = 1
        print "FAILURE client %d: %s" % (self.clientIndex, msg)
        self.done()


#parse arguments

#Function: format_server_addr
#Description: function to parse host and port number.
def format_server_addr(address):
    addr, port = address.split(":")
    return (addr, int(port))

#figure out what arguments the user pass to the client.
parser = argparse.ArgumentParser(
        prog='client',
        description='TCP file transfer protocol')
parser.add_argument('--serverAddr', '-s',
                    metavar='host:port',
                    dest='server',
                    type=format_server_addr,
                    default=('localhost',50000),
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

#get global variables like: host name, port, mode of operation.
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

#the below block of code was written by Dr. Freudenthal
# i did not modify any of the line below.

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
    rset, wset, xset = select(rmap.keys(), wmap.keys(), xmap.keys(),60)
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

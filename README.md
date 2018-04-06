# TCP File Transfer protocol
## Description.
TCP file transfer protocol is a project to demostrate how the TCP protocol works, we implemented three objects which communicate through TCP sockets: client.py server.py and stammerProxy.py. For this project we developed a custom protocol, all messages must be send with this specific format. On This implementation only two functions are available: get to a get a file from the server and put to send a file to the server. 

## How it Works.
Altough all three objects are part of the protocol we will only describe two: client.py and server.py 

The client is the one that initialize all communication, it send the first request to server. The request can be a get or a put; in the case of a get, the client will send a first message containing the action and a file name. The server will receive the request and it will response with the appropiate text for the requested file. For a put request, same as before the client sends the first messages but in this ocassion it sends the full message incluiding the content of the file. The server will receive the message and it will identify that the client sent a put request which means that the server needs to save in a local file all the data that the client sent. All the messages between client and server must follow a format (we will discuss the format later).

As mentioned before the client can only send two types of messages: get and put. 
* get: the client sends a request to get a file from the server, the file will be store in a local copy within the current directory. 
* put: the client sends a request to save a file into the server, the fille will be store in a local copy on the server within the current directory. 

### Multiple clients.
The server can receive multiple clients, the functionality of receiving multiples clients it just to demostrate that our server can handle and process multiple connections. The way we implemented our client, make the idea of multiple a little messy. To avoid race conditions and to make thing simpler each local copy is save by appending the client id at the beginning, this means that if the server received 3 connections it will create three files: 0filename.txt (client 1), 1filename.txt (client 2), and 3filename.txt (client 3).

### Functions.
Client and server have the same sets of function, they work in a similar way with the only difference that the client is the one that initiates the communication. 

* send: send a message, it can be a request or a response. Must use protocol format
* receive: receive incomming messages, client and server will keep reading until the full messages gets delivered
* check read/write: by using a select client and server keeps listening for any change on the socket. The socket can be ready to read or to write. 

### Message Format. 
Our TCP protocol use a custom protocol, all messages must follow the format otherwise the server and client won't be able to process messages. The protocol is delimiter by ":"

#### Example get request
Message's Lenght | : | Type | : | Text Lengt | : | Text 
---------------- | -- | ---- | ---| ---------- | -- | ----------
24 | : | get | : | 16 | : | declaration.txt




## State Diagram



# Lab Instructions.

## nets-tcp-file-transfer

For this lab, you must define a file transfer protocol and implement a client and server.  The server must be 
* single-threaded, 
* and accept multiple concurrent client connections.   

Like the demo code provided for this course, your code 
* should be structured around a single loop with a single call to select(), 
* and all information about protocol state should be explicitly stored in variables 

Recall that unlike UDP, which is a message-oriented protocol, TCP is stream-oriented.  

A practical implication of this difference is that the outputs of multiple writes may be concatenated and reads may only return a portion of the data already sent.  You are strongly encouraged to test your implementation using the stammering proxy from https://github.com/robustUTEP/nets-tcp-proxy.git


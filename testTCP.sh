#!/bin/csh -f
##################################################
#This small test script, will test the connection and
#transfer of data between the server and the client.
#The script starts up three programs
# server.py
# stammerProxy.py
# client.py
#You MUST pass three arguments: action, file name, number of clients
# example: testTCP.sh get declaration.txt 1
##################################################

#check arguments
if ($#argv != 3) then
    echo "Invalid number of arguments"
    exit 1
endif

echo "Starting server.py..."
python server/server.py &
setenv serverPID $!

echo "Starting stammerProxy..."
python stammerProxy.py &
setenv proxyPID $!

echo "Starting client..."
python client.py --"$1" "$2" -nc $3 &

echo "verify success"
setenv success 0
if ($1 == "get") then
    setenv index 0
    setenv serverFileSize `ls -l server/"$2" | awk '{print $5}'`
    echo "Server File Size: " $serverFileSize
    while ($index < $3)
        sleep 2
        setenv filename $index$2
        setenv clientFileSize `ls -l "$filename" | awk '{print $5}'`
        echo "client file" $filename
        echo "Client File Size: " $clientFileSize
        if ($serverFileSize != $clientFileSize) then
            @ success++
        endif
        @ index++
    end
else if ($1 == "put") then
    setenv index 0
    setenv clientFileSize `ls -l "$2" | awk '{print $5}'`
    echo "Client File Size: " $clientFileSize
    while ($index < $3)
        sleep 2
        setenv filename $index$2
        setenv serverFileSize `ls -l server/"$filename" | awk '{print $5}'`
        echo "Server file" $filename
        echo "Server File Size: " $serverFileSize
        if ($serverFileSize != $clientFileSize) then
            @ success++
        endif
        @ index++
    end
endif

echo "success" $success
if ($success == 0) then
    echo "*************************Everything OK, all file's size match**************************"
endif

sleep 2
echo "Shutting down server and proxy"
pkill -P $$

import struct
import sys
import socket as sock
import random
import os

PORT = 2696
BUFFER_SIZE = 65536
OPCODE_WRQ = 1
OPCODE_DATA = 3
OPCODE_ACK = 4
OPCODE_ERROR = 5
TIMEOUT = .1
MODE = "octet"
FILE_NAME = "space.jpg"
IP6MODE = True
SLIDE_WIN_MODE = False
DROP1 = False
DROP_NUMBER = 17

serverip4 = "127.0.0.1"
serverip6 = "::1"
# For localhostipv6 use serverip6 = "::1"

BLOCK_NUMBER = 0
SLIDE_WIN_SIZE = 0
BLOCKS_SENT = []
WIN_POS = 0

def sendFileNoSW():
    setOptions()
    if SLIDE_WIN_MODE is True:
        return False
    socket = createSocket()

    FILE = openFile(socket)

    data = lastdata = FILE.read(512)

    #WRQ Packet
    if DROP1 is False:
        sendWRQ(socket)
    elif random.randrange(1, 101) != DROP_NUMBER:
        sendWRQ(socket)

    #Data Packet
    addToBlock(1)
    print("Sending block " + str(BLOCK_NUMBER))
    if DROP1 is False:
        sendData(socket, data)
    elif random.randrange(1, 101) != DROP_NUMBER:
        sendData(socket, data)
    else:
        print("Dropping DATA...")
    waitForACK(socket, data)

    while len(data) == 512:
        data = lastdata = FILE.read(512)
        #print ("Size of packet: " + str(len(data)))
        addToBlock(1)
        print("Sending block " + str(BLOCK_NUMBER))
        if DROP1 is False:
            sendData(socket, data)
        elif random.randrange(1, 101) != DROP_NUMBER:
            sendData(socket, data)
        else:
            print("Dropping DATA...")
        waitForACK(socket, data)

    FILE.close()
    return True

def setTimeout(time):
    global TIMEOUT
    TIMEOUT = time

def sendFileWithSW():
    # Read entire file first into list
    SWSize = int(raw_input("How many packets should be sent at a time using sliding windows... "))
    setSWSize(SWSize)
    setTimeout(SWSize*TIMEOUT)
    socket = createSocket()

    FILE = openFile(socket)

    #Working on it
    allBlocks = []
    block = 1
    data = FILE.read(512)
    allBlocks.append([block, data])
    while len(data) == 512:
        data = FILE.read(512)
        if data == "":
            break
        block += 1
        allBlocks.append([block, data])

    #WRQ Packet
    if DROP1 is False:
        sendWRQ(socket)
    elif random.randrange(1, 101) != DROP_NUMBER:
        sendWRQ(socket)

    totalBlocks = len(allBlocks)
    end = False
    while end is False:
        sent = 0
        while sent < SLIDE_WIN_SIZE and end is False:
            addToBlock(1)
            if DROP1 is False:
                sendData(socket, allBlocks[BLOCK_NUMBER-1][1])
            elif random.randrange(1, 101) != DROP_NUMBER:
                sendData(socket, allBlocks[BLOCK_NUMBER-1][1])
            else:
                print("Dropping DATA...")
            BLOCKS_SENT.append(BLOCK_NUMBER)
            if totalBlocks-BLOCK_NUMBER == 0:
                print("Reached end of file.")
                end = True
            sent += 1
        waitForACKs(socket, sent)

    FILE.close()

def openFile(socket):
    try:
        FILE = open(FILE_NAME, "r")
    except IOError:
        if DROP1 is False:
            sendError(socket, "File Not Found!", '1')
        elif random.randrange(1, 101) != DROP_NUMBER:
            sendError(socket, "File Not Found!", '1')
    return FILE

def setSWSize(size):
    global SLIDE_WIN_SIZE
    SLIDE_WIN_SIZE = size

def setIPMode(answer):
    global IP6MODE
    if "y" in answer:
        IP6MODE = True
    elif "n" in answer:
        IP6MODE = False
    else:
        return False
    return True

def setSlideWinMode(answer):
    global SLIDE_WIN_MODE
    if "y" in answer:
        SLIDE_WIN_MODE = True
    elif "n" in answer:
        SLIDE_WIN_MODE = False
    else:
        return False
    return True

def setDropMode(answer):
    global DROP1
    if "y" in answer:
        DROP1 = True
    elif "n" in answer:
        DROP1 = False
    else:
        return False
    return True

def setOptions():
    ipmode = raw_input("Enable IPv6...(y/n): ")
    sliding = raw_input("Use sliding windows...(y/n): ")
    drop = raw_input("Drop 1% of packets...(y/n)")

    if setIPMode(ipmode) and setSlideWinMode(sliding) and setDropMode(drop):
        print "Preferences acknowledged..."
    else:
        sys.exit("Some input was invalid... exiting program...")

def sendError(socket, errmsg, errcode):
    print("Sending ERROR packet...")
    if IP6MODE is False:
        socket.sendto(ERRPacket(errmsg, errcode), (serverip4, PORT))
    else:
        socket.sendto(ERRPacket(errmsg, errcode), getSockAddr())
    socket.close()
    sys.exit("Error Code " + errcode + ":\n" + errmsg)

def ERRPacket(errmsg, errcode):
    formattedEM = str(errmsg)
    addIn = 128-len(str(errmsg))
    i = 0
    while i < addIn:
        formattedEM = formattedEM + " "
        i += 1
    packet = struct.pack("!cc%dsc" % len(formattedEM), str(OPCODE_ERROR), str(errcode), str(errmsg), '0')
    return packet

def getRemainder(number, divisor):
    remainder = number
    divisions = 0
    while remainder >= divisor:
        remainder = remainder-divisor
        divisions += 1
    outcome = [divisions, remainder]
    return outcome

def addToBlock(amount):
    global BLOCK_NUMBER
    BLOCK_NUMBER = BLOCK_NUMBER+amount

def waitForACK(socket, data):
    try:
        packet, client = socket.recvfrom(BUFFER_SIZE)
    except Exception:
        print("Timeout... no ACK received... resending data packet...")
        sendData(socket, data)
        socket.settimeout(TIMEOUT*2)
        packet, client = socket.recvfrom(BUFFER_SIZE)
        socket.settimeout(TIMEOUT)

    opcode = int(packet[0:1])
    if opcode == 4:
        print("Received ACK...")
        serverblock = int(packet[1:11])
        if BLOCK_NUMBER != serverblock:
            print("Incorrect ACK... waiting...")
            sendData(socket, data)
            socket.settimeout(TIMEOUT*2)
            packet, client = socket.recvfrom(BUFFER_SIZE)
            socket.settimeout(TIMEOUT)
    elif opcode == 5:
        print("Received ERROR...")
        errcode = packet[1:2]
        errmsg = packet[2:129]
        socket.close()
        sys.exit("Error Code " + errcode + ":\n" + errmsg)

def setWINPOS(position):
    global WIN_POS
    WIN_POS = position

def waitForACKs(socket, sent):
    packets = []
    received = []
    #Initially set to resend all of them
    resend = BLOCKS_SENT
    try:
        i = 0
        while i < sent:
            packet, client = socket.recvfrom(BUFFER_SIZE)
            packets.append(packet)
            i += 1
            setWINPOS(BLOCK_NUMBER)
    except Exception:
        print("Timeout... not all ACKs received...")
        j = 0
        while j < len(packets):
            opcode = int(packets[j][0:1])
            if opcode == 4:
                print("Received ACK...")
                serverblock = int(packets[j][1:11])
                received.append(serverblock)
            elif opcode == 5:
                print("Received ERROR...")
                errcode = packets[j][1:2]
                errmsg = packets[j][2:129]
                socket.close()
                sys.exit("Error Code " + errcode + ":\n" + errmsg)
            j += 1
        #Now decide what packets need to be resent
        print resend
        k = 0
        while k < len(received):
            l = 0
            found = False
            while l < len(BLOCKS_SENT) and found is False:
                if received[k] == BLOCKS_SENT[l]:
                    found = True
                    resend.remove(BLOCKS_SENT[l])
                l += 1
            k += 1
        #Now we know what blocks need to be resent
        #We will choose the earliest block number
        print resend
        earliest = resend[0]
        setBlockNumber(earliest-1)
        setWINPOS(earliest-1)
    clearBlocksSent()

def setBlockNumber(blocknumber):
    global BLOCK_NUMBER
    BLOCK_NUMBER = blocknumber

def sendData(socket, data):
    if IP6MODE is False:
        socket.sendto(DataPacket(data), (serverip4, PORT))
    else:
        socket.sendto(DataPacket(data), getSockAddr())

def sendWRQ(socket):
    if IP6MODE is False:
        socket.sendto(WRQPacket(socket), (serverip4, PORT))
    else:
        socket.sendto(WRQPacket(socket), getSockAddr())

def getSockAddr():
    res = sock.getaddrinfo(serverip6, PORT, sock.AF_INET6, sock.SOCK_DGRAM)
    family, socktype, proto, canonname, sockaddr = res[0]
    return sockaddr

def DataPacket(data):
    formattedBN = str(BLOCK_NUMBER)
    addIn = 10-len(str(BLOCK_NUMBER))
    i = 0
    while i < addIn:
        formattedBN = formattedBN + " "
        i += 1
    #print "Encoded output:"
    #print data.encode("utf-8")
    #print("Length of encoded data: " + str(len(data.encode("utf-8"))))
    packet = struct.pack("!c%ds%ds" % (len(formattedBN),len(data)), str(OPCODE_DATA), str(formattedBN), str(data))
    return packet

def appendBlock(blocknumber, dataPack):
    global BLOCKS_SENT
    BLOCKS_SENT.append([blocknumber, dataPack])

def clearBlocksSent():
    global BLOCKS_SENT
    BLOCKS_SENT = []

def WRQPacket(socket):
    FNLength = len(FILE_NAME)
    addIn = 64-FNLength
    formatedName = FILE_NAME

    if addIn < 0:
        socket.close()
        sys.exit("Specified file's name is too large! Ending program!")
    else:
        i = 0
        while i < addIn:
            formatedName = formatedName + " "
            i += 1

    formattedMode = MODE
    addIn = 8-len(MODE)
    i = 0
    while i < addIn:
        formattedMode = formattedMode + " "
        i += 1

    FN = formatedName.encode(encoding='UTF-8')
    M = formattedMode.encode(encoding='UTF-8')
    packet = struct.pack("!c%dsc%dsc" % (len(FN), len(M)), str(OPCODE_WRQ).encode(encoding='UTF-8'), FN, '0', M, '0')

    return packet

def createSocket():
    if IP6MODE is False:
        socket = sock.socket(sock.AF_INET, sock.SOCK_DGRAM)
        socket.settimeout(TIMEOUT)
        return socket
    else:
        socket = sock.socket(sock.AF_INET6, sock.SOCK_DGRAM)
        socket.settimeout(TIMEOUT)
        return socket

if sendFileNoSW() is False:
    sendFileWithSW()

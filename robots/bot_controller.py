# bot_controller v1.2.0
# v1.2.0 updates bot_controller to newer view of netbots
# a highjackable viewer that can be used to control a NetBot
# initially designed for the Coastal Renaissance, but should be portable enough
# for use with other NetBots.
# Based on the official NetBots viewer
# Created by 2019 class of APCS

import argparse
import time
import signal
import tkinter as t
import os
import sys
import math
import random

# import threading # make multiple processes instead of one big ugly one
# import multiprocessing

# NOTE: Assumes this is in the bot directory
# comment out below lines if in the src directory
robotpath = os.path.dirname(os.path.abspath(__file__))
srcpath = os.path.join(os.path.dirname(robotpath), "src")
sys.path.insert(0, srcpath)

from netbots_log import log
from netbots_log import setLogLevel
from netbots_server import SrvData
import netbots_ipc as nbipc
import netbots_math as nbmath


class ViewerData:
    viewerSocket = None

    window = None
    frame = None
    statusWidget = None
    replayWidget = None
    canvas = None
    botWidgets = {}
    botCurrentDirection = {}
    botRequestedDirection = {}
    botCanon = {}
    botTrackLeft = {}
    botTrackRight = {}
    botScan = {}
    botStatusWidgets = {}
    shellWidgets = {}
    explWidgets = {}
    bigMsg = None
    colors = ['#ACACAC', '#87FFCD', '#9471FF', '#FF9DB6', '#2ED2EB', '#FA8737', '#29B548', '#FFBC16', '#308AFF',
              '#FF3837']
    lastViewData = time.time()
    scale = 1
    
    borderSize = 10
    
    nextKeepAlive = time.time() + 2
    srvIP = None
    srvPort = None
    conf = None
    
    updateThread = None  # thread for drawing to window.
    
    # don't call these before creating the window or the behaviour is...
    # undefined...
    # might fix in future revision, idk
    # For more information on events, refer to:
    # https://www.tcl.tk/man/tcl8.5/TkCmd/bind.htm#M7
    def setKeyPressHandler(self, handler):
        self.window.bind_all("<KeyPress>", handler)
    
    def setKeyReleaseHandler(self, handler):
        self.window.bind_all("<KeyRelease>", handler)
    
    def setMousePressHandler(self, handler):
        # handles both left and right click
        self.canvas.bind("<ButtonPress>", handler)
    
    def setMouseMoveHandler(self, handler):
        self.canvas.bind("<Motion>", handler)
    
    def setMouseReleaseHandler(self, handler):
        self.canvas.bind("<ButtonRelease>", handler)


def colorVariant(hexColor, brightnessOffset=1):
    """ takes a color like #87c95f and produces a lighter or darker variant """
    if len(hexColor) != 7:
        raise Exception("Passed %s into colorVariant(), needs to be in #87c95f format." % hexColor)
    rgbHex = [hexColor[x:x + 2] for x in [1, 3, 5]]
    newRGBInt = [int(hexValue, 16) + brightnessOffset for hexValue in rgbHex]
    newRGBInt = [min([255, max([0, i])]) for i in newRGBInt]  # make sure new values are between 0 and 255
    
    hexstr = "#"
    for i in newRGBInt:
        if i < 16:
            hexstr += "0"
        # hex() produces "0x88" or "0x8", we want just "88" or "8"
        hexstr += hex(i)[2:]
    return hexstr


def checkForUpdates(d):
    msg = {"type": "Error", "result": "We never got any new data from server."}
    try:
        # keep getting messages until we get the last one and then an exception is thrown.
        while True:
            msg, ip, port = d.viewerSocket.recvMessage()
    except nbipc.NetBotSocketException as e:
        # if message type is Error and we have not got good data for 100 steps then quit
        if msg['type'] == 'Error' and d.lastViewData + d.conf['stepSec'] * 100 < time.time():
            # We didn't get anything from the buffer or it was an invalid message.
            d.canvas.itemconfigure(d.bigMsg, text="Server stopped sending data.")
    except Exception as e:
        log(str(e), "ERROR")
        quit()
    
    if msg['type'] == 'viewData':
        # if gameNumber == 0 then post message
        if msg['state']['gameNumber'] == 0:
            leftToJoin = d.conf['botsInGame'] - len(msg['bots'])
            if leftToJoin == 1:
                s = ""
            else:
                s = "s"
            d.canvas.itemconfigure(d.bigMsg, text="Waiting for " +
                                                  str(leftToJoin) +
                                                  " robot" + s + " to join.")
        else:
            d.canvas.itemconfigure(d.bigMsg, text="")

        for src, bot in msg['bots'].items():
            # ensure all bots on server have widgets
            if not src in d.botStatusWidgets:
                # pick color for this bot
                c = d.colors.pop()
        
                # create bot status widget
                d.botStatusWidgets[src] = t.Message(d.frame, width=200, justify='center')
                d.botStatusWidgets[src].config(highlightbackground=c)
                d.botStatusWidgets[src].config(highlightthickness=d.borderSize)
                d.botStatusWidgets[src].pack(fill=t.X)
        
                # create bot widgets
                d.botScan[src] = d.canvas.create_arc(0, 0, 50, 50, start=0, extent=0,
                                                     style='arc', width=4, outline='#bbb')
                d.botTrackLeft[src] = d.canvas.create_line(0, 0, 50, 50, width=
                d.conf['botRadius'] * (10 / 24.0), fill='grey')
                d.botTrackRight[src] = d.canvas.create_line(0, 0, 50, 50, width=
                d.conf['botRadius'] * (10 / 24.0), fill='grey')
                d.botWidgets[src] = d.canvas.create_oval(0, 0, 0, 0, fill=c)
                d.botCanon[src] = d.canvas.create_line(0, 0, 50, 50, width=
                d.conf['botRadius'] * (1 / 3.0), fill=c)
                d.botRequestedDirection[src] = d.canvas.create_line(0, 0, 50, 50, width=
                d.conf['botRadius'] * (5 / 24.0), arrow=t.LAST, fill=colorVariant(c, -100))
                d.botCurrentDirection[src] = d.canvas.create_line(0, 0, 50, 50, width=
                d.conf['botRadius'] * (5 / 24.0), arrow=t.LAST, fill=colorVariant(c, 100))
            
            # update text for each bot
            d.botStatusWidgets[src].config(text=bot['name'] +
                                                "\nClass: " + "%s" % (bot['class']) +
                                                "\n" + "----------------------------------" +
                                                "\nPoints: " + str(bot['points']) +
                                                "\nCanon Fired: " + str(bot['firedCount']) +
                                                "\nShell Damage Inflicted: " + '%.1f' % (bot['shellDamage']) +
                                                "\n" + "----------------------------------" +
                                                "\nHealth: " + '%.1f' % (bot['health']) + "%"
                                                " | missedSteps: " + '%.1f' % (bot['missedSteps']) +
                                                "\nx: " + '%.1f' % (bot['x']) +
                                                "  |  y: " + '%.lf' % (bot['y']) +
                                                "\ncurSpeed: " + '%.1f' % (bot['currentSpeed']) +
                                                "  |  reqSpeed: " + '%.1f' % (bot['requestedSpeed']) +
                                                "\nfireDir: " + '%.1f' % (bot['last']['fireCanonRequest']['direction']) +
                                                "  |  fireDist: " + '%.1f' % (bot['last']['fireCanonRequest']['distance']) +
                                                "\nscanStart: " + '%.1f' % (bot['last']['scanRequest']['startRadians']) +
                                                "  |  scanEnd: " + '%.1f' % (bot['last']['scanRequest']['endRadians'])
                                           )
    
            # update location of bot widgets or hide if health == 0
            if bot['health'] == 0:
                d.canvas.itemconfigure(d.botWidgets[src], state='hidden')
                d.canvas.itemconfigure(d.botRequestedDirection[src], state='hidden')
                d.canvas.itemconfigure(d.botCurrentDirection[src], state='hidden')
                d.canvas.itemconfigure(d.botTrackLeft[src], state='hidden')
                d.canvas.itemconfigure(d.botTrackRight[src], state='hidden')
                d.canvas.itemconfigure(d.botScan[src], state='hidden')
                d.canvas.itemconfigure(d.botCanon[src], state='hidden')
            else:
                centerX = bot['x'] * d.scale + d.borderSize
                centerY = d.conf['arenaSize'] - bot['y'] * d.scale + d.borderSize
                d.canvas.coords(d.botWidgets[src],
                                centerX - d.conf['botRadius'],
                                centerY - d.conf['botRadius'],
                                centerX + d.conf['botRadius'],
                                centerY + d.conf['botRadius'])
        
                d.canvas.coords(d.botRequestedDirection[src], centerX + d.conf['botRadius']
                                * bot['requestedSpeed'] / 100 * (19.0 / 24.0)
                                * math.cos(-bot['requestedDirection']),  # 19
                                centerY + d.conf['botRadius']
                                * bot['requestedSpeed'] / 100 * (19.0 / 24.0) * math.sin(
                                    -bot['requestedDirection']),
                                d.conf['botRadius'] * bot['requestedSpeed'] / 100 * math.cos(
                                    -bot['requestedDirection']) + centerX,  # 24
                                d.conf['botRadius'] * bot['requestedSpeed'] / 100 * math.sin(
                                    -bot['requestedDirection']) + centerY)
        
                d.canvas.coords(d.botCurrentDirection[src], centerX + d.conf['botRadius']
                                * bot['currentSpeed'] / 100 * (19.0 / 24.0)
                                * math.cos(-bot['currentDirection']),  # 19
                                centerY + d.conf['botRadius']
                                * bot['currentSpeed'] / 100 * (19.0 / 24.0) * math.sin(
                                    -bot['currentDirection']),
                                d.conf['botRadius'] * bot['currentSpeed'] / 100 * math.cos(
                                    -bot['currentDirection']) + centerX,  # 24
                                d.conf['botRadius'] * bot['currentSpeed'] / 100 * math.sin(
                                    -bot['currentDirection']) + centerY)
        
                d.canvas.coords(d.botTrackLeft[src],
                                centerX + d.conf['botRadius'] * (30.0 / 24.0)
                                * math.cos(-bot['currentDirection'] - math.pi / 4),
                                centerY + d.conf['botRadius'] * (30.0 / 24.0)
                                * math.sin(-bot['currentDirection'] - math.pi / 4),
                                d.conf['botRadius'] * (30.0 / 24.0) * math.cos(-bot['currentDirection']
                                                                               - (3 * math.pi) / 4) + centerX,
                                d.conf['botRadius'] * (30.0 / 24.0) * math.sin(-bot['currentDirection']
                                                                               - (3 * math.pi) / 4) + centerY)
                d.canvas.coords(d.botTrackRight[src],
                                centerX + d.conf['botRadius'] * (30.0 / 24.0)
                                * math.cos(-bot['currentDirection'] - (5 * math.pi) / 4),
                                centerY + d.conf['botRadius'] * (30.0 / 24.0)
                                * math.sin(-bot['currentDirection'] - (5 * math.pi) / 4),
                                d.conf['botRadius'] * (30.0 / 24.0)
                                * math.cos(-bot['currentDirection'] - (7 * math.pi) / 4) + centerX,
                                d.conf['botRadius'] * (30.0 / 24.0)
                                * math.sin(-bot['currentDirection'] - (7 * math.pi) / 4) + centerY)
        
                x2, y2 = nbmath.project(centerX, 0, bot['last']['fireCanonRequest']['direction'],
                                        d.conf['botRadius'] * 1.35)
                y2 = centerY - y2
                d.canvas.coords(d.botCanon[src], centerX, centerY, x2, y2)
        
                d.canvas.coords(d.botScan[src],
                                centerX - d.conf['botRadius'] * 1.5,
                                centerY - d.conf['botRadius'] * 1.5,
                                centerX + d.conf['botRadius'] * 1.5,
                                centerY + d.conf['botRadius'] * 1.5)
                d.canvas.itemconfigure(d.botScan[src], start=math.degrees(bot['last']['scanRequest']['startRadians']))
                extent = bot['last']['scanRequest']['endRadians'] - bot['last']['scanRequest']['startRadians']
                if extent < 0:
                    extent += math.pi * 2
                d.canvas.itemconfigure(d.botScan[src], extent=math.degrees(extent))
        
                d.canvas.itemconfigure(d.botRequestedDirection[src], state='normal')
                d.canvas.itemconfigure(d.botCurrentDirection[src], state='normal')
                d.canvas.itemconfigure(d.botWidgets[src], state='normal')
                d.canvas.itemconfigure(d.botTrackLeft[src], state='normal')
                d.canvas.itemconfigure(d.botTrackRight[src], state='normal')
                d.canvas.itemconfigure(d.botScan[src], state='normal')
                d.canvas.itemconfigure(d.botCanon[src], state='normal')
    
            # remove shell widgets veiwer has but are not on server.
        for src in list(d.shellWidgets.keys()):
            if not src in msg['shells']:
                d.canvas.delete(d.shellWidgets[src][1])
                d.canvas.delete(d.shellWidgets[src][0])
                del d.shellWidgets[src]
    
            # add shell widgets server has that viewer doesn't
        for src in msg['shells']:
            if not src in d.shellWidgets:
                c = d.canvas.itemcget(d.botWidgets[src], 'fill')
                d.shellWidgets[src] = [
                    d.canvas.create_line(0, 0, 0, 0, width=2, arrow=t.LAST, fill=c),
                    d.canvas.create_line(0, 0, 0, 0, width=2, fill=c)
                ]
    
            # update location of shell widgets
        for src in d.shellWidgets:
            centerX = msg['shells'][src]['x'] * d.scale + d.borderSize
            centerY = d.conf['arenaSize'] - msg['shells'][src]['y'] * d.scale + d.borderSize
            shellDir = msg['shells'][src]['direction']
            shell_item_1 = d.shellWidgets[src][0]
            d.canvas.coords(shell_item_1, centerX, centerY,
                            d.scale * 1 * math.cos(-shellDir) + centerX,
                            d.scale * 1 * math.sin(-shellDir) + centerY)
            shell_item_2 = d.shellWidgets[src][1]
            d.canvas.coords(shell_item_2, centerX, centerY,
                            d.scale * 10 * math.cos(-shellDir) + centerX,
                            d.scale * 10 * math.sin(-shellDir) + centerY)
    
            # remove explosion widgets viewer has but are not on server.
        for k in list(d.explWidgets.keys()):
            if not k in msg['explosions']:
                d.canvas.delete(d.explWidgets[k])
                del d.explWidgets[k]
    
            # reduce existing explosion size by 30% and turn off fill
        for k in d.explWidgets:
            bbox = d.canvas.bbox(d.explWidgets[k])
            d.canvas.coords(d.explWidgets[k],
                            bbox[0] + (bbox[2] - bbox[0]) * 0.85,
                            bbox[1] + (bbox[3] - bbox[1]) * 0.85,
                            bbox[2] - (bbox[2] - bbox[0]) * 0.85,
                            bbox[3] - (bbox[3] - bbox[1]) * 0.85)
            d.canvas.itemconfig(d.explWidgets[k], fill='')
    
            # add explosion widgets server has that viewer doesn't
        for k, expl in msg['explosions'].items():
            if not k in d.explWidgets:
                c = d.canvas.itemcget(d.botWidgets[expl['src']], 'fill')
                centerX = expl['x'] * d.scale + d.borderSize
                centerY = d.conf['arenaSize'] - expl['y'] * d.scale + d.borderSize
                explRadius = SrvData.getClassValue(d, 'explRadius', msg['bots'][expl['src']]['class'])
                d.explWidgets[k] = d.canvas.create_oval(centerX - explRadius,
                                                        centerY - explRadius,
                                                        centerX + explRadius,
                                                        centerY + explRadius,
                                                        fill=c, width=3, outline=c)
    
            # update game status widget
        d.statusWidget.config(text=d.conf['serverName'] +
                                   "\n\nGame: " + str(msg['state']['gameNumber']) + " / " + str(d.conf['gamesToPlay']) +
                                   "\nStep: " + str(msg['state']['gameStep']) + " / " + str(d.conf['stepMax']))
        
        # record the last time we got good view data from server.
        d.lastViewData = time.time()
    
    # server needs 1 every 10 seconds to keep us alive. Send every 2 secs to be sure.
    if time.time() > d.nextKeepAlive:
        d.viewerSocket.sendMessage({'type': 'viewKeepAlive'}, d.srvIP, d.srvPort)
        d.nextKeepAlive += 1
    
    # Wait two steps before updating screen.
    # d.window.update()
    d.window.after(int(d.conf['stepSec'] * 1000), checkForUpdates, d)


def updateLoop(d):
    while (d.running):
        d.window.update()
        d.window.after(int(d.conf['stepSec'] * 1000), checkForUpdates, d)


def openWindow(d):
    d.window = t.Tk()
    d.window.title("Netbots")
    
    if d.window.winfo_screenheight() < d.conf['arenaSize'] + 100 + d.borderSize * 2:
        d.scale = d.window.winfo_screenheight() / float(d.conf['arenaSize'] + 100 + d.borderSize * 2)
        d.conf['arenaSize'] *= d.scale
        d.conf['botRadius'] *= d.scale
        d.conf['explRadius'] *= d.scale
        log("Window scale set to : " + str(d.scale))
    
    d.canvas = t.Canvas(d.window, width=d.conf['arenaSize'], height=d.conf['arenaSize'], bg='#ddd')
    d.canvas.config(highlightbackground='#000')
    d.canvas.config(highlightthickness=d.borderSize)
    d.canvas.pack(side=t.LEFT)
    
    lineAt = d.borderSize + d.conf['arenaSize'] / 40
    while lineAt < d.conf['arenaSize'] + d.borderSize:
        d.canvas.create_line(d.borderSize, lineAt, d.conf['arenaSize'] + d.borderSize, lineAt, width=1, fill="#cecece")
        d.canvas.create_line(lineAt, d.borderSize, lineAt, d.conf['arenaSize'] + d.borderSize, width=1, fill="#cecece")
        lineAt += d.conf['arenaSize'] / 40
    
    lineAt = d.borderSize + d.conf['arenaSize'] / 10
    while lineAt < d.conf['arenaSize'] + d.borderSize:
        d.canvas.create_line(d.borderSize, lineAt, d.conf['arenaSize'] + d.borderSize, lineAt, width=2, fill="#c0c0c0")
        d.canvas.create_line(lineAt, d.borderSize, lineAt, d.conf['arenaSize'] + d.borderSize, width=2, fill="#c0c0c0")
        lineAt += d.conf['arenaSize'] / 10
    
    for o in d.conf['jamZones']:
        centerX = o['x'] * d.scale + d.borderSize
        centerY = d.conf['arenaSize'] - o['y'] * d.scale + d.borderSize
        radius = o['radius'] * d.scale
        d.canvas.create_oval(centerX - radius,
                             centerY - radius,
                             centerX + radius,
                             centerY + radius,
                             fill='#ddd', outline='#c0c0c0', width=2)
    
    for o in d.conf['obstacles']:
        centerX = o['x'] * d.scale + d.borderSize
        centerY = d.conf['arenaSize'] - o['y'] * d.scale + d.borderSize
        radius = o['radius'] * d.scale
        d.canvas.create_oval(centerX - radius,
                             centerY - radius,
                             centerX + radius,
                             centerY + radius,
                             fill='black')
    
    d.bigMsg = canvasText = d.canvas.create_text(d.conf['arenaSize'] / 2 + d.borderSize,
                                                 d.conf['arenaSize'] / 2 + d.borderSize,
                                                 fill="darkblue",
                                                 font="Times 20 italic bold",
                                                 text="")
    
    d.frame = t.Frame(d.window, width=200, height=1020, bg='#888')
    d.frame.pack(side=t.RIGHT)
    
    d.statusWidget = t.Message(d.frame, width=200, justify='center')
    d.statusWidget.config(highlightbackground='#000')
    d.statusWidget.config(highlightthickness=d.borderSize)
    d.statusWidget.pack(fill=t.X)
    
    d.lastViewData = time.time()
    checkForUpdates(d)
    
    # start updating in separate thread
    # d.running = True
    # d.updateThread = threading.Thread(target = updateLoop, args = (d,))
    # d.updateThread = multiprocessing.Process(target = updateLoop, args = (d,))
    # d.updateThread.start()


def quit(signal=None, frame=None):
    log("Quiting", "INFO")
    exit()


# createController, was main
# make sure ip:port are not the same as the controlling bot or the server gets T R I G G E R E D
def createController(ip, port, sip, sp):
    d = ViewerData()
    
    # POSSIBLE BUG (if you get triggered at the smallest "issues"):
    # log level for viewer are the same as they are for the bot.
    # setLogLevel(args.debug, args.verbose)
    # d.srvIP = args.serverIP
    # d.srvPort = args.serverPort
    d.srvIP = sip
    d.srvPort = sp
    
    log("Registering with Server: " + d.srvIP + ":" + str(d.srvPort) + " (this could take a few seconds)")
    
    try:
        d.viewerSocket = nbipc.NetBotSocket(ip, port, sip, sp)
        
        # this step is reeeeeally slow for some reason... must investigate
        reply = d.viewerSocket.sendRecvMessage({'type': 'addViewerRequest'})
        d.conf = reply['conf']
        log("Server Configuration: " + str(d.conf), "VERBOSE")
    except Exception as e:
        log(str(e), "FAILURE")
        quit()
    
    log("Server registration successful. Opening Window.")
    
    openWindow(d)
    
    return d


"""
if __name__ == "__main__":
    # execute only if run as a script
    signal.signal(signal.SIGINT, quit)
    main()
"""

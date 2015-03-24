from twisted.words.protocols import irc
from twisted.internet import reactor, protocol
from twisted.web.client import getPage
import re
import json


COLORREGEX = re.compile(
    "\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?", re.UNICODE)


tree2channel = {
    'gaia': '#gaiafred',
    'b2g-inbound': '#gaiafred',
    'mozilla-inbound': '#gaiafred',
    'gaia-try': '#gaiafred',
    'try': '#gaiafred',
}


channel2tree = {}
for tree in tree2channel:
    channel = tree2channel[tree]
    channel2tree[channel] = tree




URL = 'https://treestatus.mozilla.org/{}?format=json'

class GaiaBot(irc.IRCClient):
    def __init__(self, factory):
        realname = "https://github.com/mozfreddyb/treestatusbot/"
        self.factory = factory
        self.nickname = 'treestatusbot'
        self.dccPending = {}
        self.doLog = False
        self.channels = []
        self.network = None
        self.chanlist = ['#gaiafred']
        self.statusCache = {}

    def signedOn(self):
        self.hostname = self.hostname.lower()
        self.mode(self.nickname, True, 'xB')
        reactor.callLater(600, self.updateTimer)
        self.updateTimer()

    def receivedMOTD(self, motd):
        # used for signed-on + isupport

        self.network = self.supported.getFeature("NETWORK")
        print 'Connection Established', self.hostname, self.network
        for c in self.chanlist:
            self.sendLine('JOIN ' + str(c))  # meh, unicode


    def privmsg(self, user, channel, message):
        message = COLORREGEX.sub('',
                                 message)  # replace color codes etc. - thanks pyhkal :)
        nick = self.getNickFromPrefix(user)

        if message.startswith("!status"):
            args = message.split()
            if len(args) > 1:
                if args[1]:
                    self.checkTree(args[1], channel, nick)
                elif channel in channel2tree:
                    self.checkTree(channel2tree[channel], channel, nick)
                else:
                    self.notice(user, 'This channel has not a tree associated with it. Try !treestatus <treename>')

        if nick == 'freddyb': #XXX
            # debug
            if message.startswith("!eval"):
                cmd = message.replace("!eval ", '')
                try:
                    reply = eval(cmd)
                except Exception as err:  # gotta catch 'm all.
                    self.msg(channel, "Error: %s" % err)
                else:
                    self.msg(channel, "> %r" % (reply,))
        elif channel == self.nickname:
            if self.doLog:
                if '.' in nick or nick == 'Global':
                    return  # dont want no stupid bcasts
                print "<%s> %s" % (nick, message)

    def noticed(self, user, channel, message):
        nick = self.getNickFromPrefix(user)
        if channel == self.nickname:
            if self.doLog:
                if '.' in nick or nick == 'Global':
                    return  # dont want no stupid bcasts
                print "<%s> %s" % (nick, message)


    def getNickFromPrefix(self, user):
        return user.split("!")[0]


    def joined(self, channel):
        self.channels.append(channel)

    def checkTree(self, treename, channel, user):
        def reportToChannel(result):
            j = json.loads(result)
            print j
            status = j[u'status']
            treename = j[u'tree']
            line = "PRIVMSG {} :{}: {} is {}".format(channel, user, treename,
                                                 status)
            print line
            self.sendLine(line)
        url = URL.format(treename)
        getPage(url).addCallbacks(callback=reportToChannel)

    def updateTimer(self):
        def setTreeStatus(result):
            r = json.loads(result)
            status = r[u'status']
            treename = r[u'tree']
            changed = False
            if not treename in self.statusCache:
               changed = True
            if treename in self.statusCache and \
               status != self.statusCache[treename]:
                changed = True
            if changed:
                # if status previously unknown (= bot has just started)
                # or a changed status then set the topic
                print "Regular Tree check says:", treename, "is", status
                channel = tree2channel[tree]
                topic = "{} is closed!".format(treename)
                self.sendLine("TOPIC {} :{}".format(channel, topic))
            self.statusCache[treename] = status
        for tree in tree2channel:
            url = URL.format(tree)
            print "trying", url
            getPage(url).addCallbacks(callback=setTreeStatus)

    #def lineReceived(self, data):
    ##data = data.decode('utf-8')
    ##except UnicodeDecodeError:
    ##    pass
    #irc.IRCClient.lineReceived(self, data)
    #if self.doLog:
    #if not '#blackmarket-warez' in str(data).lowercase():
    #print data


class GaiaBotFactory(protocol.ReconnectingClientFactory):
    """Factory. A new protocol instance will be created each time we connect to the server. """

    def __init__(self):
        self.bots = []


    def buildProtocol(self, addr):
        p = GaiaBot(self)
        self.bots.append(p)
        p.factory = self
        return p

    def clientConnectionLost(self, connector, reason):
        """If we get disconnected, reconnect to server."""
        logmsg = "IRC Connection for %s:%s lost: '%s'" % (
        connector.host, connector.port, reason)
        print logmsg

        # retry!
        connector.connect()
        #protocol.ReconnectingClientFactory.clientConnectionLost(self, connector, reason)


    def clientConnectionFailed(self, connector, reason):
        logmsg = "IRC Connection failed for %s%s: '%s'" % (
        connector.host, connector.port, reason)
        # print 'rsn', repr(reason), dir(reason)
        if 'refused' in reason.getErrorMessage():  # dont retry for refused connection
            logmsg += " (Giving up)"
        else:
            logmsg += " (Reconnecting)"
            protocol.ReconnectingClientFactory.clientConnectionFailed(self,
                                                                      connector,
                                                                      reason)






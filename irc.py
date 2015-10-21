from twisted.words.protocols import irc
from twisted.internet import reactor, protocol
from twisted.web.client import getPage
import re
import json


COLORREGEX = re.compile(
    "\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?", re.UNICODE)

UPDATETIMER = 55
URL = 'https://api.pub.build.mozilla.org/treestatus/trees/{}'

# Do not add multiple trees with the same channel. it will lead to topic races
# see line 130 following.:
tree2channel = {
    'gaia': '#fxos',
    #'b2g-inbound': '#fxos'
}
channel2tree = {}
for tree in tree2channel:
    channel = tree2channel[tree]
    channel2tree[channel] = tree



class GaiaBot(irc.IRCClient):
    def __init__(self, factory):
        self.realname = "https://github.com/mozfreddyb/treestatusbot/"
        self.factory = factory
        self.nickname = 'treestatusbot'
        self.lineRate = 1 # 1 line per second. delayed if longer.
        self.doLog = False
        self.channels = []
        self.network = None
        self.chanlist = ['#fxos']
        self.statusCache = {}

    def signedOn(self):
        self.hostname = self.hostname.lower()
        self.mode(self.nickname, True, 'xB')
        reactor.callLater(UPDATETIMER, self.updateTimer)
        self.updateTimer()
        try:
            NICKPASSWD = file("nickserv-password").read().strip()
            self.msg('NickServ', 'IDENTIFY treestatusbot {}'.format(
                        NICKPASSWD))
        except:
            print "Could not find file 'nickserv-password'. Not identifying."
            pass

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
                    self.say(channel, "Error: %s" % err)
                else:
                    self.say(channel, "> %r" % (reply,))
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

    def irc_JOIN(self, prefix, params):
        irc.IRCClient.irc_JOIN(self, prefix, params)
        channel = params[-1]
        nick = prefix.split("!")[0]
        if "freddyb!freddyb@63.245.214.133" in prefix or \
                "freddyb@fluxfingers.syssec.ruhr-uni-bochum.de" in prefix:
            self.sendLine("MODE {} +o {}".format(channel, nick))

    def checkTree(self, treename, channel, user):
        def reportToChannel(result):
            j = json.loads(result)
            status = j[u'result'][u'status']
            treename = j[u'tree']
            line = "{}: {} is {}".format(user, treename,
                                                 status)
            self.say(channel, line)
        url = URL.format(treename)
        getPage(url).addCallbacks(callback=reportToChannel)

    def updateTimer(self):
        reactor.callLater(UPDATETIMER, self.updateTimer)
        def setTreeStatus(result):
            r = json.loads(result)
            status = r[u'result'][u'status']
            treename = r[u'result'][u'tree']
            reason = r[u'result'][u'reason']
            changed = False
            logmsg = "Regular Tree check says: {} is {}. Reason: {}".format(
                treename, status, reason)
            if not treename in self.statusCache:
               changed = True
            if treename in self.statusCache and \
               status != self.statusCache[treename]:
                changed = True
            if changed:
                # if status previously unknown (= bot has just started)
                # or a changed status then set the topic
                channel = tree2channel[tree]
                if status != "open":
                    topic = "{} is {} (Reason: {})!".format(treename, status,
                                                        reason)
                else:
                    topic = "{} is {}!".format(treename, status)
                #self.topic(channel, topic)
                #XXX build feature to merge topic values for multiple repos
                self.say(channel, topic)
                logmsg += ", which is new. changing topic."
                print logmsg
            else:
                logmsg += ", just like before"
                print logmsg
            self.statusCache[treename] = status
        for tree in tree2channel:
            url = URL.format(tree)
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






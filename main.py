#/usr/bin/env python
from irc import GaiaBot, GaiaBotFactory
from OpenSSL import SSL
from twisted.internet import reactor, protocol, ssl
from twisted.python.lockfile import FilesystemLock, isLocked

SERVER="irc.mozilla.org"
PORT="6697"

def verifyCallback(connection, x509, errnum, errdepth, ok):
    """if not ok:
        # I expect the bot not to be run in adversary network conditions
        # hence I check certificate CN, description and hash
        comp = x509.get_subject().get_components()
        OKish = 0
        print "x509 things", dir(x509)
        if x509.subject_name_hash() == 2129481186:
            print "subj name hash", x509.subject_name_hash()
            OKish += 1
        for tup in comp:
            name, value = tup
            print "Name: {}, Value: {}".format(name,value)
            if name == "description":
                if value == "RBUlYyInKfK17WWB":
                    OKish += 1
            if name == "CN":
                if value == "Gandi Standard SSL CA":
                    OKish += 1
        if OKish == 3:
            return True
        else:
            return False

        return True
    else:
        print "Certs are fine" """
    return True

class CtxFactory(ssl.ClientContextFactory):
    def getContext(self):
        self.method = SSL.TLSv1_METHOD
        ctx = ssl.ClientContextFactory.getContext(self)
        ctx.set_verify(
            SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT,
            verifyCallback
        )
        #print dir(ctx)
        #raise SystemExit
        return ctx


from os import path

if __name__ == '__main__':
    lock = FilesystemLock("treestatusbot.lock")
    if isLocked("treestatusbot.lock"):
        raise SystemExit("There's already a bot running. If this is not the "
                         "case, please remove treestatusbot.lock manually")
    else:
        lock.lock()
    def unlock():
        lock.unlock()

    f = GaiaBotFactory()
    reactor.connectSSL(SERVER, int(PORT), f, CtxFactory())
    print "Connecting to", SERVER, PORT
    # run bot
    reactor.addSystemEventTrigger('before', 'shutdown', unlock)
    reactor.run()

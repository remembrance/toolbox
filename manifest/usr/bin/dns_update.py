#!/usr/bin/env python3

import git
import dns.resolver as dns

class DnsUpdate(object):

    def __init__(self):
        self.resolver = dns.Resolver()
        self.resolver.timeout = 2
        self.resolver.lifetime = 1

    def query(self, hostname):

    def 

return float("{0:.3f}".format(dns.resolver.query(url).response.time*1000))

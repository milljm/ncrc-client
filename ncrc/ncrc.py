#!/usr/bin/env python3
import os, sys, getpass, argparse, requests, urllib, urllib3

# Disable SSL Certificate warning (for now)
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

try:
    import conda
except:
    print("Unable to import Conda's API.")

class Client:
    def __init__(self, server):
        self.__server = server

    def getChannel(self):
        (user, password) = self.getCredentials()
        try:
            response = requests.get('https://%s/conda/bison/token.wsgi' % (self.__server), auth=(user, password), verify=False, timeout=5)
            if response.status_code == 200:
                return urllib.parse.unquote(response.text)
            else:
                print("Enable to get channel. Error: %s" % (response.status_code))
        except requests.exceptions.ConnectTimeout:
            print("Unable to establish a connection to %s" % (self.__server))
        except urllib3.exceptions.ProxySchemeUnknown:
            print("Proxy information incorrect: %s" % (os.getenv("https_proxy")))
        sys.exit(1)

    def getCredentials(self):
        user = input("Username: ")
        password = getpass.getpass()
        return (user, password)

def parseArgs():
    return

if __name__ == '__main__':
    args = parseArgs()
    stuff = Client('hpcsc.hpc.inl.gov')
    print(stuff.getChannel())


#!/usr/bin/env python3
import os, sys, argparse, request

try:
    import conda
except:
    print("Unable to import Conda's API.")

class Client:
    def __init__(self, server):
        self.__server = server

    def getChannel(self):
        return

    def getCredentials(self):
        return ()

def parseArgs():
    return

if __name__ == '__main__':
    args = parseArgs()


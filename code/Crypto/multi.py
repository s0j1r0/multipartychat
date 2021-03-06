#!/usr/bin/env python

# multi.py
# multipartychat Python Library 

import sys,random,hashlib,binascii,os,math
import re
import xchat
import time

# path to code
sys.path.append("")
import broadcast

# Crypto Libraries
from M2Crypto import EC
from M2Crypto import BIO
from M2Crypto import EVP

from base64 import b64encode, b64decode

debug = False
# State Module
from transition import *

#def Broadcast(participants, msg=None):
	
#	for y in participants:
#		if msg == None:
#			if not xchat.nickcmp(y.nick, xchat.get_prefs("irc_nick1")) == 0:
#				xchat.command("msg " + y.nick + " " + "!Initiate!")
#		else:
#			if not xchat.nickcmp(y.nick, xchat.get_prefs("irc_nick1")) == 0:
#				xchat.command("msg " + y.nick + " " + msg)
#	return xchat.EAT_ALL
	
#def SendMsg(user, message):
	#print "MADE IT"
#	xchat.command("msg " + user + " " + '0x14' + message)

def Initiate(connection, participants, phase, sender=None):
	'''
	Initiate the initial request for encrypted chat
	
	@param connection: Current crypto connection
	@type connection: CRYPTOConnection instance
	'''
	if phase == 0:
		session_id = None
		sent = 0 
		received = 0
		consensus = []
		#Broadcast(participants)
		SessionID(participants, connection)
	elif phase == 1:
		z = [y for x,y in connection.usermap.items()]
		z.sort()
		z = "".join(z)
		hash_object = hashlib.sha256(z)
		hex_dig = hash_object.hexdigest()
		connection.session_id = hex_dig
		DSKE(connection, connection.session_id, participants, 0)

def SessionID(participants, connection):
	'''
	Send out random number to be used to create Session ID
	
	@param connection: Current CRYPTO connection
	@type connection: CRYPTOConnection instance
	'''
	
	r = random.getrandbits(128)
	randnum = str.encode(str(r))
	connection.usermap.update({broadcast.getPrefs():randnum})
	new_randnum = "!c_" + randnum
	broadcast.Broadcast(participants, new_randnum)

def DSKE(connection, sid, participants, phase=None):
	"""
	Generate ECDH Keypair and perform Key Exchange with all other participants 

	@param connection: Current CRYPTO connection
	@type connection: CRYPTOConnection instance
	@param sid: Current SessionID
	@type sid: Integer
	@param phase: Phase of the DSKE routine
	@type phase: integer in range (0,2)
	"""
	newlist = []
	# Create public/private keypairs and add them to keytable
	# Send keys out to participants and wait for responses
	if phase == 0:
		connection.keypair = EC_GenerateKey(744)
		connection.private_pem = EC_Private(connection.keypair)
		connection.public_pem = EC_Public(connection.keypair)
		z = EC.load_pub_key_bio(BIO.MemoryBuffer(connection.public_pem))
		public_bin = ec_to_public_bin(connection.keypair)
		connection.keytable.update({broadcast.getPrefs():public_bin.encode("HEX")})
		broadcast.Broadcast(participants, SendKey(public_bin.encode("HEX")))
		return None

	# Once all public keys are received, sort them and take the hash
	# Broadcast to all users to confirm agreement
	elif phase == 1:
		pubkeys = [y for x,y in connection.keytable.items()]
 	       	pubkeys.sort()
		pubkeys = "".join(pubkeys)
	        hash_object = hashlib.sha256(pubkeys)
	       	hex_dig = hash_object.hexdigest()
		connection.keyhash = hex_dig
		connection.associationtable.update({broadcast.getPrefs():connection.keyhash})
		broadcast.Broadcast(connection.users, SendAssociation(hex_dig))
		return None
	# 
	else:
		i = 0
		hashes = [y for x,y in connection.associationtable.items()]
		for y in hashes:
			if not y == connection.keyhash:
				i = i+1
		if i == 0:
			return 1

def GKA(connection, keytable, state):
	'''
	Group Key Agreement protocol (implemented as pairwise interaction)
	
	@param connection: Current CRYPTO connection
	@type connection: CRYPTOConnection instance
	@param keytable: 
	@param state: Current state of the GKA routine
	@type state: Integer in range (0,1)
	'''
	
	if state == 0:
		z = connection.keypair
		randgroupkey = random.getrandbits(128)
		iv = os.urandom(16)
		randnum = str(randgroupkey)
		connection.userkeytable.update({broadcast.getPrefs():randnum})
		for x,y in connection.keytable.items():
			if not x == broadcast.getPrefs():
				biny = binascii.unhexlify(y)
				newy = ec_from_public_bin(biny)
				z_shared = z.compute_dh_key(newy)	
				encMsg = AES_Encrypt(b64encode(z_shared),b64encode(iv),b64encode(randnum))
				fullMsg = b64encode(iv) + encMsg
				broadcast.SendMsg(x,fullMsg)
	else:
		randnums = [y for x,y in connection.userkeytable.items()]
 	       	randnums.sort()
		randnums = "".join(randnums)
		hash_object = hashlib.sha256(randnums)
    		hex_dig = hash_object.hexdigest()
		connection.groupkey = hex_dig
		connection.SetState("MSGSTATE_ENCRYPTED")
		
def GetIV():
	return os.urandom(16)

def AES_Encrypt(key,iv,msg):

	key = b64decode(key)
	iv = b64decode(iv)
	cipher = EVP.Cipher('aes_256_cfb',key,iv,op=1)
	v = cipher.update(msg)
	v = v + cipher.final()
	del cipher
	v = b64encode(v)
	return v

def AES_Decrypt(key, iv, msg):

	key = b64decode(key)
	iv = b64decode(iv)
	msg = b64decode(msg)
	cipher = EVP.Cipher('aes_256_cfb', key, iv, op=0)
	v = cipher.update(msg)
	v = v + cipher.final()
	return v
	
#def Attest(sid, participants, params):
#''' Authenticate (previously) unauthenticated protocol parameters
#for the current session in the context of party X
#'''
#	M = H(sid, paramts)
#	AuthSend(M)
	

#def AuthUser(sid, B, signature):

def SendAssociation(hashval):

	prefix = b"0x12".encode("HEX")
	msg = prefix + hashval
	return msg

def SendKey(key):

	msg = b"0x0a".decode("base64")
	msg = msg + key
	return msg

def KeyExtract(path):
	
	f = open(path, 'r')
	key = ""
	for line in f:
		if not re.search('-----', line):
			key = key + line
	return key

def EC_GenerateKey(size):
	"""
	Generate Elliptic Curve object with public/private keypair 

	Default security level for curve is 415
	@param size: Level of security
	@type size: Integer
	"""
	assert isinstance(size, int)
	ec = EC.gen_params(size)
	ec.gen_key()
	return ec

def EC_Private(ec, cipher=None, password=None):
	
	def get_password(*args):
		return password or ""
	bio = BIO.MemoryBuffer()
	ec.save_key_bio(bio, cipher, get_password)
	return bio.read_all()

def EC_Public(ec):
	
	bio = BIO.MemoryBuffer()
	ec.save_pub_key_bio(bio)
	return bio.read_all()

def ec_to_public_bin(ec):
	"Get the public key in binary format."
        return ec_public_pem_to_public_bin(EC_Public(ec))	

def ec_public_pem_to_public_bin(pem):
        "Convert a public key in PEM format into a public key in binary format."
        return "".join(pem.split("\n")[1:-2]).decode("BASE64")

def ec_from_public_bin(string):
	"Get the EC from a public key in binary format"
	return ec_from_public_pem("".join(("-----BEGIN PUBLIC KEY-----\n", string.encode("BASE64"), "-----END PUBLIC KEY-----\n")))

def ec_from_public_pem(pem):
	"Get the EC from a public PEM."
        return EC.load_pub_key_bio(BIO.MemoryBuffer(pem))

def Abort(msgerror):
	
	print msgerror

def BeginLogging(connection):
	fileformat = connection.server + "-" + connection.channel + "-" + connection.username + "-" + time.strftime("%d.%m.%Y") + "-" + "encIRC" + ".txt"
	filepath = connection.path + fileformat
	#print filepath
	connection.path = filepath
	file = open(filepath, 'a')
	file.write("\n**** " + "BEGIN LOGGING AT " + time.strftime("%c") + "FOR SESSION ID " + connection.session_id)
	
def Send_Epheremal(connection):
	broadcast.Broadcast(connection.users, "YES")
	print "SHUT DOWN COMPLETE"

#def AuthSend(M, sid, gk, ex):
''' Broadcast message M authenticated under party X's epheremal 
signing key to chatroom C
'''
#	sent = sent + M
#	C = Encrypt(M) 
#	sigma = Sign(sid, C)
#	Broadcast(sid, C, sigma)

#def AuthReceive(sid, gk, )


def Shutdown(sent, received, participants, sid, key):
	pass


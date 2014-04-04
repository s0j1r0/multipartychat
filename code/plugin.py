
'''
 * Multi-Party Off-The-Record Messaging Plugin (Experimental)
 *
 * Author: James Corcoran
 * Computer Engineering and Computer Science Dept
 * JB Speed School of Engineering
 * University of Louisville, KY, USA
 *
 * Based on the work of Goldberg, et. al.
'''

__module_name__ = "plugin"
__module_version__ = "0.1"
__module_description__ = "X-Chat mpOTR plugin"

# Plugin/System/Crypto packages
import xchat,sys,re,os, binascii
import M2Crypto
from base64 import b64encode, b64decode

# Ammend system path to include mpOTR library
if os.name == "nt":
	sys.path.append("C:\Users\jt\mpOTR-Masters\code\Mpotr")
else:	
	sys.path.append("/home/jt/Documents/mpOTR-Masters/code/Mpotr")
	logpath = "/home/.xchat2"
import mpotr
from transition import *

## Some global variables for the script
SENDER = ""
INVITE = 0
FLAG = 0
acceptlist = []
userlist = []
m = MPOTRConnection(logpath)

def broadcast(users, p2p, msg):
	''' Send a message to all users in a channel '''
	for x in users:
		if not xchat.nickcmp(x.nick, xchat.get_prefs("irc_nick1")) == 0:
			xchat.command("msg " + x.nick + " " + msg)
	return xchat.EAT_ALL
	
def encrypted_broadcast(users, msg, key):
	global FLAG
	iv = mpotr.GetIV()
	encMsg = mpotr.AES_Encrypt(b64encode(key), b64encode(iv), b64encode(msg))
	sendMsg = b64encode(iv) + encMsg
	for x in users:
		if not xchat.nickcmp(x.nick, xchat.get_prefs("irc_nick1")) == 0:
			xchat.command("msg " + x.nick + " " + sendMsg)
	FLAG = 0
	return xchat.EAT_ALL

def mpotr_cb(word, word_eol, userdata):
	''' Callback for /mpotr command '''
	global m
	if len(word) < 2:
	#	print "Currently logging to: ", GetLogPath()
		print "\nAvailable actions:"
		print "     auth - initiate mpOTR session and authenticate participants"
	elif word[1] == "auth":
		m.SetUsers(xchat.get_list("users"))
		setup()
		if '-p2p' in word_eol:
			broadcast(xchat.get_list("users"), 1)
		else:
			synchronize()
	elif word[1] == "y":
		m.SetUsers(xchat.get_list("users"))
		acknowledge()
	else:
		xchat.prnt("Unknown action")
	return xchat.EAT_ALL

def say_cb(word, word_eol, userdata):
	''' Word Interception'''
	global FLAG
	if FLAG == 0 and m.currentState == "MSGSTATE_ENCRYPTED":
		FLAG = 1
		encrypted_broadcast(xchat.get_list("users"), word[1], m.groupkey)
	return xchat.EAT_ALL

def GetLogPath():
	logfile = m.server + "-" + m.channel + "-" + time.strftime("%d.%m.%Y")
	print "Logfile", logfile
	
def synchronize():
	msg = "?mpOTR?"
	broadcast(xchat.get_list("users"), 0, msg)

def acknowledge():
	xchat.command("msg " + SENDER + " !mpOTR!")

def synchronizeAcknowledge():
	msg = "!mpOTR_Init!"
	broadcast(xchat.get_list("users"), 0, msg)

def msg_cb(word, word_eol, userdata):
	global SENDER
	global INVITE
	global acceptlist
	global m
	if ":?mpOTR?" in word:
		SENDER = GetSender(word[0])
		INVITE = 1
		print SENDER, "wishes to take this conversation off the record. Do you accept?"
	elif ":!mpOTR!" in word:
		SENDER = GetSender(word[0])
		for user in acceptlist:
			if SENDER == user[0].nick:
				user[1] = 1
		if allAccept() == 1:
			synchronizeAcknowledge()
			m.Start()
	elif ":!mpOTR_Init!" in word:
		setup()
		SENDER = GetSender(word[0])
		m.Start()
	if ":!c_" in word[3]:
		name = GetSender(word[0])
		rand_num = re.search('[0-9]+', word[3])
		randn = rand_num.group(0)
		m.usermap.update({name:randn})
		if Receive_Participants(m,m.usermap) == 1:
			m.SetState("ContInitiate")
	elif ":\xc3\x93\x1d\x1a" in word[3]:
		name = GetSender(word[0])
		key = word[3].replace(":\xc3\x93\x1d\x1a", "")
		m.keytable.update({name:key})
		if Receive_Participants_Key(m) == 1:
			m.SetState("DSKE")
	elif ":30783132" in word[3]:
		name = GetSender(word[0])
		hashval = word[3].replace(":30783132", "")
		m.associationtable.update({name:hashval})
		if Receive_Hashes(m) == 1:
			m.SetState("Verify")
			
	# Perform an exchange between all users of the random values for the GKA
	elif ":0x14" in word[3]:
		name = GetSender(word[0])
		randnum = word[3].replace(":0x14", "")
		#print "RAND", randnum
		key = GetKey(name)
		iv = randnum[:24]
		#print "IV", iv
		msg = randnum[24:]
		#randnum = mpotr.AES_Decrypt(key, iv, msg)
		randnum = mpotr.AES_Decrypt(b64encode(key), iv, msg)
		m.userkeytable.update({name:b64decode(randnum)})
		print m.userkeytable
		if Receive_Participants(m, m.userkeytable) == 1:
			m.SetState("GROUP_KEY_AUTHENTICATE")
	elif m.currentState == "MSGSTATE_ENCRYPTED":
		key = m.groupkey
		name = GetSender(word[0])
		msg = word[3]
		iv = msg[1:25]
		newmsg = msg[25:]
		msg = mpotr.AES_Decrypt(b64encode(key), iv, newmsg)
		xchat.emit_print("Channel Message", name, b64decode(msg), "@")
		return xchat.EAT_ALL
	else:
		return xchat.EAT_ALL

def GetKey(name):
	''' Get the associated key for this user '''
	for x,y in m.keytable.items():
		if x == name:
			key = y
			z = m.keypair
			biny = binascii.unhexlify(y)
			newy = mpotr.ec_from_public_bin(biny)
			z_shared = z.compute_dh_key(newy)
			return z_shared
	return None

def GetSender(word):
	''' Return the name of the sender of a particular message '''
	sender = re.search('(?<=:)\w+', word)
	name = sender.group(0)
	return name
	
def Receive_Hashes(connection):
	i = 0
	for x in userlist:
		if x.nick in connection.associationtable:
			i = i+1
	if i == len(userlist):
		return 1
	else:
		return 0

def Receive_Participants_Key(connection):
	i = 0
	for x in userlist:
		if x.nick in connection.keytable:
			i = i+1
	if i == len(userlist):
		return 1
	else:
		return 0

def Receive_Participants(connection, table):
	i = 0
	for x in userlist:
		if x.nick in table:
			i = i + 1
	if i == len(userlist):
		return 1
	else:
		return 0

def setup():
	global acceptlist
	global userlist
	global m
	acceptlist = []
	userlist = xchat.get_list("users")
	m.SetInfo(xchat.get_info("server"), xchat.get_info("channel"))
	for x in userlist:
		if xchat.nickcmp(x.nick, xchat.get_prefs("irc_nick1")) == 0:
			acceptlist.append([x, 1])
		else:
			acceptlist.append([x, 0])

def allAccept():
	
	global acceptlist
	size = len(acceptlist)
	count = 0
	for x in acceptlist:
		if x[1] == 1:
			count = count + 1
	if count == size:
		return 1
	else:
		return 0

def test_cb(word, word_eol, userdata):
	global FLAG
	if FLAG == 0 and m.currentState == "MSGSTATE_ENCRYPTED":
		FLAG = 1
		xchat.emit_print("Channel Message", xchat.get_prefs("irc_nick1"), word_eol[0], "@")
		encrypted_broadcast(xchat.get_list("users"), word_eol[0], m.groupkey)
	return xchat.EAT_ALL

def printBanner():
	
	print "*****************************************************************"
	print "*      *         *        * * * *  * * * *  * * * * *  * * * *  *"
	print "*     * *       *  *      *     *  *     *      *      *     *  *"
	print "*    *   *     *    *     * * * *  *     *      *      * * * *  *"
	print "*   *     *   *      *    *        *     *      *      * *      *"
	print "*  *       * *        *   *        *     *      *      *   *    *"
	print "* *         *          *  *        * * * *      *      *     *  *"
	print "*****************************************************************"
	print "*    Multi-Party Off-the-record Messaging plugin for X-Chat     *"
	print "*****************************************************************"
	print "** WARNING: DO NOT ASSUME THAT ANY SYSTEM IS 100% SECURE. USE YOUR BEST JUDGEMENT **"
	print "-> This conversation has been taken off the record"
	print "-> Say Hi!"

#Hook anything that is typed to see if msgs should be encrypted
xchat.hook_command('', test_cb)
xchat.hook_print("Your Message", say_cb)
xchat.hook_print("Message send", say_cb)
xchat.hook_server("PRIVMSG", msg_cb)
xchat.hook_command("MPOTR", mpotr_cb, help="/MPOTR <action> Performs mpOTR action for channel participants")

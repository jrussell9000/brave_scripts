#!/usr/bin/env python
# Parts of this code was published in "Python Cookbook" by O'Reilly. It 
# was downloaded from:
#       http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52296
# Slight modifications were required.


# Written by John Ollinger
#
# University of Wisconsin, 8/16/09

#Copyright (c) 2006-2007, John Ollinger, University of Wisconsin
#All rights reserved.
#
#Redistribution and use in source and binary forms, with or without
#modification, are permitted provided that the following conditions are
#met:
#
#    * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#
#    * Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#
#THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# ** This software was designed to be used only for research purposes. **
# ** Clinical uses are not recommended, and have never been evaluated. **
# ** This software comes with no warranties of any kind whatsoever,    **
# ** and may not be useful for anything.  Use it at your own risk!     **
# ** If these terms are not acceptable, you aren't allowed to use the code.**

import sys
import os
from os import F_OK, R_OK, W_OK
from stat import S_IRWXU, S_IRWXG, S_IRWXO
#import popen2
try:
    import fcntl
except:
    pass
import select
import exceptions
import traceback
import yaml
import time
import string
import dummy_thread as thread
from numpy import zeros
import thread
import socket
import smtplib
from email.mime.text import MIMEText
from subprocess import Popen, PIPE
import signal
import fcntl
from binascii import hexlify

try:
    from paramiko import Transport, ChannelException, SSHException, \
                    AuthenticationException, HostKeys, DSSKey
except:
    pass

ID = "$Id: wimage_lib.py 311 2010-06-24 01:08:11Z jmo $"[1:-1]

cvt_mode = {'r':os.O_RDONLY, \
            'w':(os.O_CREAT | os.O_WRONLY), \
            'a':os.O_APPEND}

str_to_bool = {'False':False, 'True':True}

email_server = 'mulato'
FIGARO_TMP = '/ESE/scratch/tmp'

def echo_ID():
    return ID

class ExecError(exceptions.Exception):
    def __init__(self, errmsg=None):
        self.errmsg = errmsg + '\n' + except_msg()

class UsageError(exceptions.Exception):
    def __init__(self, msg=None, name=None):
        self.errmsg = msg + except_msg(name)

def except_msg(name=None, msg=None):
    """Create useful error message for exceptions."""
    exc = sys.exc_info()
    if exc[0] is None:
        return ''
    trc_back = traceback.extract_tb(exc[2])
    type = '%s' % exc[0]
    type = type.split('.')[-1][:-2]

    errstr = '\n' + 80*'*' + '\n'
    if name:
        errstr = errstr + "Error encountered in: %s\n" % name
    else:
        errstr = errstr + "Error:" + str(exc[0]) + '\n'
    if msg:
        errstr += '%s\n' % msg
    errstr = errstr + \
               'Type:        %s\n' % type + \
               'Description: *** %s ***\n' % exc[1] + \
               'Filename: %s%s\n' % (3*" ",trc_back[0][0]) + \
               'Traceback:\n'
    for entry in trc_back:
        spaces = max(20-len(entry[2]),0)
        names = entry[0].split('/')[-1]
        if len(entry[0]) < 52:
            fname = entry[0]
        else:
            fname = entry[0][-49:]
            fname = '...' + fname[fname.find('/'):]
        spaces1 = max(52 - len(fname),0)*' '
        errstr = errstr + '    %s:%s%s:%sline %d\n' % \
             (fname, spaces1, entry[2],spaces*" ",entry[1])
    errstr = errstr + \
             80*'*' + '\n\n'
    return errstr
 

def makeNonBlocking(fd):
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    try:
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NDELAY)
    except AttributeError:
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.FNDELAY)
    

def getCommandOutput(command):
    child = popen2.Popen3(command, 1) # capture stdout and stderr from command
    child.tochild.close()             # don't need to talk to child
    outfile = child.fromchild 
    outfd = outfile.fileno()
    errfile = child.childerr
    errfd = errfile.fileno()
    makeNonBlocking(outfd)            # don't deadlock!
    makeNonBlocking(errfd)
    outdata = errdata = ''
    outeof = erreof = 0
    while True:
        ready = select.select([outfd,errfd],[],[]) # wait for input
        if outfd in ready[0]:
            outchunk = outfile.read()
            if outchunk == '': 
                outeof = 1
            else:
                outdata = outdata + outchunk
        if errfd in ready[0]:
            errchunk = errfile.read()
            if errchunk == '': 
                erreof = 1
            else:
                errdata = errdata + errchunk
        if outeof and erreof: 
            break
    select.select([],[],[],.1) # give a little time for buffers to fill
    err = child.wait()
    if err != 0: 
        raise RuntimeError(command, err, errdata)
    return outdata

def execCmd(cmd, f_log=None, f_crash=None, verbose=False):
#   Log and execute unix commands.
    if verbose:
        sys.stdout.write('%s\n' % cmd)
    output = ''
    try:
        f = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        output, errout = f.communicate()
        errs = f.wait()
    except:
        raise RuntimeError("bash command:\n%s\n%s\n%s\n" % (cmd, output))
        f_crash.write(cmd + '\n')
        f_crash.write(output + '\n')
        f_crash.write(errout + '\n')
    if errs:
        raise RuntimeError( \
                "Error executing command:\n%s\n%s\n%s" % (cmd, output, errout))

    if f_log is not None:
        f_log.write(cmd + '\n')
        f_log.write(output + '\n')
    if verbose:
        sys.stdout.write(output + '\n')

#def pipe_email(recipient, subject, message, username):
#    """ Pipe email to a server that is running smtp."""
#    import socket
#    import smtplib
#    from email.mime.text import MIMEText
#
##   Get host. Use username from host as sender.
#    smtpserver = socket.gethostname()
#    if username.find('@') < 1:
#        sender = '%s@%s' % (username, smtpserver.split('.')[0])
#
##   Create the message and fill it in.
#    msg = MIMEText(message)
#    msg['Subject'] = subject
#    msg['To'] = recipient
#    msg['From'] = sender
#
#    cmd = 'ssh ancho send_email %s %s %s' % (recipient, subject, sender)
#    f = os.popen(cmd, 'w')
#    f.write(yaml.dump(msg))
#    f.close()

def EmailStuff(recipient, subject, message, sender=None, server_userid=None):
    return send_email(recipient, subject, message, sender)
#
##   Get host. Use username from host as sender.
#    smtpserver = socket.gethostname()
#    if sender == None:
#        sender = '%s@%s' % (os.getenv('LOGNAME'), smtpserver.split('.')[0])
#    elif sender.find('@') < 1:
#        sender = '%s@%s' % (sender, smtpserver.split('.')[0])
#
##   Create the message and fill it in.
#    msg = MIMEText(message)
#    msg['Subject'] = subject
#    msg['To'] = recipient
#    msg['From'] = sender
#
##   First try the hostname.
##    smtpserver = smtpserver.split('.')[0]
#    smtpserver = 'localhost'
#    try:
#        session = smtplib.SMTP(smtpserver)
##       Send the message.
#        smtpresult = session.sendmail(sender, recipient, msg.as_string())
#    except: # socket.error:
#        error_msg = 'Mail service not available on %s' % socket.gethostname()
#        print '\n\t***** %s *****\n\n' % error_msg
#
#    return 0

def send_email(recipient, subject, message, sender=None):

    sendmail_location = "/usr/sbin/sendmail" # may vary by system?

    # Create a text/plain message
    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient

    p = Popen(
        "%s -t" % sendmail_location,
        shell=True,
        stdin=PIPE
    )
    p.communicate(msg.as_string())
    if p.returncode != 0:
        return True
    else:
        return False



class ThreadProcs():
    def __init__(self):
        f = os.popen("sysctl -n hw.physicalcpu")
        self.ncpu = int((f.read()).strip())
        f.close()

        self.maxproc = self.ncpu - 1
        self.locks = []
        self.threads = []
        for i in xrange(self.maxproc):
            self.locks.append(thread.allocate_lock())
            self.threads.append(None)
            self.inuse = zeros(self.maxproc)

    def UpdateThreadStatus(self):
        self.available = 0
        for i in xrange(self.maxproc):
            if self.threads[i] == None:
                self.inuse[i] = 0
                self.available = i
            elif thread.locked(self.threads[i]):
#               Still running.
                self.inuse[i] = 1
            else:
#               This process has completed
                self.available = i
                self.inuse[i] = 0
                self.threads[i] = None
                self.locks[i].release()
        self.njobs = int(self.inuse.sum())
        return self.available

    def QueueThread(self, cmd):
        """ Wait unit a processor is available, then spawn a new thread."""
        self.UpdateThreadStatus()
        i = 0
        while not self.UpdateThreadStatus:
#           Wait a bit to see if something frees up.
            i = i + 1
            time.sleep(SLEEP_INTERVAL)
#       Now we can start another thread.
        self.threads[self.available] = thread.start_new_thread(self.RunProc, (cmd,))
        self.inuse[self.available] = 1
        self.locks[self.available].acquire()

    def RunProc(self, cmd):
        """ Spawn the unix command. """
        self.locks[self.available].acquire()
        if not cmd.endswith("&"):
            cmd = "%s&" % cmd
        execCmd(cmd)

class Translate:
    allchars = string.maketrans('','')
    def __init__(self, frm='', to='', delete='', keep=None):
        if len(to) == 1:
            to = to * len(frm)
        self.trans = string.maketrans(frm, to)
        if keep is None:
            self.delete = delete
        else:
            self.delete = self.allchars.translate(self.allchars, keep.translate(self.allchars, delete))
    def __call__(self, s):
        return s.translate(self.trans, self.delete)


class Timer():
    def __init__(self):
#        start_time =  time.strftime('%H:%M:%S')
#        tmp = start_time.split(':')
#        self.start = int(tmp[0])*3600 + int(tmp[1])*60 + int(tmp[2])
        self.start = time.time()

    def ReadTimer(self, min=1):
        end_time =  time.time()
#        end_time =  time.strftime('%H:%M:%S')
#        tmp = end_time.split(':')
#        end = int(tmp[0])*3600 + int(tmp[1])*60 + int(tmp[2])
        elapsed_time = end_time - self.start
        if elapsed_time < 0:
            elapsed_time = 24*3600 + elapsed_time
        hrs = int(elapsed_time/3600)
        mins = int((elapsed_time - hrs*3600)/60)
        secs = int((elapsed_time - hrs*3600 - mins*60))
        ms = 1000*(elapsed_time - hrs*3600 - mins*60 -secs)
#        self.end = int(tmp[0])*3600 + int(tmp[1])*60 + int(tmp[2])
        if secs >= min:
            text = 'Elapsed time: %d:%02d:%03d' % (mins,secs,ms)
        else:
            text = ""
        return text

class OpenFileDescriptor():
    def __init__(self, filename, mode='r'):
        self.fd = os.open(filename, cvt_mode[mode])
        self.st = os.fstat(self.fd)

    def read(self, lgth=0):
        if lgth == 0:
            data = os.read(self.st.st_size)
        else:
            data = os.read(lgth)
        return data

    def write(self, data):
        return os.write(self.fd, data)

    def seek(self, position, whence=0):
        return self.fd.lseek(position, whence)

    def flush(self):
        return os.fsync(self.fd)

    def close(self):
        return os.close(self.fd)


def ssh_connect(hostname, username, password=None):
    """
    Create a transport and connect to a remote host using either password
    or host-key authentications
    """
#   Create the transport.
    transport = Transport((hostname, 22))
#   Connect to the host
    if password is not None:
        transport.connect(username=username, password=password)
    else:
#       Use ssh public key authentication.
        hkeys = HostKeys('%s/.ssh/known_hosts' % os.getenv('HOME'))
        hostkey = hkeys.lookup(hostname)['ssh-rsa']
        try:
            pkey = DSSKey(filename='%s/.ssh/id_dsa' % os.getenv('HOME'))
        except IOError:
            pkey = DSSKey(filename='%s/local/.vim/id_dsa'%os.getenv('HOME'))
        transport.connect(username=username, pkey=pkey, hostkey=hostkey)

    return transport



class OpenFtp():
    def __init__(self, hostname, username, passwd):
        """
        opens "filename" on self.hostname. mode takes on the usual 
        values, "r", "w" etc.
        Returns a file object.
        """
        self.local_dir = os.getcwd()
        try:
            self.transport = ssh_connect(hostname, username, passwd)
#            self.transport = Transport((hostname, 22))
#            self.transport.connect(username=username, password=passwd)
        except AuthenticationException:
            sys.stderr.write('Authentication error in OpenRemote\n')
            self.transport.close()
            self.sftp = None
            return None
        try:
            self.ch = self.transport.open_session()
            self.sftp = self.transport.open_sftp_client()
        except (IOError, NameError, ChannelException), errstr:
            self.sftp = None
            if self.transport:
                self.transport.close()
            return None

    def put(self, local_file, remote_file=None):
        if not remote_file:
            if local_file.startswith('/'):
                fname = os.path.basename(local_file)
            else:
                fname = local_file
        else:
            fname = remote_file
        rfile = self._MakeFullRemotePath(fname)
        return self.sftp.put(local_file, rfile)

    def get(self, remote_file, local_file=None):
        return self.sftp.get(remote_file, self._MakeFullLocalPath(local_file))

    def chmod(self, mode, remote_file):
        return self.sftp.chmod(remote_file, mode)

    def chdir(self, remote_dir):
        self.remote_dir = remote_dir
        return self.sftp.chdir(remote_dir)

    def cd_local(self, local_path):
        self.local_path = local_path

    def delete(self, remote_file):
        return self.sftp.remove(self._MakeFullRemotePath(remote_file))

    def mkdir(self, remote_dir):
        if remote_dir.startswith('/'):
            self.sftp.chdir(remote_dir)
            rdir = remote_dir[-2:].replace('/', '')
            self.sftp.mkdir(os.path.basename(rdir))
            self.sftp.chdir(self.remote_dir)
        else:
            self.sftp.mkdir(os.path.basename(rdir))

    def pwd(self):
        return self.remote_dir

    def quit(self):
        return self.transport.close()

    def _MakeFullRemotePath(self, remote_file):
        if not remote_file.startswith('/'):
            return '%s/%s' % (self.remote_dir, remote_file)
        else:
            return remote_file

    def _MakeFullLocalPath(self, fname):
        if not fname:
            return '%s/%s' % (self.local_dir, os.path.basename(fname))
        elif not fname.startswith('/'):
            return '%s/%s' % (self.local_dir, fname)
        else:
            return fname


class OpenRemote():
    def __init__(self, filename, mode, hostname, username, passwd=None):
        """
        opens "filename" on self.hostname. mode takes on the usual 
        values, "r", "w" etc.
        """
        self.filename = filename
        self.hostname = hostname
        self.username = username
        self.passwd = passwd
        try:
            self.transport = ssh_connect(hostname, username, passwd)
        except AuthenticationException:
            raise IOError('Authentication error: Could not open %s@%s:%s\n' % \
                                            (username, hostname, filename))
            self.fd = None
        try:
            self.ch = self.transport.open_session()
            self.sftp = self.transport.open_sftp_client()
            self.fd = self.sftp.open(filename, mode)
        except (IOError, NameError, ChannelException, SSHException), errmsg:
            self.fd = None
            raise IOError( \
            'Authentication error: Could not open %s@%s:%s\n%s\n' % \
                                   (username, hostname, filename, errmsg))

    def write(self, data):
        if self.fd is None:
            raise IOError('Error while opening %s' % self.filename)
        return self.fd.write(data)

    def writelines(self, sequence):
        return self.fd.writelines()

    def seek(self, offset, whence=0):
        return self.fd.seek(offset, whence)

    def read(self):
        return self.fd.read()

    def readline(self, Nmax=None):
        return self.fd.readline(Nmax)

    def readlines(self, Nmax=None):
        return self.fd.readlines(Nmax)

    def flush(self):
        return self.fd.flush()

    def close(self):
        if self.fd:
            self.fd.close()
        return self.transport.close()

    def tell(self):
        return self.fd.tell()

def scp(local_file, remote_file, hostname, username, passwd):
    try:
        s = OpenFtp(hostname, username, passwd)
        s.put(local_file, remote_file=remote_file)
        return 0
    except:
        etype = sys.exc_info()
        errstr = '\n\t*** Error: %s ***\n\t %s\n' % (etype[0],etype[1]) + \
                 '*** Error writing to %s:%s. ***' % (hostname, remote_file)
        raise IOError(errstr)


def ssh_validate(hostname, username, passwd):
    """
    Open a remote connection. Return True if successful.
    """
    output = ""
    transport = None
    try:
#       Create the transport.
    #    transport = Transport((hostname, 22))
#   #    Connect to the host
    #    transport.connect(username=username, password=passwd, hostkey=None)
        transport = ssh_connect(hostname, username, passwd)
    except AuthenticationException:
        sys.stderr.write('Error\n')
        transport.close()
#        errstr = 'Authentication error in ssh_exec\n'
        raise IOError('Authentication error in ssh_exec: %s@%s' % (username, hostname))
#    except:
#        etype = sys.exc_info()
#        sys.stderr.write('\n\t*** Error: %s ***\n\t %s\n'%(etype[0],etype[1]))
#        if transport:
#            transport.close()
#        return False
    return True

class SSHPipe2():

    def __init__(self, cmd, hostname, username, \
                       passwd=None, \
                       read_noblock=False, \
                       readerr_noblock=False):
                       
        """
        Execute a remote command using ssh.
        An OSError exception will be raised if an error occurs.
        Will use passwd if supplied. Otherwise it will use hostkey 
        authentication.
        """
        self.cmd = cmd
        self.hostname = hostname
        self.read_noblock = read_noblock
        self.readerr_noblock = readerr_noblock

        fullcmd = 'ssh %s@%s %s' % (username, hostname, cmd)
        self.f = Popen(fullcmd, shell=True, stdout=PIPE, stderr=PIPE, stdin=PIPE)
        self.frd = self.f.stdout
        self.frderr = self.f.stderr
        self.fwrt = self.f.stdin
        self.rdtail = ''
        self.errtail = ''
        self.MakeNonblocking(self.frderr)
        self.errtail = self.ReadError()
        if self.errtail.strip().lower().endswith('password:'):
            self.errtail = ''
            if passwd is None:
                self.CleanUp()
                raise RuntimeError( \
                'Password required for command:\n%s\n' % fullcmd)
            else:
                self.fwrt.write(passwd)
                self.errtail = self.frderr.read()
                if self.errtail.strip().lower().endswith('password:'):
                    self.CleanUp()
                    raise RuntimeError( \
                    'Incorrect password for command:\n%s\n' % fullcmd)
        elif len(self.errtail) > 0:
            raise RuntimeError('Error executing command: \n\t%s\n\t%s\n' % \
                                    (fullcmd, self.errtail))
        if self.read_noblock:
            self.MakeNonblocking(self.frd)


    def CleanUp(self):
#       Kill the subprocess and reset the file attributes.
        os.kill(self.f.pid, signal.SIGINT)
        self.fin = None
        self.fout = None
        self.ferr = None

    def MakeNonblocking(self, f):
        fn = f.fileno()
        fl = fcntl.fcntl(fn, fcntl.F_GETFL)
        fcntl.fcntl(fn, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    def ReadReady(self):
        if self.read_noblock:
            try:
                data = self.frd.read()
                self.errtail += data
                return True
            except: return False
        else:
            return True

    def Write(self, data):
        self.fwrt.write(data)

    def WriteReady(self):
        if self.fwrt is None:
            return False
        else:
            return True

    def Read(self, nbytes=None):
        data = self.rdtail
        if self.read_noblock:
            try: 
                if nbytes is None:
                    data += self.frd.read()
                else:
                    data += self.frd.read(nbytes)
            except: pass
        else:
            if nbytes is None:
                data += self.frd.read()
            else:
                data += self.frd.read(nbytes)
        self.rdtail = ''
        return data

    def ReadError(self, nbytes=None, force_noblock=False, timeout=1.):
        data = self.errtail
        time0 = time.time()
        while True:
            data = self.errtail
            try: 
                if nbytes is None:
                    data += self.frderr.read()
                else:
                    data += self.frderr.read(nbytes)
                break
            except IOError:
                if self.readerr_noblock or force_noblock or \
                    (timeout is not None and (time.time() - time0) > timeout):
                    break
                else:
                    time.sleep(.005)
                    continue
        self.errtail = ''
        return data

    def ReadReady(self):
        if self.read_noblock:
            try: 
                self.rdtail += self.frd.read(1)
                return True
            except: return False
        else:
            return True

    def ReadErrorReady(self):
        if self.readerr_noblock:
            try: 
                self.errtail += self.frderr.read(1)
                return True
            except: return False
        else:
            return True

    def Flush(self):
        self.fwrt.flush()

    def Close(self):
        self.frd.close()
        self.frderr.close()
        self.fwrt.close()


class SSHPipe():

    def __init__(self, cmd, hostname, username, passwd=None, \
                                    verbose=False, background=False):
        """
        Execute a remote command using ssh.
        An OSError exception will be raised if an error occurs.
        Will use passwd if supplied. Otherwise it will use hostkey 
        authentication.
        """
        self.cmd = cmd
        self.hostname = hostname
        output = ""
        self.transport = None
        try:
#           Create a transport and open a channel
            self.transport = ssh_connect(hostname, username, passwd)
            self.ch = self.transport.open_channel(kind='session')
            self.ch.settimeout(60.)
        except AuthenticationException:
            if self.transport is not None:
                self.transport.close()
            errstr = 'Authentication error in ssh_exec: %s@%s\n' % \
                                                        (username, hostname)
            raise OSError(errstr)
        except:
            if self.transport:
                self.transport.close()
            errstr = 'Error opening channel to %s' % hostname
            raise OSError(errstr)

        try:
            status = self.ch.exec_command(cmd)
        except:
            self.transport.close()
            etype = sys.exc_info()
            errstr = 'Could not execute command on %s\ncommand: %s\n%s\n%s\n'% \
                                            (hostname, cmd, etype[0],etype[1])
            raise OSError(errstr)

    def ReadReady(self):
        return self.ch.recv_ready()

    def Write(self, data):
        status = self.ch.send(data)
        if status != len(data):
            raise OSError('Tried to send %d bytes, only sent %d' % \
                                                    (len(data), status))

    def WriteReady(self):
        return self.ch.send_ready()

    def Read(self, nbytes=1000):
        data = self.ch.recv(nbytes)
#        status = self.ch.recv_exit_status()
#        self.CheckError()
        return data

    def ReadErrorReady(self):
        return self.ch.recv_stderr_ready()

    def ReadError(self, nbytes=None):
        """
        Read from stderr.
        """
        if self.ch.recv_stderr_ready():
            return self.ch.recv_stderr(1000)
        else:
            return ''

    def Close(self):
        self.transport.close() 

    def CheckError(self):
#        status = self.ch.recv_exit_status()
        return
        errors =  self.ch.recv_stderr(0)
        print 201,errors
        if len(errors) > 0:
            self.transport.close()
            errstr = 'Error while executing %s:%s, %s' % \
                                    (self.hostname, self.cmd, errors)
            raise OSError(errstr)



def ssh_exec(cmd, hostname, username, passwd=None, verbose=False, background=False):
    """
    Execute a remote command using ssh.
    An OSError exception will be raised if an error occurs.
    Will use passwd if supplied. Otherwise it will use hostkey authentication.
    """
    output = ""
    transport = None
    try:
#       Create a transport and open a channel
        transport = ssh_connect(hostname, username, passwd)
        ch = transport.open_channel(kind='session')
    except AuthenticationException:
        if transport is not None:
            transport.close()
        errstr = 'Authentication error in ssh_exec: %s@%s\n' % (username, hostname)
        raise OSError(errstr)
    except:
        etype = sys.exc_info()
        sys.stderr.write('\n\t*** Error: %s ***\n\t %s\n'%(etype[0],etype[1]))
        if transport:
            transport.close()
        errstr = 'Error opening channel to %s' % hostname
        raise OSError(errstr)

    try:
#       Execute the command.

        if background:
#           Emulate a command in background by shutting down the client but
#           not the process it forked.
            ch.exec_command(cmd + '>&/dev/null')
            transport.atfork()
            return (0, "", "")
        else:
            ch.exec_command(cmd)

#       Grab output a line at a time.
        line = ch.recv(1000)
        output += line
        if verbose:
            sys.stdout.write(line)
            sys.stdout.flush()

        i = 0
        while len(line) > 0:
            line = ch.recv(10000)
            output += line
            if verbose:
                sys.stdout.write(line)
                sys.stdout.flush()
            i += 1

#       Finished writing to stdout, now read stderr.
        errs = ch.recv_stderr(1000)
        stat = ch.recv_exit_status()
#       Close it up.
        transport.close()
    except:
        transport.close()
        etype = sys.exc_info()
#        sys.stderr.write('\n\t*** Error: %s ***\n\t %s\n'%(etype[0],etype[1]))
        errstr = 'Could not execute command on %s\ncommand: %s\n%s\n%s\n' % \
                                        (hostname, cmd, etype[0],etype[1])
        raise OSError(errstr)
    if stat > 0:
        errstr = 'Error while executing command on %s.\n' % hostname +\
                             '\tCommand: %s' %  cmd
#        sys.stderr.write('%s\n' % errstr)
        raise OSError(errstr)
    else:
        if len(output) < 7:
            output = str_to_bool.get(output.strip(), output)
        return stat, output, errs


class   SshExec():
    def __init__(self, cmd, hostname, username, passwd):
        """
        Execute a remote command using ssh.
        An OSError exception will be raised if an error occurs.
        """
        output = ""
        self.transport = None
        self.cmd = cmd
        self.hostname = hostname
        try:
#           Create the transport.
            self.transport = ssh_connect(hostname, username, passwd)
   #         self.transport = Transport((hostname, 22))
#  #         Connect to the host
   #         self.transport.connect(username=username, password=passwd, \
   #                             hostkey=None)
#           Open a channel
            self.ch = self.transport.open_channel(kind='session')
        except AuthenticationException:
            self.transport.close()
            self.Error('Authentication')
        except:
            if self.transport:
                self.transport.close()
            self.Error('initialization')

        try:
#           Execute the command.
            self.ch.exec_command(cmd)
        except:
            self.transport.close()
            self.Error('execution')
            raise OSError(errstr)


    def readline(self):
        """
        Get one line of output.
        """
        try:
            return self.ch.recv(1000)
        except:
            self.Error('SshExec.readlines()')

    def readlines(self):
        """
        Read all lines available from stdout on remote host.
        """
        try:
            line = self.ch.recv(10000)
            output = line
            while len(line) > 0:
                line = self.ch.recv(10000)
                output += line
            return output
        except:
            self.Error('SshExec.readlines()')

    def read_stderr(self):
        """
        Read all lines available from stderr on remote host.
        """
        try:
            line = self.ch.recv_stderr(10000)
            output = line
            while len(line) > 0:
                line = self.ch.recv_stderr(10000)
                output += line
            return output
        except:
            self.Error('SshExec.read_stderr()')

    def close(self):
        """
        Read stdout and stderr and exit status on remote host and close 
        transport.
        """
        try:
            output = self.readlines()
            errs = self.read_stderr()
            stat = self.ch.recv_exit_status()
            if len(output) < 7:
#               Convert "True" or "False" to a Python boolean value.
                output = str_to_bool.get(output.strip(), output)
            self.transport.close()
            return (stat, output, errs)
        except:
            self.transport.close()
            self.Error('SshExec.close()')

    def Error(self, action):
        etype = sys.exc_info()
        sys.stderr.write('\n\t*** Error: %s ***\n\t %s\n'%(etype[0],etype[1]))
        errstr = 'Error during %s while executing command on %s\n' % \
                 self.hostname + '\tcommand: %s\n' % (self.hostname, self.cmd)
        raise OSError(errstr)

def check_freedisk(path):
    """
    Check for amount of free disk space in megabytes on the partition 
    containing "path".
    """
    st =  os.statvfs(path)
#   Round block size down to 8k to mimic the df command.
    return (.85*float(st.f_bfree)*(st.f_frsize/1000)*1000.)/1.e6

def chg_perm(path):
#   Change permissions and catch all errors. Errors are noncritical,
#   so let them go without barfing on the screen.
    try:
        os.chmod(path,S_IRWXU | S_IRWXG | S_IRWXO)
    except OSError:
#        Noncritical error, let it go.
        pass

def time_stamp():
    return('%s' % (time.strftime('%y%b%d_%H:%M:%S')))

def time_user_stamp():
    return('%s_%s' % \
            (os.environ['LOGNAME'], time.strftime('%y%b%d_%H:%M:%S')))

def get_tmp_space(max_required, systemwide_tmpdir=".", partition=None):
    """
    Find place to write temporary files.
    max_required: Maximum amount of space required in MB.
    """
    if partition and os.path.exists(partition):
        tmpdir = partition
    elif os.path.exists('/scratch.local') and \
                        check_freedisk("/scratch.local") > max_required:
        tmpdir = "/scratch.local"
    elif check_freedisk("/tmp") > max_required:
        tmpdir = "/tmp"
    elif check_freedisk(systemwide_tmpdir) > max_required:
        tmpdir = systemwide_tmpdir
    elif check_freedisk(os.getcwd()) > max_required:
        tmpdir = os.getcwd()
    else:
        tmpdir = None
        sys.stderr.write("get_tmp_space: Insufficient space on /tmp, asked for %d, only %d available\n" % (max_required, check_freedisk("/tmp")))
    try:
        os.utime(tmpdir, None)
    except OSError:
        sys.stderr.write( \
        '\nError accessing %s as tmp directory, using /tmp instead.\n' % tmpdir)
        tmpdir = '/tmp'
#   Create directory with time and user stamp.
    if tmpdir is not None:
        while True:
            time.sleep(.005) # Wait 5ms so time-tag is sure to change.
            ms = time.time()
            ms = int(1000*(ms - int(ms)))
            tmpdir = '%s/%s_%d_%s_%03d' % \
            (tmpdir,os.environ['LOGNAME'], os.getpid(), time.strftime('%y%b%d_%H_%M_%S'), ms)
            itry = 0
            while os.path.exists(tmpdir):
                itry += 1
                tmpdir = ('%s_%d' % (tmpdir, itry)).replace(' ','')
            os.makedirs(tmpdir)
            chg_perm(tmpdir)
            break

    return tmpdir

class GetTmpSpace():

    def __init__(self, size, tmpdir=None):
        if tmpdir is None:
            self.tmpdir = get_tmp_space(size)
        else:
            self.tmpdir = tmpdir
        if os.path.exists(self.tmpdir):
            self.Clean()
        os.makedirs(self.tmpdir)

    def Clean(self):
        cmd = '/bin/rm -r %s' % self.tmpdir
        f = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        output, errs = f.communicate()
        if errs:
            raise RuntimeError('Error deleting tmp space:\n\t%s\n\tError: %s'%\
                                                            (cmd, errs))


if __name__ == '__main__':
    sys.stdout.write('%s\n' % ID)

# import the command line variable
from sys import argv as sys_argv
from os import environ

# import the file functions
from os.path import exists as file_exists
from shutil import copy as file_copy, SameFileError

# import the path function
from os.path import expanduser as path_get_user_directory
from os.path import join as path_join

# import the network functions
from socket import socket as socket_open, AF_INET, SOCK_STREAM

# import the command execution functions
from os import system
from subprocess import Popen, PIPE

# import the thread object
from threading import Thread, enumerate as enumerate_threads


# shdo settings
SHDO_AUTO_BOUNCE = True
SHDO_BOUNCE_FOLDER_PATH = "/storage/self/primary/"
SHDO_DEBUG_FOLDER_PATH = "/data/local/tmp/"
ADB_SERVER_PORT_FILENAME = ".last_adb_server_port"


# shdo global variables
current_adb_port = None
connected_adb_port = None


# main function
def main():

    # parse the command line parameters
    argc = len(sys_argv)
    argv = sys_argv

    # check usage
    if argc <= 1:
        print("Usage: shdo <command> [parameters]")
        return 1
    
    # check if we're running the tool with termux
    if 'TERMUX_VERSION' not in environ:
        print("Error: You need to run this tool from Termux. If you want to run this tool anyway create the environment variable 'TERMUX_VERSION'.")
        return 1
    
    # build the command
    parameters = ""
    if argc >= 3:
        for parameter in argv[2:]:
            parameters += f" '{parameter}'"

    # run the command
    result = run_command(argv[1], parameters, verbose=False)
    if result is None:
        return 1
    
    # end of process
    return result


# run an elevated command
def run_command(command, parameters, verbose=False):

    # start the adb server
    _adb.start_server(verbose=verbose)

    # check if we are already connected
    if _adb.is_connected(verbose=verbose) == False:

        # connect to the adb server
        if _adb.connect(verbose=verbose) == False:

            # print the error if needed
            print("Error: Couldn't connect to the adb server. Are you sure the adb server is paired with Termux ? Are you sure the adb wi-fi is on ?")
            
            # couldn't connect to the adb server
            return None
        
    # auto-bounce the file or executable if needed
    if SHDO_AUTO_BOUNCE == True:

        # check if the command is an executable (bash, elf, ...)
        if file_exists(command) == True:

            # remove extra dot
            if command.startswith("./") == True:
                filename = command[2:]

            # copy the file to the bounce folder
            if verbose == True:
                print(f"[*] Copying the file {filename} to bounce folder...", end='', flush=True)
            bounce_path = SHDO_BOUNCE_FOLDER_PATH + filename
            try:
                file_copy(filename, bounce_path)
            except SameFileError:
                pass
            if verbose == True:
                print("done.")

            # copy the file to the debug folder
            if verbose == True:
                print(f"[*] Copying the file {filename} to debug folder...", end='', flush=True)
            debug_path = SHDO_DEBUG_FOLDER_PATH + filename
            _adb.shell(f"cp '{bounce_path}' '{debug_path}'")
            if verbose == True:
                print("done.")

            # give execution permission to the script or executable
            if verbose == True:
                print(f"[*] Giving the file {filename} execution permission...", end='', flush=True)
            _adb.shell(f"chmod 755 '{debug_path}'")
            if verbose == True:
                print("done.")
            
            # change the command by its new path
            command = debug_path

    # build the full command
    full_command = f"'{command}' {parameters}"
        
    # run the elevated command
    return _adb.execute(full_command, verbose=verbose)


# handle everything about android debug bridge
class _adb:
        
    # execute an adb command
    def execute(command, verbose=False):

        # execute the command
        if verbose == True:
            print("[*] Executing the command...\n")
        return system(f"adb -s 127.0.0.1:{current_adb_port} shell {command}")


    # run an adb command
    def command(command):

        # run the terminal command
        command = f"adb {command}"
        stdout, stderr = _terminal.run_command(command)

        # check if there was an error
        if stderr.startswith("adb: ") == True:

            # check if the device is unknown
            if stderr.find("not found") != -1:
                return None

            # check if the device is offline
            if stderr.find("device offline") != -1:
                return None
        
        # the command is executed
        return (stdout, stderr)


    # run an adb shell command
    def shell(command):
        global current_adb_port

        # build the adb shell command
        shell_command = ""
        if current_adb_port is not None:
            shell_command += f"-s 127.0.0.1:{current_adb_port} "
        shell_command += f"shell {command}"

        # run the adb shell command
        return _adb.command(shell_command)


    # start the adb server
    def start_server(verbose=False):

        # print a debug message
        if verbose == True:
            print("[*] Starting adb server...", end='', flush=True)

        # start the adb server
        _adb.command("start-server")
        
        # print a debug message
        if verbose == True:
            print("done.")


    # check if adb is already connected
    def is_connected(verbose=False):

        # check if adb is connected
        result = _adb.shell("echo alive")
        if result is not None and result[0] == 'alive\n':
            if verbose == True:
                print("[*] Checking adb status%s...connected." % (f" for port {current_adb_port}" if current_adb_port is not None else ""))
            return True
        
        # adb is not connected
        if verbose == True:
            print("[*] Checking adb status%s...disconnected." % (f" for port {current_adb_port}" if current_adb_port is not None else ""))
        return False


    # connect to the adb server
    def connect(verbose=False):
        global current_adb_port
        global connected_adb_port

        # connect to the adb server with the last known port
        adb_server_port = _cache.load(verbose=verbose)
        if adb_server_port is not None:
            if _adb.try_connect(adb_server_port, verbose=verbose) == True:
                return True
        
        # find all the opened tcp ports
        possible_ports = _network.scan_tcp_ports(verbose=verbose)

        # print if verbose is enabled
        if verbose == True:
            print("[*] Trying to connect to the open ports...")

        # find the new adb server port with multi-thread brute-forcing
        current_adb_port = None
        connected_adb_port = None
        threads = []
        for port in possible_ports:
            thread = Thread(target=_adb.try_connect, args=(port, verbose))
            thread.start()
            threads.append(thread)

        # wait for adb to connect
        while len(enumerate_threads()) != 1:
            if connected_adb_port is not None:
                break
            continue
        if connected_adb_port is None:
            for thread in threads:
                thread.join()
        
        # check if we found the adb server port
        if connected_adb_port is not None:
            current_adb_port = connected_adb_port
            _cache.save(connected_adb_port, verbose=verbose)
            return True

        # connection failed
        return False


    # try to connect to an adb server
    def try_connect(adb_server_port, verbose=False):
        global current_adb_port
        global connected_adb_port

        # run the adb connect command
        result = _adb.command(f"connect 127.0.0.1:{adb_server_port}")
        if result is None:
            if verbose == True:
                print(f"[*] Can't connect to adb server {adb_server_port}.")
            return False
        
        # check for errors
        if result[0].find('cannot connect to') != -1:
            if verbose == True:
                print(f"[*] Can't connect to adb server {adb_server_port}.")
            return False
        if result[0].find(': Connection refused') != -1:
            if verbose == True:
                print(f"[*] Can't connect to adb server {adb_server_port}.")
            return False
        
        # check the full connection
        current_adb_port = adb_server_port
        if _adb.is_connected(verbose=verbose) == False:
            return False
        
        # adb is connected
        connected_adb_port = adb_server_port
        if verbose == True:
            print(f"[*] Connected to adb server {adb_server_port}.")
        return True


# handle everything about terminal
class _terminal:

    # run a terminal command
    def run_command(command):

        # open a process to run the command
        process = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()

        # return the process (command) output
        stdout = stdout.decode()
        stderr = stderr.decode()
        return (stdout, stderr)


# handle everything about cache
class _cache:
        
    # load the adb server port
    def load(verbose=False):
        if verbose == True:
            print("[*] Loading adb server port from a file...", end='', flush=True)

        # build the file path
        home = path_get_user_directory("~")
        filepath = path_join(home, ADB_SERVER_PORT_FILENAME)

        # open the file
        try:
            with open(filepath, 'r') as file:

                # read the adb server port from the file
                adb_server_port = int(file.read())

        # check for errors
        except FileNotFoundError:
            if verbose == True:
                print("failure.")
            return None
        
        # the adb server port was loaded
        if verbose == True:
            print("success.")
        return adb_server_port


    # save the adb server port
    def save(adb_server_port, verbose=False):

        # build the cache file path
        if verbose == True:
            print("[*] Saving adb server port to a file...", end='', flush=True)
        home = path_get_user_directory("~")
        filepath = path_join(home, ADB_SERVER_PORT_FILENAME)

        # save the cache file
        with open(filepath, 'w') as file:
            file.write(str(adb_server_port))
        if verbose == True:
            print("success.")


# handle everything about network
class _network:
        
    # scan all the opened tcp ports
    def scan_tcp_ports(verbose=False):
        if verbose == True:
            print("[*] Scanning all opened TCP ports...")

        # open a local socket
        local_socket = socket_open(AF_INET, SOCK_STREAM)

        # scan all the ports needed
        open_ports = []
        possible_ports = list(range(0, 65535))
        for port in possible_ports:
            
            # check the port assignation
            result = _network.is_port_assigned(local_socket, port, verbose=verbose)

            # reload the socket if the port was assigned
            if result == False:
                local_socket.close()
                local_socket = socket_open(AF_INET, SOCK_STREAM)

            # save all open ports
            if result == True:
                if verbose == True:
                    print(f"[*]   The port {port} is open!")
                open_ports.append(port)

        # close the socket
        local_socket.close()

        # return the opened ports
        return open_ports


    # check if a port is assigned
    def is_port_assigned(local_socket, port, verbose=False):

        # try to assign the port to the socket
        try:
            local_socket.bind(('127.0.0.1', port))

        # check for errors when assigning the port
        except Exception as e:

            # get the response as a string
            e = str(e)

            # check if we need root access to open this socket
            permission_denied = ['forbidden by its access permissions', 'Permission denied']
            for pattern in permission_denied:
                if e.find(pattern) != -1:
                    return None

            # check if the socket is already open
            if e.find("Only one usage of each socket address (protocol/network address/port) is normally permitted") != -1 or e.find('Address already in use') != -1:
                return True
            
            # check if this is an unknown error
            else:
                if verbose == True:
                    print(f"shdo: Unknown error while binding port {port}: {e}.")
                return None

        # the port is assigned
        return False


# entry point
if __name__ == "__main__":
    exit(main())
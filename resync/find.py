from .filesystem import SshFileSystem
import logging
import netifaces
import os
import paramiko

logger = logging.getLogger(__name__)


def enumerate_candidates():

    interfaces = netifaces.interfaces()

    for interface in interfaces:
        if interface.startswith('enx'):
            addresses = netifaces.ifaddresses(interface)
            for addresses in addresses.values():
                for address in addresses:
                    if 'netmask' in address:
                        # change last digit to '1', this is the reMarkable
                        yield address['addr'][:-1] + '1'

    yield 'remarkable'

def is_remarkable(address):

    try:

        ssh_client = paramiko.SSHClient()
        ssh_client.load_system_host_keys()
        ssh_client.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
        ssh_client.connect(
            address,
            username='root',
            look_for_keys=True,
            timeout=1.0)

        fs = SshFileSystem(ssh_client, '/')
        has_xochitl = fs.exists('/usr/bin/xochitl')

        ssh_client.close()

        return has_xochitl

    except Exception as e:

        logger.exception(e)

        return False


def find_remarkable():
    '''Search for the reMarkable tablet and return its IP address.
    '''

    for candidate in enumerate_candidates():
        if is_remarkable(candidate):
            logger.debug("Found remarkable with address %s", candidate)
            return candidate

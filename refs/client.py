import logging
import paramiko
from .filesystem import SshFileSystem
from .store import RemarkableStore


logger = logging.getLogger(__name__)


class RemarkableClient:
    document_root = "/home/root/.local/share/remarkable/xochitl"
    restart_command = "/bin/systemctl restart xochitl"

    def __init__(self, address, username="root", document_root=None):
        self.ssh_client = None
        self.__connect(address, username)

        if document_root is not None:
            self.document_root = document_root

        self.fs = SshFileSystem(self.ssh_client, self.document_root)
        self.store = RemarkableStore(self.fs)

    def restart(self):
        """Restart ``xochitl`` (the GUI) on the remarkable.

        This is necessary to see changes made to the document tree.
        """
        _, out, _ = self.ssh_client.exec_command(self.restart_command)
        if out.channel.recv_exit_status() != 0:
            logger.error("Could not restart xochitl")

    def __connect(self, address, username):
        logger.info("Connecting to %s...", address)

        if self.ssh_client is not None:
            logger.error("Already connected")
            return

        ssh_client = paramiko.SSHClient()
        ssh_client.load_system_host_keys()
        ssh_client.connect(address, username=username, look_for_keys=True)

        logger.info("...connected.")
        self.ssh_client = ssh_client

    def __disconnect(self):
        self.ssh_client.close()
        self.ssh_client = None
